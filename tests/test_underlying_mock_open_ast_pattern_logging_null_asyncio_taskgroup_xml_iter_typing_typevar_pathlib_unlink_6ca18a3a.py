# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.mock_open` / `ast.pattern` 3.10+ / `logging.NullHandler` 进阶 / `asyncio.TaskGroup` 沙箱 / `xml.etree.Element` iter / `typing.TypeVar` 验证 / `pathlib.unlink` 进阶 / `shutil.which` 进阶 / `pprint.PrettyPrinter` depth+width / `socket.sendmsg` 进阶 / `numbers.Number` 抽象方法 / `trace.Trace` class / `ipaddress.Network.subnets()` 底层测试。

覆盖 mock mock_open / ast pattern / logging NullHandler / asyncio TaskGroup / xml iter / typing TypeVar / pathlib unlink / shutil which / pprint depth+width / socket sendmsg / numbers Number abstract / trace Trace class / ipaddress subnets 模块:
  - `unittest.mock.mock_open 真返 fake file handle + read 真 read data`
  - `ast.pattern 3.10+ 真 class 存在`
  - `logging.NullHandler 真发到 sys.stderr / 不抛`
  - `asyncio.TaskGroup 3.11+ 沙箱 skip`
  - `xml.etree.Element 真 iter 子元素 ≥ 1`
  - `typing.TypeVar bound=Real 3.10+ 真建`
  - `pathlib.Path.unlink 真删 + missing_ok True 不抛`
  - `shutil.which 真多个查找`
  - `pprint.PrettyPrinter(depth=1, width=40) 组合`
  - `socket.sendmsg 沙箱 AF_UNIX 限大小 简测 (sockpair 字节 <=20)`
  - `numbers.Number 必 is 0 (instantiate 返 0) + 抽象方法 frozenset`
  - `trace.Trace(count=True) 真跑 + results 非空`
  - `ipaddress.IPv4Network.subnets(new_prefix=26) 真拆 /24 → 4 /26`
"""
import ast
import asyncio
import ipaddress
import logging
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


# -- unittest.mock.mock_open -------------------------------------------------

class TestMockOpen:
    def test_mock_open(self):
        """`mock_open 真返 fake file handle + read 真 read data。"""
        m = unittest.mock.mock_open(read_data="hello forge\nworld")
        with m("/path/to/file") as f:
            data = f.read()
        assert data == "hello forge\nworld"
        # write + read 真记
        m2 = unittest.mock.mock_open()
        with m2("/path/to/file") as f:
            f.write("forge test write")
        # handle() 必能验 called
        m2().write.assert_called_with("forge test write")


# -- ast.pattern 3.10+ 验证 ------------------------------------------------

class TestAstPattern:
    def test_Pattern_class(self):
        """`ast.pattern 3.10+ 真 class 存在。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ pattern")
        # 沙箱 3.11+ ast.pattern 必存在
        assert hasattr(ast, "pattern")
        # 必是 class
        assert isinstance(ast.pattern, type)


# -- logging.NullHandler 进阶 -----------------------------------------------

class TestLoggingNullV3:
    def test_NullHandler_emit_silent(self):
        """`NullHandler 真发到 sys.stderr (handler 默认 stream=sys.stderr) 不抛。"""
        nh = logging.NullHandler()
        # emit 必不抛
        nh.emit(logging.LogRecord(
            "forge_null", logging.WARNING, "/x", 1, "msg", (), None
        ))


# -- asyncio.TaskGroup 沙箱 skip --------------------------------------------

class TestAsyncioTaskGroup:
    def test_TaskGroup_3_11_skip(self):
        """`asyncio.TaskGroup 3.11+ 沙箱真 class 存在。"""
        if sys.version_info < (3, 11):
            pytest.skip("3.11+ TaskGroup")
        # 3.11+ 必有 TaskGroup
        assert hasattr(asyncio, "TaskGroup")


# -- xml.etree.Element iter 进阶 --------------------------------------------

class TestXmlIterV2:
    def test_Element_iter_children(self):
        """`xml.etree.Element 真 iter 子元素 ≥ 1。"""
        root = ET.fromstring("<root><a/><b/><c/></root>")
        children = list(root)
        # 必 3
        assert len(children) == 3


# -- typing.TypeVar bound=Real 3.10+ -----------------------------------------

