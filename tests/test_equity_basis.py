# Copyright (c) 2026 灵感引擎工坊 (bin1732) | SPDX-License-Identifier: Apache-2.0
"""总权益只能有一个口径。

权益有两个算法:现金加持仓**成本**(账面)与现金加持仓**市值**(实际)。
界面按市值算,决策原先按成本算 —— 持仓一有浮盈浮亏,同一个"总权益"
在两处就是两个数,AI 算出的仓位与用户看到的对不上,差的是整段浮盈浮亏。

平仓时两者相等,所以这个洞在测试里看不见 —— 它只在浮盈浮亏时发作。

这些用例盯住:权益按市值算、缺现价时整体退回成本口径(不混合)、以及
报告里标明用的是哪个口径。
"""

from __future__ import annotations

import pytest

from forgemind.core.agents.portfolio_context import (
    PortfolioPosition,
    account_with_market_values,
)


class TestEquityBasis:
    def test_market_value_is_used_when_prices_are_known(self):
        """有现价:权益按市值算 —— 与界面上那个数一致。"""
        ctx = account_with_market_values(
            cash=100_000.0,
            positions=[PortfolioPosition(symbol="600519", quantity=100, avg_price=1500.0)],
            prices={"600519": 1000.0},
        )
        # 10 万现金 + 100 股 × 现价 1000 = 20 万,不是成本口径的 25 万
        assert ctx.total_equity == 200_000.0, ctx.total_equity
        assert ctx.equity_basis == "market", ctx.equity_basis

    def test_unrealized_pnl_is_computed(self):
        ctx = account_with_market_values(
            cash=0.0,
            positions=[PortfolioPosition(symbol="600519", quantity=100, avg_price=1500.0)],
            prices={"600519": 1000.0},
        )
        assert ctx.positions[0].unrealized_pnl == -50_000.0, ctx.positions[0]

    def test_missing_price_falls_back_to_cost_basis(self):
        """库里没这个标的的行情:整体留在成本口径,并标明。"""
        ctx = account_with_market_values(
            cash=100_000.0,
            positions=[PortfolioPosition(symbol="600519", quantity=100, avg_price=1500.0)],
            prices={},
        )
        assert ctx.total_equity == 250_000.0, ctx.total_equity
        assert ctx.equity_basis == "cost", ctx.equity_basis

    def test_one_missing_price_means_no_mixing(self):
        """一半市值、一半成本的混合口径比纯成本更难解释 —— 不混。"""
        ctx = account_with_market_values(
            cash=0.0,
            positions=[
                PortfolioPosition(symbol="600519", quantity=100, avg_price=1500.0),
                PortfolioPosition(symbol="000001", quantity=1000, avg_price=10.0),
            ],
            prices={"600519": 1000.0},
        )
        assert ctx.equity_basis == "cost", ctx.equity_basis
        assert ctx.total_equity == 160_000.0, ctx.total_equity

    def test_declared_equity_wins_and_is_marked(self):
        """调用方自己声明的权益:用它,但标明是声明值。"""
        ctx = account_with_market_values(
            cash=100_000.0,
            positions=[PortfolioPosition(symbol="600519", quantity=100, avg_price=1500.0)],
            prices={"600519": 1000.0},
            declared_equity=777_000.0,
        )
        assert ctx.total_equity == 777_000.0, ctx.total_equity
        assert ctx.equity_basis == "declared", ctx.equity_basis

    def test_no_positions_is_market_basis(self):
        """没有持仓:权益就是现金,市值口径与成本口径同值。"""
        ctx = account_with_market_values(cash=100_000.0, positions=[], prices={})
        assert ctx.total_equity == 100_000.0, ctx.total_equity
        assert ctx.equity_basis == "market", ctx.equity_basis

    def test_report_carries_the_basis(self):
        """报告里要标明口径 —— 不标明就核不了。"""
        ctx = account_with_market_values(
            cash=100_000.0,
            positions=[PortfolioPosition(symbol="600519", quantity=100, avg_price=1500.0)],
            prices={"600519": 1000.0},
        )
        assert ctx.describe()["equity_basis"] == "market", ctx.describe()


