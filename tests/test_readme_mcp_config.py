# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""README 里的 MCP 客户端配置必须真的能用

README 之前只说"可接 Claude Desktop / Cursor",却没给配置块 ——
对一个 MCP 优先的产品,用户装完不知道怎么连,等于装了个用不上的东西。

这里不只是检查文档里有没有 JSON,而是**照着文档真的把 MCP server
拉起来握手**,确认文档里写的命令是有效的。
"""

import json
import re
import subprocess
import sys
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"


def _readme() -> str:
    return README.read_text(encoding="utf-8")


class TestReadmeHasAUsableMcpConfig:
    def test_contains_mcp_servers_block(self):
        assert "mcpServers" in _readme(), (
            "README 没有 MCP 客户端配置块 —— 用户装了却不知道怎么连")

    def test_config_json_is_valid(self):
        blocks = re.findall(r"```json\n(\{.*?\})\n```", _readme(), re.S)
        cfg = next((b for b in blocks if "mcpServers" in b), None)
        assert cfg, "找不到含 mcpServers 的 json 代码块"
        data = json.loads(cfg)                     # 解析失败即测试失败
        assert "forgemind" in data["mcpServers"]
        entry = data["mcpServers"]["forgemind"]
        assert entry.get("command"), "必须给出 command"
        assert entry.get("args") == ["mcp"], f"args 应为 [\"mcp\"],实际 {entry.get('args')}"

    def test_it_explains_absolute_path_is_required(self):
        """MCP 客户端不用你 shell 的 PATH,必须写绝对路径 —— 这点要说明"""
        txt = _readme()
        assert ("绝对路径" in txt or "absolute" in txt.lower()), (
            "没说明命令要用绝对路径,用户会填 `forgemind` 然后连不上")

    def test_it_explains_etl_is_a_prerequisite(self):
        """K 线 / 选股 / IC 衰减都读本地 DuckDB,得先 etl"""
        txt = _readme()
        assert "etl" in txt, "没说明部分工具需要先跑 etl"

    def test_documented_command_actually_answers(self):
        """照 README 敲,server 必须真的握手成功"""
        proc = subprocess.run(
            [sys.executable, "-m", "forgemind.cli", "mcp"],
            input=json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "readme-check", "version": "1"}},
            }) + "\n",
            capture_output=True, text=True, timeout=120,
        )
        assert proc.stdout.strip(), "MCP server 无任何输出"
        first = json.loads(proc.stdout.splitlines()[0])
        assert first.get("result", {}).get("serverInfo", {}).get("name") == "forgemind", (
            f"握手结果异常: {proc.stdout[:200]}")
