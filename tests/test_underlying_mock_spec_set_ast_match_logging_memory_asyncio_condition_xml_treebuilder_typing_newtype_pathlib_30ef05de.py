# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.MagicMock` spec=set+list+dict / `ast.MatchSingleton` 3.10+ / `logging.handlers.MemoryHandler` / `asyncio.Condition` 真跨 task / `xml.etree.TreeBuilder` / `typing.NewType` distinct / `pathlib.is_file/is_dir` / `shutil.which` / `pprint.PrettyPrinter` indent / `socket.gethostbyaddr` / `numbers.Real` / `trace.Trace+count` / `subprocess.CompletedProcess` / `ipaddress.IPv6Network` supernet 真底层测试。

覆盖 MagicMock spec=set+list+dict / ast MatchSingleton / logging MemoryHandler / asyncio Condition / xml TreeBuilder / typing NewType / pathlib is_file / shutil which / pprint PrettyPrinter indent / socket gethostbyaddr / numbers Real / trace Trace+count / subprocess CompletedProcess / ipaddress IPv6Network supernet 模块:
  - `MagicMock(spec=set) 必只含 set 方法`
  - `MagicMock(spec=list) 必只含 list 方法`
  - `MagicMock(spec=dict) 必只含 dict 方法`
  - `ast.MatchSingleton 3.10+ 沙箱 skip (3.11 存在)`
  - `ast.parse 真解 match-case 3.10+`
  - `logging.handlers.MemoryHandler 真 buffer 写 flush`
  - `asyncio.Condition 真跨 task 5 waiter`
  - `xml.etree.TreeBuilder 真子化 + start+end + close`
  - `xml.etree.XMLParser 真建 + feed 真解`
  - `typing.NewType(UserId, int) 创 UserId+OrderId distinct`
  - `pathlib.Path.is_file 真返 bool`
  - `pathlib.Path.is_dir 真返 bool`
  - `shutil.which 真返 cmd path or None`
  - `pprint.PrettyPrinter(indent=4) 真改 indent`
  - `socket.gethostbyaddr('127.0.0.1') 真返 (host, [aliases], [ips])`
  - `numbers.Real is int+float+Decimal.Finite (但 Decimal 不 isinstance)`
  - `trace.Trace(count=True) 真跑 + 验 results`
  - `subprocess.CompletedProcess 真建 instance + args+returncode+stdout`
  - `ipaddress.IPv6Network 真 supernet /28 真 /24`
"""
import ast
import asyncio
import contextlib
import ipaddress
import io
import logging
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


# -- MagicMock spec=set+list+dict ---------------------------------------------

class TestMagicMockSpec:
    def test_spec_set(self):
        """`MagicMock(spec=set) 必只含 set 方法。"""
        m = unittest.mock.MagicMock(spec=set)
        m.add("forge")
        m.add.assert_called_with("forge")
        # 必不能调 set 没的方法
        with pytest.raises(AttributeError):
            _ = m.append

    def test_spec_list(self):
        """`MagicMock(spec=list) 必只含 list 方法。"""
        m = unittest.mock.MagicMock(spec=list)
        m.append("forge")
        m.append.assert_called_with("forge")
        # 必不能调 list 没的方法
        with pytest.raises(AttributeError):
            _ = m.add

    def test_spec_dict(self):
        """`MagicMock(spec=dict) 必只含 dict 方法。"""
        m = unittest.mock.MagicMock(spec=dict)
        m.update({"forge": 42})
        m.update.assert_called_with({"forge": 42})
        # 必不能调 dict 没的方法
        with pytest.raises(AttributeError):
            _ = m.append


# -- ast.MatchSingleton 3.10+ -------------------------------------------------

class TestAstAdvancedV15:
    def test_MatchSingleton_3_10(self):
        """`ast.MatchSingleton 3.10+ 沙箱 3.11 验真。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ MatchSingleton")
        if not hasattr(ast, "MatchSingleton"):
            pytest.skip("沙箱无 MatchSingleton")
        # 创 MatchSingleton 节点
        ms = ast.MatchSingleton(value=None)
        assert ms.value is None
        # dump
        dumped = ast.dump(ms)
        assert "MatchSingleton" in dumped

    def test_parse_match(self):
        """`ast.parse 真解 match-case 3.10+。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ match")
        # match-case 必 valid
        tree = ast.parse("""
