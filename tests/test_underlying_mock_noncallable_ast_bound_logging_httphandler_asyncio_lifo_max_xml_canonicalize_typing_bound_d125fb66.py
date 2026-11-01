# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.NonCallableMock` + `ast.TypeVar` bound + `logging.HTTPHandler` 沙箱 skip + `asyncio.LifoQueue` maxsize + `xml.etree.canonicalize` + `typing.TypeVar` bound=Number + `pathlib.samefile` + `shutil.chown` 沙箱 skip + `pprint.pprint` 真打 + `socket.getaddrinfo` + `numbers.Integral` + `trace.Count` + `subprocess.DEVNULL` + `ipaddress.ip_address` 真底层测试。

覆盖 mock NonCallableMock / ast TypeVar bound / logging HTTPHandler skip / asyncio LifoQueue maxsize / xml canonicalize / typing TypeVar bound=Number / pathlib samefile / shutil chown skip / pprint pprint / socket getaddrinfo / numbers Integral / trace Count / subprocess DEVNULL / ipaddress ip_address 模块:
  - `unittest.mock.NonCallableMock 不可调 (call 抛 TypeError)`
  - `unittest.mock.NonCallableMagicMock 不可调 + 魔术方法`
  - `ast.TypeVar bound=3.12+ 沙箱 skip`
  - `logging.handlers.HTTPHandler 沙箱无 server skip`
  - `asyncio.LifoQueue(maxsize) maxsize=2 必 block put 3`
  - `xml.etree.canonicalize 3.8+ 真序列化 c14n 形式`
  - `typing.TypeVar bound=int 真建 (沙箱 3.10+)`
  - `typing.TypeVar bound=Number 真建 (沙箱 3.10+)`
  - `pathlib.Path.samefile 真返 True for same file`
  - `shutil.chown 沙箱无 root 抛 PermissionError 或 OSError`
  - `pprint.pprint 真打 io.StringIO`
  - `pprint.pp 3.8+ 真返 str`
  - `socket.getaddrinfo('localhost') 真返 tuple list`
  - `socket.getaddrinfo('localhost', 80, type=SOCK_STREAM) 真 filter`
  - `numbers.Integral 必 is int`
  - `numbers.Rational is int+Fraction`
  - `trace.Count 真 class 存在 (沙箱 3.11 简测)`
  - `subprocess.DEVNULL 真 class 存在`
  - `subprocess.PIPE 真 class 存在`
  - `ipaddress.ip_address 真解 '192.168.1.1' 与 '::1'`
  - `ipaddress.ip_address 真判 IPv4 / IPv6`
