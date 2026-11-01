# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.patch.object` 进阶 / `ast.Pattern` 节点 3.10+ / `logging.handlers.SocketHandler` 进阶 / `asyncio.Future.cancel` / `xml.etree.Element` iter 树 / `typing.Union` 3.10+ / `pathlib.rmdir` / `shutil.copytree` / `pprint.PrettyPrinter` 进阶 / `socket.recvmsg` / `numbers.Number` 边界 / `trace.Trace` 进阶 / `ipaddress.Network.hosts()` 底层测试。

覆盖 mock patch.object / ast Pattern / logging SocketHandler / asyncio Future cancel / xml tree iter / typing Union / pathlib rmdir / shutil copytree / pprint PrettyPrinter / socket recvmsg / numbers Number 边界 / trace Trace / ipaddress hosts 模块:
  - `unittest.mock.patch.object 真替 classmethod`
  - `ast.Pattern 3.10+ 沙箱 3.11+ 必可建 (MatchSequence 是 Pattern 子)`
  - `logging.handlers.SocketHandler 真 class 存在`
  - `asyncio.Future 真 cancel + cancelled() 真 True`
  - `xml.etree.Element 真 iter 树 (含子嵌套)`
  - `typing.Union[int, str] 3.10+ 真建 (沙箱 3.11 skip 已是 PEP 604)`
  - `pathlib.Path.rmdir 真删空 dir`
  - `shutil.copytree 真复制 dir`
  - `pprint.PrettyPrinter(stream=buf) 真打 stream`
  - `socket.recvmsg 沙箱 AF_UNIX 简测`
  - `numbers.Number + Complex + Real + Rational + Integral 5 ABC 真继承`
  - `trace.Trace(count=True, trace=0) 真跑 + results`
  - `ipaddress.IPv4Network /30 hosts 2 不含 net+broadcast`
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


# -- unittest.mock.patch.object 进阶 -----------------------------------------

class _PatchTarget:
    @classmethod
    def class_method(cls):
        return "real_class"

    def instance_method(self):
        return "real_instance"


class TestMockPatchObject:
    def test_patch_object_classmethod(self):
        """`patch.object 真替 classmethod。"""
        with unittest.mock.patch.object(
            _PatchTarget, "class_method", return_value="forge_class"
        ):
            assert _PatchTarget.class_method() == "forge_class"
        # 退出后必还原
        assert _PatchTarget.class_method() == "real_class"


# -- ast.Pattern 3.10+ 节点 --------------------------------------------------

class TestAstPatternNode:
    def test_Pattern_node(self):
        """`ast.Pattern 3.10+ 沙箱 3.11+ 必可建 (MatchSequence 是 Pattern 子)`"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ Pattern")
        if not hasattr(ast, "Pattern"):
            pytest.skip("沙箱无 ast.Pattern")
        # 沙箱 3.11+ 必有 ast.Pattern
        assert ast.Pattern is not None
        # MatchSequence 真是 Pattern 子
        ms = ast.MatchSequence(patterns=[])
        assert isinstance(ms, ast.Pattern)


# -- logging.handlers.SocketHandler 进阶 -------------------------------------

class TestLoggingSocketHandlerV2:
    def test_SocketHandler_class(self):
        """`logging.handlers.SocketHandler 真 class 存在。"""
        assert logging.handlers.SocketHandler is not None


# -- asyncio.Future.cancel ---------------------------------------------------

class TestAsyncioFutureCancel:
    def test_Future_cancel(self):
        """`asyncio.Future 真 cancel + cancelled() 真 True。"""

        async def main():
            fut = asyncio.Future()
            # 必 not cancelled
            assert not fut.cancelled()
            # cancel 必 True
            result = fut.cancel()
            assert result is True
            # 必 cancelled
            assert fut.cancelled()
            # done 必 True
            assert fut.done()

        asyncio.run(main())


# -- xml.etree.Element tree iter ---------------------------------------------

class TestXmlTreeIter:
    def test_Element_tree_iter(self):
        """`xml.etree.Element 真 iter 树 (含子嵌套)。"""
        root = ET.fromstring("<root><a><b>1</b></a><c>2</c></root>")
        # 必能 iter 树
        all_elems = list(root.iter())
        # 必 ≥ 3 (root + a + b + c)
        assert len(all_elems) >= 3
        tags = [e.tag for e in all_elems]
        assert "root" in tags
        assert "a" in tags
        assert "b" in tags
        assert "c" in tags


# -- typing.Union 3.10+ 沙箱 skip (PEP 604 int|str) --------------------------

class TestTypingAdvancedV25:
    def test_Union(self):
        """`typing.Union[int, str] 3.10+ 沙箱 3.11 验真。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ Union PEP 604")
        # typing.Union 必存在
        U = typing.Union[int, str]
        # 必可调
        assert U is not None
        # 沙箱 3.11+ typing.get_args 必 ≥ 2
        args = typing.get_args(U)
        assert len(args) >= 2


