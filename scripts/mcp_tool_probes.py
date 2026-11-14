#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""MCP 每个工具的合法参数 —— 一处定义,判据与回归测试共用。

**为什么参数表要这么较真**:参数错了,工具照样会返回 JSON,内容却是
"参数不合法"或"找不到该因子"。那正是"看起来在工作"的典型形态 ——
只检查"有没有返回"永远发现不了。所以这份表里的每个参数都要是**真能
跑通**的,不是照着 schema 编出来的。

有一处参数没法写死:agent_approve 的 thread_id 必须是真跑一次
agent_decide 拿到的,假的那个只会得到"找不到待审批的决策"。

用法:
    from mcp_tool_probes import TOOL_CALLS, legal_args
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

#: 每个工具的合法参数(取自 tools/list 声明的 required)。
#: 顺序按注册顺序,便于日志里对照。
TOOL_CALLS: list[tuple[str, dict[str, Any]]] = [
    ("search_features", {"query": "momentum"}),
    ("get_feature", {"name": "kmid"}),
    ("trace_feature_usage", {"feature_id": "KMID"}),
    (
        "run_backtest",
        {
            "strategy": "ma_cross",
            "symbol": "600519",
            "start": "2024-01-01",
            "end": "2024-06-30",
        },
    ),
    (
        "output_signal",
        {
            "symbol": "600519.SH",
            "side": "buy",
            "confidence": 0.8,
            "rationale": "契约测试",
        },
    ),
    ("check_ic_decay", {"feature_name": "kmid", "window_days": 30}),
    ("list_factor_ic", {"symbol": "600519", "window_days": 5}),
    ("get_kline", {"symbol": "600519", "limit": 5}),
    ("query_portfolio", {}),
    ("stock_pick", {"universe": ["600519", "000001"], "top_n": 2}),
    # 人工审批链路:准备阶段停下 → 用 thread_id 拍板
    (
        "agent_decide",
        {
            "symbol": "600519.SH",
            "cash": 100000,
            "total_equity": 200000,
            "positions": [
                {"symbol": "600519.SH", "quantity": 100, "avg_price": 1500},
            ],
        },
    ),
    ("agent_approve", {"thread_id": "", "approved": True}),
]

TOOL_CALLS_BY_NAME: dict[str, dict[str, Any]] = dict(TOOL_CALLS)

#: 会读本地库的MCP 工具。库读不到时,它们必须说"读不到"而不是
#: "没有数据" —— 说成后者,模型会去建议用户拉数据,而拉数据同样连不上
#: 那个库。
TOOLS_TOUCHING_STORE: frozenset[str] = frozenset(
    {
        "run_backtest",
        "output_signal",
        "check_ic_decay",
        "list_factor_ic",
        "get_kline",
        "query_portfolio",
        "stock_pick",
        "agent_decide",
    }
)


def tool_text(response: dict[str, Any]) -> str:
    """从工具响应里取出正文。"""
    content = (response.get("result") or {}).get("content") or []
    if not content:
        return ""
    return str(content[0].get("text", ""))


def _agent_decide_thread_id() -> str:
    """真跑一次 agent_decide,拿真的 thread_id。"""
    from forgemind.mcp.server import ForgeMindMCPServer

    server = ForgeMindMCPServer()
    response = asyncio.run(
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "agent_decide",
                    "arguments": TOOL_CALLS_BY_NAME["agent_decide"],
                },
            }
        )
    )
    text = tool_text(response)
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return ""
    return str(payload.get("thread_id", ""))


def legal_args(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """补上必须是真值的参数。

    agent_approve 的 thread_id 必须是**真**的 —— 拿假的去调,工具会报
    "找不到待审批的决策",返回的是错误文本而不是 JSON,那测的就不是这个
    工具的正常输出了。
    """
    if name != "agent_approve":
        return args
    thread_id = _agent_decide_thread_id()
    return {**args, "thread_id": thread_id}
