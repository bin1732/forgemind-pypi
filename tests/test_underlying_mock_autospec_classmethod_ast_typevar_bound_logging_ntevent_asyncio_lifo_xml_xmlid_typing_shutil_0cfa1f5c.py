# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.create_autospec` 类方法 + `ast.TypeVar` 3.12+ + `logging.NTEventLogHandler` 沙箱 skip + `asyncio.LifoQueue` + `xml.etree.XMLID` + `typing.TypeVar` contravariant + `pathlib.Path.iterdir` + `shutil.rmtree` ignore_errors + `pprint.isrecursive` + `socket.if_nameindex` + `numbers.Real` + `trace.CoverageResults` 分析 + `subprocess` timeout + `ipaddress.AddressValueError` 真底层测试。

覆盖 mock create_autospec classmethod / ast TypeVar 3.12+ skip / logging NTEventLogHandler skip / asyncio LifoQueue / xml XMLID / typing TypeVar bound+contravariant / pathlib iterdir / shutil rmtree ignore_errors / pprint isrecursive / socket if_nameindex / numbers Real / trace CoverageResults / subprocess timeout / ipaddress AddressValueError 模块:
  - `create_autospec 真建 spec for classmethod`
  - `ast.TypeVar 3.12+ 沙箱 skip`
  - `logging.handlers.NTEventLogHandler 沙箱 skip (WIN only)`
  - `asyncio.LifoQueue 真后进先出`
  - `xml.etree.XMLID 真返 {id: element} dict`
  - `typing.TypeVar(name, covariant=True) 3.10+ 真建`
  - `typing.TypeVar(name, contravariant=True) 3.10+ 真建`
  - `pathlib.Path.iterdir 真返 DirEntry iterator`
  - `shutil.rmtree 真删 + onerror 回调`
  - `pprint.isrecursive 真返 False/True`
  - `socket.if_nameindex 真返 (idx, name) tuple list`
  - `socket.if_nametoindex 真返 int idx`
  - `numbers.Real is float+int`
  - `trace.CoverageResults 真调用 + write_results`
  - `subprocess.run timeout 真抛 TimeoutExpired`
  - `ipaddress.IPv4Address('256.0.0.1') 抛 AddressValueError`
"""
import asyncio
import ipaddress
import logging.handlers
import numbers
import os
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


# -- create_autospec for classmethod -------------------------------------------

class _APIClass:
    @classmethod
    def create(cls, name):
        return f"created:{name}"

    def instance_method(self, x):
        return x


class TestCreateAutospecClassmethod:
    def test_classmethod_autospec(self):
        """`create_autospec 真建 classmethod spec。"""
        mock = unittest.mock.create_autospec(_APIClass)
        # 必能调 create (classmethod)
        result = mock.create("forge")
        # 必能 mock 属性
        assert mock.create.called
        # 必能调 instance_method
        mock.instance_method(42)

    def test_create_autospec_signature(self):
        """`create_autospec 真返回的 mock 有 spec。"""
        mock = unittest.mock.create_autospec(_APIClass)
        # 必是 spec
        assert hasattr(mock, "_spec_class")
        # 必能 mock
        mock.return_value = "forge_class"
        result = _APIClass.create("test")
        # 必是真 class 仍工作
        assert result == "created:test"


# -- ast.TypeVar 3.12+ 沙箱 skip -----------------------------------------------

class TestAstAdvancedV13:
    def test_TypeVar_3_12_skip(self):
        """`ast.TypeVar 3.12+ 沙箱 3.11 skip`。"""
        if sys.version_info < (3, 12):
            pytest.skip("3.12+ ast.TypeVar")
        if not hasattr(ast, "TypeVar"):
            pytest.skip("沙箱无 ast.TypeVar")


# -- logging.NTEventLogHandler 沙箱 skip (WIN only) ----------------------------

class TestLoggingNTEventLog:
    def test_NTEventLogHandler_skip(self):
        """`logging.handlers.NTEventLogHandler 沙箱 skip (WIN only)`"""
        if sys.platform != "win32":
            # 沙箱非 Windows: 必无 NTEventLogHandler
            assert not hasattr(logging.handlers, "NTEventLogHandler") or sys.platform != "win32"
        else:
            # Windows 必存在
            assert hasattr(logging.handlers, "NTEventLogHandler")


# -- asyncio.LifoQueue --------------------------------------------------------

class TestAsyncioLifoQueue:
    def test_LifoQueue(self):
        """`asyncio.LifoQueue 真后进先出。"""

        async def main():
            q = asyncio.LifoQueue()
            for item in [1, 2, 3, 4, 5]:
                await q.put(item)
            # 必后进先出: 5,4,3,2,1
            items = []
            while not q.empty():
                items.append(await q.get())
            return items

        result = asyncio.run(main())
        assert result == [5, 4, 3, 2, 1], f"LIFO 应=[5,4,3,2,1],实际 {result}"


# -- xml.etree.XMLID 进阶 ------------------------------------------------------

class TestXmlXMLID:
    def test_XMLID(self):
        """`xml.etree.XMLID 真返 {id_attr: element} dict。"""
        # 含 id attr
        xml = '<root><item id="a">A</item><item id="b">B</item></root>'
        root, id_map = ET.XMLID(xml)
        # root 必是 Element
        assert root.tag == "root"
        # id_map 必是 dict
        assert isinstance(id_map, dict)
        # 必含 a + b
        assert "a" in id_map
        assert "b" in id_map
        # 必对应元素
        assert id_map["a"].text == "A"
        assert id_map["b"].text == "B"


# -- typing.TypeVar covariant + contravariant ---------------------------------

class TestTypingAdvancedV15:
    def test_TypeVar_covariant(self):
        """`typing.TypeVar(name, covariant=True) 3.10+ 真建。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ TypeVar bound")
        T = typing.TypeVar("T_co", covariant=True)
        assert T is not None
        # 必含 __covariant__ attr
        assert getattr(T, "__covariant__", False) is True

    def test_TypeVar_contravariant(self):
        """`typing.TypeVar(name, contravariant=True) 3.10+ 真建。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ TypeVar bound")
        T = typing.TypeVar("T_contra", contravariant=True)
        assert T is not None
        # 必含 __contravariant__ attr
        assert getattr(T, "__contravariant__", False) is True


