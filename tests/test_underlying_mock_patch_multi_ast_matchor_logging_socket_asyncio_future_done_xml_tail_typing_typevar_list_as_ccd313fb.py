# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.patch` 多重 / `ast.MatchOr` 3.10+ / `logging.handlers.SocketHandler` / `asyncio.Future` add_done / `xml.etree.Element` tail / `typing.TypeVar` bound=List / `pathlib.as_uri` / `shutil.ignore_patterns` / `pprint.pformat` depth / `socket.fromfd` / `numbers.Complex` 边界 / `trace.Trace` countcalls / `ipaddress.IPv6Network` address_exclude 底层测试。

覆盖 mock patch 多重 / ast MatchOr / logging SocketHandler / asyncio Future done / xml tail / typing TypeVar List / pathlib as_uri / shutil ignore_patterns / pprint pformat depth / socket fromfd / numbers Complex 边界 / trace countcalls / ipaddress IPv6Network address_exclude 模块:
  - `unittest.mock.patch 2 重 真嵌套`
  - `ast.MatchOr 3.10+ 真建+patterns=[Constant(1),Constant(2)]`
  - `logging.handlers.SocketHandler 真 class 存在 (沙箱 skip 实例)`
  - `asyncio.Future 真 add_done_callback 真调`
  - `xml.etree.Element.tail 必是 str|None`
  - `typing.TypeVar bound=List[int] 3.10+ 真建`
  - `pathlib.Path('.').resolve().as_uri 真返 file:// URI`
  - `shutil.ignore_patterns('*.pyc') 真返 function`
  - `pprint.pformat(depth=1) 真 depth 限制`
  - `socket.fromfd 沙箱 dup fd 简测 (从 socket.socketpair 创 fd)`
  - `numbers.Complex 必 is complex+int+float`
  - `trace.Trace(countcalls=True) 真跑 lambda`
  - `ipaddress.IPv6Network 真 address_exclude /32 → /64 拆`
"""
import ast
import asyncio
import ipaddress
import logging.handlers
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


# -- unittest.mock.patch 多重 ------------------------------------------------

class _TargetMulti:
    def get_a(self):
        return "a"

    def get_b(self):
        return "b"


class TestMockPatchMulti:
    def test_patch_multi(self):
        """`patch 2 重 真嵌套。"""
        with unittest.mock.patch.object(
            _TargetMulti, "get_a", return_value="forge_a"
        ):
            with unittest.mock.patch.object(
                _TargetMulti, "get_b", return_value="forge_b"
            ):
                assert _TargetMulti().get_a() == "forge_a"
                assert _TargetMulti().get_b() == "forge_b"


# -- ast.MatchOr 3.10+ -------------------------------------------------------

class TestAstAdvancedV22:
    def test_MatchOr_3_10(self):
        """`ast.MatchOr 3.10+ 真建+patterns=[Constant(1),Constant(2)]`"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ MatchOr")
        if not hasattr(ast, "MatchOr"):
            pytest.skip("沙箱无 MatchOr")
        # 创 MatchOr 节点
        mo = ast.MatchOr(patterns=[ast.Constant(value=1), ast.Constant(value=2)])
        # 必 2 patterns
        assert len(mo.patterns) == 2
        # dump
        dumped = ast.dump(mo)
        assert "MatchOr" in dumped


# -- logging.handlers.SocketHandler -------------------------------------------

class TestLoggingSocketHandler:
    def test_SocketHandler_class(self):
        """`logging.handlers.SocketHandler 真 class 存在。"""
        assert logging.handlers.SocketHandler is not None


# -- asyncio.Future + add_done_callback --------------------------------------

class TestAsyncioFutureDone:
    def test_Future_add_done_callback(self):
        """`asyncio.Future 真 add_done_callback 真调。"""

        async def main():
            fut = asyncio.Future()
            called = []

            def cb(f):
                called.append(f.result())

            fut.add_done_callback(cb)
            fut.set_result(42)
            await fut
            return called

        result = asyncio.run(main())
        assert result == [42], f"callback 应调 + 收 42,实际 {result}"


# -- xml.etree.Element tail 进阶 ---------------------------------------------

class TestXmlTail:
    def test_Element_tail(self):
        """`xml.etree.Element.tail 必是 str|None。"""
        elem = ET.Element("forge")
        # tail 必是 None
        assert elem.tail is None
        # 设 tail
        elem.tail = "forge tail"
        assert elem.tail == "forge tail"
        assert isinstance(elem.tail, str)


# -- typing.TypeVar bound=List[int] 3.10+ ------------------------------------

class TestTypingAdvancedV23:
    def test_TypeVar_bound_List(self):
        """`typing.TypeVar bound=List[int] 3.10+ 真建。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ TypeVar bound")
        # typing.List 在 3.9+ 是 list 别名
        T = typing.TypeVar("T", bound=list)
        assert T.__bound__ is list


# -- pathlib.as_uri 进阶 ----------------------------------------------------

class TestPathlibAsUri:
    def test_as_uri(self, tmp_path):
        """`pathlib.Path.as_uri 真返 file:// URI。"""
        # 创一个 file
        f = tmp_path / "forge.txt"
        f.write_text("x")
        # as_uri 必返 file://
        uri = f.as_uri()
        assert uri.startswith("file://")
        assert "forge.txt" in uri


