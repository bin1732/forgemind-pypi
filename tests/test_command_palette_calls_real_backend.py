# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
CommandPalette 之前 7 个命令(action)全是 alert("...") toast,按 ⌘R 弹个
"启动端到端流水线..." 没有任何真后端调用。

底层修法:每个 action 改成调 MCP tool / Rust command,出错真实告警。
本测试防止 alert(...) 复活 —— 7 个命令必须调用 call / mcpTool,
绝不能只是 alert 文本提示。
"""
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
PALETTE = REPO / "forgemind-ui" / "components" / "command-palette.tsx"

# 这些命令 id 必须存在 + 它们的 action 必须非 alert-only
COMMAND_IDS = [
    "run-pipeline",
    "compute-factors",
    "evaluate-ic",
    "train-lgbm",
    "walk-forward",
    "monte-carlo",
    "stock-pick",
    "fetch-akshare",
]


def test_command_palette_no_alert_only_actions():
    """每个命令的 action 不能只是 alert() —— 必须调 call/mcpTool 真后端

    简单粗暴的判断:action 体里出现 call( 或 mcpTool(,且只在 fetch-akshare
    例外(ETL 是 CLI 长任务,没对应 MCP)。
    """
    src = PALETTE.read_text(encoding="utf-8")
    for cmd_id in COMMAND_IDS:
        if cmd_id == "fetch-akshare":
            # ETL 是 CLI 长任务,没 MCP 对应。允许 alert 提示用户去终端跑
            continue
        # 取这条命令到下一条命令之间的整段 —— 不能用固定长度的窗口:
        # action 体一旦变长(多两行解包),真调用就落到窗口外面去了,
        # 明明调了后端却判成"只 alert"。
        start = re.search(rf'id:\s*"{cmd_id}"', src)
        if not start:
            raise AssertionError(f"command-palette 找不到 {cmd_id} 命令")
        nxt = re.search(r'id:\s*"', src[start.end():])
        body = src[start.end(): start.end() + (nxt.start() if nxt else len(src))]
        # "call(cmd, ...)" / "call<T>(cmd, ...)" / "mcpTool<T>(cmd, ...)" 都算。
        # 泛型可能嵌套(mcpTool<Record<string, unknown>>),所以不看尖括号里
        # 装了什么,只看函数名后面跟的是 ( 还是 <。
        import re as _re
        has_call = _re.search(r"\bcall\s*[(<]", body) is not None
        has_mcp = _re.search(r"\bmcpTool\s*[(<]", body) is not None
        # runPipeline() 是 backend.tsx 包装的 helper, 内部用 call("run_pipeline")
        # 仍调真后端 (Rust command → forgemind.api.main /pipeline/run)
        has_run_pipeline = "runPipeline(" in body or "N(" in body
        assert has_call or has_mcp or has_run_pipeline, (
            f"command-palette 的 {cmd_id} action 仅 alert,没调真后端;"
            " 应该用 mcpTool() / call() 触发 MCP / Rust command"
        )


def test_command_palette_imports_mcp_bridge():
    """command-palette 必须 import mcpTool + call 才能接通真后端"""
    src = PALETTE.read_text(encoding="utf-8")
    assert "mcpTool" in src, "command-palette 没 import mcpTool"
    assert 'from "@/lib/tauri"' in src, "command-palette 没 import tauri 桥"
