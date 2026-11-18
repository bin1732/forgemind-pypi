# Copyright (c) 2026 灵感引擎工坊 (bin1732) | SPDX-License-Identifier: Apache-2.0
"""决策不许拿编出来的账户当依据。

决策的仓位、权重、股数全按账户状态算。账户状态若由一个固定的默认值
代替(十万现金),AI 拿它做完决策,界面看上去一切正常,依据却是假的 ——
用户看到的是"AI 建议",看不到的是它其实在跟一个不存在的账户对话。

所以:**账户状态必须由调用方给,或者由真实持仓算出来,不能有默认值。**
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from forgemind.api.main import AgentRequest, app
from forgemind.core.agents.portfolio_context import PortfolioContext, PortfolioPosition


def _server():
    from _path_setup import prefer_source_tree

    prefer_source_tree()
    from forgemind.mcp.server import ForgeMindMCPServer

    return ForgeMindMCPServer()


async def _call(srv, name, args):
    return await srv.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        }
    )


class TestNoInventedAccount:
    def test_portfolio_context_computes_equity_when_not_given(self):
        """没给权益就按现金加持仓成本算,而不是拿一个默认数。"""
        ctx = PortfolioContext(
            cash=100_000.0,
            positions=[PortfolioPosition(symbol="600519", quantity=100, avg_price=1500.0)],
        )
        assert ctx.total_equity == 250_000.0, ctx.total_equity

    def test_given_equity_is_kept(self):
        ctx = PortfolioContext(cash=100_000.0, total_equity=987_654.0)
        assert ctx.total_equity == 987_654.0, ctx.total_equity

    def test_api_requires_cash(self):
        """接口不替用户填现金。"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as ei:
            AgentRequest(symbol="600519")  # type: ignore[call-arg]
        assert "cash" in str(ei.value), ei.value

    def test_mcp_refuses_a_decision_without_cash(self):
        """MCP 不给现金默认值;缺了就明确说去哪儿取真实状态。"""
        srv = _server()
        resp = asyncio.run(_call(srv, "agent_decide", {"symbol": "600519"}))
        result = resp.get("result", {})
        assert result.get("isError"), resp
        text = result["content"][0]["text"]
        assert "cash" in text, text
        # 不只说"不行",还要说去哪儿取真实账户状态
        assert "query_portfolio" in text, text

    def test_mcp_schema_does_not_invent_cash(self):
        """协议声明里也不能有固定的现金。"""
        srv = _server()
        resp = asyncio.run(
            srv.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                }
            )
        )
        tools = resp["result"]["tools"]
        schema = next(t for t in tools if t["name"] == "agent_decide")["inputSchema"]
        props = schema.get("properties", {})
        # 现金不给默认值:给了就是替用户编一个账户。
        assert "default" not in props.get("cash", {}), props.get("cash")
        # 权益的默认值只能是 0 —— 0 的意思是"没给,自己算"。
        # 给个具体数字(比如十万)同样是编账户。
        assert props.get("total_equity", {}).get("default") == 0, props.get("total_equity")

    def test_api_endpoint_reports_the_missing_cash(self):
        """缺现金时接口得说清楚缺的是什么。"""
        with TestClient(app) as c:
            r = c.post("/api/v1/agent/decide", json={"symbol": "600519"})
        assert r.status_code == 422, r.text[:300]
        body = r.json()
        assert "cash" in r.text, r.text
        assert body.get("detail"), body
