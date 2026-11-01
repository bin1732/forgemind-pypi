# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
扫描源码中残留的硬编码数据:

1. page.tsx Header 版本号硬编码为 "v2026.09"
   修:从 call("get_system_status") 拿真 version,fallback "v—"

2. agent-decision-panel 顶部 "6 Agent 综合 · LangGraph 编排" 静态文案
   修:加上当前 currentSymbol,变成 "6 Agent 综合 · 600519.SH · LangGraph 编排"

3. signal-table 空态文案 "forgemind signal\\n# 或 Cmd+K" — 实际不真
   修:诚实告诉用户跑什么出真信号, ⌘K → 运行端到端流水线 / forgemind signal CLI

回归测试防止硬编码数据复现。
"""
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
PAGE = REPO / "forgemind-ui" / "app" / "page.tsx"
PANEL = REPO / "forgemind-ui" / "components" / "agent-decision-panel.tsx"
SIGNAL_TABLE = REPO / "forgemind-ui" / "components" / "signal-table.tsx"


def test_page_header_version_is_dynamic():
    """page.tsx Header 版本号不得硬编码为 v2026.09"""
    src = PAGE.read_text(encoding="utf-8")
    # 旧: <span className="rounded bg-primary/10 px-2 py-0.5 text-xs">v2026.09</span>
    assert ">v2026.09<" not in src, (
        "page.tsx header 仍硬编码 v2026.09,应改用 systemStatus.version 真值"
    )
    # 必须有 systemStatus 引用
    assert "systemStatus" in src, (
        "page.tsx header 必须有 systemStatus (从 get_system_status 拉真 version)"
    )


def test_agent_decision_panel_header_shows_current_symbol():
    """顶部不能只有静态文案,必须含 currentSymbol"""
    src = PANEL.read_text(encoding="utf-8")
    # 旧 "6 Agent 综合 · LangGraph 编排" 静态 (不含 {})
    assert "6 Agent 综合 · LangGraph 编排" not in src, (
        "agent-decision-panel 顶部 '6 Agent 综合 · LangGraph 编排' 仍静态;"
        " 应加 currentSymbol,告诉用户当前看的哪个标的"
    )
    assert "{currentSymbol}" in src, (
        "agent-decision-panel 顶部应含 {currentSymbol}"
    )


def test_signal_table_empty_state_honest():
    """signal-table 空态文案应诚实说跑什么出真信号"""
    src = SIGNAL_TABLE.read_text(encoding="utf-8")
    # 旧空态: forgemind signal\\n# 或 Cmd+K → 运行端到端流水线
    # 新空态: 跑端到端流水线 + forgemind signal CLI
    assert "forgemind signal" in src  # CLI 提示保留
    assert "⌘K" in src or "运行端到端" in src  # 桌面入口保留
    assert "PipelineResult" in src, (
        "signal-table 空态应说明 PipelineResult.signals 的来源"
    )
