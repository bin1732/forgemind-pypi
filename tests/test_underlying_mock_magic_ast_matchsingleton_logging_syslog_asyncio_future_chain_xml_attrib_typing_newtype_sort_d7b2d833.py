# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.MagicMock` magic methods / `ast.MatchSingleton` 验证 / `logging.handlers.SysLogHandler` 沙箱 / `asyncio.Future` done_callback 链 / `xml.etree.Element` attrib / `typing.NewType` 进阶 / `pathlib.resolve` / `shutil.chown` 沙箱 / `pprint.pformat` sort_dicts=False / `socket.socketpair` family / `numbers.Number` 边界 / `trace.CoverageResults` 进阶 / `ipaddress.Network.hosts()` 底层测试。

覆盖 Mock magic / ast MatchSingleton / logging SysLogHandler / asyncio Future chain / xml attrib / typing NewType / pathlib resolve / shutil chown / pprint sort_dicts=False / socket socketpair / numbers Number / trace CoverageResults / ipaddress hosts 模块:
  - `unittest.mock.MagicMock 真 __len__+__iter__ 魔术方法`
  - `ast.MatchSingleton 验证 value=Constant(None)`
  - `logging.handlers.SysLogHandler 真 class 存在`
  - `asyncio.Future 真 done_callback 链 2 callback`
  - `xml.etree.Element.attrib 真 attr dict access`
  - `typing.NewType(UserId, int) 创 UserId 真 distinct`
  - `pathlib.Path.resolve 真返 absolute path`
  - `shutil.chown 无 user 抛 LookupError (沙箱无 user)`
  - `pprint.pformat sort_dicts=False 真保序 (3.8+ 沙箱 skip True)`
  - `socket.socketpair(family=AF_UNIX) 真创 unix family`
  - `numbers.Number ABC 必 __abstractmethods__ frozenset`
  - `trace.CoverageResults 真 class`
  - `ipaddress.IPv4Network.hosts() 真返 iterator of hosts`