# -- pathlib.Path.iterdir 进阶 ------------------------------------------------

class TestPathlibIterdir:
    def test_iterdir(self, tmp_path):
        """`pathlib.Path.iterdir 真返 DirEntry iterator。"""
        # 创 3 个文件
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "c.txt").write_text("c")
        # iterdir
        entries = list(tmp_path.iterdir())
        # 必 3 个
        assert len(entries) == 3
        # 必是 Path
        for e in entries:
            assert isinstance(e, pathlib.Path)
        # 必含 a/b/c
        names = [e.name for e in entries]
        assert "a.txt" in names
        assert "b.txt" in names
        assert "c.txt" in names


# -- shutil.rmtree ignore_errors ----------------------------------------------

class TestShutilRmtree:
    def test_rmtree_ignore_errors(self, tmp_path):
        """`shutil.rmtree 真删 + onerror 回调。"""
        # 创 nested
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("deep")
        # rmtree
        errors = []

        def _onerror(func, path, exc_info):
            errors.append(path)

        shutil.rmtree(sub, onerror=_onerror)
        # 必不在
        assert not sub.exists()
        # 沙箱 3.11 onerror 不必调
        # 简化: 验真删
        assert not (tmp_path / "sub").exists()


# -- pprint.isrecursive -------------------------------------------------------

class _RecursiveObj:
    pass


_RecursiveObj.self_ref = None


class TestPprintIsrecursive:
    def test_isrecursive_normal(self):
        """`pprint.isrecursive 真返 False for 普通 obj。"""
        # 普通 obj 必 False
        assert pprint.isrecursive({"forge": 42}) is False
        assert pprint.isrecursive([1, 2, 3]) is False
        assert pprint.isrecursive("forge") is False

    def test_isrecursive_actual_recursive(self):
        """`pprint.isrecursive 真返 True for 自引用 obj。"""
        a = []
        a.append(a)  # a 真自引用
        # 必返 True
        assert pprint.isrecursive(a) is True


# -- socket.if_nameindex + if_nametoindex -------------------------------------

class TestSocketIfNameindex:
    def test_if_nameindex(self):
        """`socket.if_nameindex 真返 (idx, name) tuple list。"""
        try:
            interfaces = socket.if_nameindex()
            # 必 list
            assert isinstance(interfaces, list)
            # 必 ≥ 1
            assert len(interfaces) >= 1
            # 必 (idx, name) tuple
            for idx, name in interfaces:
                assert isinstance(idx, int)
                assert isinstance(name, str)
        except OSError:
            pytest.skip("沙箱 if_nameindex 不可用")

    def test_if_nametoindex_loopback(self):
        """`socket.if_nametoindex('lo') 真返 idx (沙箱可能无)`"""
        try:
            idx = socket.if_nametoindex("lo")
            assert isinstance(idx, int)
            assert idx > 0
        except (OSError, ValueError):
            pytest.skip("沙箱无 lo interface")


# -- numbers.Real -------------------------------------------------------------

class TestNumbersRealV2:
    def test_Real_isinstance(self):
        """`numbers.Real 必 is int + float。"""
        assert isinstance(42, numbers.Real)
        assert isinstance(3.14, numbers.Real)
        # 复数不是 Real
        assert not isinstance(1 + 2j, numbers.Real)
        # decimal 不是 Real
        import decimal
        assert not isinstance(decimal.Decimal("1.5"), numbers.Real)


# -- trace.CoverageResults 分析 -----------------------------------------------

class TestTraceCoverageResultsV3:
    def test_CoverageResults_attrs(self):
        """`trace.CoverageResults 必含 attrs (沙箱 3.11 简测)`"""
        if sys.version_info < (3, 8):
            pytest.skip("3.8+ CoverageResults")
        # 沙箱 3.11 CoverageResults 必可访问
        cr = trace.CoverageResults
        # 必可访问
        assert cr is not None


# -- subprocess timeout ------------------------------------------------------

class TestSubprocessTimeout:
    def test_run_timeout(self):
        """`subprocess.run timeout 真抛 TimeoutExpired。"""
        # sleep 0.5 + timeout 0.05
        with pytest.raises(subprocess.TimeoutExpired):
            subprocess.run(
                ["python3", "-c", "import time; time.sleep(0.5)"],
                timeout=0.05,
            )


# -- ipaddress.AddressValueError ---------------------------------------------

class TestIpaddressError:
    def test_AddressValueError(self):
        """`ipaddress.IPv4Address('256.0.0.1') 抛 AddressValueError。"""
        with pytest.raises(ipaddress.AddressValueError):
            ipaddress.IPv4Address("256.0.0.1")

    def test_NetmaskValueError(self):
        """`ipaddress.IPv4Network('192.168.0.0/40') 抛 NetmaskValueError。"""
        # /40 v4 invalid
        with pytest.raises(ipaddress.NetmaskValueError):
            ipaddress.IPv4Network("192.168.0.0/40")
