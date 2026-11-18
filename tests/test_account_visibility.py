# Copyright (c) 2026 灵感引擎工坊 (bin1732) | SPDX-License-Identifier: Apache-2.0
"""账户状态要看得见,取账户的路要通。

决策的仓位按账户状态算,而账户状态平时是看不见的中间量。三件事要成立:

- 决策的报告里带着"依据的是哪份账户" —— 不然读的人只能信结论。
- 账户状态有一个可信的取法(接口里的 /api/v1/portfolio),而不是让调用
  方自己编一个。
- 审批的默认是不批 —— 人工审批是闸门,默认放行等于没有闸门。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from forgemind.api.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("FORGEMIND_DATA_DIR", str(data_dir))
    monkeypatch.setenv("FORGEMIND_DUCKDB_PATH", str(data_dir / "duckdb" / "main.db"))
    from forgemind.core.config.settings import get_settings

    get_settings.cache_clear()
    yield data_dir
    get_settings.cache_clear()


class TestPortfolioEndpoint:
    def test_empty_store_says_so_with_a_next_step(self, client, isolated_store):
        """没有组合就说没有,并给出下一步 —— 不编一个账户出来。"""
        r = client.get("/api/v1/portfolio")
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["status"] == "empty", body
        assert body["cash"] is None, body
        assert body["positions"] == [], body
        assert body["message"], body

    def test_stored_snapshot_is_returned(self, client, isolated_store):
        from forgemind.core.agents.portfolio_context import (
            PortfolioContext,
            PortfolioPosition,
        )
        from forgemind.core.data.storage import save_portfolio_snapshot

        save_portfolio_snapshot(
            PortfolioContext(
                cash=43210.5,
                positions=[PortfolioPosition(symbol="600519", quantity=20, avg_price=1500.0)],
            )
        )
        r = client.get("/api/v1/portfolio")
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["status"] == "ok", body
        assert body["cash"] == 43210.5, body
        assert body["total_equity"] > 0, body
        assert len(body["positions"]) == 1, body
        assert body["positions"][0]["symbol"] == "600519", body


class TestDecisionReportsItsAccount:
    def test_mcp_decision_reports_the_account(self, isolated_store):
        """MCP 的决策结果里要带着账户。"""
        import asyncio

        from _local_client import local_headers  # noqa: F401
        from forgemind.mcp.server import ForgeMindMCPServer

        srv = ForgeMindMCPServer()
        resp = asyncio.run(
            srv.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "agent_decide",
                        "arguments": {"symbol": "600519.SH", "cash": 12345.0},
                    },
                }
            )
        )
        result = resp.get("result", {})
        text = result.get("content", [{}])[0].get("text", "")
        assert text, resp
        import json

        payload = json.loads(text)
        # 决策失败也要说清账户(它拿到的就是这份账户)
        if payload.get("status") == "PENDING_HUMAN_REVIEW":
            used = payload["portfolio_used"]
            assert used["cash"] == 12345.0, used
            assert used["source"] == "arguments", used

    def test_account_context_describes_itself(self):
        from forgemind.core.agents.portfolio_context import (
            PortfolioContext,
            PortfolioPosition,
        )

        ctx = PortfolioContext(
            cash=1000.0,
            positions=[PortfolioPosition(symbol="600519", quantity=2, avg_price=500.0)],
        )
        described = ctx.describe()
        assert described["cash"] == 1000.0, described
        assert described["total_equity"] == 2000.0, described
        assert described["positions"][0]["quantity"] == 2, described


class TestApprovalDefaultsToNo:
    def test_mcp_approve_defaults_to_not_approving(self):
        """不传 approved 就不批 —— 闸门的默认是关着的那一边。"""
        import asyncio

        from forgemind.mcp.server import ForgeMindMCPServer

        srv = ForgeMindMCPServer()
        resp = asyncio.run(
            srv.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {},
                }
            )
        )
        schema = next(t for t in resp["result"]["tools"] if t["name"] == "agent_approve")[
            "inputSchema"
        ]
        assert schema["properties"]["approved"].get("default") is False, schema

    def test_cli_rejects_approval_without_an_account(self, isolated_store):
        """命令行在账户缺失时退出,不会拿编出来的账户去审批。"""
        import subprocess
        import sys

        from _path_setup import child_env

        env = child_env(
            FORGEMIND_DATA_DIR=str(isolated_store),
            FORGEMIND_DUCKDB_PATH=str(isolated_store / "duckdb" / "main.db"),
            FORGEMIND_NONINTERACTIVE="1",
        )
        proc = subprocess.run(
            [sys.executable, "-m", "forgemind.cli", "agent", "--symbol", "600519.SH"],
            capture_output=True,
            text=True,
            env=env,
            timeout=180,
        )
        assert proc.returncode == 2, proc.stdout[-300:] + proc.stderr[-300:]


class TestMissingCashExplainsWhereToGetIt:
    def test_the_error_says_where_to_get_the_account(self, client, isolated_store):
        """缺现金时,校验错误要带取法 —— 只丢一个字段名等于把人堵在门口。"""
        r = client.post("/api/v1/agent/decide", json={"symbol": "600519.SH"})
        assert r.status_code == 422, r.text[:300]
        text = r.text
        assert "cash" in text, text
        assert "/api/v1/portfolio" in text, text

    def test_with_cash_it_passes_validation(self, client, isolated_store):
        r = client.post(
            "/api/v1/agent/decide",
            json={"symbol": "600519.SH", "cash": 5000.0},
        )
        # 有现金就不会因为现金被拒(后面失败是别的原因)
        assert r.status_code != 422 or "cash" not in r.text, r.text[:300]
