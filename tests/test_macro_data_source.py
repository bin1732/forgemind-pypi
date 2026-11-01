# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""宏观数据源:真的要能取到数,取不到也要说清楚。

对外说明里写着提供 CN macro,那这个源就不能只是一个占位。验收看三
点:真的能取到数、取不到的指标不拿别的值顶替、对齐语义说得通(月度指标
在发布日之后一直有效)。
"""

from __future__ import annotations

import pandas as pd
import polars as pl
import pytest

from forgemind.core.data.sources.extended_sources import (
    MacroDataSource,
    get_default_registry,
)


def _monthly_frame(dates: list[str], values: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "商品": ["中国指标"] * len(dates),
        "日期": pd.to_datetime(dates),
        "今值": values,
        "预测值": [None] * len(dates),
        "前值": [None] * len(dates),
    })


class _FakeAk:
    """假 akshare:每个接口给一段可控的序列。"""

    def __init__(self):
        self.calls: list[str] = []

    def macro_china_pmi_yearly(self):
        self.calls.append("pmi")
        return _monthly_frame(["2025-01-10", "2025-02-10"], [49.0, 50.5])

    def macro_china_cpi_monthly(self):
        self.calls.append("cpi")
        return _monthly_frame(["2025-01-09"], [0.2])

    def macro_china_ppi_yearly(self):
        self.calls.append("ppi")
        return _monthly_frame(["2025-01-10"], [-2.5])

    def macro_china_m2_yearly(self):
        self.calls.append("m2")
        return _monthly_frame(["2025-01-12"], [8.1])

    def bond_zh_us_rate(self):
        self.calls.append("bond")
        return pd.DataFrame({
            "日期": pd.to_datetime(["2025-01-10", "2025-01-13"]),
            "中国国债收益率10年": [1.80, 1.85],
        })

    def currency_boc_sina(self):
        self.calls.append("fx")
        return pd.DataFrame({
            "日期": pd.to_datetime(["2025-01-10", "2025-01-13"]),
            "央行中间价": [720.0, 725.0],
        })


class TestMacroIsReal:
    def test_source_is_available(self):
        """宏观源不再是占位。

        akshare 在 [cn] extra 里,常规流水线没装 —— 那种环境下这条
        跳过,真实取数由 verify-live 的实时探针负责。
        """
        pytest.importorskip("akshare")
        ok, reason = MacroDataSource().is_available()
        assert ok, reason

    def test_registry_reports_it_available(self):
        """注册表里查到的也是可用的。"""
        pytest.importorskip("akshare")
        src = get_default_registry().get("macro")
        ok, reason = src.is_available()
        assert ok, reason

    def test_fetch_returns_schema_conforming_frame(self, monkeypatch):
        """取到的表要符合 schema:列名与类型都对得上。"""
        import sys
        import types

        fake = _FakeAk()
        monkeypatch.setitem(sys.modules, "akshare", fake)
        df = MacroDataSource().fetch(start="2025-01-01", end="2025-01-31")
        assert set(df.columns) == set(MacroDataSource().get_schema())
        assert df.schema["date"] == pl.Date
        for col in ("PMI", "CPI", "PPI", "M2_yoy", "10y_yield", "USD_CNY"):
            assert df.schema[col] == pl.Float64, col

    def test_values_are_the_real_ones(self, monkeypatch):
        """取到的值就是接口给的值,没有加工也没有编造。"""
        import sys

        monkeypatch.setitem(sys.modules, "akshare", _FakeAk())
        df = MacroDataSource().fetch(start="2025-01-01", end="2025-01-31")
        row = df.filter(pl.col("date") == pl.date(2025, 1, 13)).row(0, named=True)
        assert row["PMI"] == 49.0
        assert row["CPI"] == 0.2
        assert row["PPI"] == -2.5
        assert row["M2_yoy"] == 8.1
        assert row["10y_yield"] == 1.85
        # 外汇牌价按 100 单位报价,换算成 1 单位
        assert row["USD_CNY"] == pytest.approx(7.25)

    def test_indicator_is_empty_before_its_release(self, monkeypatch):
        """指标还没发布时是空的,不用别的值顶替。"""
        import sys

        monkeypatch.setitem(sys.modules, "akshare", _FakeAk())
        df = MacroDataSource().fetch(start="2025-01-01", end="2025-01-31")
        first = df.filter(pl.col("date") == pl.date(2025, 1, 9)).row(0, named=True)
        assert first["CPI"] == 0.2, "CPI 在自己的发布日就该有值"
        assert first["PMI"] is None, "PMI 还没发布,应当是空的"
        assert first["M2_yoy"] is None

    def test_monthly_indicator_holds_until_next_release(self, monkeypatch):
        """月度指标在发布日之后保持有效,直到下一次发布才换。"""
        import sys

        monkeypatch.setitem(sys.modules, "akshare", _FakeAk())
        df = MacroDataSource().fetch(start="2025-01-01", end="2025-02-28")
        pmi_by_date = {
            r["date"]: r["PMI"] for r in df.iter_rows(named=True)
        }
        assert pmi_by_date[pd.Timestamp("2025-01-10").date()] == 49.0
        assert pmi_by_date[pd.Timestamp("2025-01-13").date()] == 49.0, \
            "下一次发布之前应当沿用上一次的数"
        assert pmi_by_date[pd.Timestamp("2025-02-10").date()] == 50.5, \
            "2 月 10 日发布了新值,应当换过来"

    def test_one_indicator_down_does_not_fabricate_others(self, monkeypatch):
        """一个指标取不到,那一列空着,别的指标照常。"""
        import sys

        fake = _FakeAk()

        def boom():
            raise ConnectionError("reset by peer")

        fake.macro_china_cpi_monthly = boom
        monkeypatch.setitem(sys.modules, "akshare", fake)
        df = MacroDataSource().fetch(start="2025-01-01", end="2025-01-31")
        assert df["CPI"].null_count() == df.height, "取不到的指标应当整列为空"
        assert df["PMI"].null_count() < df.height, "别的指标不该受牵连"
        # 取不到的指标连它自己的发布日都不该出现在时间轴上
        assert df.filter(pl.col("date") == pl.date(2025, 1, 9)).height == 0

    def test_all_sources_down_gives_empty_table_with_schema(self, monkeypatch):
        """全部取不到时给一张空表,而不是编几行数字。"""
        import sys

        class DeadAk:
            def __getattr__(self, name):
                def boom():
                    raise ConnectionError("reset by peer")
                return boom

        monkeypatch.setitem(sys.modules, "akshare", DeadAk())
        df = MacroDataSource().fetch(start="2025-01-01", end="2025-01-31")
        assert df.height == 0
        assert set(df.columns) == set(MacroDataSource().get_schema())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
