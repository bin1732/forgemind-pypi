# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`xml.etree.ElementTree` XPath + `http.cookies` + `socketserver` 进阶 + `wsgiref.util` 真底层测试。

覆盖 XML XPath / Cookie / socket server / WSGI utility 模块:
  - `ET.fromstring + findall` 真 XPath 查
  - `ET.fromstring + findall('item[@id]')` 真 attribute filter
  - `ET.fromstring + findtext('item')` 真取 text
  - `ET.QName` 真建 qualified name
  - `ET.iterparse` 真流式解析
  - `ET.register_namespace` 真注册
  - `http.cookies.SimpleCookie` 真解析 'a=1; b=2'
  - `http.cookies.Morsel 真 access morsel attrs`
  - `http.cookies.SimpleCookie().output()` 真生成 Set-Cookie header
  - `socketserver.TCPServer` 真启
  - `socketserver.ThreadingMixIn` 真多线程
  - `socketserver.StreamRequestHandler` 子化
  - `socketserver.BaseRequestHandler` 子化
  - `wsgiref.util.application_uri` 真返 URI
  - `wsgiref.util.request_uri` 真返 path+query
  - `wsgiref.util.guess_scheme` 真判 wsgi/https
  - `wsgiref.util.shift_path_info` 真取 path segment
