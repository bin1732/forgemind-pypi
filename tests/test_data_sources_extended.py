# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import polars as pl
from datetime import datetime, timedelta


class TestTusharePro:
    def test_mock_data(self):
        from forgemind.core.data.sources import TushareProSource
        source = TushareProSource(token="")  # 无 token 走 mock
        df = source.fetch(
            symbols=["600519.SH", "000001.SZ"],
            start="2024-01-01", end="2024-06-30",
        )
        assert len(df) > 0
        assert "pe" in df.columns
        assert "pb" in df.columns
    
    def test_schema(self):
        from forgemind.core.data.sources import TushareProSource
        source = TushareProSource()
        schema = source.get_schema()
        assert "pe" in schema


class TestNewsDataSource:
    def test_mock_news(self):
        from forgemind.core.data.sources import NewsDataSource
        source = NewsDataSource()
        df = source.fetch(
            symbols=["600519.SH", "000001.SZ"],
            start="2024-01-01", end="2024-03-31",
        )
        assert len(df) > 0
        assert "sentiment_score" in df.columns
        assert "title" in df.columns
        # sentiment 应该 -1 到 1
        assert -1 <= df["sentiment_score"].min()
        assert df["sentiment_score"].max() <= 1


class TestMacroDataSource:
    def test_macro_data(self):
        from forgemind.core.data.sources import MacroDataSource
        source = MacroDataSource()
        df = source.fetch(start="2024-01-01", end="2024-12-31")
        assert len(df) > 0
        assert "PMI" in df.columns
        assert "CPI" in df.columns


class TestSectorDataSource:
    def test_sector_classification(self):
        from forgemind.core.data.sources import SectorDataSource
        source = SectorDataSource(classification="申万")
        df = source.fetch(symbols=["600519.SH", "000001.SZ", "000333.SZ"])
        assert len(df) == 3
        assert "sector" in df.columns


class TestRegistry:
    def test_default_registry(self):
        from forgemind.core.data.sources import get_default_registry
        registry = get_default_registry()
        
        sources = registry.list_sources()
        assert "tushare" in sources
        assert "news" in sources
        assert "macro" in sources
        assert "sector" in sources
        assert "fundamental" in sources
    
    def test_fetch_multi(self):
        from forgemind.core.data.sources import get_default_registry
        registry = get_default_registry()
        
        result = registry.fetch_multi(
            ["news", "sector"],
            symbols=["600519.SH"],
            start="2024-01-01",
            end="2024-03-31",
        )
        assert "news" in result or "sector" in result


class TestDataSourceBase:
    def test_data_source_abstract(self):
        from forgemind.core.data.sources import DataSource
        # 不能直接实例化抽象类
        with pytest.raises(TypeError):
            DataSource()


class TestFundamentalIntegration:
    def test_fundamental_with_sector(self):
        """基本面 + 行业 — 端到端集成"""
        from forgemind.core.data.sources import (
            FundamentalDataSource, SectorDataSource,
        )
        
        fundamental = FundamentalDataSource()
        sector_source = SectorDataSource()
        
        symbols = ["600519.SH", "000001.SZ"]
        
        df_fund = fundamental.fetch(symbols, start="2024-01-01", end="2024-06-30")
        df_sector = sector_source.fetch(symbols)
        
        assert len(df_fund) > 0
        assert len(df_sector) > 0
        # 可以 join
        # (df_fund.join(df_sector, on="symbol"))