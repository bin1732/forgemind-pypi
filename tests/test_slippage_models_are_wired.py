# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""README 说"3 种滑点模型",但三个模型一次都没被调用过

`SlippageModel` 实现了 fixed / linear / sqrt 三种,只从 `__init__.py` 再导出,
而引擎的成交价始终按固定 bps 算 —— 用户以为能选冲击模型,实际选不了,
而且模型存在这件事本身给了 README 底气。

接线时还存在一个更隐蔽的问题:下单股数硬编码成 1。冲击模型的意义就在
按规模估冲击,1 股的冲击小到可以忽略,三个模型算出来一样 —— 模型接上了
却不生效。现在股数按 名义金额 / 价格 推算。

只验"参数被接受"是不够的:必须验三个模型真的给出不同结果。
"""

import numpy as np
import pandas as pd
import pytest

from forgemind.core.backtest.engine import SimpleBacktestEngine
from forgemind.core.strategies.base import MovingAverageCrossStrategy


def _panel(n=300, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.018, n)))
    return pd.DataFrame({
        "open": close, "high": close * 1.01, "low": close * 0.99,
        "close": close, "volume": np.full(n, 1e6),
    }, index=pd.date_range("2024-01-01", periods=n))


def _run(model, adv=1_000_000.0):
    e = SimpleBacktestEngine(100_000.0, slippage_model=model, adv_shares=adv)
    r = e.run(MovingAverageCrossStrategy(
        parameters={"fast_period": 5, "slow_period": 20}), _panel())
    return r, e


class TestSlippageModelsAreSelectable:
    @pytest.mark.parametrize("m", ["fixed", "linear", "sqrt"])
    def test_each_model_runs(self, m):
        r, e = _run(m)
        assert e.slippage_model == m
        assert np.isfinite(r.total_return)

    def test_impact_models_actually_change_the_result(self):
        """接线不等于生效 —— 仅"值不同"还不够,必须是真实可见的经济差异

        这里只 assert `set > 1` —— 而当 _slip_price 被错误实现成
        raw_price*(1+1e-6) 之类时,三个模型之间会有微小浮点差异,
        但对用户来说三种模型"算出来一样",而测试还显示 PASS。空转断言。
        现在钉一个 50bps 的可见差异,模型真正起作用的最小证据。
        """
        results = {m: _run(m)[0].total_return for m in ("fixed", "linear", "sqrt")}
        spread = max(results.values()) - min(results.values())
        assert spread >= 5e-3, (
            f"三种滑点模型的 spread 应 < 0.5%,实际只 {spread:.6%};"
            f"results={results} —— 冲击项没真起作用")

    def test_sqrt_is_less_painful_than_fixed_for_small_orders(self):
        """经济方向:满仓下 sqrt 冲击 ≈ price*sqrt(0.1)*5bps ≈ 1.6bps,
        fixed = 5bps。sqrt 应比 fixed 应占便宜 (更高收益)。"""
        fixed, sqrt = _run("fixed")[0].total_return, _run("sqrt")[0].total_return
        assert sqrt > fixed, (
            f"sqrt ({sqrt:+.4%}) 应优于 fixed ({fixed:+.4%}) —— "
            "sqrt 对小单冲击小,固定 bps 反而更贵")

    def test_no_slippage_at_all_would_be_detected(self):
        """如果 _slip_price 形同虚设(无论选哪个模型都不扣滑点),
        三个模型必然给出同一个结果。"""
        class FakeEngine(SimpleBacktestEngine):
            def _slip_price(self, raw_price, size, is_buy):  # noqa: D401
                return raw_price
        results = {}
        for m in ("fixed", "linear", "sqrt"):
            e = FakeEngine(100_000.0, slippage_model=m, adv_shares=1_000_000.0)
            results[m] = e.run(
                MovingAverageCrossStrategy(
                    parameters={"fast_period": 5, "slow_period": 20}),
                _panel()).total_return
        spread = max(results.values()) - min(results.values())
        assert spread < 1e-9, (
            f"_slip_price 不生效时三个模型应一致,实际 spread={spread};{results}")

    def test_impact_model_without_adv_degrades_and_says_so(self):
        r, e = _run("sqrt", adv=0)
        assert e.slippage_degraded_to_fixed is True, (
            "没给 adv 时应如实标记退化为 fixed,而不是假装用了 sqrt")
        fixed, _ = _run("fixed", adv=0)
        assert abs(r.total_return - fixed.total_return) < 1e-12

    def test_unknown_model_is_rejected_at_construction(self):
        with pytest.raises(ValueError, match="滑点模型"):
            SimpleBacktestEngine(100_000.0, slippage_model="bogus")

    def test_order_size_follows_notional(self):
        e = SimpleBacktestEngine(100_000.0, slippage_model="sqrt",
                                  adv_shares=1_000_000.0)
        # 10 万名义 / 100 元股价 = 1000 股,而不是 1
        assert e._order_size(100.0) == 1000
        assert e._order_size(0) == 0


class TestCliExposesIt:
    """没有入口 = 用户选不了,README 那句话仍是空的"""

    def test_parser_accepts_the_flag(self):
        from forgemind.cli import build_parser

        a = build_parser().parse_args(
            ["backtest", "--slippage-model", "sqrt", "--adv", "1000000"])
        assert a.slippage_model == "sqrt"
        assert a.adv == 1000000

    def test_invalid_value_rejected_by_argparse(self):
        from forgemind.cli import build_parser

        with pytest.raises(SystemExit):
            build_parser().parse_args(["backtest", "--slippage-model", "nope"])
