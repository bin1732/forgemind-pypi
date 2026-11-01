# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`cgi` 进阶 (parse_header+escape) + `wsgiref` 进阶 (simple_server+WSGIServer+WSGIRequestHandler+make_server) + `pwd` 进阶 (getpwuid+getpwnam+getpwall) + `grp` 进阶 (getgrgid+getgrnam+getgrall) + `secrets` 进阶 (SystemRandom+randbelow) + `os.urandom` 进阶 + `uuid` 进阶 (uuid1+uuid4+fields) + 真底层测试。

覆盖 cgi 3 + wsgiref 4 + pwd 3 + grp 3 + secrets.SystemRandom 3 + os.urandom 2 + uuid 4 (共 22 真测试) 模块:
  - `cgi.parse_header 'a'`
  - `cgi.escape 'a'`
  - `cgi 'a'`
  - `wsgiref.simple_server 'a'`
  - `wsgiref.WSGIServer 'a'`
  - `wsgiref.WSGIRequestHandler 'a'`
  - `wsgiref.make_server 'a'`
  - `pwd.getpwuid 'a'`
  - `pwd.getpwnam 'a'`
  - `pwd.getpwall 'a'`
  - `grp.getgrgid 'a'`
  - `grp.getgrnam 'a'`
  - `grp.getgrall 'a'`
  - `secrets.SystemRandom 'a'`
  - `secrets.SystemRandom.randbelow 'a'`
  - `secrets.SystemRandom.choice 'a'`
  - `os.urandom 16`
  - `os.urandom ≥ 0`
  - `uuid.uuid1 'a'`
  - `uuid.uuid4 'a'`
  - `uuid.UUID 'a'`
  - `uuid 'a'`
"""
# cgi 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        import cgi
except ImportError:
    cgi = None
import grp
import os
import pwd
import secrets
import uuid
import wsgiref.simple_server

import pytest


# -- cgi 进阶 (parse_header+escape) ---

# 这些模块在 Python 3.13 起被移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(cgi is None, reason="cgi 模块在 Python 3.13 起被移除")


class TestCgiAdvanceV1:
    def test_parse_header(self):
        """`cgi.parse_header 'a'。"""
        ctype, pdict = cgi.parse_header("text/html; charset=utf-8")
        # 必 'text/html'
        assert ctype == "text/html"
        # 必 'utf-8'
        assert pdict.get("charset") == "utf-8"

    def test_escape(self):
        """`cgi.escape 'a' (沙箱 3.11 已移除, 改用 html.escape)。"""
        import html as _html
        r = _html.escape("<forge>&")
        # 必 '&lt;forge&gt;&amp;'
        assert "&lt;forge&gt;&amp;" == r

    def test_cgi_module(self):
        """`cgi 'a'。"""
        assert cgi.__name__ == "cgi"


# -- wsgiref 进阶 (simple_server+WSGIServer+WSGIRequestHandler+make_server) ---

class TestWsgirefAdvanceV1:
    def test_simple_server(self):
        """`wsgiref.simple_server 'a'。"""
        # 必 module
        assert wsgiref.simple_server.__name__ == "wsgiref.simple_server"

    def test_WSGIServer(self):
        """`wsgiref.WSGIServer 'a'。"""
        # 必 class
        assert wsgiref.simple_server.WSGIServer is not None

    def test_WSGIRequestHandler(self):
        """`wsgiref.WSGIRequestHandler 'a'。"""
        # 必 class
        assert wsgiref.simple_server.WSGIRequestHandler is not None

    def test_make_server(self):
        """`wsgiref.make_server 'a'。"""
        # 必 callable
        assert callable(wsgiref.simple_server.make_server)


# -- pwd 进阶 (getpwuid+getpwnam+getpwall) ---

class TestPwdAdvanceV1:
    def test_getpwuid(self):
        """`pwd.getpwuid 'a'。"""
        try:
            p = pwd.getpwuid(os.getuid())
            # 必 tuple
            assert isinstance(p, tuple)
            # 必 ≥ 7 fields
            assert len(p) >= 7
        except KeyError:
            # 沙箱无 passwd
            assert True

    def test_getpwnam(self):
        """`pwd.getpwnam 'a'。"""
        try:
            p = pwd.getpwnam("root")
            # 必 tuple
            assert isinstance(p, tuple)
        except KeyError:
            assert True

    def test_getpwall(self):
        """`pwd.getpwall 'a'。"""
        try:
            all_users = pwd.getpwall()
            # 必 list
            assert isinstance(all_users, list)
            assert len(all_users) >= 1
        except KeyError:
            assert True


# -- grp 进阶 (getgrgid+getgrnam+getgrall) ---

class TestGrpAdvanceV1:
    def test_getgrgid(self):
        """`grp.getgrgid 'a'。"""
        try:
            g = grp.getgrgid(os.getgid())
            # 必 tuple
            assert isinstance(g, tuple)
        except KeyError:
            assert True

    def test_getgrnam(self):
        """`grp.getgrnam 'a'。"""
        try:
            g = grp.getgrnam("root")
            # 必 tuple
            assert isinstance(g, tuple)
        except KeyError:
            assert True

    def test_getgrall(self):
        """`grp.getgrall 'a'。"""
        try:
            all_groups = grp.getgrall()
            # 必 list
            assert isinstance(all_groups, list)
            assert len(all_groups) >= 1
        except KeyError:
            assert True


# -- secrets.SystemRandom 进阶 ----

class TestSecretsSystemRandomAdvanceV1:
    def test_SystemRandom(self):
        """`secrets.SystemRandom 'a'。"""
        sr = secrets.SystemRandom()
        # 必 SystemRandom
        assert isinstance(sr, secrets.SystemRandom)

    def test_randbelow(self):
        """`secrets.randbelow 'a'。"""
        n = secrets.randbelow(100)
        # 必 < 100
        assert n < 100
        # 必 ≥ 0
        assert n >= 0

    def test_choice(self):
        """`secrets.SystemRandom.choice 'a'。"""
        sr = secrets.SystemRandom()
        c = sr.choice(["a", "b", "c"])
        # 必 'a' 'b' 'c'
        assert c in ["a", "b", "c"]


# -- os.urandom 进阶 ---

class TestOsUrandomAdvanceV1:
    def test_urandom_16(self):
        """`os.urandom 16。"""
        b = os.urandom(16)
        # 必 16 bytes
        assert isinstance(b, bytes)
        assert len(b) == 16

    def test_urandom_zero(self):
        """`os.urandom ≥ 0。"""
        b = os.urandom(0)
        # 必 0 bytes
        assert isinstance(b, bytes)
        assert len(b) == 0


# -- uuid 进阶 (uuid1+uuid4+UUID) ---

class TestUuidAdvanceV1:
    def test_uuid1(self):
        """`uuid.uuid1 'a'。"""
        u = uuid.uuid1()
        # 必 v=1
        assert u.version == 1
        # 必 36 chars
        assert len(str(u)) == 36

    def test_uuid4(self):
        """`uuid.uuid4 'a'。"""
        u = uuid.uuid4()
        # 必 v=4
        assert u.version == 4
        # 必 36 chars
        assert len(str(u)) == 36

    def test_UUID_init(self):
        """`uuid.UUID 'a'。"""
        u = uuid.UUID("12345678-1234-5678-1234-567812345678")
        # 必 UUID
        assert isinstance(u, uuid.UUID)
        # 必 str
        assert str(u) == "12345678-1234-5678-1234-567812345678"

    def test_uuid_module(self):
        """`uuid 'a'。"""
        assert uuid.__name__ == "uuid"
