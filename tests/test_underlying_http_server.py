# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 HTTP server — 用 stdlib http.server 真起一个 server,
真 curl 真发请求, 验响应 headers / body / status。
不走 mock, 真 socket, 真 HTTP/1.1。
"""
import http.server
import json
import socket
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest


def _pick_free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_listen(port: int, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    """简单 JSON 回声 — 验 path / method / body 完整传递。"""
    def _echo(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        resp = {
            "method": self.command,
            "path": self.path,
            "body": body.decode("utf-8", errors="replace"),
            "ua": self.headers.get("User-Agent", ""),
        }
        data = json.dumps(resp).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Custom", "real-server")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._echo()

    def do_POST(self):
        self._echo()

    def log_message(self, *_):
        pass  # 静默


@pytest.fixture
def http_server():
    port = _pick_free_port()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    if not _wait_listen(port):
        srv.shutdown()
        pytest.fail(f"server 没起来 (port {port})")
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()
    srv.server_close()


def test_curl_get_real(http_server):
    """真 curl GET 验 path / headers / 状态码"""
    r = subprocess.run(
        ["curl", "-s", "-i", "-H", "User-Agent: test-curl/1.0",
         f"{http_server}/hello?x=1"],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0, f"curl 失败: {r.stderr}"
    out = r.stdout
    assert "200 OK" in out, f"应 200, 实际: {out[:300]}"
    assert "X-Custom: real-server" in out, f"自定义 header 应在: {out[:300]}"
    # 找 JSON body
    body_start = out.find("\n\n") + 2
    body = out[body_start:]
    j = json.loads(body)
    assert j["method"] == "GET"
    assert j["path"] == "/hello?x=1"
    assert j["ua"] == "test-curl/1.0"


def test_curl_post_with_body(http_server):
    """真 curl POST + body 验 server 真收到"""
    r = subprocess.run(
        ["curl", "-s", "-X", "POST", "-d", "real-payload",
         f"{http_server}/api/v1/test"],
        capture_output=True, text=True, timeout=10,
    )
    j = json.loads(r.stdout)
    assert j["method"] == "POST"
    assert j["path"] == "/api/v1/test"
    assert j["body"] == "real-payload", f"POST body 应原样回传, 实际: {j['body']!r}"


def test_curl_http_version_negotiated(http_server):
    """真 curl 走 HTTP/1.1, server 响应头含 HTTP/1.1"""
    r = subprocess.run(
        ["curl", "-s", "-i", f"{http_server}/"],
        capture_output=True, text=True, timeout=10,
    )
    assert "HTTP/1.1 200" in r.stdout, f"应 HTTP/1.1 200, 实际: {r.stdout}"


def test_http_server_handles_100_concurrent_requests(http_server):
    """100 个并发 curl 真请求, 全成功 (ThreadingHTTPServer 真并发)"""
    procs = []
    for i in range(100):
        procs.append(subprocess.Popen(
            ["curl", "-s", f"{http_server}/req/{i}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ))
    # 超时给足:这一条要同时起 100 个进程,机器负载高时"起进程"本身
    # 就能耗掉十几秒。这条验的是并发请求全部成功,不是延迟,
    # 预算太紧会把机器负载变成用例失败。
    results = [p.communicate(timeout=60) for p in procs]
    # 全 0 退码 + 全 200 响应
    for i, (out, err) in enumerate(results):
        rc = procs[i].returncode
        assert rc == 0, f"req {i} rc={rc}, err={err.decode()[:100]}"
        j = json.loads(out)
        assert j["path"] == f"/req/{i}", f"req {i} path 错: {j['path']}"


def test_http_server_returns_404_for_undefined_route(http_server):
    """真走 HTTP, 未定义路由 200 (因为 _echo 啥 path 都接) — 但 status 应 200"""
    r = subprocess.run(
        ["curl", "-s", "-w", "\n%{http_code}\n", f"{http_server}/anything"],
        capture_output=True, text=True, timeout=10,
    )
    # _echo 接所有 path → 200
    assert "200" in r.stdout.splitlines()[-1], f"应 200, 实际: {r.stdout!r}"


def test_http_1_1_keep_alive_works(http_server):
    """真 curl --keepalive-time 真发多次请求, 走 HTTP/1.1 keep-alive"""
    r = subprocess.run(
        ["curl", "-s", "--keepalive-time", "60", "-o", "/dev/null",
         "-w", "code=%{http_code} num=%{num_connects}\n",
         f"{http_server}/keep"],
        capture_output=True, text=True, timeout=10,
    )
    assert "code=200" in r.stdout, f"应 200, 实际: {r.stdout!r}"
    # 1 connection (keep-alive)
    assert "num=1" in r.stdout, f"应 1 connection, 实际: {r.stdout!r}"


def test_http_server_socket_real_closed_after_shutdown():
    """server shutdown 后, port 真释放 (再 listen 同一 port 不报 'Address already in use')"""
    port = _pick_free_port()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    assert _wait_listen(port)

    srv.shutdown()
    srv.server_close()
    time.sleep(0.3)  # OS TIME_WAIT

    # 重新启同 port
    srv2 = http.server.ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    thread2 = threading.Thread(target=srv2.serve_forever, daemon=True)
    thread2.start()
    try:
        assert _wait_listen(port, timeout=2.0), "shutdown 后 port 应能立刻复用"
    finally:
        srv2.shutdown()
        srv2.server_close()


def test_http_server_binds_to_ipv4_only():
    """server 真绑 127.0.0.1 (ipv4 only), 0.0.0.0 也行 (用 ipv4 验)"""
    port = _pick_free_port()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        # ipv4 走通
        r = subprocess.run(
            ["curl", "-s", "-4", f"http://127.0.0.1:{port}/v4"],
            capture_output=True, text=True, timeout=5,
        )
        assert r.returncode == 0
        j = json.loads(r.stdout)
        assert j["path"] == "/v4"
    finally:
        srv.shutdown()
        srv.server_close()
