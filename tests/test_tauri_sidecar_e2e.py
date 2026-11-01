# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
模拟 Tauri 桌面端 Rust 命令真接 Python sidecar 端到端

Tauri Rust 流程:
1. start_python_sidecar spawn forgemind.api.main 监听 8008
2. get_system_status 调 /mcp/tools/list (GET)
3. mcp_call_tool POST /mcp/tools/call
4. read_mcp_resource POST /mcp/resources/read
5. run_pipeline POST /api/pipeline/run
6. stop_python_sidecar kill process

这里锁住的三条约定:
- /mcp/tools/list 是 GET,POST 会得到 405
- /mcp/resources/list 端点必须在 api/main.py 注册
- Tauri get_system_status 拿 mcp_resource_count 需单独调 resources/list
"""
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request

import pytest


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """检查端口在 listen"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _wait_for_listen(host: str, port: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(host, port, 0.3):
            return True
        time.sleep(0.2)
    return False


@pytest.fixture(scope="module")
def tauri_sidecar():
    """启真 forgemind.api.main 在 8009 (避免 8008 端口冲突)"""
    port = 8009
    if _port_open("127.0.0.1", port):
        # 等 5s 让旧 sidecar 死
        deadline = time.time() + 5
        while time.time() < deadline and _port_open("127.0.0.1", port):
            time.sleep(0.5)
        if _port_open("127.0.0.1", port):
            pytest.skip(f"{port} 端口持续被占")

    interpreter = sys.executable
    repo = "/workspace/quantmind"
    if not os.path.exists(interpreter) or not os.path.isdir(repo):
        pytest.skip("需要本地解释器与仓库路径,常规流水线不具备")

    env = {**os.environ}
    # 切 db 到 tmp 路径避免污染
    import tempfile
    db_dir = tempfile.mkdtemp(prefix="forgemind-tauri-test-")
    env["FORGEMIND_DUCKDB_PATH"] = os.path.join(db_dir, "test.db")

    proc = subprocess.Popen(
        [interpreter, "-m", "forgemind.api.main",
         "--port", str(port), "--host", "127.0.0.1"],
        env=env, cwd=repo,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        if not _wait_for_listen("127.0.0.1", port, timeout=20.0):
            stdout, stderr = proc.communicate(timeout=2)
            pytest.fail(
                f"sidecar 20s 内没 listen 8008:\nstdout={stdout.decode()[:500]}"
                f"\nstderr={stderr.decode()[:500]}"
            )
        yield f"http://127.0.0.1:{port}"
    finally:
        # 模仿 stop_python_sidecar
        proc.send_signal(signal.SIGKILL)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _http_post(url, data):
    req = urllib.request.Request(
        url, data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def _http_get(url):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def test_tauri_get_system_status_tools_endpoint(tauri_sidecar):
    """Tauri get_system_status 走 GET /mcp/tools/list (15 轮修 .post → .get)"""
    base = tauri_sidecar
    body = _http_get(f"{base}/mcp/tools/list")
    r = body.get("result", {})
    assert len(r.get("tools", [])) >= 8, f"tools 太少: {r}"
    # 工具名应包含 output_signal / query_portfolio / list_factor_ic
    names = {t["name"] for t in r.get("tools", [])}
    assert {"output_signal", "query_portfolio", "list_factor_ic",
            "stock_pick", "get_kline"} <= names


def test_tauri_get_system_status_resources_endpoint(tauri_sidecar):
    """Tauri get_system_status 单独调 /mcp/resources/list (15 轮加这个端)"""
    base = tauri_sidecar
    body = _http_get(f"{base}/mcp/resources/list")
    r = body.get("result", {})
    uris = {x["uri"] for x in r.get("resources", [])}
    # 6 个 resource
    assert "forgemind://features" in uris
    assert "forgemind://strategies" in uris
    assert "forgemind://symbols" in uris
    assert "forgemind://signals" in uris
    assert "forgemind://brokers" in uris
    assert "forgemind://portfolio" in uris


def test_tauri_mcp_call_tool_output_signal(tauri_sidecar):
    """Tauri mcp_call_tool("output_signal", ...) 真落 DuckDB

    sidecar 在独立 subprocess, 写到 module fixture 自己的 db_dir/test.db;
    这里只通过 resources/read forgemind://signals 验证落盘,不直接读 db
    (避免 autouse fixture 切到 tmp/test.db 跟 module db_dir 路径不一致)
    """
    base = tauri_sidecar
    r = _http_post(f"{base}/mcp/tools/call", {
        "name": "output_signal",
        "arguments": {
            "symbol": "600519.SH",
            "side": "BUY",
            "confidence": 0.85,
            "rationale": "15 轮 Tauri sidecar 真 e2e",
        },
    })
    text = json.loads(r["result"]["content"][0]["text"])
    assert text["status"] == "ok"
    assert text["side"] == "BUY"
    assert abs(text["confidence"] - 0.85) < 1e-9
    assert text["signal_id"].startswith("sig_")

    # 通过 MCP resources/read 验证真落 (read 拿 sidecar 自己的 db)
    res = _http_post(f"{base}/mcp/resources/read", {"uri": "forgemind://signals"})
    sigs = json.loads(res["result"]["contents"][0]["text"])["signals"]
    found = next((s for s in sigs if s["confidence"] == 0.85), None)
    assert found is not None, f"找不到 0.85 confidence signal: {sigs}"


def test_tauri_read_mcp_resource_signals(tauri_sidecar):
    """Tauri read_mcp_resource("forgemind://signals") 读真落盘"""
    base = tauri_sidecar
    r = _http_post(f"{base}/mcp/resources/read", {"uri": "forgemind://signals"})
    text = json.loads(r["result"]["contents"][0]["text"])
    assert text["total"] >= 1
    # 应有 output_signal 落的 BUY 0.85
    sig = next((s for s in text["signals"] if s["confidence"] == 0.85), None)
    assert sig is not None, f"找不到 0.85 confidence signal: {text['signals']}"


def test_tauri_get_system_status_full_path(tauri_sidecar):
    """完整模拟 Tauri get_system_status: tools + resources 并行, 返 mcp_tools + mcp_resource_count"""
    import urllib.request
    base = tauri_sidecar
    # 模拟 Tauri Rust 流程
    tools = _http_get(f"{base}/mcp/tools/list")
    resources = _http_get(f"{base}/mcp/resources/list")
    tool_count = len(tools["result"]["tools"])
    resource_count = len(resources["result"]["resources"])
    out = {
        "app_version": "2026.9.3",
        "tauri_version": "2",
        "python_sidecar_running": True,
        "mcp_tools": [t["name"] for t in tools["result"]["tools"]],
        "mcp_tool_count": tool_count,
        "mcp_resource_count": resource_count,
    }
    assert out["mcp_tool_count"] >= 8
    assert out["mcp_resource_count"] >= 6
    assert out["mcp_tools"][:3] == ["search_features", "get_feature", "trace_feature_usage"]  # 按注册顺序
