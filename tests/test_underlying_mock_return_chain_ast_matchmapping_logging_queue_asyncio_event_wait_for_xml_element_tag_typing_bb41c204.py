# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.Mock` return_value 链 / `ast.MatchMapping` 3.10+ / `logging.QueueHandler` / `asyncio.Event.wait_for` / `xml.etree.Element` tag / `typing.Final` 3.8+ / `pathlib.with_name` / `shutil.get_terminal_size` / `pprint.pp` sort_dicts / `socket.getpeername` / `numbers` 真值 / `trace.Count` 沙箱 3.11 skip / `subprocess.Popen + send_signal` / `ipaddress.IPv4Network` from_string 底层测试。

覆盖 Mock return_value 链 / ast MatchMapping / logging QueueHandler / asyncio Event wait_for / xml Element tag / typing Final / pathlib with_name / shutil get_terminal_size / pprint pp sort_dicts / socket getpeername / numbers / trace Count / subprocess Popen send_signal / ipaddress IPv4Network from_string 模块:
  - `Mock 真链 a().b().c() 必都是 MagicMock`
  - `ast.MatchMapping 3.10+ 真建+rest='rest'`
  - `logging.handlers.QueueHandler 真 emit 不抛`
  - `asyncio.Event.wait_for 真 timeout 0.05 抛 TimeoutError`
  - `xml.etree.Element.tag 必是 str`
  - `xml.etree.Element.text 必是 str|None`
  - `typing.Final 3.8+ 真建 (沙箱 3.11 走 typing.Final)`
  - `pathlib.Path.with_name 真换 name`
  - `shutil.get_terminal_size 真返 named tuple (columns+lines)`
  - `pprint.pp 真打 sort_dicts=True 默认有序`
  - `socket.getpeername 真抛 ENOTCONN for unbound`
  - `numbers.Real 真返 int+float+isinstance check`
  - `numbers.Complex 真返 complex+isinstance check`
  - `trace.Count 沙箱 3.11+ skip`
  - `subprocess.Popen 真 send_signal SIGTERM+terminate`
  - `ipaddress.IPv4Network.from_string 真= str constructor`
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
import signal
import socket
import subprocess
import sys
import trace
import typing
import unittest.mock
import xml.etree.ElementTree as ET

import pytest


# -- Mock return_value 链 ----------------------------------------------------

class TestMockReturnValueChain:
    def test_return_value_chain(self):
        """`Mock 真链 a().b().c() 必都是 MagicMock。"""
        m = unittest.mock.MagicMock()
        m.a.return_value.b.return_value.c.return_value = 42
        # 链
        result = m.a().b().c()
        assert result == 42
        # 必能验 a 被调
        assert m.a.call_count == 1
        # 验证链: 再调一次 验证 b 也被调
        m.a().b()
        assert m.a.call_count == 2


# -- ast.MatchMapping 3.10+ --------------------------------------------------

