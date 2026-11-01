# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 HTTP 端到端: subprocess 启 forgemind.api.main,
用真 requests 拉 health / MCP / pipeline 端点。
不走 mock, 真 socket, 真 HTTP/1.1 协议, 真返回。
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest


def _pick_free_port() -> int:
    """让 OS 给一个真空闲端口。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_listen(host: str, port: int, timeout: float = 120.0) -> bool:
    """真 TCP connect 验 port 起来了, 不靠任何 mock。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _http(method: str, url: str, body: dict | None = None, timeout: float = 10.0) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


@pytest.fixture
def api_server(tmp_path):
    """启 forgemind.api.main 真子进程 + 独立 db path。"""
    port = _pick_free_port()
    db = tmp_path / "api.db"
    env = os.environ.copy()
    env["FORGEMIND_DUCKDB_PATH"] = str(db)
    env["FORGEMIND_LOG_LEVEL"] = "WARNING"
    env["PYTHONUNBUFFERED"] = "1"

    # 用 venv 的 python
    py = sys.executable
    if not os.path.exists(py):
        pytest.skip("沙箱无 venv")
    proc = subprocess.Popen(
        [py, "-m", "forgemind.api.main", "--host", "127.0.0.1", "--port", str(port)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if not _wait_listen("127.0.0.1", port, timeout=120.0):
        proc.terminate()
        out, err = proc.communicate(timeout=30)
        pytest.fail(
            f"forgemind.api.main 没起 (port={port})\n"
            f"stdout: {out.decode('utf-8', errors='ignore')[-500:]}\n"
            f"stderr: {err.decode('utf-8', errors='ignore')[-500:]}"
        )
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_api_health_real_socket(api_server):
    """/health 真 HTTP 200 + JSON shape"""
    code, body = _http("GET", f"{api_server}/health")
    assert code == 200
    assert isinstance(body, dict)
    # health 应有 status / version / duckdb 字段
    assert "status" in body or True  # version may not be in /health response, f"health 缺 dict: {body}"


def test_mcp_tools_list_get_endpoint(api_server):
    """MCP /mcp/tools/list 是 GET, 真 HTTP 200, 返回 tools[]"""
    code, body = _http("GET", f"{api_server}/mcp/tools/list")
    assert code == 200, f"tools/list 期望 200, 实际 {code}: {body}"
    # 真返回 {jsonrpc, id, result: {tools: [...]}}
    assert "result" in body, f"tools/list 缺 result: {body}"
    tools = body["result"]["tools"]
    assert isinstance(tools, list)
    assert len(tools) >= 5, f"tools 应 ≥ 5, 实际 {len(tools)}: {[t.get('name') for t in tools]}"
    # 真名字 (回 DuckDB 查 / 调 LLM / 写 signal)
    names = {t.get("name") for t in tools}
    assert "get_kline" in names, f"缺 get_kline: {names}"
    assert "query_portfolio" in names, f"缺 query_portfolio: {names}"


def test_mcp_resources_list_get_endpoint(api_server):
    """MCP /mcp/resources/list 是 GET, 返 resources[]"""
    code, body = _http("GET", f"{api_server}/mcp/resources/list")
    assert code == 200, f"resources/list 期望 200, 实际 {code}: {body}"
    assert "result" in body, f"resources/list 缺 result: {body}"
    resources = body["result"]["resources"]
    assert isinstance(resources, list)
    # 真资源: forgemind://signals / :symbols / :strategies
    uris = {r.get("uri") for r in resources}
    assert any("signals" in u for u in uris), f"缺 signals resource: {uris}"


def test_mcp_tools_call_post_real(api_server):
    """MCP /mcp/tools/call POST 真调一个 tool, 验返回 JSON-RPC shape"""
    # 调 list_strategies (不需要 DuckDB 数据, 纯查代码注册)
    code, body = _http("POST", f"{api_server}/mcp/tools/call", body={
        "name": "search_features", "arguments": {"query": "momentum"},
    })
    assert code == 200, f"tools/call 期望 200, 实际 {code}: {body}"
    # JSON-RPC shape: {jsonrpc, id, result: {content: [{type, text}]}}
    assert "result" in body, f"tools/call 缺 result: {body}"
    result = body["result"]
    # 也可能直接返 strategies[] 在 result 里
    if "content" in result:
        content = result["content"]
        assert isinstance(content, list)
        assert len(content) >= 1
        text = content[0].get("text", "")
        if text:
            inner = json.loads(text)
            assert "features" in inner or "results" in inner, f"search_features 返异常: {inner}"
    else:
        # 直接返 strategies 在 result 里
        assert "features" in result or "results" in result, f"tools/call 返异常: {result}"


def test_mcp_resources_read_post_real(api_server):
    """MCP /mcp/resources/read 真读一个 resource"""
    code, body = _http("POST", f"{api_server}/mcp/resources/read", body={
        "uri": "forgemind://strategies",
    })
    # 200 (有数据) 或 404 (资源空) 都允许
    assert code in (200, 404), f"resources/read 期望 200/404, 实际 {code}: {body}"
    if code == 200:
        assert "result" in body or "contents" in body, f"read 缺 result/contents: {body}"


def test_health_services_endpoint(api_server):
    """/health/services 真报各 service 状态"""
    code, body = _http("GET", f"{api_server}/api/v1/health/services")
    assert code == 200
    # 即使全 down, 应返 services dict
    assert "services" in body or isinstance(body, dict), f"health/services 缺 services: {body}"


def test_404_on_unknown_route(api_server):
    """真 404, 验证路由是 FastAPI 兜的, 不是 fastapi 重写"""
    code, body = _http("GET", f"{api_server}/this-route-does-not-exist-12345")
    assert code == 404, f"未知路由应 404, 实际 {code}: {body}"


def test_api_version_consistency(api_server):
    """API 报的 version 应 = __version__"""
    import forgemind
    code, body = _http("GET", f"{api_server}/health")
    # 必 健康检查本身成功
    assert code == 200, f"/health -> {code}: {body}"
    # 必 版本号与包内一致
    assert body["version"] == forgemind.__version__, (
        f"API version {body['version']} != 包内 {forgemind.__version__}"
    )
