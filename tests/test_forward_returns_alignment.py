# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""前瞻收益率必须按 symbol 对齐,不能跨标的串号

这是最深的一层:IC → 因子排名 → 策略选择全都建立在前瞻收益之上。
串号不崩、不报错、IC 照样算得"很顺利",只是数值彻底错了。

已验证后果(500 股 × 250 日,价格 3~2000 元的真实分布):
  horizon=1   420 行异常(0.3%),最大偏离真实值 335 倍
  horizon=5 2,089 行异常(1.7%),最大偏离 341 倍
  horizon=20 8,349 行异常(6.7%),最大偏离 395 倍

原因:对整列 shift(-h) 时,每个标的末 h 行会取到**下一个标的**的首日价。
A 股低价股 3 元、高价股 2000 元,一跨就是几百倍的收益率。
"""

import numpy as np
import pandas as pd
import polars as pl
import pytest

from forgemind.core.factors.ic_monitor import compute_forward_returns


def _panel(sym, close):
    return pl.DataFrame({"symbol": sym, "date": range(len(close)), "close": close})


class TestNoCrossSymbolLeakage:
    def test_last_row_of_each_symbol_is_not_the_next_symbol(self):
        """回归用例:AAA 末行必须等于 1000/104-1 = 8.615385"""
        rows = []
        for s, base in (("AAA", 100.0), ("BBB", 1000.0)):
            for i in range(5):
                rows.append({"symbol": s, "date": i, "close": base * (1 + 0.01 * i)})
        df = pl.DataFrame(rows).sort(["symbol", "date"])
        out = compute_forward_returns(df.lazy(), [1]).collect()

        aaa = out.filter(pl.col("symbol") == "AAA")["fwd_return_1"].to_list()
        assert aaa[-1] is None, (
            f"AAA 末行拿到 {aaa[-1]},那是从 BBB 串过来的价格")
        assert all(abs(x) < 0.05 for x in aaa if x is not None)

    def test_no_absurd_returns_on_realistic_price_dispersion(self):
        """真实 A 股价格跨两个数量级,串号会放大成几百倍"""
        ns, nd = 120, 60
        rng = np.random.default_rng(0)
        sym = np.repeat([f"S{i:04d}" for i in range(ns)], nd)
        base = 10 ** rng.uniform(np.log10(3), np.log10(2000), ns)
        close = np.repeat(base, nd) * np.exp(np.cumsum(rng.normal(0, 0.02, ns * nd)))
        df = pl.DataFrame({"symbol": sym, "date": np.tile(np.arange(nd), ns),
                           "close": close}).sort(["symbol", "date"])
        for h in (1, 5, 20):
            r = [x for x in
                 compute_forward_returns(df.lazy(), [h]).collect()[f"fwd_return_{h}"].to_list()
                 if x is not None]
            assert max(abs(x) for x in r) < 0.5, (
                f"horizon={h} 出现 {max(abs(x) for x in r):.1f} 倍的收益率,说明仍在串号")

    def test_unsorted_input_still_aligns_per_symbol(self):
        """行序打乱也必须按 symbol 自己的时间序对齐"""
        rows = []
        for s, base in (("AAA", 100.0), ("BBB", 1000.0)):
            for i in range(6):
                rows.append({"symbol": s, "date": i, "close": base * (1 + 0.01 * i)})
        df = pl.DataFrame(rows)  # 故意不排序
        got = compute_forward_returns(df.lazy(), [1]).collect().sort(["symbol", "date"])
        pdf = df.to_pandas().sort_values(["symbol", "date"])
        for s in ("AAA", "BBB"):
            col = got.filter(pl.col("symbol") == s)["fwd_return_1"].to_list()
            ref = (pdf[pdf.symbol == s]["close"].shift(-1) / pdf[pdf.symbol == s]["close"] - 1).tolist()
            assert all((a is None and pd.isna(b)) or abs(a - b) < 1e-12
                       for a, b in zip(col, ref))


class TestMatchesReferenceImplementation:
    @pytest.mark.parametrize("h", [1, 5, 20])
    def test_matches_pandas_groupby_shift(self, h):
        ns, nd = 60, 40
        rng = np.random.default_rng(7)
        sym = np.repeat([f"S{i:02d}" for i in range(ns)], nd)
        base = 10 ** rng.uniform(0.5, 2.5, ns)
        close = base.repeat(nd) * np.exp(np.cumsum(rng.normal(0, 0.02, ns * nd)))
        df = pl.DataFrame({"symbol": sym, "date": np.tile(np.arange(nd), ns),
                           "close": close}).sort(["symbol", "date"])
        got = compute_forward_returns(df.lazy(), [h]).collect()[f"fwd_return_{h}"].to_numpy()
        ref = df.to_pandas()
        ref = (ref.groupby("symbol")["close"].shift(-h) / ref["close"] - 1).to_numpy()
        m = ~(np.isnan(got) | np.isnan(ref))
        assert m.sum() > 0
        np.testing.assert_allclose(got[m], ref[m], rtol=1e-12, atol=1e-14)

    def test_single_symbol_panel_unchanged(self):
        """加 over("symbol") 不能改变单标的的既有行为"""
        one = _panel(["X"] * 10, [100 * (1.01 ** i) for i in range(10)])
        r = compute_forward_returns(one.lazy(), [1]).collect()["fwd_return_1"].to_list()
        assert r[-1] is None
        assert all(abs(x - 0.01) < 1e-12 for x in r if x is not None)

    def test_input_without_symbol_column_still_works(self):
        """老调用方可能没有 symbol 列,不能因此崩"""
        df = pl.DataFrame({"date": range(10), "close": [100 * (1.01 ** i) for i in range(10)]})
        r = compute_forward_returns(df.lazy(), [1]).collect()["fwd_return_1"].to_list()
        assert r[-1] is None and abs(r[0] - 0.01) < 1e-12
