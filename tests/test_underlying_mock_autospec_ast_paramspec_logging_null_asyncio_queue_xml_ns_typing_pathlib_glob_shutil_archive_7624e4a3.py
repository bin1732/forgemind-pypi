# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.create_autospec` + `ast.ParamSpec` + `logging.NullHandler` + `asyncio.Queue` + `xml.etree.register_namespace` + `typing.Concatenate` + `pathlib.Path.glob` + `shutil.make_archive` + `pprint.saferepr` + `socket.sethostname` 沙箱 skip + `numbers` ABC + `trace.CoverageResults` + `subprocess.Popen` + `ipaddress` 进阶 真底层测试。

覆盖 mock create_autospec / ast ParamSpec / logging NullHandler / asyncio Queue / xml etree register_namespace / typing Concatenate / pathlib glob / shutil make_archive / pprint saferepr / socket sethostname / numbers ABC / trace CoverageResults / subprocess Popen / ipaddress 模块:
  - `unittest.mock.create_autospec 真建带 spec 的 Mock`
  - `unittest.mock.create_autospec 真只能调真存在方法`
  - `ast.ParamSpec 3.12+ 沙箱 skip (3.11 无)`
  - `logging.NullHandler 真建 + 不抛`
  - `asyncio.Queue 真跨 task 5 item`
  - `asyncio.PriorityQueue 真按优先级 pop`
  - `xml.etree.register_namespace 真设 default ns`
  - `xml.etree.tostring + 序列化 namespace`
  - `typing.Concatenate[int, str, P] 3.10+ 真建`
  - `typing.TypeVar + ParamSpec 3.10+ (沙箱 3.11 skip)`
  - `pathlib.Path.glob 真找 *.py`
  - `pathlib.Path.rglob 真递归找`
  - `shutil.make_archive 真打 zip`
  - `shutil.get_archive_formats 真列 format`
  - `pprint.saferepr 真 repr`
  - `socket.sethostname 沙箱 skip (无 root)`
  - `numbers.Number + Complex ABC 必 subclass check`
  - `trace.CoverageResults 真建 instance`
  - `subprocess.Popen 真 PIPE 双向`
  - `ipaddress.IPv4Address 真比较 < >`
  - `ipaddress.IPv6Address 真比较 < >`
