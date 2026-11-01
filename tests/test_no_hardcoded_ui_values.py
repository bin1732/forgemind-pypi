# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真实桌面的两个面板(portfolio-panel / agent-decision-panel)原本塞了一堆
硬编码的"假"数字:Sharpe 1.42 / Sortino 1.87 / Max DD -8.3% / 胜率 58.5%,
还有 6 条 AGENT_VOTES(PE 28 < 行业 35、RSI 67 接近超买)。

这些都是从 demo 草稿抄来的,跟任何标的的回测 / agent 决策都没关系。
本测试扫描两个组件源码,确保:
  - 不再有 Sharpe / Sortino / Max DD / 胜率 的字面常量
  - 不再有 AGENT_VOTES 数组
  - 风险指标 / 6 Agent 投票都通过 useAppStore 拿

回归目的:防止硬编码数据再次出现。
"""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PANEL_DIR = REPO / "forgemind-ui" / "components"

# 硬编码反例 — 文档/注释里出现不算,只查 JSX/逻辑代码
HARDCODED_METRICS = [
    ("Sharpe", "1.42"),    # 之前的 Sharpe 硬编码
    ("Sortino", "1.87"),   # 之前的 Sortino 硬编码
    ("Max DD", "-8.3"),    # 之前的 Max DD 硬编码
    ("胜率", "58.5"),      # 之前的胜率硬编码
]


def test_portfolio_panel_no_hardcoded_risk_metrics():
    src = (PANEL_DIR / "portfolio-panel.tsx").read_text(encoding="utf-8")
    for label, hardcoded in HARDCODED_METRICS:
        # 只查 label 紧跟 hardcoded 数字的模式,即冒号后接硬编码值的 JSX
        # 注释里允许出现(说"之前这里是 1.42")所以用更严的 regex
        import re
        # 找 : "1.42" 这样的字面量(注释通常不带冒号引号)
        for pattern in (
            rf">{label}.*?{re.escape(hardcoded)}<",  # >Sharpe\n<span...>1.42<
            rf"{re.escape(hardcoded)}\b.*?{label}",   # 1.42 在前 + label
        ):
            assert not re.search(pattern, src, re.DOTALL), (
                f"portfolio-panel.tsx 仍含硬编码风险指标 {label}={hardcoded};"
                " 改用 useAppStore().riskMetrics 派生"
            )


def test_agent_decision_panel_no_hardcoded_votes():
    src = (PANEL_DIR / "agent-decision-panel.tsx").read_text(encoding="utf-8")
    # AGENT_VOTES const 数组不能再出现(那段硬编码 PE 28 / RSI 67 等)
    assert "AGENT_VOTES" not in src, (
        "agent-decision-panel.tsx 仍含 AGENT_VOTES 硬编码;"
        " 改用 useAppStore().agentDecisions 派生"
    )
    # 之前 6 条 PE / RSI / 机构调研 等 demo 文案不能再出现
    bad_theses = [
        "PE 28 < 行业 35",
        "RSI 67 接近超买",
        "机构调研 12 次",
        "白酒龙头溢价合理",
    ]
    for bad in bad_theses:
        assert bad not in src, (
            f"agent-decision-panel.tsx 仍含 demo 硬编码论据 \"{bad}\";"
            " 改从 forgemind agent 落盘的 portfolio_decision 表派生"
        )


def test_query_portfolio_returns_decisions_and_risk_metrics():
    """query_portfolio MCP 工具必须返回 decisions + risk_metrics 字段

    之前只返回 positions / cash / total_equity。桌面 6 Agent + 风险指标面板
    是从这两个新字段拿的。回归这两个字段不能从契约里消失。
    """
    from forgemind.mcp.server import ForgeMindMCPServer
    import asyncio

    async def _check():
        server = ForgeMindMCPServer()
        req = {
            "jsonrpc": "2.0",
            "id": "t1",
            "method": "tools/call",
            "params": {"name": "query_portfolio", "arguments": {}},
        }
        r = await server.handle_request(req)
        text = r["result"]["content"][0]["text"]
        import json
        body = json.loads(text)
        assert "decisions" in body, (
            "query_portfolio 缺 decisions 字段;桌面 6 Agent 面板将无可显示投票"
        )
        assert "risk_metrics" in body, (
            "query_portfolio 缺 risk_metrics 字段;桌面风险指标面板将显示空"
        )
        # 即使没 snapshot 也要返回结构(空列表 / None),不抛 KeyError
        assert isinstance(body["decisions"], list)
        assert body["risk_metrics"] is None or isinstance(body["risk_metrics"], dict)

    asyncio.run(_check())


def test_storage_has_decision_and_backtest_run_tables():
    """portfolio_decision + backtest_run 两张表必须存在 schema

    桌面 6 Agent + 风险指标都从这两张表读,删表 = 桌面回归到硬编码。
    """
    from forgemind.core.data.storage import init_duckdb, DuckDBStorage

    init_duckdb()
    with DuckDBStorage() as db:
        for table in ("portfolio_decision", "backtest_run"):
            exists = db.query_scalar(
                "SELECT COUNT(*) FROM information_schema.tables "
                f"WHERE table_name='{table}'"
            )
            assert exists, f"存储层缺 {table} 表,6 Agent / 风险指标面板将无数据可读"
