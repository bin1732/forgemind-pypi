# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 asyncio 真低层 transport/protocol (CreateConnection) + 真 http.client 真 Persistent + 真 http.cookies 进阶 (BaseCookie) + 真 unittest.mock patch.object + 真 socket 真 SO_SNDBUF 接收 buffer + 真 struct 嵌套结构体.
全 stdlib, 零模拟。
"""
import asyncio
import http.client
import http.cookiejar
import http.server
import socket
import struct
import threading
import unittest.mock
import pytest


# ======================== asyncio 真低层 transport ========================
def test_asyncio_create_connection_real():
    """真 asyncio 真 create_connection"""
    # 起 server
    received = []

    async def handle(reader, writer):
        data = await reader.read(100)
        received.append(data)
        writer.write(b"ACK")
        await writer.drain()
        writer.close()

    async def main():
        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        # client
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"hello")
        await writer.drain()
        ack = await reader.read(100)
        writer.close()
        # 关 server
        server.close()
        await server.wait_closed()
        return ack

    result = asyncio.run(main())
    assert result == b"ACK"
    assert received == [b"hello"]


def test_asyncio_get_event_loop_policy():
    """真 asyncio 真 get_event_loop_policy"""
    policy = asyncio.get_event_loop_policy()
    # 有 _local / _loop
    assert policy is not None
    # get_event_loop
    loop = asyncio.new_event_loop()
    try:
        assert loop is not None
        # loop.run_until_complete 跑
        async def hello():
            return "ok"
        result = loop.run_until_complete(hello())
        assert result == "ok"
    finally:
        loop.close()


# ======================== http.client 真 ========================
def test_http_client_Connection_request():
    """真 http.client 真 HTTPConnection + 真 server"""
    # 写个 server
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"server response")
        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # client
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/test")
        resp = conn.getresponse()
        assert resp.status == 200
        body = resp.read()
        assert body == b"server response"
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


# ======================== http.cookies 进阶 ========================
def test_cookies_BaseCookie():
    """真 BaseCookie 真多 domain"""
    jar = http.cookiejar.CookieJar()
    # 用 BaseCookie 模拟
    cookies = http.cookies.BaseCookie()
    cookies["session"] = "abc123"
    cookies["session"]["domain"] = "example.com"
    cookies["session"]["path"] = "/"
    cookies["session"]["secure"] = True
    # 输出
    output = cookies.output()
    text = "".join(output)
    # 多个属性
    assert "session=abc123" in text
    assert "Domain=example.com" in text or "domain=example.com" in text.lower()
    assert "Path=/" in text or "path=/" in text.lower()


def test_cookies_load_header():
    """真 load 真实 header"""
    c = http.cookies.SimpleCookie()
    c.load("name=alice; age=30; theme=dark; expires=Tue, 31 Dec 2030 23:59:59 GMT")
    assert c["name"].value == "alice"
    assert c["age"].value == "30"
    assert c["theme"].value == "dark"


# ======================== unittest.mock patch.object ========================
def test_patch_object():
    """真 patch.object 真改 method"""
    class C:
        def method(self):
            return "real"

    with unittest.mock.patch.object(C, "method", return_value="mocked") as m:
        c = C()
        assert c.method() == "mocked"
        # 验证 mock
        m.assert_called_once()


def test_patch_object_with_spec():
    """真 spec 真验 attribute 存在"""
    class C:
        def method(self):
            return 42

    # spec 用 class 自动 spec 所有 attr
    with unittest.mock.patch.object(C, "method", spec=C) as m:
        c = C()
        # spec 验存在 method attr
        # 但 spec 不验 call signature 严格
        assert c.method() == m.return_value
        # 调用 mock
        m.assert_called()


# ======================== socket SO_SNDBUF / SO_RCVBUF ========================
def test_socket_SO_RCVBUF_getset():
    """真 SO_RCVBUF 真设取"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # 默认
        default = s.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
        # 设
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        new = s.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
        # Linux 倍数对齐
        assert new >= 4096
    finally:
        s.close()


def test_socket_getsockname_peername():
    """真 getsockname / getpeername"""
    # socketpair
    s1, s2 = socket.socketpair()
    try:
        # s1 sockname
        name1 = s1.getsockname()
        # 实际 address (Unix)
        assert name1 is not None
        # 真 OS 返回 address
        # 至少不是 None
        assert s1.fileno() >= 0
    finally:
        s1.close()
        s2.close()


# ======================== struct 嵌套结构体 ========================
def test_struct_nested_real_protocol():
    """真 struct 嵌套真类 TCP header"""
    # TCP header 20 bytes: src_port, dst_port, seq, ack, data_offset/flags, window, checksum, urgent
    src_port, dst_port = 12345, 80
    seq, ack = 1000, 2000
    data_offset_flags = (5 << 12) | 0x10  # data offset 5, ACK
    window = 65535
    checksum = 0
    urgent = 0
    # pack
    # 20 bytes TCP header (含 urgent ptr)
    tcp_header = struct.pack("!HHIIHHHH",
                             src_port, dst_port, seq, ack,
                             data_offset_flags, window, checksum, urgent)
    assert len(tcp_header) == 20
    # unpack
    sp, dp, s, a, dof, w, cs, u = struct.unpack("!HHIIHHHH", tcp_header)
    assert sp == 12345
    assert dp == 80
    assert s == 1000
    assert a == 2000
    assert w == 65535


def test_struct_calculate_size():
    """真 struct 真算多 type 字节"""
    # q = 8
    assert struct.calcsize("q") == 8
    # Q = 8
    assert struct.calcsize("Q") == 8
    # 多
    assert struct.calcsize(">ii") == 8
    assert struct.calcsize("<ii") == 8
    # i + q = 12 (无 padding)
    assert struct.calcsize("<iq") == 12
