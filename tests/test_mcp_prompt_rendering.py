# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""MCP prompts/get 必须把 arguments 渲染进模板

`prompts/get` 直接返回 `p.template`,调用方(Claude Desktop 等)
拿到的是

    "分析 {symbol} 当前投资价值。"

—— 字面量的 {symbol}。整条提示词是坏的:模型会去分析一个名字就叫
"{symbol}" 的股票。而响应结构完全正常,看起来一切正常。

MCP 协议里 prompts/get 的 arguments 就是给模板填空用的,不填等于
把占位符当内容发出去了。
"""

import ast
import json
import queue
import subprocess
import sys
import threading

import pytest

from forgemind.mcp.server import _render_prompt


class TestRenderHelper:
    def test_substitutes_all_placeholders(self):
        text, missing = _render_prompt("分析 {symbol},研究 {factor}", {"symbol": "600519",
                                                                "factor": "ROC"})
        assert text == "分析 600519,研究 ROC"
        assert missing == []

    def test_missing_placeholder_is_kept_and_reported(self):
        """缺失的不能静默:str.format 会直接 KeyError,那样更糟"""
        text, missing = _render_prompt("分析 {symbol} 买入 {factor}", {"symbol": "600519"})
        assert "600519" in text
        assert "{factor}" in text
        assert missing == ["factor"]

    def test_extra_arguments_are_ignored(self):
        text, missing = _render_prompt("无占位符", {"a": 1, "b": 2})
        assert text == "无占位符"
        assert missing == []

    def test_braces_that_are_not_placeholders_survive(self):
        text, _ = _render_prompt("JSON 示例 {\"a\": 1} 与 {x}", {"x": "Y"})
        assert "{\"a\": 1}" in text
        assert "Y" in text


class TestPromptsGetOverStdio:
    """走真实协议,这是用户连过来的那条路"""

    @pytest.fixture
    def mcp(self):
        import os

        env = {**os.environ, "PYTHONPATH": str(__import__("pathlib").Path(
            __file__).resolve().parent.parent)}
        proc = subprocess.Popen(
            [sys.executable, "-m", "forgemind.cli", "mcp"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env,
            bufsize=1)
        q: queue.Queue = queue.Queue()

        def pump():
            for line in proc.stdout:
                line = line.strip()
                if line:
                    try:
                        q.put(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        threading.Thread(target=pump, daemon=True).start()

        def send(o):
            proc.stdin.write(json.dumps(o) + "\n")
            proc.stdin.flush()

        def read(timeout=30):
            try:
                return q.get(timeout=timeout)
            except queue.Empty:
                return None

        send({"jsonrpc": "2.0", "id": "1", "method": "initialize",
              "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                         "clientInfo": {"name": "t", "version": "1"}}})
        read()
        yield send, read
        try:
            proc.stdin.close()
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    def test_list_returns_three_prompts(self, mcp):
        send, read = mcp
        send({"jsonrpc": "2.0", "id": "2", "method": "prompts/list", "params": {}})
        names = [p["name"] for p in read()["result"]["prompts"]]
        assert sorted(names) == ["factor_research", "risk_check", "stock_analysis"]

    @pytest.mark.parametrize("name,args", [
        ("stock_analysis", {"symbol": "600519.SH"}),
        ("factor_research", {"feature_name": "ROC_3_10"}),
        ("risk_check", {"symbol": "600519.SH"}),
    ])
    def test_no_placeholder_survives_into_the_message(self, mcp, name, args):
        import re

        send, read = mcp
        send({"jsonrpc": "2.0", "id": "3", "method": "prompts/get",
              "params": {"name": name, "arguments": args}})
        resp = read()
        assert "error" not in resp, f"参数齐全却报错: {resp.get('error')}"
        res = resp["result"]
        text = " ".join(m.get("content", {}).get("text", "")
                        for m in res["messages"])
        assert text
        leftovers = re.findall(r"\{\w+\}", text)
        assert not leftovers, (
            f"{name} 的提示词里残留未替换的占位符 {leftovers} —— "
            f"调用方会把它当内容发给模型")

    def test_echoed_value_appears_in_rendered_text(self, mcp):
        send, read = mcp
        send({"jsonrpc": "2.0", "id": "4", "method": "prompts/get",
              "params": {"name": "stock_analysis",
                         "arguments": {"symbol": "600519.SH"}}})
        text = " ".join(m.get("content", {}).get("text", "")
                        for m in read()["result"]["messages"])
        assert "600519.SH" in text

    def test_missing_argument_fails_the_whole_request(self, mcp):
        """缺参数要整个请求失败 —— 半渲染的提示词会被当正文发给模型"""
        send, read = mcp
        send({"jsonrpc": "2.0", "id": "5", "method": "prompts/get",
              "params": {"name": "stock_analysis", "arguments": {}}})
        r = read()
        assert "result" not in r, f"缺参数却返回了结果: {r.get('result')}"
        err = r.get("error", {})
        assert err.get("code") == -32602, err
        assert "symbol" in err.get("message", ""), err

    def test_unknown_prompt_is_a_clean_error(self, mcp):
        send, read = mcp
        send({"jsonrpc": "2.0", "id": "6", "method": "prompts/get",
              "params": {"name": "does_not_exist", "arguments": {}}})
        r = read()
        assert r.get("error", {}).get("code") == -32602, r


class TestTemplatePlaceholdersMatchRegistration:
    def test_declared_templates_have_no_unreachable_placeholders(self):
        """模板里的占位符必须是有意义的参数名"""
        import pathlib
        import re

        src = (pathlib.Path(__file__).resolve().parent.parent
               / "forgemind/mcp/server.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        cls = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.ClassDef) and n.name.endswith("MCPServer"))
        for n in ast.walk(cls):
            if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "_prompt":
                name, tpl = n.args[0].value, n.args[2].value
                for ph in re.findall(r"\{(\w+)\}", tpl):
                    assert ph.islower() and ("_" in ph or ph.islower()), (
                        f"{name} 的占位符 {{{ph}}} 看起来不是参数名"
                    )
