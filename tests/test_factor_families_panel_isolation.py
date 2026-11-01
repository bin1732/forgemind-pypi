# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""alpha101 与 barra 也必须按 symbol 隔离

alpha158 的同类问题修好后,这两个家族没被一起查 —— 结果 alpha101 的
ALPHA006 / ALPHA038 / ALPHA041 与 barra 的 BARRA_BETA /
BARRA_MOMENTUM / BARRA_RESIDUAL_VOL 同样跨标的。

**本文件最关键的一条断言是"首行必须为空"**,而不是只比中段:
窗口类因子在前 window-1 行本就无值,若第 2 只票的第一行就有了数,
说明窗口跨到了上一只票。

这个坑我连踩三次:每次都只比对了"干净的中段"就宣布通过 ——
  1. alpha158:只查每只票最后 5 行,污染在开头
  2. barra:只查第 252 行之后,污染在开头
  3. barra 测试数据里每只票用了相同收益序列,对称性把污染抹平了
"""

import numpy as np
import polars as pl

from forgemind.core.factors.alpha101 import compute_alpha101
from forgemind.core.factors.barra import barra_beta, barra_momentum, barra_residual_vol

RAW = ("symbol", "date", "open", "high", "low", "close", "volume",
       "amount", "returns", "mkt_returns", "vwap", "cap", "mkt_cap")


def _ohlcv(ns=6, nd=300, seed=9):
    """每只票**不同**的收益序列 —— 对称数据会把跨标的污染抹平,必须避开"""
    rng = np.random.default_rng(seed)
    sym = np.repeat([f"S{i:02d}" for i in range(ns)], nd)
    base = 10 ** rng.uniform(0.5, 3.0, ns)
    close = np.repeat(base, nd) * np.exp(np.cumsum(rng.normal(0, 0.02, ns * nd)))
    return pl.DataFrame({
        "symbol": sym, "date": np.tile(np.arange(nd), ns),
        "open": close * 0.999, "high": close * 1.02, "low": close * 0.98,
        "close": close, "volume": 1e6, "amount": close * 1e6, "vwap": close,
        "cap": 1e9, "mkt_cap": close * 1e7,
        "returns": rng.normal(0.0004, 0.011, ns * nd),
        "mkt_returns": np.tile(rng.normal(0.0003, 0.010, nd), ns),
    }).sort(["symbol", "date"])


def _is_nullish(v):
    return v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v)))


class TestBarraWindowsStayInsideSymbol:
    def test_beta_is_null_before_the_window_fills(self):
        """252 日窗口 → 前 251 行必为空,包括第 2 只及以后的票

        S01/S02/S03 的**第一行**不应有 beta(窗口取到了上一只票)。
        """
        df = _ohlcv()
        out = barra_beta(df.lazy()).collect()
        for s in sorted(set(df["symbol"].to_list())):
            v = out.filter(pl.col("symbol") == s)["BARRA_BETA"].to_numpy()
            assert all(_is_nullish(x) for x in v[:251]), (
                f"{s} 的前 251 行应为空,实际第 0 行 = {v[0]} —— 窗口跨标的了")
            assert not _is_nullish(v[251]), f"{s} 第 252 行窗口应已填满"

    def test_beta_matches_per_symbol_computation(self):
        df = _ohlcv()
        panel = barra_beta(df.lazy()).collect()
        for s in sorted(set(df["symbol"].to_list())):
            one = barra_beta(df.filter(pl.col("symbol") == s).lazy()).collect()
            two = panel.filter(pl.col("symbol") == s)
            a = one["BARRA_BETA"].to_numpy()
            b = two["BARRA_BETA"].to_numpy()
            m = ~np.isnan(a) & ~np.isnan(b)
            assert m.sum() > 20
            np.testing.assert_allclose(a[m], b[m], rtol=1e-9, atol=1e-12)

    def test_momentum_and_residual_vol_also_isolated(self):
        df = _ohlcv()
        for fn, col, warmup in (
            (barra_momentum, "BARRA_MOMENTUM", 504),
            (barra_residual_vol, "BARRA_RESIDUAL_VOL", 252),
        ):
            panel = fn(df.lazy()).collect()
            for s in sorted(set(df["symbol"].to_list())):
                v = panel.filter(pl.col("symbol") == s)[col].to_numpy()
                # 窗口未满的前若干行必须为空
                head = v[:max(1, warmup - 1)]
                assert all(_is_nullish(x) for x in head), (
                    f"{col} 在 {s} 的前 {warmup-1} 行应为空,"
                    f"实际第 0 行 = {v[0]}")


class TestAlpha101SurfaceIntact:
    """声明的因子必须真的都被算出来

    改造 compute_alpha101 时我用字符串切片搬动函数体,把链条开头的
    `df = alpha_001(df)` 一起切掉了 —— 结果少产出一个因子,值还是对的,
    不看列名根本发现不了。ruff 不检查"调用链是否完整"。
    """

    def test_every_declared_factor_is_produced(self):
        from forgemind.core.factors import compute_alpha101, list_alpha101_factors
        import sys as _s
        _s.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
        from test_factor_library import make_test_data

        out = compute_alpha101(make_test_data(60, 5)).collect()
        missing = [f for f in list_alpha101_factors() if f not in out.columns]
        assert not missing, f"声明了却没算出来: {missing}"

    def test_chain_mentions_every_implemented_factor(self):
        """更直接的一层:链条里必须出现每个已实现的 alpha_xxx"""
        import ast
        from pathlib import Path

        src = (Path(__file__).resolve().parent.parent
               / "forgemind/core/factors/alpha101.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name == "_compute_alpha101_one")
        called = {c.func.id for c in ast.walk(fn)
                  if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        defined = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)
                   and n.name.startswith("alpha_")}
        missing = defined - called
        assert not missing, (
            f"这些因子函数定义了却没进调用链:{sorted(missing)}")


class TestAlpha101Isolated:
    def _panel(self, ns=6, nd=120, seed=5):
        rng = np.random.default_rng(seed)
        sym = np.repeat([f"S{i:02d}" for i in range(ns)], nd)
        base = 10 ** rng.uniform(0.5, 3.0, ns)
        close = np.repeat(base, nd) * np.exp(np.cumsum(rng.normal(0, 0.02, ns * nd)))
        vol = rng.integers(1e5, 1e6, ns * nd).astype(float)
        return pl.DataFrame({
            "symbol": sym, "date": np.tile(np.arange(nd), ns),
            "open": close * 0.999, "high": close * 1.02, "low": close * 0.98,
            "close": close, "volume": vol, "amount": close * vol,
            "vwap": close, "returns": rng.normal(0, 0.01, ns * nd), "cap": 1e9,
        }).sort(["symbol", "date"])

    def test_panel_equals_per_symbol(self):
        df = self._panel()
        panel = compute_alpha101(df.lazy()).collect()
        n = 0
        for s in sorted(set(df["symbol"].to_list())):
            one = compute_alpha101(df.filter(pl.col("symbol") == s).lazy()).collect()
            two = panel.filter(pl.col("symbol") == s)
            for f in panel.columns:
                if f in RAW:
                    continue
                a = one[f].to_numpy()
                b = two[f].to_numpy()
                m = ~np.isnan(a) & ~np.isnan(b) & ~np.isinf(a) & ~np.isinf(b)
                if not m.sum():
                    continue
                n += int(m.sum())
                np.testing.assert_allclose(a[m], b[m], rtol=1e-9, atol=1e-11,
                                           err_msg=f"{f} 在 {s} 上与逐只计算不符")
        assert n > 5_000, f"比对样本太少({n}),测试可能失效"

    def test_rows_before_window_fills_are_null(self):
        """窗口未满的前几行必须为空

        暖机期按因子各自的差分窗口定,不能一刀切:
          ALPHA053 = diff(9)   → 前 9 行为空
          ALPHA012 = diff(1)   → 只有第 0 行为空
          ALPHA007 = np.where 的 -1 兜底值,**不是**空值
        """
        df = self._panel(nd=120)
        out = compute_alpha101(df.lazy()).collect()
        for s in sorted(set(df["symbol"].to_list())):
            sub = out.filter(pl.col("symbol") == s)
            for f, warmup in (("ALPHA053", 9), ("ALPHA012", 1)):
                if f not in out.columns:
                    continue
                v = sub[f].to_numpy()
                assert all(_is_nullish(x) for x in v[:warmup]), (
                    f"{f} 在 {s} 的前 {warmup} 行应为空,实际 {v[:warmup]}"
                    " —— 窗口跨标的了")