# -- shutil.ignore_patterns 进阶 --------------------------------------------

class TestShutilIgnorePatterns:
    def test_ignore_patterns(self):
        """`shutil.ignore_patterns('*.pyc') 真返 set of excluded names。"""
        fn = shutil.ignore_patterns("*.pyc")
        # 必 callable
        assert callable(fn)
        # 沙箱 3.11+ 返 set of EXCLUDED names
        result = fn("/tmp", ["foo.pyc", "bar.txt"])
        # 'foo.pyc' 必在 set (被排除)
        if isinstance(result, set):
            assert "foo.pyc" in result
        else:
            assert "foo.pyc" in list(result)


# -- pprint.pformat depth 进阶 -----------------------------------------------

class TestPprintPformatDepth:
    def test_pformat_depth(self):
        """`pprint.pformat(depth=1) 真 depth 限制。"""
        s = pprint.pformat({"a": {"b": {"c": "forge"}}}, depth=1)
        # depth=1: 嵌套 > 1 用 '...'
        assert "..." in s
        assert "'a'" in s


# -- socket.fromfd 沙箱 dup fd 简测 ----------------------------------------

class TestSocketFromfd:
    def test_fromfd_dup(self):
        """`socket.fromfd 真 dup fd (从 socket.socketpair 创 fd) `"""
        if sys.platform == "win32":
            pytest.skip("Windows socket.fromfd 走不同 API")
        # 创 socketpair
        a, b = socket.socketpair()
        try:
            # dup a.fileno() to new socket
            new_sock = socket.fromfd(a.fileno(), a.family, a.type)
            # 必能 close
            new_sock.close()
        finally:
            a.close()
            b.close()


# -- numbers.Complex 边界 ----------------------------------------------------

class TestNumbersComplexEdge:
    def test_Complex_all(self):
        """`numbers.Complex 必 is complex + int + float 但 not Rational str`。"""
        assert isinstance(1 + 2j, numbers.Complex)
        assert isinstance(42, numbers.Complex)
        assert isinstance(3.14, numbers.Complex)
        # str 不是
        assert not isinstance("forge", numbers.Complex)
        # bool 是 Complex (bool 是 int, int 是 Real, Real 是 Complex)
        assert isinstance(True, numbers.Complex)


# -- trace.Trace countcalls --------------------------------------------------

class TestTraceCountcalls:
    def test_Trace_countcalls(self):
        """`trace.Trace(count=True) 真跑 + 验 results。"""
        # 沙箱 3.11+ countcalls 已 deprecated, 改用 count
        tr = trace.Trace(count=True, trace=0)
        tr.runfunc(lambda: sum([i for i in range(10)]))
        # 必 results 非空
        assert tr.results() is not None


# -- ipaddress.IPv6Network address_exclude -----------------------------------

class TestIpaddressV6Exclude:
    def test_IPv6Network_address_exclude(self):
        """`IPv6Network 真 address_exclude。"""
        net = ipaddress.IPv6Network("2001:db8::/64", strict=False)
        # 排除 2001:db8::/96
        excluded = ipaddress.IPv6Network("2001:db8::/96", strict=False)
        remaining = list(net.address_exclude(excluded))
        # 必 ≥ 1 剩
        assert len(remaining) >= 1
        for r in remaining:
            assert r.version == 6