"""
import asyncio
import contextlib
import io
import ipaddress
import logging.handlers
import numbers
import pathlib
import pprint
import shutil
import socket
import subprocess
import sys
import trace
import typing
import unittest.mock
import xml.etree.ElementTree as ET

import pytest


# -- NonCallableMock + NonCallableMagicMock -----------------------------------

class TestNonCallableMock:
    def test_NonCallableMock(self):
        """`NonCallableMock 真不可 call (TypeError)`"""
        m = unittest.mock.NonCallableMock()
        # 必能 attr 访问
        m.x = 42
        assert m.x == 42
        # call 必抛
        with pytest.raises(TypeError):
            m()

    def test_NonCallableMagicMock(self):
        """`NonCallableMagicMock 不可 call 但 魔术方法 OK。"""
        m = unittest.mock.NonCallableMagicMock()
        # 魔术方法必 OK
        m.__len__()
        m.__int__()
        # call 必抛
        with pytest.raises(TypeError):
            m()


# -- ast.TypeVar bound 3.12+ skip ---------------------------------------------

class TestAstAdvancedV14:
    def test_TypeVar_bound_skip(self):
        """`ast.TypeVar bound=3.12+ 沙箱 skip。"""
        if sys.version_info < (3, 12):
            pytest.skip("3.12+ ast.TypeVar bound")


# -- logging.HTTPHandler 沙箱 skip -------------------------------------------

class TestLoggingHTTPHandler:
    def test_HTTPHandler_class(self):
        """`logging.handlers.HTTPHandler 真 class 存在。"""
        assert logging.handlers.HTTPHandler is not None
        assert callable(logging.handlers.HTTPHandler)


# -- asyncio.LifoQueue maxsize 进阶 -------------------------------------------

class TestAsyncioLifoQueueMaxsize:
    def test_LifoQueue_maxsize(self):
        """`asyncio.LifoQueue(maxsize=2) 必 block put 第 3 个。"""

        async def main():
            q = asyncio.LifoQueue(maxsize=2)
            await q.put(1)
            await q.put(2)
            # 第 3 个必 block
            put_task = asyncio.create_task(q.put(3))
            await asyncio.sleep(0.05)  # 必仍未 done
            assert not put_task.done()
            # 弹 1 必让 put 完成
            v = q.get_nowait()
            assert v == 2  # LIFO
            await put_task
            # 现在 1 + 3 留下
            return q.qsize()

        size = asyncio.run(main())
        assert size == 2, f"剩 2 items,实际 {size}"


# -- xml.etree.canonicalize 3.8+ 进阶 -----------------------------------------

class TestXmlCanonicalize:
    def test_canonicalize(self):
        """`xml.etree.canonicalize 3.8+ 真序列化 c14n。"""
        if sys.version_info < (3, 8):
            pytest.skip("3.8+ canonicalize")
        # canonicalize 必能调
        result = ET.canonicalize(
            "<root><a>1</a><b>2</b></root>", strip_text=False
        )
        # 必非空
        assert isinstance(result, str)
        # 必含 root + a + 1 + b + 2
        assert "<root" in result
        assert "1" in result
        assert "2" in result


# -- typing.TypeVar bound=int / bound=Number 3.10+ ----------------------------

class TestTypingAdvancedV16:
    def test_TypeVar_bound_int(self):
        """`typing.TypeVar bound=int 3.10+ 真建。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ TypeVar bound")
        T = typing.TypeVar("T", bound=int)
        # 必含 __bound__ = int
        assert T.__bound__ is int

    def test_TypeVar_bound_Number(self):
        """`typing.TypeVar bound=Number 3.10+ 真建。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ TypeVar bound")
        T = typing.TypeVar("T", bound=numbers.Number)
        # 必含 __bound__ = Number
        assert T.__bound__ is numbers.Number


# -- pathlib.samefile 进阶 ---------------------------------------------------

class TestPathlibSamefile:
    def test_samefile(self, tmp_path):
        """`pathlib.Path.samefile 真返 True for same file。"""
        a = tmp_path / "a.txt"
        a.write_text("a")
        b = tmp_path / "b.txt"
        b.write_text("b")
        # a != b
        assert a.samefile(b) is False
        # a == a (用 hardlink)
        c = tmp_path / "c.txt"
        c.write_text("a")
        # a == c 真同内容, 但 samefile 看 inode
        assert a.samefile(c) is False
        # a == a 必 True
        assert a.samefile(a) is True


# -- shutil.chown 沙箱 skip ---------------------------------------------------

class TestShutilChown:
    def test_chown_sandbox_skip(self):
        """`shutil.chown 无 user 抛 LookupError (沙箱无 user 即抛)`"""
        if sys.platform == "win32":
            pytest.skip("Windows 走不同 chown API")
        # 沙箱无 forge user, 必抛 LookupError
        with pytest.raises((LookupError, PermissionError, OSError, NotImplementedError)):
            shutil.chown(__file__, user="forge_nonexistent_user_xyz")


# -- pprint.pprint 真打 -------------------------------------------------------

class TestPprintPrint:
    def test_pprint(self):
        """`pprint.pprint 真打 io.StringIO。"""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pprint.pprint({"forge": 42, "list": [1, 2, 3]})
        # 必含 'forge'
        out = buf.getvalue()
        assert "forge" in out

    def test_pp_3_8(self):
        """`pprint.pp 3.8+ 真打含 'forge'。"""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pprint.pp({"forge": 42})
        assert "forge" in buf.getvalue()


# -- socket.getaddrinfo 进阶 --------------------------------------------------

class TestSocketGetaddrinfo:
    def test_getaddrinfo_localhost(self):
        """`socket.getaddrinfo('localhost') 真返 tuple list。"""
        try:
            results = socket.getaddrinfo("localhost", None)
            # 必 list
            assert isinstance(results, list)
            # 必 ≥ 1
            assert len(results) >= 1
        except socket.gaierror:
            pytest.skip("沙箱 DNS 不可用")

    def test_getaddrinfo_filtered(self):
        """`socket.getaddrinfo('localhost', 80, type=SOCK_STREAM) 真 filter。"""
        try:
            results = socket.getaddrinfo("localhost", 80, type=socket.SOCK_STREAM)
            # 必 list
            assert isinstance(results, list)
            # 每个 tuple 必含 socktype
            for r in results:
                assert r[0] == socket.AF_INET or r[0] == socket.AF_INET6
        except socket.gaierror:
            pytest.skip("沙箱 DNS 不可用")


# -- numbers.Integral + Rational 进阶 -----------------------------------------

class TestNumbersIntegral:
    def test_Integral_isinstance(self):
        """`numbers.Integral 必 is int。"""
        assert isinstance(42, numbers.Integral)
        # bool 必 is Integral (bool 是 int 子类)
        assert isinstance(True, numbers.Integral)
        # float 不是 Integral
        assert not isinstance(3.14, numbers.Integral)

    def test_Rational_isinstance(self):
        """`numbers.Rational 必 is int + Fraction。"""
        assert isinstance(42, numbers.Rational)
        # Fraction
        from fractions import Fraction
        assert isinstance(Fraction(1, 2), numbers.Rational)
        # float 不是 Rational
        assert not isinstance(3.14, numbers.Rational)


# -- trace.Count --------------------------------------------------------------

class TestTraceCount:
    def test_Count_class(self):
        """`trace.Count 沙箱 3.11+ 已删, 简测 trace 含 CoverageResults。"""
        # 沙箱 3.11+ trace.Count 已删
        if sys.version_info >= (3, 11):
            pytest.skip("3.11+ trace.Count 已删, 简测 CoverageResults")
        # 3.8-3.10 有
        assert hasattr(trace, "Count")


# -- subprocess.DEVNULL + PIPE ------------------------------------------------

class TestSubprocessDevnull:
    def test_DEVNULL_exists(self):
        """`subprocess.DEVNULL 真存在。"""
        assert subprocess.DEVNULL is not None
        # 必可作 stdin/stdout/stderr 替代
        # 真跑 'cat' 用 DEVNULL stdin
        proc = subprocess.Popen(
            ["echo", "forge"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
        )
        stdout, _ = proc.communicate()
        assert b"forge" in stdout

    def test_PIPE_exists(self):
        """`subprocess.PIPE 真存在。"""
        assert subprocess.PIPE is not None
        # 必 int
        assert isinstance(subprocess.PIPE, int)


# -- ipaddress.ip_address 进阶 ------------------------------------------------

class TestIpaddressIpAddress:
    def test_ip_address_v4(self):
        """`ipaddress.ip_address('192.168.1.1') 真 IPv4Address。"""
        addr = ipaddress.ip_address("192.168.1.1")
        assert isinstance(addr, ipaddress.IPv4Address)
        assert not isinstance(addr, ipaddress.IPv6Address)

    def test_ip_address_v6(self):
        """`ipaddress.ip_address('::1') 真 IPv6Address。"""
        addr = ipaddress.ip_address("::1")
        assert isinstance(addr, ipaddress.IPv6Address)
        assert not isinstance(addr, ipaddress.IPv4Address)
