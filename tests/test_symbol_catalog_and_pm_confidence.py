# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
桌面端两处真 bug:

1. workspace-layout / page.tsx <select> 写死 5 个假 symbol
   (600519.SH / 000001.SZ / 000333.SZ / 601318.SH / 300750.SZ)
   切到 DuckDB 里没有的标的会让 K 线说 "暂无数据"。
   底层修法:forgemind://symbols MCP resource 读 DuckDB kline_daily distinct,
   store 加 symbols 字段,page.tsx <select> 用真 symbols。

2. agent-decision-panel 综合 confidence 写死
   `Math.min(0.95, 0.5 + avgScore / 10)` 一份不可解释的算法,
   跟 PM 节点的 confidence 没关系。
   底层修法:从 votes 里找 PM 那条,confidence 用 PM.confidence 真值(0-1)。

本测试防止复活。
"""
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
PAGE = REPO / "forgemind-ui" / "app" / "page.tsx"
PANEL = REPO / "forgemind-ui" / "components" / "agent-decision-panel.tsx"
STORE = REPO / "forgemind-ui" / "lib" / "store.ts"

# 之前 page.tsx <select> 写死 5 个 symbol 的字符串
HARDCODED_SYMBOL_OPTIONS = [
    '<option>600519.SH</option>',
    '<option>000001.SZ</option>',
    '<option>000333.SZ</option>',
    '<option>601318.SH</option>',
    '<option>300750.SZ</option>',
]


def test_page_select_no_hardcoded_symbol_options():
    """page.tsx <select> 不能写死 5 个假 option,必须用 store.symbols 真列表"""
    src = PAGE.read_text(encoding="utf-8")
    for opt in HARDCODED_SYMBOL_OPTIONS:
        assert opt not in src, (
            f"page.tsx <select> 仍含{opt};"
            " 改用 useAppStore().symbols 派生真 ETL 过的标的"
        )


def test_page_select_uses_symbols_store():
    """<select> 应 map useAppStore().symbols + currentSymbol fallback"""
    src = PAGE.read_text(encoding="utf-8")
    assert "useAppStore" in src
    # 选 select 块里应该 map symbols
    assert "symbols.map" in src or "...symbols" in src, (
        "page.tsx <select> 应基于 useAppStore().symbols map 出 <option>"
    )


def test_store_has_symbols_field():
    """store 应该有 symbols 字段 (从 forgemind://symbols 派生)"""
    src = STORE.read_text(encoding="utf-8")
    assert "symbols: string[]" in src or "symbols: string[];" in src, (
        "store.ts 缺 symbols 字段;桌面 header <select> 无真数据来源"
    )
    assert "setSymbols" in src


def test_agent_decision_panel_uses_pm_confidence():
    """综合 confidence 必须是 PM.confidence 真值,不是 Math.min(0.95, 0.5 + ...)"""
    src = PANEL.read_text(encoding="utf-8")
    # 旧算法不能复活
    assert "Math.min(0.95, 0.5 + avgScore / 10)" not in src, (
        "agent-decision-panel 综合 confidence 仍是写死算法"
        " (Math.min(0.95, 0.5 + avgScore / 10));"
        " 改读 PM 节点的 confidence 真值"
    )
    # 必须用 PM.confidence
    assert "PM" in src and "confidence" in src, (
        "agent-decision-panel 必须读 PM.confidence"
    )


def test_mcp_symbol_resource_exists():
    """MCP server 必须有 forgemind://symbols resource (从 DuckDB kline_daily 派生)"""
    server = REPO / "forgemind" / "mcp" / "server.py"
    src = server.read_text(encoding="utf-8")
    assert 'forgemind://symbols' in src, (
        "mcp/server.py 缺 forgemind://symbols resource;"
        " 桌面 <select> 无真数据"
    )
    # 必须读 DuckDB kline_daily
    assert "kline_daily" in src, (
        "mcp/server.py 的 symbols resource 必须读 DuckDB kline_daily"
    )
