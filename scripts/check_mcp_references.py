# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""MCP 的用户可见文字里点名的工具必须真的存在。

提示词与工具说明是直接给模型看的:它照着"用 get_feature 查询"去调工具,
那个工具要是没了,模型拿到的就是一个空错误,还以为是数据的问题。

只查"用 <标识符>"这种明确点名的地方 —— 那里的标识符指的就是工具。
散文里的普通词不算。
"""

from __future__ import annotations

import re
import sys

# 明确点名某个工具的写法:用 get_feature 查询 / 用 query_portfolio 获取
TOOL_REFERENCE = re.compile(r"用\s+([a-z][a-z0-9_]*)")

# 出现在"用 X"里、但说的不是本服务工具的词,以及理由
NOT_A_TOOL = {
    "vnpy": "指的是用户自己的执行层框架,不是 MCP 工具",
}


def main() -> int:
    from forgemind.mcp.server import ForgeMindMCPServer

    server = ForgeMindMCPServer()
    known = set(server.tools)

    problems: list[str] = []

    def scan(label: str, text: str) -> None:
        for token in TOOL_REFERENCE.findall(text or ""):
            if token in NOT_A_TOOL:
                continue
            if token not in known:
                problems.append(f"{label} 提到不存在的工具 {token}")

    for name, prompt in server.prompts.items():
        scan(f"提示词 {name}", prompt.description)
        scan(f"提示词 {name}", prompt.template)
    for name, tool in server.tools.items():
        scan(f"工具 {name}", tool.description)
    for uri, resource in server.resources.items():
        scan(f"资源 {uri}", resource.description)

    if problems:
        print("MCP 的文字里点名了不存在的工具:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(
        f"MCP 点名的工具都存在(工具 {len(known)} 个、"
        f"提示词 {len(server.prompts)} 个、资源 {len(server.resources)} 个)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
