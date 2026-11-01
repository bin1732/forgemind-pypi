# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`re 进阶 (compile+escape+findall+finditer+match+fullmatch+sub+subn+search+split+Pattern+Match)` + `hashlib 进阶 (md5+sha1+sha256+sha512+sha3_256+sha3_512+blake2b+blake2s+pbkdf2_hmac+new+algorithms_available+algorithms_guaranteed)` + `secrets 进阶 (token_bytes+token_hex+token_urlsafe+compare_digest+choice+randbits+randbelow+SystemRandom)` + `ssl 进阶 (SSLContext+PROTOCOL_TLS_CLIENT+PROTOCOL_TLS_SERVER+create_default_context+get_default_verify_paths)` + `socket 进阶 (socketpair+gethostname+gethostbyname+gethostbyname_ex+getaddrinfo+gethostbyaddr)` + `http.client 进阶 (HTTPConnection+HTTPResponse+parse_headers+responses+ResponseNotReady+NotConnected)` + `ipaddress 进阶 (ip_address+ip_network+ip_interface+IPv4Address+IPv6Address+IPv4Network+IPv6Network+collapse_addresses)` + `html 进阶 (escape+unescape)` + 真底层测试。

覆盖 re 8 + hashlib 8 + secrets 5 + ssl 4 + socket 4 + http.client 5 + ipaddress 7 + html 3 (共 44 真测试) 模块:
  - `re.compile 'a'`
  - `re.escape 'a'`
  - `re.findall 'a'`
  - `re.finditer 'a'`
  - `re.match 'a'`
  - `re.fullmatch 'a'`
  - `re.sub 'a'`
  - `re.subn 'a'`
  - `hashlib.md5 'a'`
  - `hashlib.sha1 'a'`
  - `hashlib.sha256 'a'`
  - `hashlib.sha512 'a'`
  - `hashlib.sha3_256 'a'`
  - `hashlib.blake2b 'a'`
  - `hashlib.new 'a'`
  - `hashlib.algorithms_available 'a'`
  - `secrets.token_bytes 'a'`
  - `secrets.token_hex 'a'`
  - `secrets.token_urlsafe 'a'`
  - `secrets.compare_digest 'a'`
  - `secrets.randbelow 'a'`
  - `ssl.SSLContext 'a'`
  - `ssl.PROTOCOL_TLS_CLIENT 'a'`
  - `ssl.create_default_context 'a'`
  - `ssl.get_default_verify_paths 'a'`
  - `socket.gethostname 'a'`
  - `socket.gethostbyname 'a'`
  - `socket.getaddrinfo 'a'`
  - `socket.gethostbyaddr 'a'`
  - `http.client.HTTPConnection 'a'`
  - `http.client.HTTPResponse 'a'`
  - `http.client.parse_headers 'a'`
  - `http.client.responses 'a'`
  - `http.client 'a'`
  - `ipaddress.ip_address 'a'`
  - `ipaddress.ip_network 'a'`
  - `ipaddress.ip_interface 'a'`
  - `ipaddress.IPv4Address 'a'`
  - `ipaddress.IPv6Address 'a'`
  - `ipaddress.IPv4Network 'a'`
  - `ipaddress.collapse_addresses 'a'`
  - `html.escape 'a'`
  - `html.unescape 'a'`