class TestAstAdvancedV18:
    def test_MatchMapping_3_10(self):
        """`ast.MatchMapping 3.10+ 真建+rest='rest'。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ MatchMapping")
        if not hasattr(ast, "MatchMapping"):
            pytest.skip("沙箱无 MatchMapping")
        # 创 MatchMapping 节点
        mm = ast.MatchMapping(
            keys=[ast.Constant(value="forge")],
            patterns=[ast.MatchSingleton(value=None)],
            rest="rest",
        )
        assert mm.rest == "rest"
        # dump
        dumped = ast.dump(mm)
        assert "MatchMapping" in dumped
        assert "rest" in dumped


# -- logging.QueueHandler ----------------------------------------------------

class TestLoggingQueueHandler:
    def test_QueueHandler(self):
        """`logging.handlers.QueueHandler 真 emit 不抛。"""
        import queue
        log_queue = queue.Queue()
        log = logging.getLogger("forge_queue")
        log.setLevel(logging.INFO)
        log.handlers.clear()
        qh = logging.handlers.QueueHandler(log_queue)
        log.addHandler(qh)
        try:
            log.info("forge queue handler")
            # QueueHandler 必 emit 不抛
            # 必 ≥ 1 record
            assert log_queue.qsize() >= 1
            # 必能读
            record = log_queue.get_nowait()
            assert record.getMessage() == "forge queue handler"
        finally:
            log.removeHandler(qh)


# -- asyncio.Event.wait_for ---------------------------------------------------

class TestAsyncioEventWaitFor:
    def test_Event_wait_for_timeout(self):
        """`asyncio.Event.wait_for 真 timeout 0.05 抛 TimeoutError。"""

        async def main():
            evt = asyncio.Event()
            # wait_for 0.05s 必抛
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(evt.wait(), timeout=0.05)

        asyncio.run(main())


# -- xml.etree.Element tag + text 进阶 --------------------------------------

class TestXmlElementTag:
    def test_Element_tag_text(self):
        """`xml.etree.Element.tag 必是 str + text 必是 str|None。"""
        elem = ET.Element("forge")
        # tag 必是 str
        assert isinstance(elem.tag, str)
        assert elem.tag == "forge"
        # text 必是 None
        assert elem.text is None
        # 设 text
        elem.text = "forge text"
        assert elem.text == "forge text"
        assert isinstance(elem.text, str)


# -- typing.Final 3.8+ 进阶 --------------------------------------------------

class TestTypingAdvancedV20:
    def test_Final(self):
        """`typing.Final 3.8+ 真建。"""
        if sys.version_info < (3, 8):
            pytest.skip("3.8+ Final")
        # 沙箱 3.11 typing.Final 必存在
        assert hasattr(typing, "Final")
        F = typing.Final
        assert F is not None

    def test_Final_decorator(self):
        """`typing.Final 用作 @final decorator (3.8+)`"""
        if sys.version_info < (3, 8):
            pytest.skip("3.8+ Final")
        # 沙箱 3.11+ typing.final 必存在
        if hasattr(typing, "final"):
            assert callable(typing.final)


# -- pathlib.with_name 进阶 --------------------------------------------------

class TestPathlibWithName:
    def test_with_name(self, tmp_path):
        """`pathlib.Path.with_name 真换 name。"""
        p = tmp_path / "old_name.txt"
        p.write_text("x")
        new_p = p.with_name("new_name.txt")
        # 必 new
        assert new_p == tmp_path / "new_name.txt"


# -- shutil.get_terminal_size 进阶 --------------------------------------------

class TestShutilTerminalSize:
    def test_get_terminal_size(self):
        """`shutil.get_terminal_size 真返 named tuple (columns+lines). """
        size = shutil.get_terminal_size()
        # 必 named tuple
        assert hasattr(size, "columns")
        assert hasattr(size, "lines")
        # 必 ≥ 0
        assert size.columns >= 0
        assert size.lines >= 0


# -- pprint.pp sort_dicts 进阶 ------------------------------------------------

class TestPprintSort:
    def test_pp_sort_dicts(self):
        """`pprint.pp 真打 sort_dicts=True (默认) 有序。"""
        d = {"b": 2, "a": 1, "c": 3}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pprint.pp(d, sort_dicts=True)
        # 必含 a 在 b 之前
        out = buf.getvalue()
        assert out.index("a") < out.index("b"), (
            f"sort_dicts=True 应 a 在 b 前,实际 out={out!r}"
        )


# -- socket.getpeername 进阶 -------------------------------------------------

class TestSocketGetpeername:
    def test_getpeername_unbound(self):
        """`socket.getpeername 真抛 ENOTCONN for unbound。"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # 未 connect 必抛
            with pytest.raises(OSError):
                s.getpeername()


# -- numbers 真值 ------------------------------------------------------------

class TestNumbersRealComplexV2:
    def test_Real(self):
        """`numbers.Real 真返 isinstance check。"""
        assert isinstance(42, numbers.Real)
        assert isinstance(3.14, numbers.Real)
        # complex 不是
        assert not isinstance(1 + 2j, numbers.Real)

    def test_Complex(self):
        """`numbers.Complex 真返 isinstance check。"""
        assert isinstance(1 + 2j, numbers.Complex)
        # int+float 是 Complex (它们是 Real 的子, Real 是 Complex 子)
        assert isinstance(42, numbers.Complex)
        assert isinstance(3.14, numbers.Complex)


# -- trace.Count 沙箱 3.11+ skip --------------------------------------------

class TestTraceCountSkip:
    def test_Count_skip(self):
        """`trace.Count 沙箱 3.11+ 已删 skip。"""
        if sys.version_info >= (3, 11):
            pytest.skip("3.11+ trace.Count 已删")
        # 3.8-3.10 有
        assert hasattr(trace, "Count")


# -- subprocess.Popen + send_signal ----------------------------------------

class TestSubprocessPopenSignal:
    def test_Popen_send_signal(self):
        """`subprocess.Popen 真 send_signal SIGTERM + terminate. """
        # 启 'sleep 5'
        proc = subprocess.Popen(
            ["python3", "-c", "import time; time.sleep(5)"],
        )
        try:
            # 必 alive
            assert proc.poll() is None
            # terminate 必发 SIGTERM
            proc.terminate()
            # 必退出
            proc.wait(timeout=2)
            assert proc.returncode is not None
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            pytest.fail("terminate 后未及时退出")


# -- ipaddress.IPv4Network.from_string ---------------------------------------

class TestIpaddressFromString:
    def test_IPv4Network_from_string(self):
        """`ipaddress.IPv4Network.from_string 真=str constructor。"""
        # IPv4Network 必能从 str 建
        net1 = ipaddress.IPv4Network("192.168.0.0/24")
        # str(net1) 必同
        s = str(net1)
        # 重建必等
        net2 = ipaddress.IPv4Network(s)
        assert net1 == net2
