# Copyright (c) 2026 灵感引擎工坊 (bin1732) | SPDX-License-Identifier: Apache-2.0
"""决策报告要带上"依据的行情截止到哪天"。

决策的 as_of 是"现在",但依据的行情是库里最后一根 K 线 —— 可能是几周前
的收盘价。用户看到"上穿 MA20"却不知道那是上个月的形态,于是把一个
陈旧的结论当今天的依据。

措辞与 `forgemind pick` 用的是同一套(data_freshness),一处说"依据的
行情最新日期"、另一处只给个数字,读的人得自己对两套说法。

这些用例盯住:技术面带日期、决策带日期、没有行情时说"未知"而不是编
一个日期。
"""

from __future__ import annotations

import pytest


@pytest.fixture
def store_with_klines(tmp_path, monkeypatch):
    """一个自己的库,里面躺着 40 根日线。"""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("FORGEMIND_DATA_DIR", str(data_dir))
    monkeypatch.setenv("FORGEMIND_DUCKDB_PATH", str(data_dir / "duckdb" / "main.db"))
    from forgemind.core.config.settings import get_settings

    get_settings.cache_clear()

    from forgemind.core.data.storage import DuckDBStorage, init_duckdb

    init_duckdb()
    with DuckDBStorage() as db:
        rows = []
        for i in range(40):
            day = f"2024-01-{i + 1:02d}" if i < 31 else f"2024-02-{i - 30:02d}"
            rows.append(f"('{day}','600519',100.0,101.0,99.0,{100.0 + i:.1f},1000,'x')")
        db.execute("INSERT INTO kline_daily VALUES " + ",".join(rows))
    yield data_dir
    get_settings.cache_clear()


class TestTechnicalAnalysisCarriesTheDate:
    def test_technical_analysis_has_last_date(self, store_with_klines):
        from forgemind.core.agents.portfolio_context import technical_node

        out = technical_node({"symbol": "600519"})
        tech = out["technical_analysis"]
        assert tech["status"] == "ok", tech
        assert tech.get("last_date"), tech
        assert str(tech["last_date"]).startswith("2024-02"), tech

    def test_no_klines_means_no_date(self, tmp_path, monkeypatch):
        """没有行情就没有日期 —— 不许拿今天凑一个。"""
        data_dir = tmp_path / "data"
        monkeypatch.setenv("FORGEMIND_DATA_DIR", str(data_dir))
        monkeypatch.setenv("FORGEMIND_DUCKDB_PATH", str(data_dir / "duckdb" / "main.db"))
        from forgemind.core.config.settings import get_settings

        get_settings.cache_clear()
        from forgemind.core.agents.portfolio_context import technical_node

        out = technical_node({"symbol": "600519"})
        tech = out["technical_analysis"]
        assert tech["status"] == "unavailable", tech
        assert not tech.get("last_date"), tech
        get_settings.cache_clear()


class TestDecisionReportsTheBasis:
    def test_pm_decision_carries_data_as_of(self, store_with_klines):
        from forgemind.core.agents.portfolio_context import portfolio_manager_node

        state = {
            "symbol": "600519",
            "portfolio": {"total_equity": 200_000.0, "positions": []},
            "technical_analysis": {"status": "ok", "last_close": 120.0, "last_date": "2024-02-09"},
            "fundamentals_analysis": {"confidence": 0.5},
            "news_analysis": {"confidence": 0.5},
            "bull_case": {"target_weight": 0.1, "thesis": "看涨"},
            "bear_case": {"max_weight": 0.05, "thesis": "看跌"},
        }
        pm = portfolio_manager_node(state)["pm_decision"]
        assert pm["data_as_of"]["last_date"] == "2024-02-09", pm
        assert "2024-02-09" in pm["data_as_of"]["freshness"], pm

    def test_freshness_of_an_unknown_date_says_unknown(self):
        """没有日期就说未知 —— 不猜一个。"""
        from forgemind.core.data.storage import data_freshness

        assert "未知" in data_freshness(None)
        assert "未知" in data_freshness("")

    def test_api_helper_reports_the_basis(self):
        from forgemind.api.main import _data_as_of

        out = _data_as_of({"technical_analysis": {"last_date": "2024-02-09"}})
        assert out["last_date"] == "2024-02-09", out
        assert "2024-02-09" in out["freshness"], out