class TestLoadLatestClose:
    @pytest.fixture
    def store(self, tmp_path, monkeypatch):
        data_dir = tmp_path / "data"
        monkeypatch.setenv("FORGEMIND_DATA_DIR", str(data_dir))
        monkeypatch.setenv("FORGEMIND_DUCKDB_PATH", str(data_dir / "duckdb" / "main.db"))
        from forgemind.core.config.settings import get_settings

        get_settings.cache_clear()
        yield data_dir
        get_settings.cache_clear()

    def test_latest_close_per_symbol(self, store):
        from forgemind.core.data.storage import (
            DuckDBStorage,
            init_duckdb,
            load_latest_close,
        )

        init_duckdb()
        with DuckDBStorage() as db:
            db.execute(
                "INSERT INTO kline_daily VALUES "
                "('2024-01-02','600519',1,1,1,1500.0,1,'x'),"
                "('2024-01-03','600519',1,1,1,1600.0,1,'x'),"
                "('2024-01-02','000001',1,1,1,10.0,1,'x')"
            )
        prices = load_latest_close(["600519.SH", "000001", "999999"])
        # 键是传进来的原样,查询时内部才归一化
        assert prices["600519.SH"] == 1600.0, prices
        assert prices["000001"] == 10.0, prices
        # 没拉过行情的标的:不给,不用别处的数冒充
        assert "999999" not in prices, prices

    def test_empty_input(self, store):
        from forgemind.core.data.storage import load_latest_close

        assert load_latest_close([]) == {}
        assert load_latest_close(["   "]) == {}


class TestReadBackIsMarkedToMarket:
    """读出来的账户也要是市值口径 —— 接口与界面给的得是同一个数。"""

    @pytest.fixture
    def store(self, tmp_path, monkeypatch):
        data_dir = tmp_path / "data"
        monkeypatch.setenv("FORGEMIND_DATA_DIR", str(data_dir))
        monkeypatch.setenv("FORGEMIND_DUCKDB_PATH", str(data_dir / "duckdb" / "main.db"))
        from forgemind.core.config.settings import get_settings

        get_settings.cache_clear()
        yield data_dir
        get_settings.cache_clear()

    def _store_snapshot_and_prices(self):
        from forgemind.core.agents.portfolio_context import (
            PortfolioContext,
            PortfolioPosition,
        )
        from forgemind.core.data.storage import (
            DuckDBStorage,
            init_duckdb,
            save_portfolio_snapshot,
        )

        init_duckdb()
        with DuckDBStorage() as db:
            db.execute("INSERT INTO kline_daily VALUES ('2024-01-03','600519',1,1,1,1000.0,1,'x')")
        # 快照是成本口径落的那一份(成本 1500,现价 1000)
        save_portfolio_snapshot(
            PortfolioContext(
                cash=100_000.0,
                positions=[PortfolioPosition(symbol="600519", quantity=100, avg_price=1500.0)],
            )
        )

    def test_api_returns_the_market_value_equity(self, store):
        from fastapi.testclient import TestClient

        from forgemind.api.main import app

        self._store_snapshot_and_prices()
        with TestClient(app) as c:
            r = c.get("/api/v1/portfolio")
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        # 10 万现金 + 100 股 × 现价 1000 = 20 万,不是落盘那一刻的成本口径
        assert body["total_equity"] == 200_000.0, body
        assert body["equity_basis"] == "market", body
        assert body["positions"][0]["unrealized_pnl"] == -50_000.0, body

    def test_snapshot_revaluation_keeps_the_other_fields(self, store):
        from forgemind.core.agents.portfolio_context import (
            portfolio_snapshot_marked_to_market,
        )
        from forgemind.core.data.storage import load_latest_portfolio

        self._store_snapshot_and_prices()
        snapshot = load_latest_portfolio()
        revalued = portfolio_snapshot_marked_to_market(snapshot)
        assert revalued["total_equity"] == 200_000.0, revalued
        assert revalued["snapshot_id"] == snapshot["snapshot_id"], revalued
        assert revalued["currency"] == snapshot["currency"], revalued