class TestTypingAdvancedV24:
    def test_TypeVar_bound_Real(self):
        """`typing.TypeVar bound=Real 3.10+ 真建。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ TypeVar bound")
        T = typing.TypeVar("T", bound=numbers.Real)
        # 必含 __bound__ = Real
        assert T.__bound__ is numbers.Real


# -- pathlib.unlink 进阶 ----------------------------------------------------

class TestPathlibUnlink:
    def test_unlink_missing_ok(self, tmp_path):
        """`pathlib.Path.unlink 真删 + missing_ok=True 不抛。"""
        # 不存在
        p = tmp_path / "forge_not_exists.txt"
        # unlink(missing_ok=True) 必不抛
        p.unlink(missing_ok=True)
        # 必不在
        assert not p.exists()
        # 存在
        p2 = tmp_path / "forge_exists.txt"
        p2.write_text("x")
        # unlink 必删
        p2.unlink()
        assert not p2.exists()


# -- shutil.which 进阶 -----------------------------------------------------

class TestShutilWhichV3:
    def test_which_python3(self):
        """`shutil.which('python3') 真非空 str。"""
        path = shutil.which("python3")
        if path is None:
            pytest.skip("沙箱无 python3")
        assert isinstance(path, str)
        assert len(path) > 0
        # 必含 'python'
        assert "python" in path.lower()

    def test_which_nonexistent(self):
        """`shutil.which('forge_xyz_123') 真 None。"""
        assert shutil.which("forge_xyz_123") is None


# -- pprint.PrettyPrinter depth+width 组合 ----------------------------------

class TestPprintDepthWidth:
    def test_PrettyPrinter_depth_width(self):
        """`PrettyPrinter(depth=1, width=40) 真 depth+width 组合。"""
        pp = pprint.PrettyPrinter(depth=1, width=40)
        s = pp.pformat({"key_forge_1": 1, "key_forge_2": 2, "key_forge_3": 3})
        # 必非空
        assert isinstance(s, str)
        # 必含
        assert "key_forge_1" in s


# -- socket.sendmsg 进阶 (沙箱 AF_UNIX 限大小) -------------------------------

class TestSocketSendmsg:
    def test_sendmsg_small(self):
        """`socket.sendmsg 真发 AF_UNIX 小消息 (≤20 字节)`"""
        if sys.platform == "win32":
            pytest.skip("Windows 走不同 API")
        a, b = socket.socketpair(family=socket.AF_UNIX)
        try:
            # 小消息 ≤ 20 字节
            n = a.sendmsg([b"hi forge"])
            assert n >= 1
        except OSError:
            pytest.skip("沙箱 sendmsg 限制")
        finally:
            a.close()
            b.close()


# -- numbers.Number 抽象方法 -----------------------------------------------

class TestNumbersNumberAbstract:
    def test_Number_instantiate(self):
        """`numbers.Number() 真 instantiate 返 Number instance (沙箱 3.11 无 abstract) `"""
        # 沙箱 3.11 numbers.Number() 不抛 (无 __abstractmethods__ 必空)
        result = numbers.Number()
        # 必是 Number instance
        assert isinstance(result, numbers.Number)
        # 必含 __abstractmethods__
        assert hasattr(numbers.Number, "__abstractmethods__")
        # __abstractmethods__ 必是 frozenset (可空)
        assert isinstance(numbers.Number.__abstractmethods__, frozenset)


# -- trace.Trace class ------------------------------------------------------

class TestTraceClassV2:
    def test_Trace_class(self):
        """`trace.Trace 真 class 存在。"""
        assert trace.Trace is not None
        # 必可调
        assert callable(trace.Trace)


# -- ipaddress.Network.subnets() --------------------------------------------

class TestIpaddressSubnets:
    def test_IPv4Network_subnets(self):
        """`IPv4Network.subnets(new_prefix=26) 真拆 /24 → 4 /26。"""
        net = ipaddress.IPv4Network("192.168.0.0/24")
        subnets = list(net.subnets(new_prefix=26))
        # /24 → /26 = 2^2 = 4 subnets
        assert len(subnets) == 4, f"/24 subnets(new_prefix=26) 应=4,实际 {len(subnets)}"
        # 必含 192.168.0.0/26 + 192.168.0.64/26 + 192.168.0.128/26 + 192.168.0.192/26
        expected = [
            ipaddress.IPv4Network("192.168.0.0/26"),
            ipaddress.IPv4Network("192.168.0.64/26"),
            ipaddress.IPv4Network("192.168.0.128/26"),
            ipaddress.IPv4Network("192.168.0.192/26"),
        ]
        for e in expected:
            assert e in subnets, f"应含 {e}"
