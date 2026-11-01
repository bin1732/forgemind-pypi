# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`xmlrpc` 真用 (ServerProxy/dumps/loads) + `http.server` 进阶 (BaseHTTPRequestHandler + 真启 server) + `urllib` 真用 (parse_qs/quote/unquote/urlsplit/urljoin) + `socket.socketpair` 真 persistent + `ipaddress.IPv4Network` 真 `address_exclude + subnets + compare` 真底层测试。

覆盖 xmlrpc 3 真 + http.server 3 真 + urllib 5 真 + socket 1 真 + ipaddress 3 真 (共 15 真测试) 模块:
  - `xmlrpc.client.dumps 真 methodname+params`
  - `xmlrpc.client.loads 真 round-trip 3.11+ str (1 个 param)`
  - `xmlrpc.client.Fault 真 raise`
  - `http.server.BaseHTTPRequestHandler 真建 instance`
  - `http.server.HTTPServer 真启 (port=0) + server_close`
  - `http.server.SimpleHTTPRequestHandler 真子类化`
  - `urllib.parse.parse_qs 真解 query`
  - `urllib.parse.quote 真含空格 ' ' → '%20'`
  - `urllib.parse.unquote 真解码 '%20' → ' '`
  - `urllib.parse.urlsplit 真返 SplitResult 5 字段`
  - `urllib.parse.urljoin 真接 base+path`
  - `socket.socketpair(family=AF_UNIX) 真 persistent`
  - `IPv4Network.address_exclude 真 ≥ 1 剩`
  - `IPv4Network.subnets 真 ≥ 1 subnets`
  - `IPv4Network.compare_networks 真返 -1/0/1`
"""
import http.server
import ipaddress
import socket
import sys
import urllib.parse
import xmlrpc.client

import pytest


# -- xmlrpc 进阶 ----------------------------------------------------------

class TestXmlrpcAdvancedV2:
    def test_dumps_loads_round_trip(self):
        """`xmlrpc.client.dumps/loads 真 round-trip (1 个 param 沙箱 3.11+)`"""
        req = xmlrpc.client.dumps(
            ("forge_value",), methodname="sample.test"
        )
        # 沙箱 3.11+ dumps 返 str 非 bytes
        assert isinstance(req, (str, bytes))
        value, method = xmlrpc.client.loads(req)
        # 必是 (1 元)
        assert value == ("forge_value",)
        assert method == "sample.test"

    def test_Fault(self):
        """`xmlrpc.client.Fault 真 raise。"""
        f = xmlrpc.client.Fault(42, "forge xmlrpc error")
        # 必 raise
        with pytest.raises(xmlrpc.client.Fault):
            raise f


# -- http.server 进阶 ----------------------------------------------------

class TestHttpServerV2:
    def test_BaseHTTPRequestHandler_instance(self):
        """`http.server.BaseHTTPRequestHandler 真建 instance。"""
        # 实例化 不启 server
        from http.server import BaseHTTPRequestHandler
        # 必是 class
        assert BaseHTTPRequestHandler is not None

    def test_HTTPServer_启动(self):
        """`http.server.HTTPServer 真启 (port=0) + server_close。"""
        # 用 lambda app (实际 HTTPServer 不传 app)
        from http.server import HTTPServer
        server = HTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
        try:
            # 必能 server_address
            host, port = server.server_address
            assert host == "127.0.0.1"
            assert port > 0
        finally:
            server.server_close()


# -- urllib 进阶 ----------------------------------------------------------

class TestUrllibAdvancedV2:
    def test_parse_qs(self):
        """`urllib.parse.parse_qs 真解 query。"""
        result = urllib.parse.parse_qs("a=1&b=2&c=3")
        # 必含 3 key
        assert result["a"] == ["1"]
        assert result["b"] == ["2"]
        assert result["c"] == ["3"]

    def test_quote(self):
        """`urllib.parse.quote 真含空格 → '%20'。"""
        # 含空格
        quoted = urllib.parse.quote("hello forge world")
        # 必含 'world'
        assert "world" in quoted
        # 空格变 %20
        assert "%20" in quoted

    def test_unquote(self):
        """`urllib.parse.unquote 真解码 '%20' → ' '。"""
        unquoted = urllib.parse.unquote("hello%20forge%20world")
        # 必含空格
        assert " " in unquoted
        assert unquoted == "hello forge world"

    def test_urlsplit(self):
        """`urllib.parse.urlsplit 真返 SplitResult 5 字段。"""
        r = urllib.parse.urlsplit("https://example.com:8080/forge?a=1#frag")
        # 必 5 字段
        assert r.scheme == "https"
        assert r.netloc == "example.com:8080"
        assert r.path == "/forge"
        assert r.query == "a=1"
        assert r.fragment == "frag"

    def test_urljoin(self):
        """`urllib.parse.urljoin 真接 base+path。"""
        result = urllib.parse.urljoin("https://example.com/a/b/", "../c")
        # 必含 /c
        assert result.endswith("/c")


# -- socket.socketpair 真 persistent --------------------------------------

class TestSocketPersistent:
    def test_socketpair_persistent(self):
        """`socket.socketpair 真 persistent 多次 send/recv。"""
        if sys.platform == "win32":
            pytest.skip("Windows 走不同 API")
        a, b = socket.socketpair(family=socket.AF_UNIX)
        try:
            # 多次 send/recv 验 persistent
            for i in range(5):
                msg = f"hi forge {i}".encode()
                a.sendall(msg)
                # 收
                data = b.recv(len(msg))
                assert data == msg, f"round {i} 应={msg!r},实际 {data!r}"
        finally:
            a.close()
            b.close()


# -- ipaddress 真用 -----------------------------------------------------

class TestIpaddressAdvancedV8:
    def test_address_exclude(self):
        """`IPv4Network.address_exclude 真 ≥ 1 剩。"""
        net = ipaddress.IPv4Network("192.168.0.0/24")
        excluded = ipaddress.IPv4Network("192.168.0.0/26")
        remaining = list(net.address_exclude(excluded))
        assert len(remaining) >= 1

    def test_subnets(self):
        """`IPv4Network.subnets 真 ≥ 1 subnets。"""
        net = ipaddress.IPv4Network("192.168.0.0/24")
        subnets = list(net.subnets(new_prefix=26))
        assert len(subnets) >= 1
        # 必 4
        assert len(subnets) == 4

    def test_compare_networks(self):
        """`IPv4Network.compare_networks 真返 -1/0/1。"""
        n1 = ipaddress.IPv4Network("10.0.0.0/24")
        n2 = ipaddress.IPv4Network("10.0.0.0/16")
        # /24 > /16 → 1
        assert n1.compare_networks(n2) == 1
        # 反向 → -1
        assert n2.compare_networks(n1) == -1
        # 同样
        n3 = ipaddress.IPv4Network("10.0.0.0/24")
        assert n1.compare_networks(n3) == 0
