# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""策略清单与跑回测的那个工具,不许自相矛盾。

这两个都是**直接给模型看的**:
`forgemind://strategies` 告诉模型有哪些策略、哪些跑不了、为什么跑不了;
`run_backtest` 是模型真正去调的那个。

它们曾经对不上:清单说 9 个策略能跑,工具只认 5 个,而且把"存在但这个
命令喂不了"的说成"未知策略"。模型照着清单挑一个单标的的扩展策略,工具
回一句它没听过 —— 模型只能二选一:信清单,或者信工具。

现在解析只有一份(命令与 MCP 共用),所以这里盯的是**两边一致**:清单说
跑不了的,工具不许说"未知";清单说能跑的,工具必须收下。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "forgemind"))

from forgemind.mcp.server import ForgeMindMCPServer  # noqa: E402


def _server() -> ForgeMindMCPServer:
    return ForgeMindMCPServer()


def _call(srv: ForgeMindMCPServer, name: str, arguments: dict) -> dict:
    return asyncio.run(srv.handle_request({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }))


def _run_backtest(srv: ForgeMindMCPServer, strategy: str) -> dict:
    resp = _call(srv, "run_backtest", {
        "strategy": strategy, "symbol": "600519",
        "start": "2024-01-01", "end": "2024-03-31",
    })
    result = resp["result"]
    import json

    return {
        "is_error": bool(result.get("isError")),
        "payload": json.loads(result["content"][0]["text"]),
    }


class TestStrategyListAgreesWithTheTool:
    def test_no_existing_strategy_is_called_unknown(self):
        """清单里有的策略,工具不许说"未知" —— 那是两处说法打架"""
        srv = _server()
        catalog = srv._strategy_catalog()
        for entry in catalog["strategies"]:
            name = entry["name"]
            out = _run_backtest(srv, name)
            err = out["payload"].get("error", "")
            assert "未知策略" not in err, (
                f"{name} 在策略清单里列着,工具却说它未知: {err}"
            )

    def test_runnable_ones_are_accepted(self):
        """清单说能跑的,工具必须收下 —— 收不下就是两处说法打架"""
        srv = _server()
        catalog = srv._strategy_catalog()
        runnable = [e["name"] for e in catalog["strategies"] if e.get("cli_runnable")]
        assert runnable, "策略清单里一个能跑的都没有"
        for name in runnable:
            out = _run_backtest(srv, name)
            assert not out["is_error"], (
                f"{name} 在清单里标着能跑,工具却拒绝了: {out['payload']}"
            )

    def test_unusable_ones_are_refused_with_the_same_reason(self):
        """清单说跑不了的,工具要拒绝,而且理由是同一句"""
        srv = _server()
        catalog = srv._strategy_catalog()
        unusable = [
            e for e in catalog["strategies"]
            if not e.get("cli_runnable") and e.get("unusable_reason")
        ]
        assert unusable, "策略清单里没有跑不了的策略,这份测试就没意义了"
        for entry in unusable:
            name = entry["name"]
            out = _run_backtest(srv, name)
            assert out["is_error"], (
                f"{name} 跑不了,工具却收下了: {out['payload']}"
            )
            assert entry["unusable_reason"] in out["payload"].get("error", ""), (
                f"{name} 的拒绝理由与清单里写的不是同一句: "
                f"{out['payload'].get('error')} / {entry['unusable_reason']}"
            )

    def test_unknown_name_is_still_unknown(self):
        """真不存在的,还是得说未知 —— 别把什么都推成"跑不了" """
        srv = _server()
        out = _run_backtest(srv, "压根不存在的策略")
        assert out["is_error"], out
        assert "未知策略" in out["payload"].get("error", ""), out["payload"]
        # 也要给出一条走得通的路
        assert out["payload"].get("runnable"), out["payload"]


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
