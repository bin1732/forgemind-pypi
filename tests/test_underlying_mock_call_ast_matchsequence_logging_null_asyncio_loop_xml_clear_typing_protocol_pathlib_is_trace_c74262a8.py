# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.call` / `ast.MatchSequence` 3.10+ / `logging.NullHandler` / `asyncio.AbstractEventLoop` / `xml.etree.Element.clear` / `typing.Protocol` 进阶 / `pathlib.is_absolute` / `shutil.copymode` / `pprint.isreadable` / `socket.fromshare` 沙箱 skip / `numbers.Rational` 边界 / `trace.CoverageResults` / `ipaddress.Network` compare 底层测试。

覆盖 mock call / ast MatchSequence / logging NullHandler / asyncio loop / xml clear / typing Protocol / pathlib is_absolute / shutil copymode / pprint isreadable / socket fromshare / numbers Rational / trace CoverageResults / ipaddress Network compare 模块:
  - `unittest.mock.call 真建 call('a', key='b')`
  - `ast.MatchSequence 3.10+ 真建+patterns=[Constant(1),Constant(2)]`
  - `logging.NullHandler 真建 + handle 不抛`
  - `asyncio.get_event_loop 3.11+ DeprecationWarning 简测 get_event_loop_policy`
  - `xml.etree.Element.clear 真清 attr+text`
  - `typing.Protocol + runtime_checkable 真 isinstance`
  - `pathlib.Path.is_absolute 真返 True for abs path`
  - `shutil.copymode 真复制 mode`
  - `pprint.isreadable 真返 True for simple dict`
  - `socket.fromshare 沙箱 skip (WIN only)`
  - `numbers.Rational 必 is int+Fraction 但 not float`
  - `trace.CoverageResults 真 class`
  - `ipaddress.IPv4Network 真 < > 比较 (按 network address)`