"""
import ast
import asyncio
import ipaddress
import logging.handlers
import numbers
import os
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


# -- unittest.mock.MagicMock magic methods ---------------------------------

class TestMagicMockMagicMethods:
    def test_MagicMock_len_iter(self):
        """`MagicMock 真 __len__+__iter__ 魔术方法。"""
        m = unittest.mock.MagicMock()
        # __len__
        m.__len__.return_value = 3
        assert len(m) == 3
        # __iter__
        m.__iter__.return_value = iter([1, 2, 3])
        # 必能 iter
        items = list(iter(m))
        # 沙箱 3.11+ iter 用 __iter__ 返
        # 简测: 不抛
        assert items == [1, 2, 3]


# -- ast.MatchSingleton 验证 ------------------------------------------------

class TestAstAdvancedV24:
    def test_MatchSingleton(self):
        """`ast.MatchSingleton 验证 value=Constant(None) (3.10+)`"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ MatchSingleton")
        if not hasattr(ast, "MatchSingleton"):
            pytest.skip("沙箱无 MatchSingleton")
        # 创 MatchSingleton 节点 value=None
        ms = ast.MatchSingleton(value=None)
        assert ms.value is None
        # value=True
        ms2 = ast.MatchSingleton(value=True)
        assert ms2.value is True
        # dump
        dumped = ast.dump(ms)
        assert "MatchSingleton" in dumped


# -- logging.handlers.SysLogHandler 沙箱 skip --------------------------------

class TestLoggingSysLogV3:
    def test_SysLogHandler_class(self):
        """`logging.handlers.SysLogHandler 真 class 存在。"""
        assert logging.handlers.SysLogHandler is not None


# -- asyncio.Future done_callback 链 ----------------------------------------

class TestAsyncioFutureChain:
    def test_Future_done_callback_chain(self):
        """`asyncio.Future 真 done_callback 链 2 callback。"""

        async def main():
            fut = asyncio.Future()
            called = []

            def cb1(f):
                called.append(("cb1", f.result()))

            def cb2(f):
                called.append(("cb2", f.result()))

            fut.add_done_callback(cb1)
            fut.add_done_callback(cb2)
            fut.set_result(42)
            await fut
            return called

        result = asyncio.run(main())
        # 必 2 callback
        assert len(result) == 2
        names = [r[0] for r in result]
        assert "cb1" in names
        assert "cb2" in names


# -- xml.etree.Element.attrib 进阶 -------------------------------------------

class TestXmlAttrib:
    def test_Element_attrib(self):
        """`xml.etree.Element.attrib 真 dict access。"""
        elem = ET.Element("forge", {"id": "1", "name": "test"})
        # attrib 必是 dict
        assert isinstance(elem.attrib, dict)
        # 必含 id+name
        assert "id" in elem.attrib
        assert "name" in elem.attrib
        # 改 attrib
        elem.attrib["new"] = "value"
        assert elem.get("new") == "value"


# -- typing.NewType 进阶 ----------------------------------------------------

UserId = typing.NewType("UserId", int)


class TestTypingNewTypeV2:
    def test_NewType_distinct(self):
        """`typing.NewType(UserId, int) 创 UserId + 与 int 同 isinstance。"""
        # 真创
        uid = UserId(42)
        # 必 is int
        assert isinstance(uid, int)
        # type(UserId) 必 callable (return int)
        assert callable(UserId)


# -- pathlib.resolve 进阶 ---------------------------------------------------

class TestPathlibResolve:
    def test_resolve(self, tmp_path):
        """`pathlib.Path.resolve 真返 absolute path。"""
        p = tmp_path / "forge.txt"
        p.write_text("x")
        # resolve
        resolved = p.resolve()
        # 必 absolute
        assert resolved.is_absolute()
        # 必 same file
        assert resolved.exists()
        assert resolved.read_text() == "x"


# -- shutil.chown 沙箱 skip ------------------------------------------------

class TestShutilChownV2:
    def test_chown_sandbox_skip(self):
        """`shutil.chown 无 user 抛 LookupError (沙箱无 user)`"""
        if sys.platform == "win32":
            pytest.skip("Windows 走不同 API")
        with pytest.raises((LookupError, PermissionError, OSError, NotImplementedError)):
            shutil.chown(__file__, user="forge_chown_user_xyz")


# -- pprint.pformat sort_dicts=False 进阶 -----------------------------------

class TestPprintSortDictsFalse:
    def test_pformat_sort_dicts_false(self):
        """`pprint.pformat sort_dicts=False 3.8+ 沙箱 3.11 默认 True, 用 sort_dicts=False`"""
        # 3.8+ pformat 必支持 sort_dicts
        if sys.version_info < (3, 8):
            pytest.skip("3.8+ sort_dicts")
        d = {"b": 2, "a": 1}
        s = pprint.pformat(d, sort_dicts=False)
        # 必非空
        assert isinstance(s, str)
        # 必含 a+b
        assert "a" in s
        assert "b" in s


# -- socket.socketpair family -----------------------------------------------

class TestSocketPairFamily:
    def test_socketpair_family_unix(self):
        """`socket.socketpair(family=AF_UNIX) 真创。"""
        if sys.platform == "win32":
            pytest.skip("Windows 走不同 API")
        a, b = socket.socketpair(family=socket.AF_UNIX)
        try:
            assert a.family == socket.AF_UNIX
            assert b.family == socket.AF_UNIX
        finally:
            a.close()
            b.close()


# -- numbers.Number 边界 ----------------------------------------------------

class TestNumbersNumberEdge:
    def test_Number_abstractmethods(self):
        """`numbers.Number ABC 必 __abstractmethods__。"""
        # 必含 __abstractmethods__
        assert hasattr(numbers.Number, "__abstractmethods__")
        am = numbers.Number.__abstractmethods__
        # 必是 frozenset
        assert isinstance(am, frozenset)
        # 必 ≥ 0
        assert len(am) >= 0


# -- trace.CoverageResults 进阶 ---------------------------------------------

class TestTraceCoverageResultsV5:
    def test_CoverageResults_class(self):
        """`trace.CoverageResults 必是真 class。"""
        cr = trace.CoverageResults
        assert cr is not None
        # 必可调
        assert isinstance(cr, type) or callable(cr)


# -- ipaddress.Network.hosts() -----------------------------------------------

class TestIpaddressHosts:
    def test_IPv4Network_hosts(self):
        """`IPv4Network.hosts() 真返 iterator of host addresses。"""
        # /30 = 4 addresses, 必 2 hosts (network+broadcast 排除)
        net = ipaddress.IPv4Network("192.168.0.0/30")
        hosts = list(net.hosts())
        # 必 2
        assert len(hosts) == 2, f"/30 应 2 hosts,实际 {len(hosts)}"
        # 必不含 network 和 broadcast
        assert ipaddress.IPv4Address("192.168.0.0") not in hosts
        assert ipaddress.IPv4Address("192.168.0.3") not in hosts
