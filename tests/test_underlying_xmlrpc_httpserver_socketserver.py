# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`xmlrpc` / `http.server` / `socketserver` 真底层测试。

- xmlrpc:真的起一个 XML-RPC 服务并调用
- http.server:真的起一个 HTTP 服务,用真实请求访问
- socketserver:真的起一个 TCP 服务并交换数据

覆盖 xmlrpc 5 + http.server 5 + socketserver 5 + 真底层测试。
"""

import http.client
import socket
import socketserver
import threading
import time
import xmlrpc.client
import xmlrpc.server
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


# ======================== xmlrpc ========================


def _add(a, b):
    """给远程调用的加法。"""
    return a + b


def _echo(text):
    """原样返回文本。"""
    return text


class _QuietXMLRPCServer(xmlrpc.server.SimpleXMLRPCServer):
    """不往标准输出写日志。"""

    def log_message(self, format, *args):  # noqa: A002 - 与基类同名
        pass


@pytest.fixture
def xmlrpc_server():
    """真的起一个 XML-RPC 服务。"""
    server = _QuietXMLRPCServer(("127.0.0.1", 0), logRequests=False,
                                allow_none=True)
    server.register_function(_add, "add")
    server.register_function(_echo, "echo")
    server.register_introspection_functions()
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{port}/", server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestXmlrpc:
    """XML-RPC 调用"""

    def test_server_binds_local_port(self, xmlrpc_server):
        """服务绑在本机随机端口"""
        url, server = xmlrpc_server
        assert url.startswith("http://127.0.0.1:")
        assert server.server_address[1] > 0

    def test_call_add(self, xmlrpc_server):
        """真的远程调用加法"""
        url, server = xmlrpc_server
        proxy = xmlrpc.client.ServerProxy(url)
        assert proxy.add(2, 3) == 5

    def test_call_echo(self, xmlrpc_server):
        """真的远程回传文本"""
        url, server = xmlrpc_server
        proxy = xmlrpc.client.ServerProxy(url)
        assert proxy.echo("forge") == "forge"

    def test_call_with_none(self, xmlrpc_server):
        """两端都允许空值时能传空"""
        url, server = xmlrpc_server
        proxy = xmlrpc.client.ServerProxy(url, allow_none=True)
        assert proxy.echo(None) is None

    def test_call_none_without_allow_none(self, xmlrpc_server):
        """客户端没放开时,空值传不过去"""
        url, server = xmlrpc_server
        proxy = xmlrpc.client.ServerProxy(url)
        with pytest.raises(TypeError):
            proxy.echo(None)

    def test_introspection(self, xmlrpc_server):
        """自省接口可用"""
        url, server = xmlrpc_server
        proxy = xmlrpc.client.ServerProxy(url)
        methods = proxy.system.listMethods()
        assert "add" in methods
        assert "echo" in methods

    def test_unknown_method_raises(self, xmlrpc_server):
        """调用不存在的接口报错"""
        url, server = xmlrpc_server
        proxy = xmlrpc.client.ServerProxy(url)
        with pytest.raises(xmlrpc.client.Fault):
            proxy.no_such_method()


# ======================== http.server ========================


class _Handler(BaseHTTPRequestHandler):
    """回固定内容的处理器。"""

    def do_GET(self):  # noqa: N802 - 与基类同名
        """回一个带自定义头的响应。"""
        if self.path == "/missing":
            self.send_error(404, "forge not found")
            return
        body = b"forge-http-body"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Forge", "yes")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002 - 与基类同名
        pass


@pytest.fixture
def http_server():
    """真的起一个 HTTP 服务。"""
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield host, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestHttpServer:
    """HTTP 服务"""

    def test_server_binds_local_port(self, http_server):
        """服务绑在本机随机端口"""
        host, port = http_server
        assert host == "127.0.0.1"
        assert port > 0

    def test_get_returns_body(self, http_server):
        """真的取回响应体"""
        host, port = http_server
        conn = http.client.HTTPConnection(host, port, timeout=10)
        try:
            conn.request("GET", "/")
            response = conn.getresponse()
            assert response.status == 200
            assert response.read() == b"forge-http-body"
        finally:
            conn.close()

    def test_get_returns_custom_header(self, http_server):
        """自定义响应头可读"""
        host, port = http_server
        conn = http.client.HTTPConnection(host, port, timeout=10)
        try:
            conn.request("GET", "/")
            response = conn.getresponse()
            assert response.getheader("X-Forge") == "yes"
            assert response.getheader("Content-Type") == "text/plain"
        finally:
            conn.close()

    def test_missing_path_returns_404(self, http_server):
        """未知路径返回 404"""
        host, port = http_server
        conn = http.client.HTTPConnection(host, port, timeout=10)
        try:
            conn.request("GET", "/missing")
            response = conn.getresponse()
            assert response.status == 404
            response.read()
        finally:
            conn.close()

    def test_raw_socket_request(self, http_server):
        """用裸套接字发请求也拿到响应"""
        host, port = http_server
        with socket.create_connection((host, port), timeout=10) as sock:
            sock.sendall(b"GET / HTTP/1.0\r\n\r\n")
            chunks = []
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
        response = b"".join(chunks)
        assert b"200" in response
        assert b"forge-http-body" in response


# ======================== socketserver ========================


class _EchoHandler(socketserver.StreamRequestHandler):
    """把收到的数据原样送回。"""

    def handle(self):
        """读一行再写回去。"""
        line = self.rfile.readline()
        if not line:
            return
        self.wfile.write(b"echo:" + line)


class _ThreadedTCPServer(socketserver.ThreadingTCPServer):
    """每个连接一个线程。"""

    allow_reuse_address = True
    daemon_threads = True


@pytest.fixture
def tcp_server():
    """真的起一个 TCP 服务。"""
    server = _ThreadedTCPServer(("127.0.0.1", 0), _EchoHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, host, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestSocketserver:
    """TCP 服务"""

    def test_server_binds_local_port(self, tcp_server):
        """服务绑在本机随机端口"""
        server, host, port = tcp_server
        assert host == "127.0.0.1"
        assert port > 0

    def test_connection_is_echoed(self, tcp_server):
        """连上去发的数据被送回"""
        server, host, port = tcp_server
        with socket.create_connection((host, port), timeout=10) as sock:
            sock.sendall(b"forge\n")
            data = sock.recv(1024)
        assert data == b"echo:forge\n"

    def test_multiple_connections(self, tcp_server):
        """多个连接各自独立"""
        server, host, port = tcp_server
        for index in range(3):
            with socket.create_connection((host, port), timeout=10) as sock:
                sock.sendall(f"n{index}\n".encode())
                assert sock.recv(1024) == f"echo:n{index}\n".encode()

    def test_server_address_type(self, tcp_server):
        """服务地址是二元组"""
        server, host, port = tcp_server
        assert isinstance(server.server_address, tuple)
        assert len(server.server_address) == 2

    def test_request_queue_size(self, tcp_server):
        """请求队列长度可读"""
        server, host, port = tcp_server
        assert server.request_queue_size >= 1
