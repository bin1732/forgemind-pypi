# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""API 的人工审批必须真的落到 DuckDB。

当初的岔子:落 portfolio snapshot 与 6 条决策明细的那段代码只写在 CLI
里,API 的 /approve 走的是共用的 resume_decision,但那段落库逻辑不在共用
层 —— 于是批完了决策,组合却一动不动。

桌面端的"组合概览"与"多 Agent 决策"面板读的就是这两张表(经
query_portfolio)。落库没做,面板上看到的就是上一次的组合:界面看起来
正常,数据却是旧的。

现在落库在共用层(resume_decision 内部),CLI 与 API 走同一条路。

    python -m pytest tests/test_api_approve_persists.py -v
"""

from __future__ import annotations

import asyncio

import pytest

from forgemind.api.main import AgentRequest, agent_approve, agent_decide
from forgemind.core.data.storage import load_latest_decisions, load_latest_portfolio


class TestApiApprovePersists:
    def test_approve_writes_snapshot_and_six_decisions(self):
        request = AgentRequest(
            symbol="600519.SH",
            cash=100_000.0,
            total_equity=200_000.0,
            positions=[{"symbol": "600519.SH", "quantity": 100, "avg_price": 1500.0}],
        )
        prepared = asyncio.run(agent_decide(request))
        assert prepared.thread_id
        assert prepared.requires_human_review

        approved = asyncio.run(
            agent_approve(prepared.thread_id, _approval_request())
        )
        assert approved.approved
        # 落库结果随响应回来 —— 桌面端据此显示"已落盘"还是"落盘失败"
        assert approved.persisted is not None
        assert approved.persisted.get("error") is None, approved.persisted
        assert approved.persisted.get("snapshot_id")
        assert approved.persisted.get("decisions_written") == 6

        # 真的落进 DuckDB 了
        snapshot = load_latest_portfolio()
        assert snapshot is not None
        assert snapshot["snapshot_id"] == approved.persisted["snapshot_id"]
        assert snapshot["cash"] == 100_000.0

        decisions = load_latest_decisions()
        assert len(decisions) == 6
        assert {d["agent"] for d in decisions} == {
            "Fundamentals",
            "Technical",
            "News",
            "Bull",
            "Bear",
            "PM",
        }

    def test_pm_decision_carries_the_price_it_used(self):
        """下单量按真股价算,决策里带着用的股价"""
        request = AgentRequest(
            symbol="600519.SH",
            cash=100_000.0,
            total_equity=200_000.0,
            positions=[{"symbol": "600519.SH", "quantity": 100, "avg_price": 1500.0}],
        )
        prepared = asyncio.run(agent_decide(request))
        approved = asyncio.run(
            agent_approve(prepared.thread_id, _approval_request())
        )
        decision = approved.pm_decision or {}
        assert "price" in decision
        price = decision["price"]
        if price > 0:
            # 股数 = |目标金额 - 当前市值| / 股价
            delta_value = abs(decision["delta_weight"]) * 200_000.0
            assert decision["quantity"] == int(delta_value / price)
        else:
            assert decision["quantity"] == 0


def _approval_request():
    from forgemind.api.main import AgentApprovalRequest

    return AgentApprovalRequest(reviewer="test", notes="pytest")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
