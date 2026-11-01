# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""回测指标的**数值正确性**验证(不是"能不能跑",是"算得对不对")

Sortino 的分母用了"仅负收益子集的标准差" downside.std(),
而不是标准的下行偏差 sqrt(mean(min(r,0)^2))。该实现会系统性高估分母,
使 Sortino 被低估约 15%(已验证 1.0599 vs empyrical 1.2471)。

所有"跑通了"的测试都发现不了这个问题 —— 因为它不崩,只是算错。
本文件用 empyrical(已在依赖中)做第三方交叉校验。
"""

import numpy as np
import pandas as pd
import pytest

from forgemind.core.agents.stock_picker import WEIGHTS, StockPickerAgent
from forgemind.core.backtest.advanced import BacktestReport
from forgemind.core.backtest.engine import SimpleBacktestEngine
from forgemind.core.factors.ic_monitor import _cross_sectional_ic_series
from forgemind.core.strategies.base import MovingAverageCrossStrategy

empyrical = pytest.importorskip("empyrical")


def _fixture(n=500, seed=11):
    """确定性的价格序列,保证每次跑出同样的数字"""
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.018, n)))
    return pd.DataFrame({
        "open": close * (1 + rng.normal(0, 0.003, n)),
        "high": close * 1.01, "low": close * 0.99,
        "close": close, "volume": rng.integers(1_000_000, 5_000_000, n),
    })


def _run(df):
    strat = MovingAverageCrossStrategy(parameters={"fast_period": 10, "slow_period": 40})
    eng = SimpleBacktestEngine(initial_capital=100_000.0)
    res = eng.run(strat, df)
    equity = eng._simulate_equity(df, strat.generate_signals(df))
    return res, equity


class TestMetricsAgainstEmpyrical:
    """核心指标必须与第三方权威实现一致(浮点精度内)"""

    def test_sharpe_matches_empyrical(self):
        df = _fixture()
        res, equity = _run(df)
        r = equity.pct_change().dropna()
        assert res.sharpe == pytest.approx(float(empyrical.sharpe_ratio(r.values)), abs=1e-9)

    def test_max_drawdown_matches_empyrical(self):
        df = _fixture()
        res, equity = _run(df)
        r = equity.pct_change().dropna()
        assert res.max_drawdown == pytest.approx(
            float(empyrical.max_drawdown(r.values)), abs=1e-9
        )

    def test_sortino_matches_empyrical(self):
        """回归重点:Sortino 曾用错误的下行波动定义,与 empyrical 差 15%"""
        df = _fixture()
        res, equity = _run(df)
        r = equity.pct_change().dropna()
        assert res.sortino == pytest.approx(
            float(empyrical.sortino_ratio(r.values)), abs=1e-9
        )

    def test_sortino_uses_downside_deviation_definition(self):
        """显式验证:分母必须是全部周期的下行偏差,不是负收益子集标准差"""
        df = _fixture()
        res, equity = _run(df)
        r = equity.pct_change().dropna()
        downside_dev = float(np.sqrt(np.mean(np.minimum(r.to_numpy(), 0.0) ** 2)))
        expected = float(r.mean() / downside_dev * np.sqrt(252))
        assert res.sortino == pytest.approx(expected, abs=1e-9)

    def test_sortino_differs_from_the_wrong_formula(self):
        """防止有人"改回去":结果必须不等于旧的错误公式"""
        df = _fixture()
        res, equity = _run(df)
        r = equity.pct_change().dropna()
        wrong = r[r < 0].std()
        wrong_result = float(r.mean() / wrong * np.sqrt(252))
        assert abs(res.sortino - wrong_result) > 1e-6


class TestMetricsInternalConsistency:
    """自洽性:不需要第三方也能查出的矛盾"""

    def test_total_return_equals_equity_ratio(self):
        df = _fixture()
        res, equity = _run(df)
        assert res.total_return == pytest.approx(
            float(equity.iloc[-1] / equity.iloc[0] - 1), abs=1e-12
        )

    def test_equity_starts_at_initial_capital(self):
        df = _fixture()
        _, equity = _run(df)
        assert equity.iloc[0] == pytest.approx(100_000.0, abs=1e-6)

    def test_equity_never_negative(self):
        df = _fixture()
        _, equity = _run(df)
        assert (equity > 0).all()

    def test_max_drawdown_never_positive(self):
        df = _fixture()
        res, _ = _run(df)
        assert res.max_drawdown <= 0

    def test_trade_count_consistent(self):
        df = _fixture()
        strat = MovingAverageCrossStrategy(parameters={"fast_period": 10, "slow_period": 40})
        eng = SimpleBacktestEngine(initial_capital=100_000.0)
        res = eng.run(strat, df)
        sig = strat.generate_signals(df)
        equity = eng._simulate_equity(df, sig)
        trades = eng._extract_trades(df, sig, equity)
        assert len(trades) == res.n_trades

    def test_win_rate_consistent_with_trades(self):
        df = _fixture()
        strat = MovingAverageCrossStrategy(parameters={"fast_period": 10, "slow_period": 40})
        eng = SimpleBacktestEngine(initial_capital=100_000.0)
        res = eng.run(strat, df)
        sig = strat.generate_signals(df)
        equity = eng._simulate_equity(df, sig)
        trades = eng._extract_trades(df, sig, equity)
        if trades:
            wins = sum(1 for t in trades if t["win"])
            assert res.win_rate == pytest.approx(wins / len(trades), abs=1e-12)


class TestMetricsOnMultipleSeeds:
    """不能只在一个种子上碰巧通过"""

    @pytest.mark.parametrize("seed", [1, 7, 42, 99, 2024])
    def test_sharpe_sortino_dd_all_match(self, seed):
        df = _fixture(seed=seed)
        res, equity = _run(df)
        r = equity.pct_change().dropna()
        assert res.sharpe == pytest.approx(float(empyrical.sharpe_ratio(r.values)), abs=1e-8)
        assert res.sortino == pytest.approx(float(empyrical.sortino_ratio(r.values)), abs=1e-8)
        assert res.max_drawdown == pytest.approx(
            float(empyrical.max_drawdown(r.values)), abs=1e-8
        )


class TestICMetricsAreNotFabricated:
    """回归:ICIR / positive_ratio 必须来自真实 IC 序列

    :
      * icir = ic_mean / 0.01(除以硬编码常数,只是把 IC 线性缩放)
      * ic_std = 0.01 硬编码
      * positive_ratio = 1.0 if ic>0 else 0.0(注释写"IC>0 的天数比例",实际只有 0/1)
    """

    @staticmethod
    def _panel(n_symbols=30, n_days=500, seed=5):
        import polars as pl

        rng = np.random.default_rng(seed)
        rows = []
        for i in range(n_symbols):
            c = 100 * np.exp(np.cumsum(rng.normal(0, 0.015, n_days)))
            d = pd.DataFrame({
                "date": pd.date_range("2024-01-01", periods=n_days),
                "symbol": f"S{i}", "close": c,
                "factor": rng.normal(0, 1, n_days),
            })
            d["fwd_ret_5"] = d.groupby("symbol")["close"].pct_change(5).shift(-5)
            rows.append(d)
        pdf = pd.concat(rows).dropna(subset=["fwd_ret_5", "factor"])
        return pl.from_pandas(pdf).lazy()

    def test_icir_comes_from_real_series(self):
        from forgemind.core.factors.ic_monitor import compute_ic

        r = compute_ic(self._panel(), "factor", forward_returns_col="fwd_ret_5")
        assert len(r.ic_series) > 50, "未产出逐期 IC 序列"
        expected = r.ic_series.mean() / r.ic_series.std(ddof=1)
        assert r.icir == pytest.approx(float(expected), abs=1e-9)

    def test_ic_std_is_series_std(self):
        from forgemind.core.factors.ic_monitor import compute_ic

        r = compute_ic(self._panel(), "factor", forward_returns_col="fwd_ret_5")
        assert r.ic_std == pytest.approx(float(r.ic_series.std(ddof=1)), abs=1e-12)

    def test_positive_ratio_is_a_real_fraction(self):
        from forgemind.core.factors.ic_monitor import compute_ic

        r = compute_ic(self._panel(), "factor", forward_returns_col="fwd_ret_5")
        assert r.positive_ratio == pytest.approx(float((r.ic_series > 0).mean()), abs=1e-12)

    def test_positive_ratio_not_a_binary_flag(self):
        from forgemind.core.factors.ic_monitor import compute_ic

        r = compute_ic(self._panel(), "factor", forward_returns_col="fwd_ret_5")
        assert r.positive_ratio not in (0.0, 1.0), "positive_ratio 退化成 0/1 标志位"

    def test_icir_not_the_old_fake_formula(self):
        from forgemind.core.factors.ic_monitor import compute_ic

        r = compute_ic(self._panel(), "factor", forward_returns_col="fwd_ret_5")
        assert not np.isclose(r.icir, r.ic_mean / 0.01)

    def test_ic_core_matches_scipy(self):
        """核心 IC 本身必须与 scipy 一致(之前就是对的,别改坏)"""
        from scipy import stats

        from forgemind.core.factors.ic_monitor import compute_ic

        lazy = self._panel()
        r = compute_ic(lazy, "factor", forward_returns_col="fwd_ret_5")
        pdf = lazy.collect().to_pandas().dropna(subset=["factor", "fwd_ret_5"])
        x, y = pdf["factor"].values, pdf["fwd_ret_5"].values
        assert r.ic_mean == pytest.approx(float(stats.pearsonr(x, y).statistic), abs=1e-9)
        assert r.rank_ic_mean == pytest.approx(float(stats.spearmanr(x, y).statistic), abs=1e-9)

    def test_batch_compute_ic_does_not_silently_drop_factors(self):
        """:except: continue —— 出错的因子凭空消失且无任何提示"""
        from forgemind.core.factors.ic_monitor import batch_compute_ic

        lazy = self._panel()
        good = batch_compute_ic(lazy, ["factor"], forward_returns_col="fwd_ret_5")
        assert len(good) == 1
        mixed = batch_compute_ic(
            lazy, ["factor", "does_not_exist"], forward_returns_col="fwd_ret_5"
        )
        assert [m.factor for m in mixed] == ["factor"], "失败的因子应被记录而非静默消失"


def _independent_simulate(open_, close_, entries, exits, capital=100_000.0,
                          fee=0.0, slip=0.0):
    """参考实现:逐 bar 推演,只用当日 open/close

    与 SimpleBacktestEngine._simulate_equity 完全独立地写一遍,
    用来抓"资金曲线本身算错"这类错误 —— 只比对指标公式是不够的,
    因为指标公式和资金曲线可以一起错,两边对拍仍然一致。
    """
    n = len(open_)
    eq = np.empty(n)
    eq[0] = capital
    pos = 0
    for i in range(1, n):
        prev_close = close_[i - 1]
        if pos == 0 and entries[i - 1]:
            pos = 1
            entry = open_[i] * (1 + slip)
            eq[i] = eq[i - 1] * (1 - fee) * ((close_[i] / entry) if entry else 1.0)
        elif pos == 1 and exits[i - 1]:
            pos = 0
            step = (open_[i] * (1 - slip)) / prev_close - 1 if prev_close else 0.0
            eq[i] = eq[i - 1] * (1 + step) * (1 - fee)
        else:
            eq[i] = eq[i - 1] * ((close_[i] / prev_close) if pos == 1 else 1.0)
    return eq


class TestEquityCurveIsNotDoubleCounted:
    """核心回归:资金曲线不得重复计入持仓期涨幅

    :卖出时用**整笔交易**的完整收益
        equity[i] = equity[i-1] * (1 + exit/entry - 1)
    而持仓期 [entry, i-1] 已逐日按 close 复利过,整段被算两遍。
    100 买 → 持有一日 105 → 110 卖:正确 110000,旧实现 115500。
    所有下游指标(总收益/Sharpe/Sortino/Calmar/胜率/盈亏比)因此全部虚高。
    """

    def test_single_two_day_trade(self):
        """最直白的复现:100 买,隔一天 105,110 卖 → 必须是 110000"""
        idx = pd.date_range("2024-01-01", periods=4)
        o = np.array([99.0, 100.0, 105.0, 110.0])
        c = o.copy()
        df = pd.DataFrame({"open": o, "high": c * 1.01, "low": c * 0.99,
                           "close": c, "volume": 1e6}, index=idx)
        sig = pd.DataFrame({"entries": [True, False, False, False],
                            "exits": [False, False, True, False]}, index=idx)
        eng = SimpleBacktestEngine(initial_capital=100_000.0, fees=0.0,
                                   slippage_bps=0.0, use_next_open=True)
        eq = eng._simulate_equity(df, sig)
        assert eq.iloc[3] == pytest.approx(110_000.0, abs=1e-6)

    @pytest.mark.parametrize("seed", list(range(10)))
    def test_matches_independent_simulation(self, seed):
        """随机场景逐点对拍,任何一根 bar 都不允许有偏差"""
        rng = np.random.default_rng(seed)
        n = 300
        o = np.abs(100 + np.cumsum(rng.normal(0, 1, n)))
        c = np.abs(100 + np.cumsum(rng.normal(0, 1, n)))
        ent = np.zeros(n, dtype=bool)
        ex = np.zeros(n, dtype=bool)
        for i in range(20, n - 10, 17):
            ent[i] = True
            if i + 9 < n:
                ex[i + 9] = True
        df = pd.DataFrame({"open": o, "high": c * 1.01, "low": c * 0.99,
                           "close": c, "volume": 1e6},
                          index=pd.date_range("2024-01-01", periods=n))
        sig = pd.DataFrame({"entries": ent, "exits": ex}, index=df.index)
        eng = SimpleBacktestEngine(initial_capital=100_000.0, fees=0.0,
                                   slippage_bps=0.0, use_next_open=True)
        got = eng._simulate_equity(df, sig).to_numpy()
        want = _independent_simulate(o, c, ent, ex)
        assert np.max(np.abs(got - want)) < 1e-6, "资金曲线与独立模拟不一致"

    def test_with_fees_and_slippage(self):
        """带手续费和滑点时同样要对得上"""
        rng = np.random.default_rng(3)
        n = 250
        o = np.abs(100 + np.cumsum(rng.normal(0, 1, n)))
        c = np.abs(100 + np.cumsum(rng.normal(0, 1, n)))
        ent = np.zeros(n, dtype=bool)
        ex = np.zeros(n, dtype=bool)
        for i in range(15, n - 8, 13):
            ent[i] = True
            if i + 7 < n:
                ex[i + 7] = True
        df = pd.DataFrame({"open": o, "high": c * 1.01, "low": c * 0.99,
                           "close": c, "volume": 1e6},
                          index=pd.date_range("2024-01-01", periods=n))
        sig = pd.DataFrame({"entries": ent, "exits": ex}, index=df.index)
        eng = SimpleBacktestEngine(initial_capital=100_000.0, fees=0.0005,
                                   slippage_bps=8.0, use_next_open=True)
        got = eng._simulate_equity(df, sig).to_numpy()
        want = _independent_simulate(o, c, ent, ex, fee=0.0005, slip=8.0 / 10000)
        assert np.max(np.abs(got - want)) < 1e-6

    def test_return_cannot_exceed_the_actual_price_move(self):
        """总收益不得超过标的实际的涨跌幅"""
        idx = pd.date_range("2024-01-01", periods=4)
        o = np.array([99.0, 100.0, 105.0, 110.0])
        c = o.copy()
        df = pd.DataFrame({"open": o, "high": c * 1.01, "low": c * 0.99,
                           "close": c, "volume": 1e6}, index=idx)
        # 这里走完整 run() 流程,信号由策略自己产生,无需手工构造
        strat = MovingAverageCrossStrategy(parameters={"fast_period": 1, "slow_period": 2})
        eng = SimpleBacktestEngine(initial_capital=100_000.0, fees=0.0,
                                   slippage_bps=0.0, use_next_open=True)
        res = eng.run(strat, df)
        assert res.total_return <= 0.10 + 1e-9, "收益被虚高到超过真实涨幅"


class TestEntryBarIntradayMoveIsNotLost:
    """买入当日 open→close 的涨幅不得丢弃

    :买入 bar 只扣手续费,当日日内涨幅整段丢失,而卖出 bar 却补了
    close[i-1]→卖出价 —— 进出两端不对称。100 买 / 130 卖(同日)时引擎报 0%,
    正确是 +30%。
    """

    def test_same_day_gap_up_is_counted(self):
        idx = pd.date_range("2024-01-01", periods=4)
        o = np.array([99.0, 100.0, 130.0, 130.0])
        c = np.array([99.0, 130.0, 130.0, 130.0])
        df = pd.DataFrame({"open": o, "high": c * 1.01, "low": c * 0.99,
                           "close": c, "volume": 1e6}, index=idx)
        sig = pd.DataFrame({"entries": [True, False, False, False],
                            "exits": [False, True, False, False]}, index=idx)
        eng = SimpleBacktestEngine(initial_capital=100_000.0, fees=0.0,
                                   slippage_bps=0.0, use_next_open=True)
        eq = eng._simulate_equity(df, sig)
        assert eq.iloc[2] == pytest.approx(130_000.0, abs=1e-6)

    def test_entry_and_exit_are_symmetric(self):
        """进出两端必须对称:同样的日内波动不能只算一边"""
        idx = pd.date_range("2024-01-01", periods=4)
        o = np.array([99.0, 100.0, 130.0, 130.0])
        c = np.array([99.0, 130.0, 130.0, 130.0])
        df = pd.DataFrame({"open": o, "high": c * 1.01, "low": c * 0.99,
                           "close": c, "volume": 1e6}, index=idx)
        sig = pd.DataFrame({"entries": [True, False, False, False],
                            "exits": [False, True, False, False]}, index=idx)
        eng = SimpleBacktestEngine(initial_capital=100_000.0, fees=0.0,
                                   slippage_bps=0.0, use_next_open=True)
        eq = eng._simulate_equity(df, sig)
        want = _independent_simulate(o, c, sig["entries"].values, sig["exits"].values)
        assert np.allclose(eq.to_numpy(), want, atol=1e-6)

    def test_repeated_random_scenarios(self):
        """随机场景下与独立实现逐点一致(含日内跳空)"""
        for seed in range(10):
            rng = np.random.default_rng(seed + 100)
            n = 250
            o = np.abs(100 + np.cumsum(rng.normal(0, 2.0, n)))
            c = np.abs(100 + np.cumsum(rng.normal(0, 2.0, n)))
            ent = np.zeros(n, dtype=bool)
            ex = np.zeros(n, dtype=bool)
            for i in range(10, n - 5, 11):
                ent[i] = True
                if i + 3 < n:
                    ex[i + 3] = True
            df = pd.DataFrame({"open": o, "high": c * 1.01, "low": c * 0.99,
                               "close": c, "volume": 1e6},
                              index=pd.date_range("2024-01-01", periods=n))
            sig = pd.DataFrame({"entries": ent, "exits": ex}, index=df.index)
            eng = SimpleBacktestEngine(initial_capital=100_000.0, fees=0.0,
                                       slippage_bps=0.0, use_next_open=True)
            got = eng._simulate_equity(df, sig).to_numpy()
            want = _independent_simulate(o, c, ent, ex)
            assert np.max(np.abs(got - want)) < 1e-6, f"seed {seed} 资金曲线不一致"


class TestStockPickerFactorsAreDiscriminating:
    """回归:选股因子必须保有区分度

    :因子用固定 scale=0.05 线性归一化,±5% 之外全部压到 0/1,
    30% 权重的动量因子对绝大多数标的退化成二值标志(已验证 -15% 与 -5% 同为 0.0,
    +8%/+15%/+30% 同为 1.0)。改为横截面百分位归一化。
    """

    def test_normalize_is_monotonic_and_spreads(self):
        raws = [{"momentum": v} for v in (-0.3, -0.15, -0.05, 0.0, 0.03, 0.08, 0.15, 0.3)]
        out = StockPickerAgent._cross_sectional_normalize(raws)
        vals = [o["momentum"] for o in out]
        assert vals == sorted(vals), "归一化破坏了单调性"
        assert vals[0] == 0.0, "最小值应为 0"
        assert vals[-1] == 1.0, "最大值应为 1"
        assert len(set(vals)) == len(vals), "不同输入得到相同输出,区分度丢失"

    def test_old_saturating_formula_is_not_used(self):
        """旧实现会把 -15% 与 -5% 都压成 0 —— 新实现必须区分"""
        raws = [{"momentum": v} for v in (-0.15, -0.05)]
        out = StockPickerAgent._cross_sectional_normalize(raws)
        assert out[0]["momentum"] != out[1]["momentum"]

    def test_all_equal_inputs_get_neutral(self):
        raws = [{"momentum": 0.1}, {"momentum": 0.1}, {"momentum": 0.1}]
        out = StockPickerAgent._cross_sectional_normalize(raws)
        assert all(o["momentum"] == 0.5 for o in out), "无法区分时应给中性 0.5"

    def test_empty_input(self):
        assert StockPickerAgent._cross_sectional_normalize([]) == []

    def test_raw_factors_are_finite(self):
        rng = np.random.default_rng(9)
        n = 200
        c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
        df = pd.DataFrame({
            "close": c,
            "open": c, "high": c * 1.01, "low": c * 0.99,
            "volume": rng.integers(1_000_000, 5_000_000, n).astype(float),
        })
        raw = StockPickerAgent()._compute_raw_factors(df)
        for k, v in raw.items():
            assert np.isfinite(v), f"{k} 非有限值: {v}"

    def test_pure_uptrend_scores_above_pure_downtrend(self):
        """纯上涨序列的动量因子必须高于纯下跌序列"""
        n = 200
        up = 100 * np.exp(np.linspace(0, 0.3, n))
        down = 100 * np.exp(np.linspace(0, -0.3, n))
        def mk(s):
            return pd.DataFrame({
                "close": s, "open": s, "high": s * 1.01, "low": s * 0.99,
                "volume": np.full(n, 1e6),
            })

        ru = StockPickerAgent()._compute_raw_factors(mk(up))
        rd = StockPickerAgent()._compute_raw_factors(mk(down))
        assert ru["momentum"] > 0 > rd["momentum"]

    def test_normalized_scores_span_range(self):
        """横截面得分必须有区分度(不是全 0.5 / 全 1.0)"""
        rng = np.random.default_rng(4)
        raws = []
        for _ in range(10):
            d = {k: float(rng.normal(0, 1)) for k in
                 ("momentum", "trend", "volume_price", "volatility", "mean_reversion")}
            raws.append(d)
        norm = StockPickerAgent._cross_sectional_normalize(raws)
        scores = [sum(n[k] * WEIGHTS[k] for k in n) for n in norm]
        assert len(set(scores)) >= 8, f"得分区分度不足: {scores}"


class TestEtlFailureIsDiagnosable:
    """回归:取数失败必须给出可行动的原因分类

    :get_history 捕获所有异常后只返回空 DataFrame,
    run() 静默 continue,用户最终只看到"拉到 0 条数据",
    无法判断是网络不通、被限流、依赖缺失还是代码格式错。
    """

    @pytest.mark.parametrize(("exc", "expected"), [
        (ConnectionError("Connection refused"), "network_unreachable"),
        (TimeoutError("Read timed out"), "network_unreachable"),
        (__import__("json").JSONDecodeError("Expecting value", "", 0),
         "upstream_returned_non_json"),
        (ModuleNotFoundError("No module named 'akshare'"), "akshare_not_installed"),
        (ValueError("invalid symbol format 600519.SH"), "invalid_symbol_format"),
        (RuntimeError("请求过于频繁"), "rate_limited"),
        (ValueError("随便什么错"), "unclassified"),
    ])
    def test_classify_fetch_error(self, exc, expected):
        from forgemind.core.data.akshare_etl import AKShareDataSource

        assert expected in AKShareDataSource._classify_fetch_error(exc)

    def test_run_returns_failure_breakdown(self):
        """run() 必须把每个标的的成功/失败统计带出来,而不是只有 klines 计数"""
        import inspect

        from forgemind.core.data.akshare_etl import AKShareETL

        src = inspect.getsource(AKShareETL.run)
        assert '"failures"' in src or "'failures'" in src, "run() 未返回失败分类"
        assert "failures" in src, "run() 未统计失败标的"
        assert "continue" not in src.split("if df.empty")[-1][:200], \
            "取数失败仍在静默 continue"

    def test_data_source_initialises_error_state(self):
        from forgemind.core.data.akshare_etl import AKShareDataSource

        ds = AKShareDataSource()
        assert ds._last_error is None


class TestOpenPositionIsForceClosed:
    """回归:回测结束时仍持有的仓位必须计入交易

    :signals 只给 entry 不给 exit 时(横截面动量等策略常见),
    该笔交易完全不出现在 trade 列表,于是报告变成
    "Total Return 50.76% / Trades: 0 / win_rate 0" —— 收益是真的,
    交易统计却是错的,自相矛盾。标准做法是期末按收盘价强制平仓。
    """

    @staticmethod
    def _no_exit_signals(n):
        idx = pd.date_range("2024-01-01", periods=n)
        return pd.DataFrame({
            "entries": [False] * 5 + [True] + [False] * (n - 6),
            "exits": [False] * n,
        }, index=idx)

    def test_open_position_is_counted(self):
        n = 200
        rng = np.random.default_rng(1)
        close = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.01, n)))
        idx = pd.date_range("2024-01-01", periods=n)
        df = pd.DataFrame({"open": close, "high": close * 1.01,
                           "low": close * 0.99, "close": close,
                           "volume": 1_000_000}, index=idx)
        eng = SimpleBacktestEngine(initial_capital=100_000.0)
        sig = self._no_exit_signals(n)
        eq = eng._simulate_equity(df, sig)
        trades = eng._extract_trades(df, sig, eq)
        assert len(trades) == 1, f"未平仓的持仓没被计入交易: {trades}"
        assert trades[0].get("forced_close") is True
        assert trades[0]["exit_idx"] == n - 1

    def test_trade_count_never_contradicts_return(self):
        """核心不变量:有非零收益就不该报 0 笔交易"""
        for seed in range(6):
            n = 200
            rng = np.random.default_rng(seed)
            close = 100 * np.exp(np.cumsum(rng.normal(0.0012, 0.012, n)))
            idx = pd.date_range("2024-01-01", periods=n)
            df = pd.DataFrame({"open": close, "high": close * 1.01,
                               "low": close * 0.99, "close": close,
                               "volume": 1_000_000}, index=idx)
            eng = SimpleBacktestEngine(initial_capital=100_000.0)
            sig = self._no_exit_signals(n)
            eq = eng._simulate_equity(df, sig)
            trades = eng._extract_trades(df, sig, eq)
            ret = float(eq.iloc[-1] / eq.iloc[0] - 1)
            assert len(trades) > 0 or abs(ret) < 1e-9, (
                f"seed {seed}: 收益 {ret:+.2%} 却报 0 笔交易")

    def test_normal_closed_trades_unaffected(self):
        """已有完整进出的交易统计不应被影响"""
        n = 300
        rng = np.random.default_rng(5)
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, n)))
        idx = pd.date_range("2024-01-01", periods=n)
        df = pd.DataFrame({"open": close, "high": close * 1.01,
                           "low": close * 0.99, "close": close,
                           "volume": 1_000_000}, index=idx)
        s = MovingAverageCrossStrategy(parameters={"fast_period": 5, "slow_period": 20})
        eng = SimpleBacktestEngine(initial_capital=100_000.0)
        res = eng.run(s, df)
        assert res.n_trades > 0
        assert 0.0 <= res.win_rate <= 1.0


class TestAdvancedReportMetrics:
    """BacktestReport 的指标也必须与 empyrical 一致

    :Sortino/Sharpe 在 engine.py 与 advanced.py 各写了一份,
    engine 已按标准下行偏差修正而 advanced 仍用旧公式(仅负收益子集标准差),
    报出的 Sortino 比标准值高约 15%(已验证 1.90 vs 1.65)。现统一到
    engine.sortino_ratio / sharpe_ratio。
    """

    @pytest.mark.parametrize("seed", [9, 1, 42, 7, 100])
    def test_sortino_matches_empyrical(self, seed):
        r = pd.Series(np.random.default_rng(seed).normal(0.0008, 0.012, 504))
        m = BacktestReport.compute_metrics(r)
        assert m.sortino == pytest.approx(
            float(empyrical.sortino_ratio(r.values)), abs=1e-8
        )

    @pytest.mark.parametrize("seed", [9, 1, 42])
    def test_sharpe_and_drawdown_match_empyrical(self, seed):
        r = pd.Series(np.random.default_rng(seed).normal(0.0008, 0.012, 504))
        m = BacktestReport.compute_metrics(r)
        assert m.sharpe == pytest.approx(
            float(empyrical.sharpe_ratio(r.values)), abs=1e-2
        )
        assert m.max_drawdown == pytest.approx(
            float(empyrical.max_drawdown(r.values)), abs=1e-9
        )

    def test_volatility_is_annualised_std(self):
        r = pd.Series(np.random.default_rng(3).normal(0.0005, 0.01, 252))
        m = BacktestReport.compute_metrics(r)
        assert m.volatility == pytest.approx(float(r.std() * np.sqrt(252)), abs=1e-9)

    def test_cagr_consistent_with_total_return(self):
        r = pd.Series(np.random.default_rng(5).normal(0.0008, 0.01, 504))
        m = BacktestReport.compute_metrics(r)
        years = len(r) / 252
        assert m.cagr == pytest.approx((1 + m.total_return) ** (1 / years) - 1, abs=1e-9)

    def test_empty_returns_is_all_zero(self):
        m = BacktestReport.compute_metrics(pd.Series([], dtype=float))
        assert m.total_return == 0
        assert m.sharpe == 0
        assert m.sortino == 0


class TestThreeWayCrossCheck:
    """三方对拍:engine / advanced / empyrical 必须给出同一个数

    这层抓到了单层测试漏掉的东西:重构时把 advanced 的 Sharpe 改成走
    共享 helper,而 helper 内部用了 numpy 默认的 ddof=0,engine 用的却是
    pandas 的 ddof=1 —— 两处报出的 Sharpe 差 ~1e-3,单看任何一层都"没错"。
    只有三方互相对拍才会暴露。
    """

    @staticmethod
    def _series(seed=11, n=504):
        import numpy as np
        import pandas as pd

        g = np.random.default_rng(seed)
        close = 100 * np.exp(np.cumsum(g.normal(0.0006, 0.014, n)))
        df = pd.DataFrame({
            "open": close, "high": close * 1.01, "low": close * 0.99,
            "close": close, "volume": 1_000_000,
        }, index=pd.date_range("2024-01-01", periods=n))
        s = MovingAverageCrossStrategy(
            parameters={"fast_period": 10, "slow_period": 40})
        e = SimpleBacktestEngine(100_000.0)
        res = e.run(s, df)
        eq = e._simulate_equity(df, s.generate_signals(df))
        return res, eq.pct_change().dropna()

    @pytest.mark.parametrize("seed", [1, 42, 99, 2024, 7])
    def test_sharpe_identical_across_three_implementations(self, seed):
        res, r = self._series(seed)
        adv = BacktestReport.compute_metrics(r)
        ref = float(empyrical.sharpe_ratio(r.to_numpy()))
        assert res.sharpe == pytest.approx(adv.sharpe, abs=1e-9), (
            "engine 与 advanced 的 Sharpe 不一致 —— 多半是 std 的 ddof 口径分叉")
        assert res.sharpe == pytest.approx(ref, abs=1e-9)

    @pytest.mark.parametrize("seed", [1, 42, 99])
    def test_sortino_identical_across_three(self, seed):
        res, r = self._series(seed)
        adv = BacktestReport.compute_metrics(r)
        ref = float(empyrical.sortino_ratio(r.to_numpy()))
        assert res.sortino == pytest.approx(adv.sortino, abs=1e-9)
        assert res.sortino == pytest.approx(ref, abs=1e-9)

    @pytest.mark.parametrize("seed", [1, 42, 99])
    def test_max_drawdown_identical_across_three(self, seed):
        res, r = self._series(seed)
        adv = BacktestReport.compute_metrics(r)
        ref = float(empyrical.max_drawdown(r.to_numpy()))
        assert res.max_drawdown == pytest.approx(adv.max_drawdown, abs=1e-9)
        assert res.max_drawdown == pytest.approx(ref, abs=1e-9)

    def test_compute_metrics_accepts_ndarray(self):
        """调用方手上常是 .to_numpy(),不该因缺 .dropna() 而炸"""
        import numpy as np

        r = np.random.default_rng(3).normal(0.0005, 0.011, 300)
        m = BacktestReport.compute_metrics(r)  # ndarray 而非 Series
        assert isinstance(m.sharpe, float)


class TestCrossSectionalICEquivalence:
    """逐期横截面 IC 必须与 scipy 的口径完全一致

    为了速度,这条路径从 scipy.stats.pearsonr 换成了"中心化 + 点积"的
    向量实现,并把 pandas 的逐组切片换成一次 factorize + argsort。
    两处都是等价变换,但等价必须被证明,不能靠"看起来一样"。

    换之前的已验证:20 票 × 1 年的 pipeline 里这条路径占 63% 耗时
    (33000 次 pearsonr 调用),改完端到端 97.2s -> 32.1s。
    """

    @staticmethod
    def _reference(df, f="f", r="r", mn=5):
        """原实现:逐期 scipy.stats.pearsonr"""
        from scipy import stats as st

        out = []
        for _, g in df.groupby("date", sort=True):
            gx = g[[f, r]].dropna()
            if len(gx) < mn:
                continue
            xv, yv = gx[f].to_numpy(float), gx[r].to_numpy(float)
            if np.std(xv) == 0 or np.std(yv) == 0:
                continue
            v, _ = st.pearsonr(xv, yv)
            if np.isfinite(v):
                out.append(float(v))
        return np.array(out, dtype=float)

    @staticmethod
    def _panel():
        return pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01"] * 50 + ["2024-01-02"] * 40),
            "f": np.r_[np.random.default_rng(1).normal(0, 1, 50),
                       np.random.default_rng(2).uniform(-5, 5, 40)],
            "r": np.r_[np.random.default_rng(3).normal(0, 0.02, 50),
                       np.random.default_rng(4).normal(0, 0.03, 40)],
        })

    def _assert_matches_reference(self, df):
        got = _cross_sectional_ic_series(df, "f", "r")
        want = self._reference(df)
        assert got.shape == want.shape
        if want.size:
            np.testing.assert_allclose(got, want, rtol=1e-10, atol=1e-12)
        return got

    def test_matches_reference_on_clean_panel(self):
        assert self._assert_matches_reference(self._panel()).size == 2

    def test_matches_reference_with_missing_on_either_side(self):
        df = self._panel()
        df.loc[0:5, "f"] = np.nan
        self._assert_matches_reference(df)
        df2 = self._panel()
        df2.loc[3:9, "r"] = np.nan
        self._assert_matches_reference(df2)

    def test_matches_reference_with_constant_and_extreme_values(self):
        df = self._panel()
        df["f"] = 1.0
        self._assert_matches_reference(df)          # 常量因子:双方都跳过
        df2 = self._panel()
        df2.loc[0, "f"] = 1e18
        self._assert_matches_reference(df2)         # 极端值:不能溢出成 nan

    def test_matches_reference_on_unsorted_and_string_dates(self):
        self._assert_matches_reference(self._panel().sample(frac=1, random_state=7))
        df = self._panel()
        df["date"] = df["date"].astype(str)
        self._assert_matches_reference(df)

    def test_empty_when_cross_section_too_small(self):
        assert _cross_sectional_ic_series(self._panel().head(3), "f", "r").size == 0

    def test_materially_faster_than_scipy_loop(self):
        """提速不能以正确性为代价,也不能悄悄退化回去"""
        import time

        rng = np.random.default_rng(0)
        dates = pd.bdate_range("2024-01-01", periods=120)
        df = pd.DataFrame({
            "date": np.repeat(dates, 20),
            "f": rng.normal(0, 1, 2400),
            "r": rng.normal(0, 0.02, 2400),
        })
        t0 = time.time()
        _cross_sectional_ic_series(df, "f", "r")
        fast = time.time() - t0
        t0 = time.time()
        self._reference(df)
        slow = time.time() - t0
        assert fast < slow, f"新实现 {fast:.3f}s 反而慢于参考 {slow:.3f}s"