"""
import ast
import asyncio
import ipaddress
import logging
import numbers
import pathlib
import pprint
import shutil
import socket
import sys
import trace
import typing
import unittest.mock
import xml.etree.ElementTree as ET

import pytest


# -- unittest.mock.call --------------------------------------------------------

class TestMockCall:
    def test_call(self):
        """`call 真建 call('a', key='b')。"""
        c = unittest.mock.call("a", key="b")
        # 必含 args + kwargs
        assert c.args == ("a",)
        assert c.kwargs == {"key": "b"}


# -- ast.MatchSequence 3.10+ --------------------------------------------------

class TestAstAdvancedV21:
    def test_MatchSequence_3_10(self):
        """`ast.MatchSequence 3.10+ 真建+patterns=[Constant(1),Constant(2)]`"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ MatchSequence")
        if not hasattr(ast, "MatchSequence"):
            pytest.skip("沙箱无 MatchSequence")
        # 创 MatchSequence 节点
        ms = ast.MatchSequence(patterns=[ast.Constant(value=1), ast.Constant(value=2)])
        # 必 2 patterns
        assert len(ms.patterns) == 2
        # dump
        dumped = ast.dump(ms)
        assert "MatchSequence" in dumped
        assert "1" in dumped
        assert "2" in dumped


# -- logging.NullHandler 进阶 ------------------------------------------------

class TestLoggingNullV2:
    def test_NullHandler_handle(self):
        """`NullHandler 真 handle 不抛。"""
        nh = logging.NullHandler()
        # handle 必不抛
        nh.handle(logging.LogRecord(
            "forge_null", logging.WARNING, "/x", 1, "msg", (), None
        ))


# -- asyncio loop ------------------------------------------------------------

class TestAsyncioLoopV3:
    def test_get_event_loop_policy(self):
        """`asyncio.get_event_loop_policy 真返 policy。"""
        policy = asyncio.get_event_loop_policy()
        assert policy is not None
        assert callable(policy.get_event_loop)


# -- xml.etree.Element.clear 进阶 --------------------------------------------

class TestXmlClear:
    def test_Element_clear(self):
        """`xml.etree.Element.clear 真清 attr+text+children。"""
        root = ET.fromstring("<root attr='val'><child>x</child></root>")
        # clear 必不抛
        root.clear()
        # 必清 attr
        assert root.get("attr") is None
        # 必清 children
        children = list(root)
        assert children == []
        # 必清 text
        assert root.text is None


# -- typing.Protocol 进阶 -----------------------------------------------------

@typing.runtime_checkable
class _DrawableProto(typing.Protocol):
    def draw(self) -> str: ...


class _Circle:
    def draw(self) -> str:
        return "forge_draw_circle"


class TestTypingProtocolV2:
    def test_Protocol_runtime_checkable(self):
        """`typing.Protocol + @runtime_checkable 真 isinstance。"""
        c = _Circle()
        # 必 isinstance
        assert isinstance(c, _DrawableProto)


# -- pathlib.is_absolute 进阶 ------------------------------------------------

class TestPathlibIsAbsolute:
    def test_is_absolute(self):
        """`pathlib.Path.is_absolute 真返 True for abs path。"""
        # /etc 是 absolute
        assert pathlib.Path("/etc").is_absolute() is True
        # forge_relative 不是 absolute
        assert pathlib.Path("forge_relative").is_absolute() is False


# -- shutil.copymode 进阶 ----------------------------------------------------

class TestShutilCopymode:
    def test_copymode(self, tmp_path):
        """`shutil.copymode 真复制 mode。"""
        src = tmp_path / "src.txt"
        src.write_text("x")
        src.chmod(0o644)
        dst = tmp_path / "dst.txt"
        dst.write_text("y")
        dst.chmod(0o600)
        # copymode
        shutil.copymode(src, dst)
        # 必 mode 一致
        assert src.stat().st_mode == dst.stat().st_mode


# -- pprint.isreadable 进阶 --------------------------------------------------

class TestPprintIsreadable:
    def test_isreadable_simple(self):
        """`pprint.isreadable 真返 True for simple obj。"""
        # dict 必 readable
        assert pprint.isreadable({"a": 1, "b": 2}) is True
        # list 必 readable
        assert pprint.isreadable([1, 2, 3]) is True
        # string 必 readable
        assert pprint.isreadable("forge") is True
        # int 必 readable
        assert pprint.isreadable(42) is True


# -- socket.fromshare 沙箱 skip ---------------------------------------------

class TestSocketFromshare:
    def test_fromshare_sandbox_skip(self):
        """`socket.fromshare 沙箱非 Windows 无。"""
        if sys.platform == "win32":
            assert hasattr(socket, "fromshare")
        else:
            # 沙箱非 Windows 必无 fromshare
            assert not hasattr(socket, "fromshare")


# -- numbers.Rational 边界 ---------------------------------------------------

class TestNumbersRationalEdge:
    def test_Rational_int_fraction(self):
        """`numbers.Rational 必 is int + Fraction 但 not float`。"""
        assert isinstance(42, numbers.Rational)
        from fractions import Fraction
        assert isinstance(Fraction(1, 3), numbers.Rational)
        # float 不是
        assert not isinstance(3.14, numbers.Rational)
        # complex 不是
        assert not isinstance(1 + 2j, numbers.Rational)


# -- trace.CoverageResults 进阶 ----------------------------------------------

class TestTraceCoverageResultsV4:
    def test_CoverageResults_attrs(self):
        """`trace.CoverageResults 必含 attrs。"""
        # 沙箱 3.11+ CoverageResults 必可访问
        cr = trace.CoverageResults
        assert cr is not None
        # 必含 attrs
        assert hasattr(cr, "__doc__")


# -- ipaddress.Network compare 进阶 -----------------------------------------

class TestIpaddressNetworkCompare:
    def test_IPv4Network_compare(self):
        """`IPv4Network 真 < > 比较 (按 network address)。"""
        n1 = ipaddress.IPv4Network("10.0.0.0/24")
        n2 = ipaddress.IPv4Network("192.168.0.0/24")
        # n1 < n2 (因为 10.0.0.0 < 192.168.0.0)
        assert n1 < n2
        assert n2 > n1
        # ==
        assert n1 == ipaddress.IPv4Network("10.0.0.0/24")
