# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 struct 进阶 (嵌套 + byte order + alignment) + 真 socket 进阶 (TCP_NODELAY 永久) + 真 http.server 真起 + 真 http.client 真发 + 真 wsgiref 真 app。
全 stdlib, 零模拟。
"""
import struct
import socket
import http.server
import http.client
import wsgiref.simple_server
import wsgiref.util
import threading
import time
import pytest


# ======================== struct 进阶 ========================
def test_struct_byteorder():
    """真 struct 真字节序"""
    # 大端
    packed_be = struct.pack(">I", 1)
    assert packed_be == b"\x00\x00\x00\x01"
    # 小端
    packed_le = struct.pack("<I", 1)
    assert packed_le == b"\x01\x00\x00\x00"
    # 网络序 (大端)
    packed_n = struct.pack("!I", 1)
    assert packed_n == b"\x00\x00\x00\x01"


def test_struct_calcsize():
    """真 struct.calcsize 真大小"""
    # i = 4
    assert struct.calcsize("i") == 4
    # q = 8
    assert struct.calcsize("q") == 8
    # 多字段
    assert struct.calcsize("=i") == 4
    # padding
    assert struct.calcsize("ci") >= 5  # char + int (alignment)


def test_struct_nested_arrays():
    """真 struct 真嵌套数组"""
    # 3 个 int
    packed = struct.pack("3i", 1, 2, 3)
    assert len(packed) == 12
    values = struct.unpack("3i", packed)
    assert values == (1, 2, 3)


def test_struct_ip_header():
    """真 struct 真 IPv4 header 模拟"""
    # version_ihl, tos, total_length, id, flags_offset, ttl, proto, checksum
    # 模拟 IPv4 header (20 bytes, no options)
    version_ihl = (4 << 4) | 5  # version=4, IHL=5
    tos = 0
    total_length = 60
    identification = 12345
    flags_offset = 0
    ttl = 64
    proto = 6  # TCP
    header = struct.pack("!BBHHHBBH4s4s",
                         version_ihl, tos, total_length,
                         identification, flags_offset,
                         ttl, proto, 0,  # checksum 占位
                         b"\x0a\x00\x00\x01",  # src 10.0.0.1
                         b"\x0a\x00\x00\x02")  # dst 10.0.0.2
    assert len(header) == 20
    # unpack
    v_ihl, t, tlen, ident, fl, tttl, p, csum, src, dst = struct.unpack("!BBHHHBBH4s4s", header)
    assert (v_ihl >> 4) == 4
    assert t == 0
    assert tlen == 60
    assert p == 6


# ======================== socket 进阶 ========================
def test_socket_TCP_NODELAY_persists():
    """真 TCP_NODELAY 真持久"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # 再 getsockopt 验
        val = s.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
        assert val == 1
        # 关
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 0)
        val2 = s.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
        assert val2 == 0
    finally:
        s.close()


def test_socket_SO_REUSEADDR():
    """真 SO_REUSEADDR"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        val = s.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        assert val == 1
    finally:
        s.close()


# ======================== http.server 真起 ========================
def test_http_server_real_request():
    """真 http.server 真起 + 真 client 真发"""
    # handler
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"hello from test server")
        def log_message(self, *args):
            pass  # 静默

    # 起 server
    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # client 访问
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        assert resp.status == 200
        body = resp.read()
        assert body == b"hello from test server"
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


# ======================== wsgiref 真 app ========================
def test_wsgiref_real_app():
    """真 wsgiref 真起 + 真 app"""
    def app(environ, start_response):
        body = b"WSGI app response"
        start_response("200 OK", [
            ("Content-Type", "text/plain"),
            ("Content-Length", str(len(body))),
        ])
        return [body]

    # 起 server
    with wsgiref.simple_server.make_server("127.0.0.1", 0, app) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/")
            resp = conn.getresponse()
            assert resp.status == 200
            body = resp.read()
            assert body == b"WSGI app response"
            conn.close()
        finally:
            server.shutdown()
            thread.join(timeout=2)