# -- pathlib.rmdir ------------------------------------------------------------

class TestPathlibRmdir:
    def test_rmdir(self, tmp_path):
        """`pathlib.Path.rmdir 真删空 dir。"""
        d = tmp_path / "forge_dir"
        d.mkdir()
        assert d.exists()
        # rmdir
        d.rmdir()
        # 必不在
        assert not d.exists()


# -- shutil.copytree ---------------------------------------------------------

class TestShutilCopytree:
    def test_copytree(self, tmp_path):
        """`shutil.copytree 真复制 dir。"""
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.txt").write_text("a")
        sub = src / "sub"
        sub.mkdir()
        (sub / "b.txt").write_text("b")
        # copytree
        dst = tmp_path / "dst"
        shutil.copytree(src, dst)
        # 必含 a.txt + sub/b.txt
        assert (dst / "a.txt").exists()
        assert (dst / "a.txt").read_text() == "a"
        assert (dst / "sub" / "b.txt").exists()
        assert (dst / "sub" / "b.txt").read_text() == "b"


# -- pprint.PrettyPrinter stream --------------------------------------------

class TestPprintStream:
    def test_PrettyPrinter_stream(self):
        """`PrettyPrinter(stream=buf) 简测: pformat 必返 str (不直接打 stream)`"""
        import io
        buf = io.StringIO()
        pp = pprint.PrettyPrinter(stream=buf)
        # pformat 必返 str (不直接打 stream)
        s = pp.pformat({"forge": 42})
        assert "forge" in s
        # 必含 str
        assert isinstance(s, str)


# -- socket.recvmsg 沙箱 简测 ------------------------------------------------

class TestSocketRecvmsg:
    def test_recvmsg_small(self):
        """`socket.recvmsg 沙箱 AF_UNIX 简测 (≤20 字节)`"""
        if sys.platform == "win32":
            pytest.skip("Windows 走不同 API")
        a, b = socket.socketpair(family=socket.AF_UNIX)
        try:
            b.sendall(b"hi")
            data, ancdata, msg_flags, addr = a.recvmsg(16)
            # 必收 'hi'
            assert data == b"hi", f"data 应 'hi',实际 {data!r}"
        finally:
            a.close()
            b.close()


# -- numbers 5 ABC 继承 -----------------------------------------------------

class TestNumbers5AbcInherit:
    def test_5_ABC_inheritance(self):
        """`numbers 5 ABC 真继承 Number>Complex>Real>Rational>Integral。"""
        # 必 is subclass
        assert issubclass(numbers.Complex, numbers.Number)
        assert issubclass(numbers.Real, numbers.Complex)
        assert issubclass(numbers.Rational, numbers.Real)
        assert issubclass(numbers.Integral, numbers.Rational)


# -- trace.Trace 进阶 --------------------------------------------------------

class TestTraceAdvancedV3:
    def test_Trace_count_trace(self):
        """`trace.Trace(count=True, trace=0) 真跑 + results。"""
        tr = trace.Trace(count=True, trace=0)
        tr.runfunc(lambda: sum([i for i in range(5)]))
        # 必 results 非空
        assert tr.results() is not None


# -- ipaddress.Network.hosts() 进阶 ------------------------------------------

class TestIpaddressHostsV2:
    def test_IPv4Network_hosts(self):
        """`IPv4Network /30 hosts 真 2 不含 net+broadcast。"""
        net = ipaddress.IPv4Network("192.168.0.0/30")
        hosts = list(net.hosts())
        # 必 2
        assert len(hosts) == 2
        # 必不含 192.168.0.0 (net) + 192.168.0.3 (broadcast)
        for h in hosts:
            assert h != ipaddress.IPv4Address("192.168.0.0")
            assert h != ipaddress.IPv4Address("192.168.0.3")
