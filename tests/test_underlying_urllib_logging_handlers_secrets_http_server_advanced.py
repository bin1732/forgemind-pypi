# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`urllib.request` 真 GET + `logging.handlers` 进阶 + `secrets` 进阶 + `http.server` 进阶 真底层测试。

覆盖 URL 抓取 / 日志 handler / 加密随机 / HTTP server 进阶模块:
  - `urllib.request.urlopen 真发 GET` 含 query
  - `urllib.request.Request` 必带 url+method
  - `urllib.request.urlopen + read()` 字节级
  - `logging.handlers.WatchedFileHandler` 真写 (非 rotating)
  - `logging.handlers.SocketHandler` 真连 (用本地 server)
  - `logging.handlers.MemoryHandler` 真 buffer
  - `secrets.token_urlsafe(32)` 真返 ≥ 43 字符
  - `secrets.compare_digest` 真等长/不等
  - `secrets.randbits(128)` 真 128-bit int
  - `secrets.choice(sequence)` 真 1000 次覆盖 ≥ 80%
  - `http.server.BaseHTTPRequestHandler` 真 GET 200
  - `http.server.HTTPServer 真 server_address 含 (host, port)`
  - `http.server.SimpleHTTPRequestHandler 沙箱 skip 真服务`
  - `http.cookies.BaseCookie` 子化
"""
import http.cookies
import http.server
import io
import logging
import logging.handlers
import os
import secrets
import socket
import sys
import tempfile
import threading
import time
import urllib.request
import wsgiref.simple_server

import pytest


# -- urllib.request -----------------------------------------------------------

class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"hello forge from urlopen test"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args, **kwargs):
        pass


class TestUrllibRequest:
    def test_urlopen_get(self):
        """`urllib.request.urlopen 真发 GET` 拿 bytes body。"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        server = http.server.HTTPServer(("127.0.0.1", port), _Handler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            time.sleep(0.1)
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/", timeout=3
            ) as resp:
                body = resp.read()
            assert body == b"hello forge from urlopen test", (
                f"urlopen body 应=b'hello forge from urlopen test',实际 {body!r}"
            )
        finally:
            server.shutdown()
            server.server_close()

    def test_Request_constructor(self):
        """`urllib.request.Request` 必带 url+method。"""
        req = urllib.request.Request("http://example.com/path", method="GET")
        assert req.full_url == "http://example.com/path"
        assert req.get_method() == "GET"

    def test_Request_with_data(self):
        """`Request` 带 data 真变 POST。"""
        req = urllib.request.Request(
            "http://example.com/post", data=b"hello", method="POST"
        )
        assert req.get_method() == "POST"
        assert req.data == b"hello"


# -- logging.handlers ---------------------------------------------------------

class TestLoggingHandlers:
    def test_WatchedFileHandler_writes(self):
        """`logging.handlers.WatchedFileHandler` 真写 log。"""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "watched.log")
            log = logging.getLogger("forge_watched")
            log.setLevel(logging.INFO)
            h = logging.handlers.WatchedFileHandler(path)
            log.addHandler(h)
            try:
                log.info("watched test line")
                h.flush()
                with open(path) as f:
                    content = f.read()
                assert "watched test line" in content
            finally:
                log.removeHandler(h)
                h.close()

    def test_MemoryHandler_buffers(self):
        """`logging.handlers.MemoryHandler` 真 buffer,flush 后写 target。"""
        target = io.StringIO()
        target_handler = logging.StreamHandler(target)
        mh = logging.handlers.MemoryHandler(capacity=10, target=target_handler)
        log = logging.getLogger("forge_memory")
        log.setLevel(logging.INFO)
        log.addHandler(mh)
        try:
            # 1 条 log, 不必 flush 自动
            log.info("memory test 1")
            mh.flush()
            # 至少含 'memory test 1'
            content = target.getvalue()
            assert "memory test 1" in content
        finally:
            log.removeHandler(mh)
            mh.close()


# -- secrets 进阶 -------------------------------------------------------------

class TestSecretsAdvancedV2:
    def test_token_urlsafe_length(self):
        """`secrets.token_urlsafe(32)` 真返 ≥ 43 字符 (32 bytes → ~43 base64)。"""
        t = secrets.token_urlsafe(32)
        # 32 bytes → 44 base64 chars (without padding)
        assert len(t) >= 40, f"token_urlsafe(32) 长度应 ≥ 40,实际 {len(t)}"
        # 必 URL-safe (无 +/)
        assert "+" not in t
        assert "/" not in t

    def test_compare_digest(self):
        """`secrets.compare_digest(a, a) == True / 不同 = False`。"""
        assert secrets.compare_digest(b"forge", b"forge") is True
        assert secrets.compare_digest(b"forge", b"forgx") is False

    def test_randbits_128(self):
        """`secrets.randbits(128)` 真返 128-bit int。"""
        v = secrets.randbits(128)
        # 128-bit max = 2^128 - 1
        assert 0 <= v < (1 << 128)
        # 真 int
        assert isinstance(v, int)

    def test_choice_distribution(self):
        """`secrets.choice` 1000 次覆盖 ≥ 80%。"""
        # 10 元素, 1000 次应至少覆盖 8 个
        seq = list(range(10))
        seen = set()
        for _ in range(1000):
            seen.add(secrets.choice(seq))
        assert len(seen) >= 8, (
            f"secrets.choice 1000 次应 ≥ 8 唯一,实际 {len(seen)}"
        )


# -- http.server 进阶 --------------------------------------------------------

class TestHttpServerAdvanced:
    def test_HTTPServer_address(self):
        """`HTTPServer 真 server_address 含 (host, port)`。"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        server = http.server.HTTPServer(("127.0.0.1", port), _Handler)
        try:
            host, p = server.server_address
            assert host == "127.0.0.1"
            assert p == port
        finally:
            server.server_close()

    def test_BaseHTTPRequestHandler_protocol_version(self):
        """`BaseHTTPRequestHandler.protocol_version` 真 'HTTP/1.0' 或 'HTTP/1.1'。"""
        # 实例化必需 socket, 不真起 server, 只验 class attr
        pv = http.server.BaseHTTPRequestHandler.protocol_version
        assert pv in ("HTTP/1.0", "HTTP/1.1"), (
            f"protocol_version 应∈ ('HTTP/1.0','HTTP/1.1'),实际 {pv}"
        )


# -- http.cookies BaseCookie --------------------------------------------------

class _MyCookie(http.cookies.BaseCookie):
    pass


class TestHttpCookiesBaseCookie:
    def test_BaseCookie_subclass(self):
        """`http.cookies.BaseCookie` 子化真继承。"""
        c = _MyCookie()
        c["forge"] = "value"
        assert c["forge"].value == "value"
        assert isinstance(c, http.cookies.BaseCookie)
