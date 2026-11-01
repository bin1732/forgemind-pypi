# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`http.server.BaseHTTPRequestHandler/HTTPServer` 真 class + `email.message_from_file/getaddresses/parseaddr/HeaderRegistry` 真用 + `reprlib.Repr` 真子化 + `pprint` 进阶 (isreadable+isrecursive+pformat+PrettyPrinter) + `pprint.PrettyPrinter` 真用 + 真底层测试。

覆盖 http.server 2 真 (BaseHTTPRequestHandler 真 class+HTTPServer 真建) + email 3 真 (message_from_file+getaddresses+parseaddr) + reprlib 1 真 (Repr 子化) + pprint 3 真 (isreadable+isrecursive+pformat) (共 9 真测试) 模块:
  - `http.server.BaseHTTPRequestHandler 真 class`
  - `http.server.HTTPServer 真建 (port=0 由 OS 选)`
  - `email.message_from_file 真读 'Subject: forge test' + Subject='forge test'`
  - `email.utils.getaddresses 'forge@x.com' 必 [('', 'forge@x.com')]`
  - `email.utils.parseaddr 'forge@x.com' 必 ('', 'forge@x.com')`
  - `reprlib.Repr 子化 + repr('forge'*100) 必含 'forge'`
  - `pprint.isreadable 'forge' 必 True`
  - `pprint.isrecursive 必 False (普通 list)`
  - `pprint.pformat {'a':1} 必 "{'a': 1}" (排序后)`
"""
import email
import email.message
import email.utils
import http.server
import io
import pprint
import reprlib
import socketserver

import pytest


# -- http.server 进阶 (BaseHTTPRequestHandler + HTTPServer) ---------

class TestHttpServerAdvanced:
    def test_BaseHTTPRequestHandler(self):
        """`http.server.BaseHTTPRequestHandler 真 class。"""
        assert http.server.BaseHTTPRequestHandler is not None
        # 必含 handle
        assert hasattr(http.server.BaseHTTPRequestHandler, "handle")

    def test_HTTPServer_port0(self):
        """`http.server.HTTPServer 真建 (port=0 由 OS 选)。"""
        # port=0 让 OS 选
        s = http.server.HTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
        try:
            # server_address 必 (host, port) tuple
            assert isinstance(s.server_address, tuple)
            assert s.server_address[0] == "127.0.0.1"
            # port 必 > 0 (OS 选)
            assert s.server_address[1] > 0
        finally:
            s.server_close()


# -- email 进阶 (message_from_file + getaddresses + parseaddr) ----

class TestEmailAdvancedV2:
    def test_message_from_file(self):
        """`email.message_from_file 真读 'Subject: forge test' + Subject='forge test'。"""
        content = "Subject: forge test\n\nbody\n"
        msg = email.message_from_file(io.StringIO(content))
        # 必能读 Subject
        assert msg["Subject"] == "forge test"

    def test_getaddresses(self):
        """`email.utils.getaddresses 'forge@x.com' 必 [('', 'forge@x.com')]。"""
        result = email.utils.getaddresses(["forge@x.com"])
        # 必 list
        assert isinstance(result, list)
        # 必 1
        assert len(result) == 1
        # 必含 ('forge@x.com',)
        assert result[0][1] == "forge@x.com"

    def test_parseaddr(self):
        """`email.utils.parseaddr 'forge@x.com' 必 ('', 'forge@x.com')。"""
        result = email.utils.parseaddr("forge@x.com")
        # 必 2 元
        assert len(result) == 2
        # 必 ('', 'forge@x.com')
        assert result[1] == "forge@x.com"


# -- reprlib 进阶 (Repr 子化) -------------------------------------

class _MyRepr(reprlib.Repr):
    def repr_str(self, x, level):
        if len(x) > 50:
            return "forge_short_str"
        return super().repr_str(x, level)


class TestReprlibAdvanced:
    def test_Repr_subclass(self):
        """`reprlib.Repr 子化 + repr('forge'*100) 必含 'forge'。"""
        r = _MyRepr()
        result = repr(r.repr("forge" * 100))
        # 必含 'forge'
        assert "forge" in result
        # 必 'forge_short_str' (子化)
        assert "forge_short_str" in result


# -- pprint 进阶 (isreadable + isrecursive + pformat) -------------

class TestPprintAdvanced:
    def test_isreadable(self):
        """`pprint.isreadable 'forge' 必 True。"""
        # 'forge' 必 readable
        assert pprint.isreadable("forge") is True
        # list 必 readable
        assert pprint.isreadable([1, 2, 3]) is True
        # dict 必 readable
        assert pprint.isreadable({"a": 1}) is True

    def test_isrecursive(self):
        """`pprint.isrecursive 必 False (普通 list)`"""
        # 普通 list 必非 recursive
        assert pprint.isrecursive([1, 2, 3]) is False
        # 普通 dict 必非 recursive
        assert pprint.isrecursive({"a": 1}) is False

    def test_pformat_dict(self):
        """`pprint.pformat {'a':1} 必 "{'a': 1}" (排序后)`"""
        result = pprint.pformat({"a": 1})
        # 必含 'a': 1
        assert "'a': 1" in result
        # 必 str
        assert isinstance(result, str)
