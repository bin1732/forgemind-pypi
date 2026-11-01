# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""选股器的数值正确性 —— 之前每一条都是错的

三个缺陷叠在一起,输出却完全"像样":

1. **_get_kline 返回倒序数据**(最严重)
   SQL 是 `ORDER BY date DESC LIMIT 100`,取到的确实是最新 100 根,
   但顺序是新→旧。所有因子都按 `close.iloc[-1]` 当最新一根,于是
   `iloc[-1]` 实际是 **100 天前**那根。均线、动量、量价全部错位 100 根 K 线。
   已验证:真实跌幅 -97% 的股票被算出动量 **+225%**,据此给出
   "buy / 0.70 置信 / 多头排列,趋势向上"。

2. **rationale 用横截面百分位陈述个股事实**
   全员下跌的池子里,榜首的动量百分位照样 >= 0.7,于是被告知
   "动量强劲,过去 20/60 日涨幅明显" —— 纯相对排名,句句是假。

3. **方向与置信只看池内排名,没有绝对闸门**
   跌得最慢的那只 = "买入"。
"""

import asyncio

import numpy as np
import pytest


@pytest.fixture
def universe_db(tmp_path, monkeypatch):
    """造一个行情库,返回 (build 函数, 股票代码列表)"""
    monkeypatch.chdir(tmp_path)
    from forgemind.core.data.storage import DuckDBStorage

    with DuckDBStorage() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS kline_daily (
            date DATE, symbol VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE,
            close DOUBLE, volume BIGINT, provider VARCHAR,
            PRIMARY KEY (date, symbol))""")

    def build(drift, vol, n=30, seed=0):
        with DuckDBStorage() as db:
            db.execute("DELETE FROM kline_daily")
            rng = np.random.default_rng(seed)
            rows = []
            for s in range(n):
                sym = f"S{s:04d}"
                c = 100 * np.exp(np.cumsum(rng.normal(drift, vol, 120)))
                for i in range(120):
                    rows.append((f"2024-{i // 28 + 1:02d}-{(i % 28) + 1:02d}", sym,
                                 c[i] * 0.999, c[i] * 1.004, c[i] * 0.996, c[i],
                                 1_000_000, None))
            for r in rows:
                db.execute("INSERT OR REPLACE INTO kline_daily "
                           "(date,symbol,open,high,low,close,volume,provider) "
                           "VALUES (?,?,?,?,?,?,?,?)", list(r))
        return [f"S{s:04d}" for s in range(n)]

    return build


class TestKlineIsChronological:
    def test_rows_come_back_oldest_first(self, universe_db):
        """因子用 iloc[-1] 取"最新一根",顺序反了整条链路就全错"""
        from forgemind.core.agents.stock_picker import StockPickerAgent

        syms = universe_db(-0.001, 0.01, n=2)
        df = StockPickerAgent()._get_kline(syms[0], None)
        assert df is not None and len(df) > 1
        assert list(df["date"]) == sorted(df["date"]), "K 线必须按日期正序"

    def test_takes_the_most_recent_bars_not_the_oldest(self, universe_db):
        """不能用 ORDER BY date ASC + LIMIT 取 —— 那样拿到的是最早 100 根"""
        from forgemind.core.agents.stock_picker import StockPickerAgent

        syms = universe_db(0.0, 0.01, n=2)
        df = StockPickerAgent()._get_kline(syms[0], None)
        assert len(df) == 100, "总共 120 根,应取最新 100 根"
        assert df["date"].max() == df["date"].iloc[-1]
        assert df["date"].max().month >= 4, "应覆盖到 5 月(数据末尾)"

    def test_momentum_sign_matches_the_actual_price_path(self, universe_db):
        """真实下跌的股票,动量必须为负

        真实 -97% 的股票曾被算出 **+225%** 并被标成"动量强劲"。
        """
        from forgemind.core.agents.stock_picker import StockPickerAgent

        syms = universe_db(-0.03, 0.005, n=2)  # 每天 -3%
        p = StockPickerAgent()
        df = p._get_kline(syms[0], None)
        raw = p._compute_raw_factors(df)
        assert raw["momentum"] < -0.3, (
            f"崩盘行情下动量应为大幅负值,实际 {raw['momentum']:+.1%}")
        assert raw["trend"] < 0, f"趋势应为负,实际 {raw['trend']:+.3f}"


class TestRationaleStaysTrue:
    @pytest.mark.parametrize("drift,vol,label", [
        (-0.010, 0.005, "明确下跌"),
        (-0.030, 0.005, "崩盘"),
    ])
    def test_crashing_pool_never_gets_buy_or_bullish_claims(
        self, universe_db, drift, vol, label
    ):
        from forgemind.core.agents.stock_picker import StockPickerAgent

        syms = universe_db(drift, vol)
        picks = asyncio.run(StockPickerAgent().pick(universe=syms, top_n=3))
        assert picks, f"{label}: 应仍有池内排名结果"
        for p in picks:
            assert p.direction != "buy", (
                f"{label}: 榜首 {p.symbol} 真实动量在跌,不应给 buy"
                f" —— rationale:\n{p.rationale}")
            assert "多头排列" not in p.rationale, f"{label}: 不可声称多头排列"
            assert "动量强劲" not in p.rationale, f"{label}: 不可声称动量强劲"
            assert "确实在涨" not in p.rationale
            assert p.confidence <= 0.35, (
                f"{label}: 池内领先但自身在跌,置信不应高:{p.confidence}")

    def test_rising_pool_still_gets_buy(self, universe_db):
        """绝对闸门不能把该买的也挡掉"""
        from forgemind.core.agents.stock_picker import StockPickerAgent

        syms = universe_db(0.005, 0.01)
        picks = asyncio.run(StockPickerAgent().pick(universe=syms, top_n=3))
        assert any(p.direction == "buy" for p in picks), (
            "普涨行情下应有买入信号,绝对闸门过严会误杀")

    def test_score_is_labelled_as_relative(self, universe_db):
        from forgemind.core.agents.stock_picker import StockPickerAgent

        syms = universe_db(0.0, 0.01)
        p = asyncio.run(StockPickerAgent().pick(universe=syms, top_n=1))[0]
        assert "候选池" in p.rationale or "池内" in p.rationale, (
            "必须说明分数是池内相对排名,0.8 不代表股票本身质地好")


class TestNoDegenerateNormalizerLeftBehind:
    def test_fixed_scale_normalizer_is_gone(self):
        """旧的 scale=0.05 线性归一化会把 ±5% 之外全压成 0/1

        调用方已改用 _cross_sectional_normalize,但这个方法还留在类里,
        谁调用谁就重新已修复。必须删掉,不留 landmine。
        """
        from forgemind.core.agents.stock_picker import StockPickerAgent

        assert not hasattr(StockPickerAgent, "_normalize_score"), (
            "退化的 scale=0.05 归一化方法仍存在,一旦被调用即恢复原 bug")

    def test_cross_sectional_normalize_spreads_across_universe(self):
        from forgemind.core.agents.stock_picker import StockPickerAgent

        raws = [{"momentum": v, "trend": -v} for v in np.linspace(-0.5, 0.5, 20)]
        out = StockPickerAgent._cross_sectional_normalize(raws)
        vals = [o["momentum"] for o in out]
        assert len(set(np.round(vals, 9))) == 20, "百分位应铺满,不应退化"
        assert min(vals) == 0.0 and max(vals) == 1.0