"""
import http.cookies
import io
import os
import socket
import socketserver
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
import wsgiref.util

import pytest


# -- xml.etree.ElementTree XPath -----------------------------------------------

class TestETXPath:
    def test_findall(self):
        """`ET.fromstring + findall('item')` 真查所有 item。"""
        root = ET.fromstring("<root><item>1</item><item>2</item></root>")
        items = root.findall("item")
        assert len(items) == 2
        assert items[0].text == "1"
        assert items[1].text == "2"

    def test_findall_attribute_filter(self):
        """`ET.findall('item[@id]')` 真 attribute 过滤。"""
        root = ET.fromstring(
            '<root><item id="1">a</item><item id="2">b</item><item>x</item></root>'
        )
        with_id = root.findall("item[@id]")
        assert len(with_id) == 2
        # 第一个 id=1
        assert with_id[0].get("id") == "1"

    def test_findtext(self):
        """`ET.findtext('item')` 真取第一个 item text。"""
        root = ET.fromstring("<root><item>forge</item><item>v2026</item></root>")
        text = root.findtext("item")
        assert text == "forge"

    def test_QName(self):
        """`ET.QName('ns', 'tag')` 真建 qualified name。"""
        qn = ET.QName("http://example.com/ns", "tag")
        # 含 {ns}tag
        assert "tag" in str(qn)
        assert "{http://example.com/ns}" in str(qn)

    def test_iterparse(self):
        """`ET.iterparse(file)` 真流式解析。"""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "data.xml")
            with open(path, "wb") as f:
                f.write(b"<root><a>1</a><b>2</b></root>")
            events = []
            for event, elem in ET.iterparse(path):
                events.append((event, elem.tag))
        # 必含 'end' 事件 for 'a' and 'b'
        assert any(e == "end" and t == "a" for e, t in events)
        assert any(e == "end" and t == "b" for e, t in events)

    def test_register_namespace(self):
        """`ET.register_namespace('ns', 'http://...')` 真注册。"""
        ET.register_namespace("forge", "http://forgemind.test/ns")
        # 之后 tostring 必含 xmlns:forge
        root = ET.Element("{http://forgemind.test/ns}item")
        out = ET.tostring(root)
        assert b"forge" in out


# -- http.cookies --------------------------------------------------------------

class TestHttpCookies:
    def test_SimpleCookie_parse(self):
        """`SimpleCookie().load('a=1; b=2')` 真解析。"""
        c = http.cookies.SimpleCookie()
        c.load("a=1; b=2")
        assert c["a"].value == "1"
        assert c["b"].value == "2"

    def test_SimpleCookie_morsel_attrs(self):
        """`SimpleCookie() 真有 morsel 含 value+key+domain+path+expires`。"""
        c = http.cookies.SimpleCookie()
        c["forge"] = "value123"
        m = c["forge"]
        # 必含 value
        assert m.value == "value123"
        # 必含 key
        assert m.key == "forge"
        # 必含 domain/path/expires attr (Morsel)
        assert m["domain"] == "" or "domain" in m

    def test_SimpleCookie_output(self):
        """`SimpleCookie().output()` 真生成 Set-Cookie header。"""
        c = http.cookies.SimpleCookie()
        c["a"] = "1"
        out = c.output()
        # 必含 'a=1' and 'Set-Cookie'
        assert "a=1" in out
        assert "Set-Cookie" in out


# -- socketserver --------------------------------------------------------------

class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b"hello forge from socketserver\n")


class _BaseHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.sendall(b"from base handler\n")


class TestSocketserver:
    def test_TCPServer_threaded(self):
        """`socketserver.ThreadingMixIn + TCPServer` 真启多线程。"""
        # 用 ThreadingMixIn
        class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
            daemon_threads = True
            allow_reuse_address = True

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        server = ThreadedServer(("127.0.0.1", port), _Handler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            time.sleep(0.1)
            s = socket.socket()
            s.connect(("127.0.0.1", port))
            data = s.recv(1024)
            s.close()
            assert data == b"hello forge from socketserver\n"
        finally:
            server.shutdown()
            server.server_close()

    def test_StreamRequestHandler(self):
        """`StreamRequestHandler.handle` 子化真 self.wfile.write。"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        server = socketserver.TCPServer(("127.0.0.1", port), _Handler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            time.sleep(0.1)
            c = socket.socket()
            c.connect(("127.0.0.1", port))
            data = b""
            while not data.endswith(b"\n"):
                data += c.recv(1024)
            c.close()
            assert data == b"hello forge from socketserver\n"
        finally:
            server.shutdown()
            server.server_close()

    def test_BaseRequestHandler(self):
        """`BaseRequestHandler.handle` 子化真 self.request.sendall。"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        server = socketserver.TCPServer(("127.0.0.1", port), _BaseHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            time.sleep(0.1)
            c = socket.socket()
            c.connect(("127.0.0.1", port))
            data = c.recv(1024)
            c.close()
            assert data == b"from base handler\n"
        finally:
            server.shutdown()
            server.server_close()


# -- wsgiref.util -------------------------------------------------------------

class TestWsgirefUtil:
    def test_application_uri(self):
        """`wsgiref.util.application_uri(environ)` 真返 URI。"""
        environ = {
            "wsgi.url_scheme": "http",
            "HTTP_HOST": "example.com",
            "SCRIPT_NAME": "/app",
        }
        uri = wsgiref.util.application_uri(environ)
        assert uri == "http://example.com/app", (
            f"application_uri 应='http://example.com/app',实际 {uri!r}"
        )

    def test_request_uri(self):
        """`wsgiref.util.request_uri(environ)` 真返 path+query (需 wsgi.url_scheme)。"""
        environ = {
            "PATH_INFO": "/api/test",
            "QUERY_STRING": "a=1&b=2",
            "SCRIPT_NAME": "",
            "wsgi.url_scheme": "http",
            "HTTP_HOST": "localhost",
        }
        uri = wsgiref.util.request_uri(environ)
        # 必含 /api/test
        assert "/api/test" in uri
        # 必含 query
        assert "a=1" in uri

    def test_guess_scheme_https(self):
        """`wsgiref.util.guess_scheme(environ)` 真判 https。"""
        environ_https = {"HTTPS": "on"}
        environ_http = {"HTTPS": "off"}
        assert wsgiref.util.guess_scheme(environ_https) == "https"
        assert wsgiref.util.guess_scheme(environ_http) == "http"

    def test_shift_path_info(self):
        """`wsgiref.util.shift_path_info(environ)` 真取首个 path segment。"""
        environ = {"PATH_INFO": "/a/b/c", "SCRIPT_NAME": ""}
        first = wsgiref.util.shift_path_info(environ)
        assert first == "a"
        # 之后 path 变 /b/c
        assert environ["PATH_INFO"] == "/b/c"
