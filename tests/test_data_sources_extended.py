# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0


import pytest


class TestTusharePro:
    def test_refuses_without_token_instead_of_fabricating_pe(self):
        """无 token 时必须拒绝,不能拿 np.random 造 PE/PB

        原实现返回 5-50 之间随机的 PE —— 字段齐全、数值合理,
        与真实的茅台 PE(约 20-25)难以区分,却完全是编的。
        """
        from forgemind.core.data.sources import TushareProSource
        from forgemind.core.data.sources.extended_sources import (
            DataSourceUnavailableError,
        )

        source = TushareProSource(token="")
        ok, why = source.is_available()
        assert not ok
        assert "TUSHARE_TOKEN" in why
        with pytest.raises(DataSourceUnavailableError):
            source.fetch(symbols=["600519.SH"], start="2024-01-01", end="2024-06-30")

    def test_schema(self):
        from forgemind.core.data.sources import TushareProSource
        source = TushareProSource()
        schema = source.get_schema()
        assert "pe" in schema


class TestNewsDataSource:
    def test_refuses_instead_of_fabricating_headlines(self):
        """原实现凭空造 '600519.SH 出现新闻标题 847' 和 example.com 链接"""
        from forgemind.core.data.sources import NewsDataSource
        from forgemind.core.data.sources.extended_sources import (
            DataSourceUnavailableError,
        )

        source = NewsDataSource()
        ok, why = source.is_available()
        assert not ok
        with pytest.raises(DataSourceUnavailableError):
            source.fetch(symbols=["600519.SH"], start="2024-01-01", end="2024-03-31")


class TestMacroDataSource:
    def test_is_backed_by_real_sources(self):
        """宏观源已经接到公开接口上,不再是占位。

        早期这里每次调用都给出不同的 PMI/CPI/PPI/十年期国债收益率 ——
        字段齐全、数值合理,却完全是编的。现在取的是接口给的真实值,
        取不到时给空表;这两条由 tests/test_macro_data_source.py 守着。
        """
        from forgemind.core.data.sources import MacroDataSource

        # akshare 在 [cn] extra 里,常规流水线没装 —— 那种环境下这条
        # 跳过,真实取数由 verify-live 的实时探针负责。
        pytest.importorskip("akshare")
        source = MacroDataSource()
        ok, why = source.is_available()
        assert ok, why


class TestSectorDataSource:
    def test_refuses_instead_of_fabricating_sector(self):
        """原实现用 np.random.choice 从 8 个行业里抽 —— 银行会被标成医药

        行业分类是行业中性化 IC 的分组依据,分错组会让中性化完全失效。
        """
        from forgemind.core.data.sources import SectorDataSource
        from forgemind.core.data.sources.extended_sources import (
            DataSourceUnavailableError,
        )

        source = SectorDataSource(classification="申万")
        assert not source.is_available()[0]
        with pytest.raises(DataSourceUnavailableError):
            source.fetch(symbols=["600519.SH", "000333.SZ"])


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

    def test_fetch_multi_excludes_failing_sources(self):
        """契约是"失败的单源不阻塞其他,失败的**不在结果里**"

        不可用的源以前会返回编造数据,于是它们悄悄出现在结果中,
        与真实拉到的数据混在一起且无法区分。现在它们必须缺席。
        """
        from forgemind.core.data.sources import get_default_registry
        registry = get_default_registry()

        result = registry.fetch_multi(
            ["news", "sector"],
            symbols=["600519.SH"],
            start="2024-01-01",
            end="2024-03-31",
        )
        for name in ("news", "sector"):
            assert result.get(name) is None, (
                f"{name} 未实现真实数据源,fetch_multi 不该把它算作成功")
        assert isinstance(result, dict)


class TestDataSourceBase:
    def test_data_source_abstract(self):
        from forgemind.core.data.sources import DataSource
        # 不能直接实例化抽象类
        with pytest.raises(TypeError):
            DataSource()


class TestFundamentalIntegration:
    def test_fundamental_and_sector_both_refuse(self):
        """基本面与行业都依赖未接入的数据源,都必须拒绝而不是编造

        端到端串联时最危险:行业分类错组会让行业中性化 IC 失效,
        而用户看到的是一份完整的、字段齐全的表。
        """
        from forgemind.core.data.sources import (
            FundamentalDataSource,
            SectorDataSource,
        )
        from forgemind.core.data.sources.extended_sources import (
            DataSourceUnavailableError,
        )

        with pytest.raises(DataSourceUnavailableError):
            FundamentalDataSource().fetch(
                ["600519.SH", "000001.SZ"], start="2024-01-01", end="2024-06-30")
        with pytest.raises(DataSourceUnavailableError):
            SectorDataSource().fetch(["600519.SH", "000001.SZ"])
