# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""因子引擎必须按 symbol 隔离,窗口不能跨标的滑动

alpha158.py 里 34 处窗口操作(shift / rolling_* / ewm_mean / diff)存在
**全部**跑在整列上。面板按 symbol 排序时,每只票开头的若干行会取到
**上一只票的收盘价** —— 3 元股的窗口碰到 2000 元股,因子值放大几百倍。

已验证 500 股 × 250 日(按 symbol 排序),缺陷形态:

    MOM_10    3.3% 的行是垃圾,最大偏离 368 倍
    MOM_60   20.5%,456 倍
    MOM_120  42.6%,501 倍
    MOM_240  81.5%,619 倍

合计 27.2% 的因子值错误,而 IC 排序完全建立在这上面。

对照:compute_forward_returns 有同样问题,已单独修复。
"""

import numpy as np
import polars as pl

from forgemind.core.factors.alpha158 import compute_alpha158

OHLCV = ("symbol", "date", "open", "high", "low", "close", "volume")


def _panel(ns=12, nd=150, seed=7):
    rng = np.random.default_rng(seed)
    sym = np.repeat([f"S{i:02d}" for i in range(ns)], nd)
    base = 10 ** rng.uniform(np.log10(3), np.log10(2000), ns)  # 真实 A 股价差
    close = np.repeat(base, nd) * np.exp(np.cumsum(rng.normal(0, 0.02, ns * nd)))
    return pl.DataFrame({
        "symbol": sym, "date": np.tile(np.arange(nd), ns),
        "open": close, "high": close * 1.01, "low": close * 0.99,
        "close": close,
        "volume": rng.integers(1e5, 1e6, ns * nd).astype(float),
    }).sort(["symbol", "date"])


class TestPanelMatchesPerSymbolComputation:
    """决定性判据:面板结果必须与逐只单独计算一致

    单标的没有第二个 symbol 可串,天然是正确的参照系。
    串号会表现为 O(1) 的差异(已验证过 619 倍);
    纯浮点噪声在 1e-6 以下 —— 阈值据此设定。
    """

    def test_panel_equals_per_symbol(self):
        df = _panel()
        panel = compute_alpha158(df.lazy()).collect()
        worst, worst_f, n = 0.0, None, 0
        for s in sorted(set(df["symbol"].to_list())):
            one = compute_alpha158(
                df.filter(pl.col("symbol") == s).drop("symbol").lazy()).collect()
            two = panel.filter(pl.col("symbol") == s)
            for f in panel.columns:
                if f in OHLCV:
                    continue
                a = one[f].to_numpy()
                b = two[f].to_numpy()
                m = ~(np.isnan(a) | np.isnan(b))
                if not m.sum():
                    continue
                n += int(m.sum())
                d = float(np.nanmax(np.abs(a[m] - b[m])))
                if d > worst:
                    worst, worst_f = d, f
        assert n > 50_000, f"比对样本太少({n}),测试可能失效"
        assert worst < 1e-6, (
            f"面板与逐只计算最大偏差 {worst:.2e}({worst_f}) —— 窗口跨标的了")

    def test_same_path_different_price_scales_agree(self):
        """两只票路径完全相同、价格差 10 倍,相对型因子必须一致"""
        rows = []
        for sym, b in (("AAA", 100.0), ("BBB", 1000.0)):
            for i in range(40):
                c = b * (1.01 ** i)
                rows.append({"symbol": sym, "date": i, "open": c,
                             "high": c * 1.002, "low": c * 0.998, "close": c,
                             "volume": 1e6, "amount": c * 1e6})
        out = compute_alpha158(
            pl.DataFrame(rows).sort(["symbol", "date"]).lazy()).collect()
        for f in ("MOM_5", "MOM_10", "ROC_5_10", "ROC_3_20", "RET_1"):
            if f not in out.columns:
                continue
            a = out.filter(pl.col("symbol") == "AAA")[f].to_numpy()
            b = out.filter(pl.col("symbol") == "BBB")[f].to_numpy()
            m = ~(np.isnan(a) | np.isnan(b))
            assert m.sum() > 10
            np.testing.assert_allclose(a[m], b[m], rtol=1e-9, atol=1e-12)

    def test_first_rows_are_null_not_garbage(self):
        """串号专挑每只票的头几行 —— 那里必须没有值,而不是 605% 动量"""
        rows = []
        for sym, b in (("AAA", 100.0), ("BBB", 1000.0)):
            for i in range(40):
                c = b * (1.01 ** i)
                rows.append({"symbol": sym, "date": i, "open": c,
                             "high": c * 1.002, "low": c * 0.998, "close": c,
                             "volume": 1e6, "amount": c * 1e6})
        out = compute_alpha158(
            pl.DataFrame(rows).sort(["symbol", "date"]).lazy()).collect()
        bbb = out.filter(pl.col("symbol") == "BBB")["MOM_5"].to_numpy()
        assert all(v is None or (isinstance(v, float) and np.isnan(v))
                   for v in bbb[:5]), (
            f"BBB 前 5 行应无值(窗口不足),实际 {bbb[:5]} —— 上一只票的价格串进来了")


class TestSingleSymbolInputUnaffected:
    """无 symbol 列的输入必须仍能算(单标的用法)"""

    def test_works_without_symbol_column(self):
        rng = np.random.default_rng(3)
        n = 120
        c = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.015, n)))
        df = pl.DataFrame({
            "date": range(n), "open": c * 0.999, "high": c * 1.01,
            "low": c * 0.99, "close": c,
            "volume": rng.integers(1e5, 1e6, n).astype(float),
        })
        out = compute_alpha158(df.lazy()).collect()
        mom5 = out["MOM_5"].to_numpy()
        valid = mom5[~np.isnan(mom5)]
        assert len(valid) > 100
        # 漂移 +0.05%/日 → 5 日动量**均值**理论值 5*0.0005 = 0.0025。
        # 两个易错点:
        #  1. 用中位数断言 —— 随机游走里重叠的 5 日收益中位数接近 0,
        #     会得到一个看似合理的错误期望值;
        #  2. 容差拍脑袋定 0.001 —— 而本例 n=115 时均值标准误就有 0.0029,
        #     再小的容差也必然翻车。
        # 正确做法:容差取标准误的 4 倍,才既不误杀又拦得住真串号
        # (串号的量级是 O(1),比标准误大两个数量级)。
        mean = float(np.mean(valid))
        se = float(np.std(valid)) / np.sqrt(len(valid))
        assert abs(mean - 0.0025) < 4 * se, (
            f"MOM_5 均值 {mean:+.5f} 偏离理论 0.0025 超过 4 倍标准误({4*se:.5f})")

    def test_symbol_column_optional_but_preserved(self):
        df = _panel(ns=2, nd=60)
        out = compute_alpha158(df.lazy()).collect()
        assert "symbol" in out.columns
        assert out["symbol"].n_unique() == 2
