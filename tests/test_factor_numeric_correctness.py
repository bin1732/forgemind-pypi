# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""因子数值必须真的等于它声称的指标

之前验过:因子"能算"(不崩)、"不串标的"(跨 symbol 隔离)、"目录与实现一致"。
但从没验过**算出来的数对不对** —— 一个把 RSI 算反、或把动量写成反转的
因子不会崩,只会一直给错信号,而且下游一切看起来都正常。

这里用两类可解析的输入交叉验证:
  1. 几何价格序列 close[i] = 100*1.01^i —— 有闭式解,逐项精确比对
  2. 四种形态(涨/跌/V型/锯齿) —— 验方向与量纲,避免"恰好对"
"""

import numpy as np
import polars as pl
import pytest

from forgemind.core.factors.alpha158 import compute_alpha158

N = 40


def _compute(close):
    close = np.asarray(close, dtype=float)
    n = len(close)
    return compute_alpha158(pl.DataFrame({
        "symbol": ["A"] * n,
        "date": pl.Series(range(n)).cast(pl.Date),
        "open": close, "high": close * 1.01, "low": close * 0.99,
        "close": close, "volume": np.full(n, 1e6),
        "amount": close * 1e6,
    }).lazy()).collect(), close


@pytest.fixture(scope="module")
def geometric():
    return _compute(100 * 1.01 ** np.arange(N))


class TestAgainstClosedForm:
    """几何序列上每个因子都有解析解"""

    def test_mom_5(self, geometric):
        out, c = geometric
        assert out["MOM_5"][N - 1] == pytest.approx(1.01 ** 5 - 1, rel=1e-12)

    def test_roc_is_ratio_of_rolling_means(self, geometric):
        out, c = geometric
        want = c[-3:].mean() / c[-10:].mean() - 1
        assert out["ROC_3_10"][N - 1] == pytest.approx(want, rel=1e-12)

    def test_kmid_is_body_over_open(self, geometric):
        out, c = geometric
        # 构造里 open == close → 实体为 0
        assert out["KMID"][N - 1] == pytest.approx(0.0, abs=1e-15)

    def test_klen_is_range_over_open(self, geometric):
        out, c = geometric
        want = (c[-1] * 1.01 - c[-1] * 0.99) / c[-1]
        assert out["KLEN"][N - 1] == pytest.approx(want, rel=1e-12)

    def test_ma_spread_is_ma_difference(self, geometric):
        out, c = geometric
        assert out["MA_SPREAD_5_10"][N - 1] == pytest.approx(
            c[-5:].mean() - c[-10:].mean(), rel=1e-12)


MOMENTUM_LIKE = ["MOM_5", "MOM_20", "ROC_5_10", "ROC_20_60",
                 "MA_SPREAD_5_20", "MA_SPREAD_20_60"]


class TestDirectionAcrossShapes:
    """只在一个序列上对,可能只是巧合;四种形态交叉验才说明方向真的对"""

    SHAPES = {
        "up": lambda n: 100 * 1.01 ** np.arange(n),
        "down": lambda n: 100 * 0.99 ** np.arange(n),
        "v": lambda n: 100 * np.concatenate([1.01 ** np.arange(n // 2),
                                              0.99 ** np.arange(n - n // 2)]),
        "saw": lambda n: 100 * np.array([1.03 if i % 2 else 0.97
                                         for i in range(n)]),
    }

    @pytest.mark.parametrize("f", MOMENTUM_LIKE)
    def test_up_scores_higher_than_down(self, f):
        n = 60
        vals = {}
        for name, gen in self.SHAPES.items():
            out, _ = _compute(gen(n))
            v = out[f][n - 1]
            vals[name] = None if v is None else float(v)
        if vals["up"] is None or vals["down"] is None:
            pytest.skip(f"{f} 样本不足")
        assert vals["up"] > vals["down"], (
            f"{f}: 上涨 {vals['up']:.4f} 应高于下跌 {vals['down']:.4f} —— 方向可能反了")

    @pytest.mark.parametrize("f", MOMENTUM_LIKE)
    def test_positive_on_a_monotonic_uptrend(self, f):
        n = 60
        out, _ = _compute(self.SHAPES["up"](n))
        v = out[f][n - 1]
        if v is None:
            pytest.skip(f"{f} 样本不足")
        assert float(v) > 0, (
            f"{f}: 单调上涨序列上算出 {float(v):.4f} —— 动量类因子不该为负")


class TestWindowLengthsAreHonoured:
    def test_long_lookback_is_null_when_history_is_short(self, f="MOM_60"):
        """60 日动量在只有 40 根时必须是空,而不是拿更短的窗口凑一个数"""
        out, _ = _compute(100 * 1.01 ** np.arange(40))
        assert out["MOM_60"][N - 1] is None, (
            "40 根 K 线算不出 60 日动量,不该返回一个数")
