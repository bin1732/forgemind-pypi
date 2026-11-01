# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真底层:MCP stdio 协议 — 不走 HTTP, 真启 subprocess + 真 stdin/stdout 握手

这是真实用户路径:
  claude_desktop_config.json → command: "forgemind" args: ["mcp"] → stdio
"""
import json
import os
import subprocess
import sys
import time

import pytest


def _send_stdio(proc: subprocess.Popen, payload: dict, timeout: float = 30.0) -> dict:
    """发一条 JSON-RPC 消息, 读一条响应"""
    line = json.dumps(payload) + "\n"
    proc.stdin.write(line)
    proc.stdin.flush()
    # 读一行 (一行一协议)
    end = time.time() + timeout
    while time.time() < end:
        line = proc.stdout.readline()
        if line:
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError as e:
                # MCP 服务器可能在响应前会发 banner/log
                continue
    raise TimeoutError(f"stdin/stdout {timeout}s 内没响应")


def test_mcp_stdio_initialize_and_list_tools():
    """真启 forgemind mcp 子进程, 发 initialize + tools/list"""
    # 找 forgemind 二进制 (走 venv 的, 沙箱没装)
    forgemind_bin = "/workspace/.venv/bin/forgemind"
    if not os.path.exists(forgemind_bin):
        pytest.skip(f"{forgemind_bin} 不存在, 沙箱跳过")

    # 启动 MCP stdio server
    env = os.environ.copy()
    # 用独立 db, 避免污染
    env["FORGEMIND_DUCKDB_PATH"] = "/tmp/test_mcp_stdio.db"
    # 走 quiet — MCP 协议不要 log 污染 stdout
    env["FORGEMIND_LOG_LEVEL"] = "ERROR"

    proc = subprocess.Popen(
        [forgemind_bin, "mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        bufsize=1,  # line buffered
    )
    try:
        # 1) initialize 握手
        r = _send_stdio(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }, timeout=30)
        assert "result" in r, f"initialize 应回 result, 实际 {r}"
        result = r["result"]
        assert "serverInfo" in result, f"result 应有 serverInfo, 实际 {result}"
        assert result["serverInfo"]["name"] == "forgemind", (
            f"serverInfo.name 应是 forgemind, 实际 {result['serverInfo']}"
        )
        assert "capabilities" in result
        assert "protocolVersion" in result

        # 2) initialized 通知
        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }) + "\n")
        proc.stdin.flush()

        # 3) tools/list
        r = _send_stdio(proc, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }, timeout=30)
        assert "result" in r, f"tools/list 应回 result, 实际 {r}"
        tools = r["result"].get("tools", [])
        assert len(tools) >= 5, (
            f"tools 应 ≥ 5, 实际 {len(tools)}: {[t.get('name') for t in tools]}"
        )
        # 必须有核心 tool
        tool_names = {t["name"] for t in tools}
        for required in ("search_features", "get_feature", "query_portfolio",
                         "stock_pick", "list_factor_ic", "check_ic_decay",
                         "get_kline", "run_backtest", "output_signal",
                         "trace_feature_usage"):
            assert required in tool_names, f"MCP tools 应含 {required}, 实际: {tool_names}"

        # 4) tools/call — 调 search_features (无 db 依赖, 走内置因子目录)
        r = _send_stdio(proc, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "search_features",
                "arguments": {"query": "alpha"},
            },
        }, timeout=30)
        assert "result" in r, f"tools/call 应回 result, 实际 {r}"
        call_result = r["result"]
        content = call_result.get("content", [])
        assert len(content) > 0, f"content 应非空, 实际 {call_result}"
        text = content[0].get("text", "")
        assert text, f"content[0].text 应非空"
        try:
            sf = json.loads(text)
        except json.JSONDecodeError:
            pytest.fail(f"content[0].text 不是 JSON: {text[:200]}")
        # 因子目录应非空 (alpha query)
        assert "features" in sf or "results" in sf, f"应有 features/results, 实际 {sf}"

        # 5) resources/list (MCP 资源)
        r = _send_stdio(proc, {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/list",
            "params": {},
        }, timeout=30)
        assert "result" in r, f"resources/list 应回 result, 实际 {r}"
        resources = r["result"].get("resources", [])
        assert len(resources) >= 3, (
            f"resources 应 ≥ 3, 实际 {len(resources)}: "
            f"{[r.get('uri') for r in resources]}"
        )
        # 6) resources/read — forgemind://signals
        r = _send_stdio(proc, {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {"uri": "forgemind://signals"},
        }, timeout=30)
        assert "result" in r, f"resources/read 应回 result, 实际 {r}"
        # content.contents[0].text 是 JSON
        contents = r["result"].get("contents", [])
        assert len(contents) > 0, f"contents 应非空"
        signals_text = contents[0].get("text", "")
        signals = json.loads(signals_text)
        assert "signals" in signals, f"forgemind://signals 应有 signals, 实际 {signals}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_mcp_stdio_handles_invalid_request_gracefully():
    """stdio 协议: 非法 method / 错误参数不应让进程崩溃, 应回 error JSON-RPC"""
    forgemind_bin = "/workspace/.venv/bin/forgemind"
    if not os.path.exists(forgemind_bin):
        pytest.skip(f"{forgemind_bin} 不存在, 沙箱跳过")

    env = os.environ.copy()
    env["FORGEMIND_DUCKDB_PATH"] = "/tmp/test_mcp_err.db"
    env["FORGEMIND_LOG_LEVEL"] = "ERROR"

    proc = subprocess.Popen(
        [forgemind_bin, "mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        bufsize=1,
    )
    try:
        # 发未 initialize 直接 tools/list (协议违规, 但不应让进程崩)
        r = _send_stdio(proc, {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/list",
            "params": {},
        }, timeout=10)
        # 接受两种合理反应:
        # 1) 进程不响应 (重连)— 抛 TimeoutError
        # 2) 进程回 error JSON-RPC
        # 3) 进程回了正常 result (宽容实现)
        if "error" in r:
            assert isinstance(r["error"], dict)
        elif "result" in r:
            # OK — 宽容实现
            pass
        else:
            pytest.fail(f"非法 request 应回 result/error, 实际: {r}")

        # 进程应仍活着 — 发一个 initialize
        r2 = _send_stdio(proc, {
            "jsonrpc": "2.0",
            "id": 100,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }, timeout=10)
        assert "result" in r2 or "error" in r2, f"initialize 后应回 response, 实际 {r2}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
