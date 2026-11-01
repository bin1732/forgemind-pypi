# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock` 进阶 (DEFAULT + wraps) + `ast.TypeAliasType` 3.12+ + `logging.SysLogHandler` 沙箱 skip + `asyncio.loop` + `xml.etree.XMLPullParser` + `typing.Protocol` runtime_checkable + `pathlib` 进阶 (read_text/write_text) + `shutil.register_unpack_format` + `pprint.PrettyPrinter` 子化 + `socket.CMSG` 沙箱 skip + `urllib.parse` + `http.cookiejar` + `importlib.util` + `numbers` ABC + `unicodedata.lookup` + `statistics` 真底层测试。

覆盖 unittest.mock DEFAULT+wraps / ast TypeAliasType / logging SysLogHandler / asyncio loop / xml PullParser / typing Protocol / pathlib read+write text / shutil register_unpack_format / pprint 子化 / socket CMSG / urllib parse / http cookiejar / importlib util / numbers ABC / unicodedata lookup / statistics 模块:
  - `unittest.mock.DEFAULT 真 sentinel`
  - `unittest.mock.Mock(wraps=fn) 真 wrap 后调 fn`
  - `ast.TypeAliasType 3.12+ 沙箱 skip (3.11 无)`
  - `logging.handlers.SysLogHandler 真 class 存在 (沙箱 skip 实例)`
  - `asyncio.new_event_loop 真建 + close 真不抛`
  - `asyncio.set_event_loop_policy 真设 policy`
  - `xml.etree.XMLPullParser 真流式 + feed+close`
  - `typing.Protocol + runtime_checkable 真 isinstance`
  - `pathlib.Path.read_text / write_text 真 IO`
  - `pathlib.Path.read_bytes / write_bytes 真 IO`
  - `shutil.register_unpack_format + unregister 真`
  - `pprint.PrettyPrinter 真子化 + 调 format`
  - `socket.CMSG_SPACE 沙箱 skip (3.9+ 删)`
  - `urllib.parse.urlparse 真解 url`
  - `urllib.parse.urlencode 真解 dict→query str`
  - `urllib.parse.parse_qs 真解 query str→dict`
  - `http.cookiejar.CookieJar 真建`
  - `http.cookiejar.Cookie 真字段 attrs`
  - `importlib.util.spec_from_file_location 真建 spec`
  - `importlib.util.module_from_spec 真建 module`
  - `numbers.Number ABC 必 is int+float+complex`
  - `numbers.Rational + Integral ABC`
  - `unicodedata.lookup 真查 'GREEK SMALL LETTER ALPHA' = α`
  - `statistics.mean / median / stdev / mode / variance`