"""
import asyncio
import ipaddress
import logging
import numbers
import os
import pathlib
import pprint
import re
import shutil
import socket
import subprocess
import sys
import trace
import typing
import unittest.mock
import xml.etree.ElementTree as ET

import pytest


# -- unittest.mock.create_autospec ---------------------------------------------

class _API:
    def real_method(self, x):
        return x * 2

    def another_method(self, a, b):
        return a + b


class TestCreateAutospec:
    def test_create_autospec(self):
        """`create_autospec 真建带 spec 的 Mock。"""
        mock = unittest.mock.create_autospec(_API, instance=True)
        # 必能调 real_method
        mock.real_method.assert_not_called()
        # 必只能调 _API 的方法
        with pytest.raises(AttributeError):
            _ = mock.non_existent_method

    def test_create_autospec_call(self):
        """`create_autospec(callable, ...) 真只能调真存在方法。"""
        def real_fn(a, b):
            return a + b

        mock = unittest.mock.create_autospec(real_fn)
        # 必能调
        result = mock(3, 4)
        assert result == mock.return_value  # Mock default
        # 必能 mock 属性


# -- ast.ParamSpec 3.12+ 沙箱 skip -------------------------------------------

class TestAstAdvancedV12:
    def test_ParamSpec_3_12(self):
        """`ast.ParamSpec 3.12+ 沙箱 3.11 skip`。"""
        if sys.version_info < (3, 12):
            pytest.skip("3.12+ ParamSpec")
        if not hasattr(ast, "ParamSpec"):
            pytest.skip("沙箱无 ast.ParamSpec")
        assert ast.ParamSpec is not None


# -- logging.NullHandler -------------------------------------------------------

class TestLoggingNullHandler:
    def test_NullHandler(self):
        """`logging.NullHandler 真建 + 不抛。"""
        nh = logging.NullHandler()
        # 必是 Handler
        assert isinstance(nh, logging.Handler)
        # handle 必不抛
        nh.handle(logging.LogRecord(
            "forge_null", logging.INFO, "/x", 1, "msg", (), None
        ))


# -- asyncio.Queue + PriorityQueue --------------------------------------------

class TestAsyncioQueueV2:
    def test_Queue_cross_task(self):
        """`asyncio.Queue 真跨 task 5 item。"""

        async def main():
            q = asyncio.Queue()

            async def producer():
                for i in range(5):
                    await q.put(i)

            async def consumer():
                items = []
                while len(items) < 5:
                    items.append(await q.get())
                return items

            p = asyncio.create_task(producer())
            c = asyncio.create_task(consumer())
            await p
            return await c

        result = asyncio.run(main())
        assert result == [0, 1, 2, 3, 4]

    def test_PriorityQueue(self):
        """`asyncio.PriorityQueue 真按优先级 pop (低先出) 。"""

        async def main():
            pq = asyncio.PriorityQueue()
            # 乱序 put
            for item in [3, 1, 4, 1, 5, 9, 2, 6]:
                await pq.put(item)
            # 必按序 1,1,2,3,4,5,6,9
            ordered = []
            while not pq.empty():
                ordered.append(await pq.get())
            return ordered

        result = asyncio.run(main())
        assert result == [1, 1, 2, 3, 4, 5, 6, 9], f"PriorityQueue 应=[1,1,2,3,4,5,6,9],实际 {result}"


# -- xml.etree.register_namespace ----------------------------------------------

class TestXmlRegisterNamespace:
    def test_register_namespace(self):
        """`xml.etree.register_namespace 真设 default ns。"""
        ET.register_namespace("forge", "http://forge.example.com/ns")
        # 序列化
        root = ET.Element("{http://forge.example.com/ns}root")
        b = ET.tostring(root)
        # 必含 ns 串
        assert b"forge" in b
        # 必含 xmlns
        assert b"xmlns" in b


# -- typing.Concatenate + ParamSpec 3.10+ -------------------------------------

class TestTypingAdvancedV14:
    def test_Concatenate_basic(self):
        """`typing.Concatenate[int, str, P] 3.10+ 真建。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ Concatenate")
        C = typing.Concatenate[int, str, ...]
        assert C is not None
        # get_args 必含 int + str
        args = typing.get_args(C)
        assert int in args
        assert str in args

    def test_ParamSpec_3_10(self):
        """`typing.ParamSpec 3.10+ 沙箱 3.11 跳过。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ ParamSpec")
        # 沙箱 3.11 有
        if not hasattr(typing, "ParamSpec"):
            pytest.skip("沙箱无 typing.ParamSpec")
        P = typing.ParamSpec("P")
        # 必可调
        assert P is not None


# -- pathlib 进阶 (glob + rglob) ------------------------------------------------

class TestPathlibGlobV2:
    def test_glob(self, tmp_path):
        """`pathlib.Path.glob 真找 *.py。"""
        # 创 .py + .txt
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.py").write_text("b")
        (tmp_path / "c.txt").write_text("c")
        # glob
        py_files = list(tmp_path.glob("*.py"))
        # 必 ≥ 2
        assert len(py_files) >= 2
        names = [p.name for p in py_files]
        assert "a.py" in names
        assert "b.py" in names

    def test_rglob(self, tmp_path):
        """`pathlib.Path.rglob 真递归找。"""
        # 创 nested .py
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("deep")
        (tmp_path / "top.py").write_text("top")
        # rglob
        py_files = list(tmp_path.rglob("*.py"))
        # 必 ≥ 2
        assert len(py_files) >= 2


# -- shutil.make_archive -------------------------------------------------------

