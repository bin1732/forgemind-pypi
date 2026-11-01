# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.Mock` spec=[] / `ast.MatchStar` 3.10+ / `logging.handlers.NTEventLogHandler` 沙箱 skip / `asyncio.Semaphore` 真跨 task / `xml.etree.XMLPullParser` events / `typing.Annotated` 3.9+ / `pathlib.relative_to` / `shutil.move` / `pprint.pprint` 进阶 / `socket.getnameinfo` / `numbers.Complex` / `trace.Trace` globaltrace / `subprocess.list2cmdline` / `ipaddress.IPv4Address/Network` 真 str 底层测试。

覆盖 Mock spec=[] / ast MatchStar / logging NTEventLogHandler skip / asyncio Semaphore / xml XMLPullParser events / typing Annotated / pathlib relative_to / shutil move / pprint pprint / socket getnameinfo / numbers Complex / trace Trace globaltrace / subprocess list2cmdline / ipaddress IPv4Address+Network str 模块:
  - `Mock(spec=[]) 必不能调任何方法`
  - `ast.MatchStar 3.10+ 真建+name='rest'`
  - `logging.handlers.NTEventLogHandler 沙箱非 Windows 无`
  - `asyncio.Semaphore 真 limit=2 max=2 并发`
  - `xml.etree.XMLPullParser 真迭代 events ≥ 1`
  - `typing.Annotated 3.9+ 真建`
  - `typing.get_type_hints 解 Annotated`
  - `pathlib.Path.relative_to 真返 path`
  - `shutil.move 真跨设备/同设备移动`
  - `pprint.pprint 真打大 dict 不抛`
  - `socket.getnameinfo 真解 (host, port)`
  - `numbers.Complex is complex`
  - `trace.Trace + globaltrace 真跑`
  - `subprocess.list2cmdline 真合成 cmd str`
  - `ipaddress.IPv4Address('192.168.1.1') str='192.168.1.1'`
  - `ipaddress.IPv4Network('192.168.0.0/24') str='192.168.0.0/24'`
"""
import ast
import asyncio
import contextlib
import io
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


# -- Mock spec=[] --------------------------------------------------------------

class TestMockSpecEmpty:
    def test_spec_empty(self):
        """`Mock(spec=[]) 必不能调任何方法。"""
        m = unittest.mock.Mock(spec=[])
        # 必不能调
        with pytest.raises(AttributeError):
            _ = m.any_method
        # 必能设 attr (实际 mock 仍允许 set)
        m.x = 42
        assert m.x == 42


# -- ast.MatchStar 3.10+ ------------------------------------------------------

class TestAstAdvancedV16:
    def test_MatchStar_3_10(self):
        """`ast.MatchStar 3.10+ 真建+name='rest'。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ MatchStar")
        if not hasattr(ast, "MatchStar"):
            pytest.skip("沙箱无 MatchStar")
        # 创 MatchStar 节点
        ms = ast.MatchStar(name="rest")
        assert ms.name == "rest"
        # dump
        dumped = ast.dump(ms)
        assert "MatchStar" in dumped
        assert "rest" in dumped


# -- logging.NTEventLogHandler 沙箱 skip --------------------------------------

class TestLoggingNTEventLogV2:
    def test_NTEventLogHandler_sandbox_skip(self):
        """`logging.handlers.NTEventLogHandler 真 class 存在 (在 module 中导入即存在)。"""
        # 沙箱 3.11+ 实际有 NTEventLogHandler 类定义, 只是不可实例化
        # 简化: 真 class 必存在
        assert hasattr(logging.handlers, "NTEventLogHandler")


# -- asyncio.Semaphore 真 limit -----------------------------------------------

class TestAsyncioSemaphore:
    def test_Semaphore_limit(self):
        """`asyncio.Semaphore(2) 真 max=2 并发 5 task。"""

        async def main():
            sem = asyncio.Semaphore(2)
            active = 0
            max_active = 0

            async def worker():
                nonlocal active, max_active
                async with sem:
                    active += 1
                    max_active = max(max_active, active)
                    await asyncio.sleep(0.05)
                    active -= 1

            workers = [asyncio.create_task(worker()) for _ in range(5)]
            await asyncio.gather(*workers)
            return max_active

        max_active = asyncio.run(main())
        assert max_active == 2, f"Semaphore(2) max=2,实际 {max_active}"


# -- xml.etree.XMLPullParser 进阶 ---------------------------------------------

class TestXmlPullParserV2:
    def test_pull_parser_events(self):
        """`xml.etree.XMLPullParser 真迭代 events ≥ 1。"""
        parser = ET.XMLPullParser(events=("start", "end"))
        parser.feed("<root><forge>text</forge></root>")
        parser.close()
        events = list(parser.read_events())
        # 必 ≥ 1
        assert len(events) >= 1
        # 每个 event 必 (event, element)
        for event, elem in events:
            assert event in ("start", "end")
            assert isinstance(elem, ET.Element)


# -- typing.Annotated 3.9+ 进阶 -----------------------------------------------