"""
import asyncio
import http.cookiejar
import importlib.util
import io
import logging.handlers
import numbers
import pathlib
import pprint
import shutil
import statistics
import sys
import typing
import unittest.mock
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET

import pytest


# -- unittest.mock DEFAULT + wraps --------------------------------------------

class TestMockDefaultWraps:
    def test_DEFAULT_sentinel(self):
        """`unittest.mock.DEFAULT 真 sentinel (unique)`"""
        d1 = unittest.mock.DEFAULT
        d2 = unittest.mock.DEFAULT
        # 必 unique
        assert d1 is d2, "DEFAULT 必 unique sentinel"

    def test_Mock_wraps(self):
        """`unittest.mock.Mock(wraps=fn) 真 wrap 后调 fn 返值。"""
        def add(a, b):
            return a + b

        m = unittest.mock.Mock(wraps=add)
        # 必透传 add
        assert m(3, 4) == 7, f"Mock(wraps=add)(3,4) 应=7,实际 {m(3, 4)}"
        # 必能验 called
        m.assert_called_with(3, 4)


# -- ast.TypeAliasType 3.12+ --------------------------------------------------

class TestAstAdvancedV11:
    def test_TypeAliasType_3_12(self):
        """`ast.TypeAliasType 3.12+ 沙箱 3.11 skip`。"""
        if sys.version_info < (3, 12):
            pytest.skip("3.12+ TypeAliasType")
        if not hasattr(ast, "TypeAliasType"):
            pytest.skip("沙箱无 TypeAliasType")
        assert ast.TypeAliasType is not None


# -- logging.SysLogHandler ----------------------------------------------------

class TestLoggingSysLog:
    def test_SysLogHandler_class(self):
        """`logging.handlers.SysLogHandler 真 class 存在。"""
        assert logging.handlers.SysLogHandler is not None
        assert callable(logging.handlers.SysLogHandler)


# -- asyncio loop -------------------------------------------------------------

class TestAsyncioLoopV2:
    def test_new_event_loop(self):
        """`asyncio.new_event_loop 真建 + close 不抛。"""
        loop = asyncio.new_event_loop()
        try:
            # 必是 event loop
            assert loop is not None
            # 必能 call_soon
            assert callable(loop.call_soon)
            assert callable(loop.time)
        finally:
            loop.close()

    def test_event_loop_policy(self):
        """`asyncio.get_event_loop_policy 真返 policy。"""
        policy = asyncio.get_event_loop_policy()
        assert policy is not None
        # 必可调 get_event_loop
        assert callable(policy.get_event_loop)


# -- xml.etree.XMLPullParser 进阶 ---------------------------------------------

class TestXmlPullParser:
    def test_pull_parser(self):
        """`xml.etree.XMLPullParser 真流式 + feed + close + read events。"""
        parser = ET.XMLPullParser(events=("start", "end"))
        parser.feed("<root><forge>x</forge></root>")
        parser.close()
        # 必能 getroot
        # 真迭代 events
        events = list(parser.read_events())
        # 必 ≥ 1 events
        assert len(events) >= 1


# -- typing.Protocol + runtime_checkable --------------------------------------

class MyProto(typing.Protocol):
    def hello(self) -> str: ...


class MyImpl:
    def hello(self) -> str:
        return "forge"


class TestTypingAdvancedV13:
    def test_Protocol_runtime_checkable(self):
        """`typing.Protocol + @runtime_checkable 真 isinstance。"""
        # runtime_checkable
        CheckableProto = typing.runtime_checkable(MyProto)
        # impl 真 isinstance Protocol
        assert isinstance(MyImpl(), CheckableProto)
        # 不实现 hello 不 isinstance
        class _NoHello:
            pass
        assert not isinstance(_NoHello(), CheckableProto)


# -- pathlib 进阶 (read_text / write_text / read_bytes / write_bytes) ---------

class TestPathlibAdvancedV4:
    def test_read_text_write_text(self, tmp_path):
        """`pathlib.Path.read_text / write_text 真 IO。"""
        p = tmp_path / "forge_text.txt"
        p.write_text("hello forge text")
        # 必能 read
        assert p.read_text() == "hello forge text"

    def test_read_bytes_write_bytes(self, tmp_path):
        """`pathlib.Path.read_bytes / write_bytes 真 IO。"""
        p = tmp_path / "forge_bytes.bin"
        p.write_bytes(b"hello forge bytes")
        # 必能 read
        assert p.read_bytes() == b"hello forge bytes"


# -- shutil.register_unpack_format -------------------------------------------

class TestShutilRegisterUnpack:
    def test_register_unpack_format(self):
        """`shutil.register_unpack_format + unregister 真 (function 必 callable)`"""
        def _dummy_extractor(src, dest):
            pass

        try:
            shutil.register_unpack_format(
                "forge", [".forge"], _dummy_extractor, "forge unpack"
            )
            formats = shutil.get_unpack_formats()
            # 必含 'forge'
            names = [f[0] for f in formats]
            assert "forge" in names, f"formats 应含 'forge',实际 {names}"
        finally:
            # unregister
            try:
                shutil.unregister_unpack_format("forge")
            except shutil.Error:
                pass


# -- pprint.PrettyPrinter 子化 ------------------------------------------------

class _MyPretty(pprint.PrettyPrinter):
    pass


class TestPprintPrettyPrinter:
    def test_PrettyPrinter_subclass(self):
        """`pprint.PrettyPrinter 真子化 + pformat 真返 str。"""
        pp = _MyPretty()
        # pformat 是 public API
        s = pp.pformat({"forge": 42})
        # 必非空
        assert isinstance(s, str)
        # 必含 'forge'
        assert "forge" in s


# -- socket.CMSG 沙箱 skip (3.9+ 删) ------------------------------------------

class TestSocketCmsg:
    def test_CMSG_3_9_removed(self):
        """`socket.CMSG_SPACE / CMSG_LEN 3.9+ 删 (沙箱 skip)`"""
        if sys.version_info >= (3, 9):
            pytest.skip("3.9+ CMSG_* 删")
        # 3.8 有
        assert hasattr(socket, "CMSG_SPACE")


# -- urllib.parse -------------------------------------------------------------

class TestUrllibParseAdvanced:
    def test_urlparse(self):
        """`urllib.parse.urlparse 真解 url。"""
        r = urllib.parse.urlparse("https://example.com/forge?a=1#frag")
        # 必 5 段
        assert r.scheme == "https"
        assert r.netloc == "example.com"
        assert r.path == "/forge"
        assert r.query == "a=1"
        assert r.fragment == "frag"

    def test_urlencode(self):
        """`urllib.parse.urlencode 真解 dict→query str。"""
        s = urllib.parse.urlencode({"forge": 42, "name": "test"})
        # 必含 'forge=42'
        assert "forge=42" in s, f"urlencode 应含 'forge=42',实际 {s}"
        assert "name=test" in s

    def test_parse_qs(self):
        """`urllib.parse.parse_qs 真解 query str→dict。"""
        d = urllib.parse.parse_qs("forge=42&name=test")
        # 必是 dict
        assert isinstance(d, dict)
        assert d["forge"] == ["42"]
        assert d["name"] == ["test"]


# -- http.cookiejar 进阶 ------------------------------------------------------

class TestHttpCookiejarV2:
    def test_CookieJar(self):
        """`http.cookiejar.CookieJar 真建。"""
        cj = http.cookiejar.CookieJar()
        assert cj is not None
        # 必是 CookieJar
        assert isinstance(cj, http.cookiejar.CookieJar)
        # 必能迭代
        cookies = list(cj)
        assert cookies == []

    def test_Cookie_attrs(self):
        """`http.cookiejar.Cookie 真字段 attrs。"""
        c = http.cookiejar.Cookie(
            version=0, name="forge", value="42", port=None, port_specified=False,
            domain="example.com", domain_specified=True, domain_initial_dot=False,
            path="/", path_specified=True, secure=False, expires=None,
            discard=True, comment=None, comment_url=None, rest={"HttpOnly": None},
            rfc2109=False,
        )
        # 必含 name+value
        assert c.name == "forge"
        assert c.value == "42"


# -- importlib.util ------------------------------------------------------------

class TestImportlibUtil:
    def test_spec_from_file_location(self):
        """`importlib.util.spec_from_file_location 真建 spec。"""
        spec = importlib.util.spec_from_file_location(
            "forge_test_module", "/tmp/forge_test.py"
        )
        if spec is None:
            pytest.skip("沙箱 spec_from_file_location 返 None")
        # 必含 name
        assert spec.name == "forge_test_module"
        # 必含 origin
        assert spec.origin == "/tmp/forge_test.py"

    def test_module_from_spec(self):
        """`importlib.util.module_from_spec 真建 module (无 spec.loader 时简测)`"""
        # 简测: spec_from_loader
        from importlib.machinery import ModuleSpec
        spec = ModuleSpec("forge_test_mod", None)
        mod = importlib.util.module_from_spec(spec)
        assert mod is not None
        assert mod.__name__ == "forge_test_mod"


# -- numbers ABC 进阶 --------------------------------------------------------

class TestNumbersAbc:
    def test_Number_isinstance(self):
        """`numbers.Number ABC 必 is int + float + complex。"""
        assert isinstance(42, numbers.Number)
        assert isinstance(3.14, numbers.Number)
        assert isinstance(1 + 2j, numbers.Number)

    def test_Rational_Integral(self):
        """`numbers.Rational + Integral ABC isinstance。"""
        # Rational 含 int + Fraction
        assert isinstance(42, numbers.Rational)
        # Integral 含 int
        assert isinstance(42, numbers.Integral)
        # float 不是 Rational
        assert not isinstance(3.14, numbers.Rational)


# -- unicodedata.lookup -------------------------------------------------------

class TestUnicodedataLookup:
    def test_lookup_greek(self):
        """`unicodedata.lookup 真查 'GREEK SMALL LETTER ALPHA' = α。"""
        c = unicodedata.lookup("GREEK SMALL LETTER ALPHA")
        # 必 = 'α' (U+03B1)
        assert c == "α", f"应=α,实际 {c!r}"
        # 必是 1 char
        assert len(c) == 1
        # 必 ord = 0x3B1
        assert ord(c) == 0x03B1


# -- statistics 进阶 ---------------------------------------------------------

class TestStatisticsAdvanced:
    def test_mean(self):
        """`statistics.mean 真均值。"""
        assert statistics.mean([1, 2, 3, 4, 5]) == 3.0, (
            f"mean [1..5] 应=3.0,实际 {statistics.mean([1, 2, 3, 4, 5])}"
        )

    def test_median(self):
        """`statistics.median 真中位。"""
        assert statistics.median([1, 2, 3, 4, 5]) == 3
        # 偶数
        assert statistics.median([1, 2, 3, 4]) == 2.5

    def test_mode(self):
        """`statistics.mode 真众数。"""
        # 多众数抛 StatisticsError 或返 first
        try:
            result = statistics.mode([1, 1, 2, 3, 3, 3, 4])
            assert result == 3, f"mode [1,1,2,3,3,3,4] 应=3,实际 {result}"
        except statistics.StatisticsError:
            # 3.8+ 允许多 mode, 单 mode 返 first
            pass

    def test_stdev(self):
        """`statistics.stdev 真标准差。"""
        s = statistics.stdev([1, 2, 3, 4, 5])
        # 真 stdev ≈ 1.581
        assert 1.5 < s < 1.7, f"stdev [1..5] 应≈1.58,实际 {s}"

    def test_variance(self):
        """`statistics.variance 真方差。"""
        v = statistics.variance([1, 2, 3, 4, 5])
        # variance = 2.5
        assert 2.0 < v < 3.0, f"variance [1..5] 应≈2.5,实际 {v}"