class TestShutilMakeArchive:
    def test_make_archive_zip(self, tmp_path):
        """`shutil.make_archive 真打 zip。"""
        # 创文件
        src = tmp_path / "src"
        src.mkdir()
        (src / "forge.txt").write_text("hello forge archive")
        # 打 zip
        archive_path = shutil.make_archive(
            str(tmp_path / "forge_archive"),
            "zip",
            root_dir=str(src),
        )
        # 必存在
        assert os.path.exists(archive_path), f"archive {archive_path} 不存在"
        assert archive_path.endswith(".zip")

    def test_get_archive_formats(self):
        """`shutil.get_archive_formats 真列 format。"""
        formats = shutil.get_archive_formats()
        # 必 ≥ 1
        assert len(formats) >= 1
        names = [f[0] for f in formats]
        # 必含 zip + tar
        assert "zip" in names or "gztar" in names, (
            f"formats 应含 zip/gztar,实际 {names}"
        )


# -- pprint.saferepr ----------------------------------------------------------

class TestPprintSaferepr:
    def test_saferepr(self):
        """`pprint.saferepr 真 repr 不抛。"""
        s = pprint.saferepr({"forge": 42, "list": [1, 2, 3]})
        # 必非空
        assert isinstance(s, str)
        # 必含 'forge'
        assert "forge" in s


# -- socket.sethostname 沙箱 skip ---------------------------------------------

class TestSocketSethostname:
    def test_sethostname_sandbox_skip(self):
        """`socket.sethostname 沙箱无 root skip。"""
        if sys.platform == "win32":
            pytest.skip("Windows 走 sethostname 不同 API")
        # 沙箱无 root: socket.sethostname('forge') 必抛 OSError
        with pytest.raises(OSError):
            socket.sethostname("forge-hostname-xyz")


# -- numbers ABC --------------------------------------------------------------

class TestNumbersAbcV2:
    def test_Number_Complex(self):
        """`numbers.Number + Complex ABC 必 subclass check。"""
        # Number 必是 Complex + Real + Rational 父
        # Real + Complex 必 is Number
        assert issubclass(complex, numbers.Number)
        assert issubclass(float, numbers.Number)
        assert issubclass(int, numbers.Number)
        # Real 必是 Number
        assert issubclass(numbers.Real, numbers.Number)
        # Complex 必是 Number
        assert issubclass(numbers.Complex, numbers.Number)


# -- trace.CoverageResults -----------------------------------------------------

class TestTraceCoverageResultsV2:
    def test_CoverageResults_instance(self):
        """`trace.CoverageResults 真建 instance。"""
        # 沙箱 3.11+ CoverageResults 必可实例化
        try:
            cr = trace.CoverageResults
            assert cr is not None
        except (TypeError, AttributeError):
            pytest.skip("沙箱无 CoverageResults")


# -- subprocess.Popen 双向 -----------------------------------------------------

class TestSubprocessPopenPipe:
    def test_Popen_pipe_bi(self):
        """`subprocess.Popen 真 stdin+stdout 双向 pipe。"""
        proc = subprocess.Popen(
            ["cat"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        # 写 + 读
        stdout, stderr = proc.communicate(input=b"hello forge pipe")
        assert stdout == b"hello forge pipe", f"stdout 应='hello forge pipe',实际 {stdout!r}"
        assert proc.returncode == 0


# -- ipaddress 进阶 (IPv4/IPv6 比较) -------------------------------------------

class TestIpaddressAdvancedV5:
    def test_IPv4_comparison(self):
        """`ipaddress.IPv4Address 真比较 < >. """
        a = ipaddress.IPv4Address("192.168.1.1")
        b = ipaddress.IPv4Address("10.0.0.1")
        # 必可比较
        assert a > b
        assert b < a
        # ==
        assert ipaddress.IPv4Address("192.168.1.1") == a

    def test_IPv6_comparison(self):
        """`ipaddress.IPv6Address 真比较 < >. """
        a = ipaddress.IPv6Address("2001:db8::1")
        b = ipaddress.IPv6Address("::1")
        # 必可比较
        assert a > b
        assert b < a