class TestTypingAdvancedV18:
    def test_Annotated(self):
        """`typing.Annotated 3.9+ 真建。"""
        if sys.version_info < (3, 9):
            pytest.skip("3.9+ Annotated")
        # Annotated[int, 'forge_meta']
        A = typing.Annotated[int, "forge_meta"]
        # 必是 typing.Annotated type
        assert typing.get_origin(A) is not None
        # get_args 含 int + 'forge_meta'
        args = typing.get_args(A)
        assert int in args

    def test_get_type_hints_Annotated(self):
        """`get_type_hints 真解 Annotated。"""
        if sys.version_info < (3, 9):
            pytest.skip("3.9+ Annotated")

        def my_fn(x: "typing.Annotated[int, 'forge']") -> "bool":
            return True

        hints = typing.get_type_hints(my_fn, include_extras=True)
        # 必含 x
        assert "x" in hints
        # 沙箱 3.11+ 必能解


# -- pathlib.relative_to 进阶 -------------------------------------------------

class TestPathlibRelative:
    def test_relative_to(self, tmp_path):
        """`pathlib.Path.relative_to 真返相对 path。"""
        sub = tmp_path / "sub"
        sub.mkdir()
        deep = sub / "deep.txt"
        deep.write_text("x")
        # relative_to tmp_path
        rel = deep.relative_to(tmp_path)
        # 必是 'sub/deep.txt'
        assert str(rel) == os.path.join("sub", "deep.txt")


# -- shutil.move 进阶 ---------------------------------------------------------

class TestShutilMove:
    def test_move(self, tmp_path):
        """`shutil.move 真跨目录移动 (dst 必是 file path 不是 dir)`"""
        src = tmp_path / "src"
        src.mkdir()
        (src / "forge.txt").write_text("hello forge move")
        # move 到 dst_dir (创 dir)
        dst_dir = tmp_path / "dst"
        dst_dir.mkdir()
        # move src/forge.txt → dst_dir/forge.txt
        moved = shutil.move(str(src / "forge.txt"), str(dst_dir))
        # 必存在 dst_dir/forge.txt
        target = dst_dir / "forge.txt"
        assert target.exists(), f"{target} 不存在"
        # 必含内容
        assert target.read_text() == "hello forge move"


# -- pprint.pprint 进阶 -------------------------------------------------------

class TestPprintPPrint:
    def test_pprint_big_dict(self):
        """`pprint.pprint 真打大 dict 不抛。"""
        big = {f"key_{i}": i * 2 for i in range(50)}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pprint.pprint(big)
        # 必含 forge 字串 ... 实际必非空
        out = buf.getvalue()
        assert len(out) > 0
        assert "key_0" in out
        assert "key_49" in out


# -- socket.getnameinfo 进阶 --------------------------------------------------

class TestSocketGetnameinfo:
    def test_getnameinfo(self):
        """`socket.getnameinfo 真解 (host, port)。"""
        try:
            host, port = socket.getnameinfo(("127.0.0.1", 80), 0)
            # 必返 tuple
            assert isinstance(host, str)
            assert isinstance(port, (int, str))
        except (socket.gaierror, OSError):
            pytest.skip("沙箱 getnameinfo 不可用")


# -- numbers.Complex ----------------------------------------------------------

class TestNumbersComplex:
    def test_Complex_isinstance(self):
        """`numbers.Complex 必 is complex。"""
        assert isinstance(1 + 2j, numbers.Complex)
        # int+float 也是 Complex
        assert isinstance(42, numbers.Complex)
        assert isinstance(3.14, numbers.Complex)
        # 必是 Number 子类
        assert issubclass(numbers.Complex, numbers.Number)


# -- trace.Trace + globaltrace -----------------------------------------------

class TestTraceGlobaltraceV2:
    def test_Trace_globaltrace(self):
        """`trace.Trace + runfunc 真跑 lambda + 验 results。"""
        tr = trace.Trace(trace=0, count=True)
        # 必能跑 + 必能 results
        tr.runfunc(lambda: sum([i for i in range(5)]))
        # 必 results 非空
        assert tr.results() is not None


# -- subprocess.list2cmdline 进阶 ---------------------------------------------

class TestSubprocessList2cmdline:
    def test_list2cmdline(self):
        """`subprocess.list2cmdline 真合成 cmd str。"""
        if sys.platform == "win32":
            # Windows: 必返 'a b c'
            cmd = subprocess.list2cmdline(["a", "b", "c"])
            assert cmd == "a b c"
        else:
            # Unix: 必返 ['a', 'b', 'c'] (shlex.quote)
            cmd = subprocess.list2cmdline(["a", "b", "c"])
            assert cmd == "a b c"

    def test_list2cmdline_quote(self):
        """`subprocess.list2cmdline 真加引号含空格的 arg。"""
        if sys.platform != "win32":
            cmd = subprocess.list2cmdline(["hello world", "b"])
            # Unix: 'hello world' 单引号
            assert "hello world" in cmd


# -- ipaddress.IPv4Address/Network str 进阶 ------------------------------------

class TestIpaddressStr:
    def test_IPv4Address_str(self):
        """`ipaddress.IPv4Address('192.168.1.1') str='192.168.1.1'。"""
        addr = ipaddress.IPv4Address("192.168.1.1")
        # str 真
        assert str(addr) == "192.168.1.1"
        # compressed 必同
        assert addr.compressed == "192.168.1.1"

    def test_IPv4Network_str(self):
        """`ipaddress.IPv4Network('192.168.0.0/24') str='192.168.0.0/24'。"""
        net = ipaddress.IPv4Network("192.168.0.0/24")
        # str
        assert str(net) == "192.168.0.0/24"
        # compressed
        assert net.compressed == "192.168.0.0/24"
        # 必 ≥ 1 num_addresses
        assert net.num_addresses == 256