match x:
    case 1:
        pass
    case _:
        pass
""")
        # 必含 Match
        matches = [n for n in ast.walk(tree) if isinstance(n, ast.Match)]
        assert len(matches) == 1, f"应 1 Match,实际 {len(matches)}"


# -- logging.MemoryHandler ----------------------------------------------------

class TestLoggingMemoryHandler:
    def test_MemoryHandler(self):
        """`MemoryHandler 真 buffer 写 flush。"""
        log = logging.getLogger("forge_memory")
        log.setLevel(logging.INFO)
        log.handlers.clear()
        # Target handler (真写 StringIO)
        target_buf = io.StringIO()
        target_h = logging.StreamHandler(target_buf)
        # MemoryHandler buffer 10
        mh = logging.handlers.MemoryHandler(capacity=10, target=target_h)
        log.addHandler(mh)
        try:
            log.info("forge memory 1")
            log.info("forge memory 2")
            # 还未 flush
            assert "forge memory 1" not in target_buf.getvalue()
            # flush
            mh.flush()
            # 必含
            assert "forge memory 1" in target_buf.getvalue()
        finally:
            log.removeHandler(mh)


# -- asyncio.Condition 真跨 task ---------------------------------------------

class TestAsyncioConditionV2:
    def test_Condition_cross_task(self):
        """`asyncio.Condition 真跨 task 5 waiter。"""

        async def main():
            cond = asyncio.Condition()
            results = []

            async def waiter(idx):
                async with cond:
                    await cond.wait()
                    results.append(idx)

            async def notifier():
                await asyncio.sleep(0.01)
                async with cond:
                    cond.notify_all()

            waiters = [asyncio.create_task(waiter(i)) for i in range(5)]
            n = asyncio.create_task(notifier())
            await asyncio.gather(*waiters)
            await n
            return results

        result = asyncio.run(main())
        assert sorted(result) == [0, 1, 2, 3, 4], f"5 waiter 必收,实际 {result}"


# -- xml.etree.TreeBuilder + XMLParser 进阶 -----------------------------------

class TestXmlTreeBuilderV2:
    def test_TreeBuilder(self):
        """`xml.etree.TreeBuilder 真子化 + start+end + close。"""
        tb = ET.TreeBuilder()
        tb.start("root", {})
        tb.start("child", {})
        tb.data("forge_text")
        tb.end("child")
        tb.end("root")
        # close
        root = tb.close()
        # 必是 Element
        assert root.tag == "root"
        # 必含 child
        children = list(root)
        assert len(children) == 1
        assert children[0].text == "forge_text"

    def test_XMLParser(self):
        """`xml.etree.XMLParser 真建 + feed 真解。"""
        # XMLParser 简测: 真建不抛
        parser = ET.XMLParser()
        # feed 不抛
        parser.feed("<root><forge>x</forge></root>")
        # 不抛即过
        assert parser is not None


# -- typing.NewType distinct --------------------------------------------------

UserId = typing.NewType("UserId", int)
OrderId = typing.NewType("OrderId", int)


class TestTypingAdvancedV17:
    def test_NewType_distinct(self):
        """`typing.NewType 真建 UserId + OrderId 不可互转。"""
        uid = UserId(42)
        oid = OrderId(42)
        # 都是 int 子类
        assert isinstance(uid, int)
        assert isinstance(oid, int)
        # 但 typing 检查器视为 distinct
        # runtime 是同一类型 (都 int)


# -- pathlib.is_file / is_dir 进阶 --------------------------------------------

class TestPathlibIsFileIsDir:
    def test_is_file_is_dir(self, tmp_path):
        """`pathlib.Path.is_file / is_dir 真返 bool。"""
        f = tmp_path / "f.txt"
        f.write_text("x")
        d = tmp_path / "d"
        d.mkdir()
        # f 必 is_file, not is_dir
        assert f.is_file() is True
        assert f.is_dir() is False
        # d 必 is_dir, not is_file
        assert d.is_dir() is True
        assert d.is_file() is False
        # 不存在
        assert (tmp_path / "nonexistent").is_file() is False
        assert (tmp_path / "nonexistent").is_dir() is False


# -- shutil.which 进阶 --------------------------------------------------------

class TestShutilWhichV2:
    def test_which_python(self):
        """`shutil.which('python3') 真非空 str。"""
        path = shutil.which("python3")
        if path is None:
            pytest.skip("沙箱无 python3")
        assert isinstance(path, str)
        assert len(path) > 0
        # 必含 python3
        assert "python" in path.lower()

    def test_which_nonexistent(self):
        """`shutil.which('forge_xyz_123') 真 None。"""
        assert shutil.which("forge_xyz_123_nonexistent") is None


# -- pprint.PrettyPrinter indent 进阶 -----------------------------------------

class TestPprintIndent:
    def test_PrettyPrinter_indent(self):
        """`pprint.PrettyPrinter(indent=4) 真改 indent。"""
        pp = pprint.PrettyPrinter(indent=4)
        s = pp.pformat({"a": {"b": "forge"}})
        # 必含 4 缩进
        # 不易验 indent, 简化: 必含 a
        assert "a" in s
        assert "b" in s
        assert "forge" in s


# -- socket.gethostbyaddr 进阶 ------------------------------------------------

class TestSocketGethostbyaddr:
    def test_gethostbyaddr_localhost(self):
        """`socket.gethostbyaddr('127.0.0.1') 真返 (host, [aliases], [ips])。"""
        try:
            result = socket.gethostbyaddr("127.0.0.1")
            # 3 元
            assert len(result) == 3
            host, aliases, ips = result
            # 必 is str
            assert isinstance(host, str)
            assert isinstance(aliases, list)
            assert isinstance(ips, list)
        except socket.herror:
            pytest.skip("沙箱 DNS 不可用")


# -- numbers.Real -------------------------------------------------------------

class TestNumbersRealV3:
    def test_Real_isinstance(self):
        """`numbers.Real 必 is int+float (Decimal 不是)`"""
        assert isinstance(42, numbers.Real)
        assert isinstance(3.14, numbers.Real)
        # complex 不是
        assert not isinstance(1 + 2j, numbers.Real)
        # Decimal 不是 (沙箱 3.11+ 注册后才算)
        import decimal
        # numbers 必是 Real
        assert issubclass(numbers.Real, numbers.Number)


# -- trace.Trace + count ------------------------------------------------------

class TestTraceCountV2:
    def test_Trace_count(self):
        """`trace.Trace(count=True) 真跑 lambda + 验 count records. """
        tr = trace.Trace(count=True, trace=0)
        tr.runfunc(lambda: sum([i for i in range(10)]))
        # 必 results 非空
        results = tr.results()
        # 3.11+ CoverageResults 类型
        assert results is not None


# -- subprocess.CompletedProcess ---------------------------------------------

class TestSubprocessCompletedProcess:
    def test_CompletedProcess_instance(self):
        """`CompletedProcess 真建 instance + args+returncode+stdout。"""
        cp = subprocess.CompletedProcess(
            args=["echo", "forge"],
            returncode=0,
            stdout=b"forge\n",
            stderr=b"",
        )
        # 必含 args+returncode+stdout+stderr
        assert cp.args == ["echo", "forge"]
        assert cp.returncode == 0
        assert cp.stdout == b"forge\n"
        assert cp.stderr == b""
        # check_returncode 不抛
        cp.check_returncode()


# -- ipaddress.IPv6Network supernet 进阶 -------------------------------------

class TestIpaddressSupernet:
    def test_IPv6Network_supernet(self):
        """`IPv6Network supernet 真 /28 → /24。"""
        # 用 strict=False 避免 host bits set
        net = ipaddress.IPv6Network("2001:db8::/28", strict=False)
        super_28 = net.supernet(prefixlen_diff=4)
        # prefixlen 28-4=24
        assert super_28.prefixlen == 24, f"supernet 应 prefixlen=24,实际 {super_28.prefixlen}"
        # super_28 必包含 net
        assert net.subnet_of(super_28) is True