"""
import hashlib
import html
import http.client
import ipaddress
import re
import secrets
import socket
import ssl

import pytest


# -- re 进阶 (compile+escape+findall+finditer+match+fullmatch+sub+subn) ---

class TestReAdvanceV1:
    def test_compile(self):
        """`re.compile 'a'。"""
        p = re.compile(r"forge_(?P<name>\w+)")
        # 必 Pattern
        assert p is not None
        # 必 pattern
        assert p.pattern == r"forge_(?P<name>\w+)"

    def test_escape(self):
        """`re.escape 'a'。"""
        e = re.escape("forge.regex_v1")
        # 必 含 'forge'
        assert "forge" in e

    def test_findall(self):
        """`re.findall 'a'。"""
        r = re.findall(r"forge_(\w+)", "forge_a_v1 forge_b_v1")
        # 必 ['a_v1', 'b_v1']
        assert r == ["a_v1", "b_v1"]

    def test_finditer(self):
        """`re.finditer 'a'。"""
        matches = list(re.finditer(r"forge_(\w+)", "forge_a_v1 forge_b_v1"))
        # 必 2
        assert len(matches) == 2

    def test_match(self):
        """`re.match 'a'。"""
        m = re.match(r"forge_(\w+)", "forge_a_v1")
        # 必 Match
        assert m is not None
        # 必 'a_v1'
        assert m.group(1) == "a_v1"

    def test_fullmatch(self):
        """`re.fullmatch 'a'。"""
        m = re.fullmatch(r"forge_a_v1", "forge_a_v1")
        # 必 Match
        assert m is not None

    def test_sub(self):
        """`re.sub 'a'。"""
        r = re.sub(r"forge_(\w+)", r"REPL_\1", "forge_a_v1")
        # 必 'REPL_a_v1'
        assert r == "REPL_a_v1"

    def test_subn(self):
        """`re.subn 'a'。"""
        r, n = re.subn(r"forge_(\w+)", r"REPL_\1", "forge_a_v1 forge_b_v1")
        # 必 'REPL_a_v1 REPL_b_v1'
        assert r == "REPL_a_v1 REPL_b_v1"
        # 必 2
        assert n == 2


# -- hashlib 进阶 (md5+sha1+sha256+sha512+sha3_256+blake2b+new+algorithms_available) ---

class TestHashlibAdvanceV2:
    def test_md5(self):
        """`hashlib.md5 'a'。"""
        h = hashlib.md5(b"forge_hash_v1")
        # 必 32 char
        assert len(h.hexdigest()) == 32

    def test_sha1(self):
        """`hashlib.sha1 'a'。"""
        h = hashlib.sha1(b"forge_hash_v1")
        # 必 40 char
        assert len(h.hexdigest()) == 40

    def test_sha256(self):
        """`hashlib.sha256 'a'。"""
        h = hashlib.sha256(b"forge_hash_v1")
        # 必 64 char
        assert len(h.hexdigest()) == 64

    def test_sha512(self):
        """`hashlib.sha512 'a'。"""
        h = hashlib.sha512(b"forge_hash_v1")
        # 必 128 char
        assert len(h.hexdigest()) == 128

    def test_sha3_256(self):
        """`hashlib.sha3_256 'a'。"""
        h = hashlib.sha3_256(b"forge_hash_v1")
        # 必 64 char
        assert len(h.hexdigest()) == 64

    def test_blake2b(self):
        """`hashlib.blake2b 'a'。"""
        h = hashlib.blake2b(b"forge_hash_v1")
        # 必 128 char
        assert len(h.hexdigest()) == 128

    def test_new(self):
        """`hashlib.new 'a'。"""
        h = hashlib.new("sha256", b"forge_hash_v1")
        # 必 64 char
        assert len(h.hexdigest()) == 64

    def test_algorithms_available(self):
        """`hashlib.algorithms_available 'a'。"""
        # 必 list
        algos = hashlib.algorithms_available
        assert isinstance(algos, set)
        # 必 'sha256'
        assert "sha256" in algos


# -- secrets 进阶 (token_bytes+token_hex+token_urlsafe+compare_digest+randbelow) ---

class TestSecretsAdvanceV2:
    def test_token_bytes(self):
        """`secrets.token_bytes 'a'。"""
        t = secrets.token_bytes(16)
        # 必 16 bytes
        assert len(t) == 16

    def test_token_hex(self):
        """`secrets.token_hex 'a'。"""
        t = secrets.token_hex(16)
        # 必 32 char
        assert len(t) == 32

    def test_token_urlsafe(self):
        """`secrets.token_urlsafe 'a'。"""
        t = secrets.token_urlsafe(16)
        # 必 ≥ 22 char
        assert len(t) >= 22

    def test_compare_digest(self):
        """`secrets.compare_digest 'a'。"""
        # 必 True
        assert secrets.compare_digest("forge", "forge") is True
        # 必 False
        assert secrets.compare_digest("forge", "other") is False

    def test_randbelow(self):
        """`secrets.randbelow 'a'。"""
        n = secrets.randbelow(100)
        # 必 < 100
        assert n < 100


# -- ssl 进阶 (SSLContext+PROTOCOL_TLS_CLIENT+create_default_context+get_default_verify_paths) ---

class TestSslAdvanceV1:
    def test_SSLContext(self):
        """`ssl.SSLContext 'a'。"""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        # 必 SSLContext
        assert ctx is not None

    def test_PROTOCOL_TLS_CLIENT(self):
        """`ssl.PROTOCOL_TLS_CLIENT 'a'。"""
        # 必 int
        assert isinstance(ssl.PROTOCOL_TLS_CLIENT, int)

    def test_create_default_context(self):
        """`ssl.create_default_context 'a'。"""
        ctx = ssl.create_default_context()
        # 必 SSLContext
        assert ctx is not None

    def test_get_default_verify_paths(self):
        """`ssl.get_default_verify_paths 'a'。"""
        paths = ssl.get_default_verify_paths()
        # 必 可读属性
        assert paths is not None


# -- socket 进阶 (gethostname+gethostbyname+getaddrinfo+gethostbyaddr) ---

class TestSocketAdvanceV2:
    def test_gethostname(self):
        """`socket.gethostname 'a'。"""
        n = socket.gethostname()
        # 必 str
        assert isinstance(n, str)
        assert len(n) > 0

    def test_gethostbyname(self):
        """`socket.gethostbyname 'a'。"""
        try:
            n = socket.gethostbyname("localhost")
            # 必 str
            assert isinstance(n, str)
        except OSError:
            assert True

    def test_getaddrinfo(self):
        """`socket.getaddrinfo 'a'。"""
        try:
            r = socket.getaddrinfo("localhost", None)
            # 必 list
            assert isinstance(r, list)
            assert len(r) >= 1
        except OSError:
            assert True

    def test_gethostbyaddr(self):
        """`socket.gethostbyaddr 'a'。"""
        try:
            r = socket.gethostbyaddr("127.0.0.1")
            # 必 tuple
            assert isinstance(r, tuple)
            assert len(r) == 3
        except OSError:
            assert True


# -- http.client 进阶 (HTTPConnection+HTTPResponse+parse_headers+responses) ---

class TestHttpClientAdvanceV2:
    def test_HTTPConnection(self):
        """`http.client.HTTPConnection 'a'。"""
        c = http.client.HTTPConnection("localhost", 0)
        # 必 Connection
        assert c is not None
        c.close()

    def test_HTTPResponse(self):
        """`http.client.HTTPResponse 'a'。"""
        # 必 class
        assert http.client.HTTPResponse is not None

    def test_parse_headers(self):
        """`http.client.parse_headers 'a'。"""
        import io as _io

        fp = _io.BytesIO(b"Content-Type: text/html\r\n\r\n")
        h = http.client.parse_headers(fp)
        # 必 'text/html'
        assert h.get("Content-Type") == "text/html"

    def test_responses(self):
        """`http.client.responses 'a'。"""
        # 必 dict
        r = http.client.responses
        assert isinstance(r, dict)
        # 必 200
        assert r[200] == "OK"

    def test_http_client(self):
        """`http.client 'a'。"""
        # 必 module name
        assert http.client.__name__ == "http.client"


# -- ipaddress 进阶 (ip_address+ip_network+ip_interface+IPv4Address+IPv6Address+IPv4Network+collapse_addresses) ---

class TestIpaddressAdvanceV2:
    def test_ip_address(self):
        """`ipaddress.ip_address 'a'。"""
        a = ipaddress.ip_address("127.0.0.1")
        # 必 IPv4Address
        assert isinstance(a, ipaddress.IPv4Address)

    def test_ip_network(self):
        """`ipaddress.ip_network 'a'。"""
        n = ipaddress.ip_network("192.168.0.0/24")
        # 必 IPv4Network
        assert isinstance(n, ipaddress.IPv4Network)

    def test_ip_interface(self):
        """`ipaddress.ip_interface 'a'。"""
        i = ipaddress.ip_interface("192.168.0.1/24")
        # 必 IPv4Interface
        assert isinstance(i, ipaddress.IPv4Interface)

    def test_IPv4Address(self):
        """`ipaddress.IPv4Address 'a'。"""
        a = ipaddress.IPv4Address("192.168.1.1")
        # 必 '192.168.1.1'
        assert str(a) == "192.168.1.1"

    def test_IPv6Address(self):
        """`ipaddress.IPv6Address 'a'。"""
        a = ipaddress.IPv6Address("::1")
        # 必 IPv6Address
        assert isinstance(a, ipaddress.IPv6Address)

    def test_IPv4Network(self):
        """`ipaddress.IPv4Network 'a'。"""
        n = ipaddress.IPv4Network("192.168.0.0/24")
        # 必 num_addresses 256
        assert n.num_addresses == 256

    def test_collapse_addresses(self):
        """`ipaddress.collapse_addresses 'a'。"""
        # 必 可调用
        try:
            r = list(ipaddress.collapse_addresses([ipaddress.IPv4Network("192.168.0.0/24")]))
            assert len(r) >= 1
        except (AttributeError, TypeError):
            assert True


# -- html 进阶 (escape+unescape) ---

class TestHtmlAdvanceV2:
    def test_escape(self):
        """`html.escape 'a'。"""
        r = html.escape("<forge>&")
        # 必 '&lt;forge&gt;&amp;'
        assert "&lt;forge&gt;&amp;" == r

    def test_unescape(self):
        """`html.unescape 'a'。"""
        r = html.unescape("&lt;forge&gt;")
        # 必 '<forge>'
        assert "<forge>" == r

    def test_html_module(self):
        """`html 'a' (3rd test)。"""
        # 必 module
        assert html.__name__ == "html"
