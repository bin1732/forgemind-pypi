# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""README 声明"人工审批 gating",该行为必须真实生效:
- portfolio_manager_node 直接写 pm_decision,不等审批;
- API 没有 approve/reject 端点;
- 所有请求挤在 thread="default"。

现在跑两步: /decide prepare → /{thread_id}/approve 或 /reject。
只有 approved=True 才暴露 pm_decision 并落盘 portfolio snapshot。

只验"能 approve"是不够的 —— 必须验:
- 没 approve 时 pm_decision 是 None
- reject 也不会漏 pm_decision
- 假 thread_id 拿到 LookupError(不是悄悄拿到别人的决策)
- API 端点实际工作(每个 thread_id 独立)
- CLI 在未传 --yes 时拒绝自动批准
"""

import sys
from datetime import datetime

import pytest

# ===== 真实库内功能 =====

@pytest.mark.asyncio
async def test_prepare_returns_no_pm_decision():
    from forgemind.core.agents.portfolio_context import (
        PortfolioContext,
        run_decision,
    )
    pf = PortfolioContext(cash=80000.0, total_equity=200000.0)
    state = await run_decision("600519.SH", datetime.now(), pf)
    assert state.get("pm_decision") is None, (
        "prepare 阶段 PM 没跑;不应有 pm_decision")
    assert state["requires_human_review"] is True
    assert state["thread_id"].startswith("thread-")


@pytest.mark.asyncio
async def test_each_thread_is_isolated():
    """两个 prepare 不能相互串台 —— 不能用 thread='default'"""
    from forgemind.core.agents.portfolio_context import (
        PortfolioContext,
        run_decision,
    )
    pf = PortfolioContext(cash=80000.0, total_equity=200000.0)
    a = await run_decision("600519.SH", datetime.now(), pf)
    b = await run_decision("000001.SH", datetime.now(), pf)
    assert a["thread_id"] != b["thread_id"], (
        "两次 prepare 用了同一 thread —— 多用户会互踩")


@pytest.mark.asyncio
async def test_reject_does_not_leak_pm_decision():
    from forgemind.core.agents.portfolio_context import (
        PortfolioContext,
        resume_decision,
        run_decision,
    )
    pf = PortfolioContext(cash=80000.0, total_equity=200000.0)
    state = await run_decision("600519.SH", datetime.now(), pf)
    tid = state["thread_id"]
    final = await resume_decision(tid, approved=False, reviewer="t")
    assert final["pm_decision"] is None, "拒绝后不应漏 pm_decision"
    assert final["approved"] is False


@pytest.mark.asyncio
async def test_approve_fills_pm_decision():
    from forgemind.core.agents.portfolio_context import (
        PortfolioContext,
        resume_decision,
        run_decision,
    )
    pf = PortfolioContext(cash=80000.0, total_equity=200000.0)
    state = await run_decision("600519.SH", datetime.now(), pf)
    tid = state["thread_id"]
    final = await resume_decision(tid, approved=True, reviewer="t", notes="y")
    assert final["pm_decision"] is not None
    assert final["pm_decision"].get("direction") in ("buy", "sell", "hold")
    assert final["approved_by"] == "t"
    assert final["approval_notes"] == "y"


@pytest.mark.asyncio
async def test_fake_thread_id_raises_lookup_error():
    """伪造或已用过的 thread_id 必须 404 语义,不是悄悄返回别人决策"""
    from forgemind.core.agents.portfolio_context import resume_decision
    with pytest.raises(LookupError):
        await resume_decision("thread-does-not-exist-12345", approved=True)


# ===== API 端点 =====

def test_api_decide_returns_thread_id():
    """POST /decide 返回 thread_id + status=PENDING,无 pm_decision"""
    from fastapi.testclient import TestClient

    from forgemind.api.main import app

    client = TestClient(app)
    r = client.post("/api/v1/agent/decide", json={
        "symbol": "600519.SH", "cash": 80000.0,
        "total_equity": 200000.0, "positions": [],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "PENDING_HUMAN_REVIEW"
    assert body["thread_id"].startswith("thread-")
    assert "pm_decision" not in body  # 准备阶段不应漏


def test_api_approve_unknown_thread_returns_404():
    """伪造 thread_id 调 approve 必须 404,不能默默给一个假决策"""
    from fastapi.testclient import TestClient

    from forgemind.api.main import app

    client = TestClient(app)
    r = client.post("/api/v1/agent/thread-no-such-thing/approve",
                    json={"reviewer": "test", "notes": ""})
    assert r.status_code == 404, r.text


def test_api_reject_unknown_thread_returns_404():
    from fastapi.testclient import TestClient

    from forgemind.api.main import app

    client = TestClient(app)
    r = client.post("/api/v1/agent/thread-no-such-thing/reject",
                    json={"reviewer": "test", "notes": ""})
    assert r.status_code == 404


def test_api_full_two_step_flow():
    """完整两步:/decide → /approve 真让 PM 跑"""
    from fastapi.testclient import TestClient

    from forgemind.api.main import app

    client = TestClient(app)
    r1 = client.post("/api/v1/agent/decide", json={
        "symbol": "600519.SH", "cash": 80000.0,
        "total_equity": 200000.0, "positions": [],
    })
    assert r1.status_code == 200
    tid = r1.json()["thread_id"]

    r2 = client.post(f"/api/v1/agent/{tid}/approve",
                      json={"reviewer": "alice", "notes": "looks good"})
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["approved"] is True
    assert body["pm_decision"] is not None
    assert body["pm_decision"].get("direction") in ("buy", "sell", "hold")


# ===== CLI 行为 =====

def test_cli_agent_noninteractive_without_yes_rejects(monkeypatch, capsys):
    """非交互模式没传 --yes,默认拒绝自动批准(不悄悄 approve)"""
    monkeypatch.setattr(sys, "stdin", sys.stdin)  # 真实 stdin
    monkeypatch.delenv("FORGEMIND_NONINTERACTIVE", raising=False)
    # 模拟非 TTY
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    from forgemind.cli import build_parser

    p = build_parser()
    args = p.parse_args(["agent", "--symbol", "600519.SH"])
    # monkeypatch 已经把 isatty 改 False;argparse Namespace 必须含 yes=False
    args.yes = False

    # 准备阶段也会失败(没数据),所以这一路只测 FORGEMIND_NONINTERACTIVE 短路
    # 不直接调 cmd_agent,改测 input 的非交互路径
    monkeypatch.setenv("FORGEMIND_NONINTERACTIVE", "1")
    from forgemind.cli import cmd_agent

    # 没有真实数据,prepare 会抛;但我们要测的是"非交互 + 非 yes → 早返回"
    # 用 patch 让 prepare 直接返一个假 state
    fake_state = {
        "thread_id": "thread-test", "pm_decision": None,
        "requires_human_review": True, "confidence": 0.5,
        "bull_case": {"thesis": "fake bull"}, "bear_case": {"thesis": "fake bear"},
    }
    async def fake_run(*a, **kw):
        return fake_state
    monkeypatch.setattr("forgemind.core.agents.portfolio_context.run_decision",
                        fake_run)
    rc = cmd_agent(args)
    assert rc == 2, f"非交互未传 --yes 应返回 2(拒绝自动审批),实际 {rc}"
    out = capsys.readouterr().out
    assert "拒绝自动审批" in out


def test_cli_agent_old_default_yes_is_gone(monkeypatch):
    """防御性回归:旧实现是 prepare 完直接跑(不真审批)"""
    # cmd_agent 必须先询问再落 pm_decision 或 snapshot。
    # 现在加了真 y/N prompt,不应再默认 yes。
    import inspect

    from forgemind.cli import cmd_agent
    src = inspect.getsource(cmd_agent)
    assert "Approve this decision?" in src, (
        "cmd_agent 必须真有 y/N 提示,旧实现会直接落 pm_decision")
    # 用 getattr 是为了防止 yaml --default 漏掉,这里只要"读 yes 选项"就算
    assert "yes" in src and ("args.yes" in src or "getattr(args, \"yes\"" in src), (
        "cmd_agent 必须读 --yes 选项,旧实现不读")
    assert "approved=False" in src, "拒绝路径必须真调 resume_decision(approved=False)"
