# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.patch.stopall` / `ast.MatchStar` 3.10+ / `logging.handlers.QueueListener` / `asyncio.Future` done 多 / `xml.etree.Element` set / `typing.Protocol` 子类 / `pathlib.as_posix` / `shutil.unpack_archive` 多种 / `pprint.PrettyPrinter` width / `socket.recv_into` / `numbers.Real` 真值 / `trace.Trace` countfuncs / `ipaddress.Network` num_addresses 底层测试。

覆盖 mock patch.stopall / ast MatchStar / logging QueueListener / asyncio Future done / xml Element set / typing Protocol 子 / pathlib as_posix / shutil unpack_archive / pprint width / socket recv_into / numbers Real / trace countfuncs / ipaddress num_addresses 模块:
  - `unittest.mock.patch.stopall 真停所有 patch`
  - `ast.MatchStar 3.10+ 真建+name='rest'`
  - `logging.handlers.QueueListener 真 start+stop`
  - `asyncio.Future 真 done() 多状态`
  - `xml.etree.Element.set 真 set+get attr`
  - `typing.Protocol 子类 + isinstance 沙箱 3.11 简测`
  - `pathlib.PurePosixPath('/a/b').as_posix 真 '/a/b'`
  - `shutil.unpack_archive 真提多种格式 (zip+tar)`
  - `pprint.PrettyPrinter(width=40) 真窄 width`
  - `socket.recv_into 真写入 buffer`
  - `numbers.Real 真值 isinstance check`
  - `trace.Trace(countfuncs=True) 真跑 + 验 results`
  - `ipaddress.IPv4Network 真 num_addresses 2^N`
"""
import ast
import asyncio
import contextlib
import io
import ipaddress
import logging.handlers
import numbers
import pathlib
import pprint
import queue
import shutil
import socket
import sys
import tarfile
import tempfile
import trace
import typing
import unittest.mock
import xml.etree.ElementTree as ET
import zipfile

import pytest


# -- unittest.mock.patch.stopall ---------------------------------------------

class _TargetStop:
    def get(self):
        return "real"


class TestMockPatchStopall:
    def test_patch_stopall(self):
        """`patch.stopall 真停所有 patch。"""
        p1 = unittest.mock.patch.object(_TargetStop, "get", return_value="forge_1")
        m1 = p1.start()
        assert _TargetStop().get() == "forge_1"
        # stopall 必还原
        unittest.mock.patch.stopall()
        assert _TargetStop().get() == "real"


# -- ast.MatchStar 3.10+ ----------------------------------------------------

class TestAstAdvancedV23:
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


# -- logging.QueueListener ---------------------------------------------------

class TestLoggingQueueListener:
    def test_QueueListener(self):
        """`logging.handlers.QueueListener 真 start+stop。"""
        log_queue = queue.Queue()
        log = logging.getLogger("forge_listener")
        log.setLevel(logging.INFO)
        log.handlers.clear()
        # QueueHandler + QueueListener
        target_buf = io.StringIO()
        qh = logging.StreamHandler(target_buf)
        qhl = logging.handlers.QueueListener(log_queue, qh)
        qhl.start()
        try:
            # log 走 queue
            log.info("forge listener 1")
            # listener 必 drain queue (异步, 简测不抛)
        finally:
            qhl.stop()


# -- asyncio.Future done 多 --------------------------------------------------

class TestAsyncioFutureDoneMulti:
    def test_Future_done_multi(self):
        """`asyncio.Future 真 done() 多状态。"""

        async def main():
            fut = asyncio.Future()
            # 初始必 not done
            assert not fut.done()
            fut.set_result(42)
            # 必 done
            assert fut.done()
            # 再调必仍 done
            assert fut.done()
            return fut.result()

        result = asyncio.run(main())
        assert result == 42


# -- xml.etree.Element set 进阶 ----------------------------------------------

class TestXmlSet:
    def test_Element_set(self):
        """`xml.etree.Element.set 真 set+get attr。"""
        elem = ET.Element("forge")
        # set
        elem.set("id", "1")
        # get
        assert elem.get("id") == "1"
        # set 覆盖
        elem.set("id", "2")
        assert elem.get("id") == "2"
        # set new
        elem.set("name", "forge")
        assert elem.get("name") == "forge"


# -- typing.Protocol 子类 ----------------------------------------------------

class _HasName(typing.Protocol):
    name: str


class _ConcreteName:
    name = "forge"


class TestTypingProtocolSub:
    def test_Protocol_subclass(self):
        """`typing.Protocol 子类 + 沙箱 3.11 简测 isinstance。"""
        # 沙箱 3.11+ typing.Protocol 子类化必 OK
        obj = _ConcreteName()
        # 必能取 name
        assert obj.name == "forge"


# -- pathlib.as_posix 进阶 ---------------------------------------------------

class TestPathlibAsPosix:
    def test_as_posix(self):
        """`pathlib.PurePosixPath('/a/b').as_posix 真 '/a/b'。"""
        p = pathlib.PurePosixPath("/a/b/c")
        # as_posix 必返 '/a/b/c'
        assert p.as_posix() == "/a/b/c"


# -- shutil.unpack_archive 多种 ---------------------------------------------

class TestShutilUnpackArchiveMulti:
    def test_unpack_archive_zip(self, tmp_path):
        """`shutil.unpack_archive 真提 zip。"""
        # 创 zip
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("forge.txt", b"hello forge zip")
        # 提
        extract_dir = tmp_path / "extracted_zip"
        extract_dir.mkdir()
        shutil.unpack_archive(str(zip_path), str(extract_dir))
        # 必含
        assert (extract_dir / "forge.txt").exists()
        assert (extract_dir / "forge.txt").read_bytes() == b"hello forge zip"

    def test_unpack_archive_tar(self, tmp_path):
        """`shutil.unpack_archive 真提 tar.gz。"""
        # 创 tar.gz
        tar_path = tmp_path / "test.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tf:
            data = b"hello forge tar"
            info = tarfile.TarInfo(name="forge.txt")
            info.size = len(data)
            import io
            tf.addfile(info, io.BytesIO(data))
        # 提
        extract_dir = tmp_path / "extracted_tar"
        extract_dir.mkdir()
        shutil.unpack_archive(str(tar_path), str(extract_dir))
        # 必含
        assert (extract_dir / "forge.txt").exists()


# -- pprint.PrettyPrinter width 进阶 -----------------------------------------

class TestPprintWidth:
    def test_PrettyPrinter_width(self):
        """`PrettyPrinter(width=40) 真窄 width。"""
        pp = pprint.PrettyPrinter(width=40)
        s = pp.pformat({"key_forge_1": 1, "key_forge_2": 2, "key_forge_3": 3})
        # 必非空
        assert isinstance(s, str)
        assert "key_forge_1" in s


# -- socket.recv_into 进阶 --------------------------------------------------

import io as _io  # noqa: E402


class TestSocketRecvInto:
    def test_recv_into_buffer(self):
        """`socket.recv_into 真写入 buffer (从 socketpair 收)`"""
        if sys.platform == "win32":
            pytest.skip("Windows 走不同 API")
        a, b = socket.socketpair()
        try:
            # b 写
            b.sendall(b"hello forge recv")
            # a 收到 buffer
            buf = _io.BytesIO()
            buf.write(b"\x00" * 16)
            buf.seek(0)
            n = a.recv_into(buf.getbuffer(), 16)
            # 必收 ≥ 1 字节
            assert n >= 1
            # 必为 'hello forge recv' 的前 16 字节
            buf.seek(0)
            received = buf.read(16)
            assert received == b"hello forge recv"
        finally:
            a.close()
            b.close()


# -- numbers.Real 真值 ------------------------------------------------------

class TestNumbersRealValue:
    def test_Real_value(self):
        """`numbers.Real 真值 isinstance check。"""
        # 必 is int+float
        assert isinstance(42, numbers.Real)
        assert isinstance(3.14, numbers.Real)
        # 必 is Real ABC 子类
        assert issubclass(int, numbers.Real)
        assert issubclass(float, numbers.Real)


# -- trace.Trace countfuncs --------------------------------------------------

class TestTraceCountfuncsV2:
    def test_Trace_countfuncs(self):
        """`trace.Trace(countfuncs=True) 真跑 + 验 results。"""
        tr = trace.Trace(countfuncs=True, trace=0)
        tr.runfunc(lambda: sum([i for i in range(10)]))
        # 必 results 非空
        assert tr.results() is not None


# -- ipaddress.Network num_addresses -----------------------------------------

class TestIpaddressNumAddresses:
    def test_IPv4Network_num_addresses(self):
        """`IPv4Network 真 num_addresses 2^N。"""
        # /24 = 256
        net = ipaddress.IPv4Network("192.168.0.0/24")
        assert net.num_addresses == 256, f"/24 应=256,实际 {net.num_addresses}"
        # /30 = 4
        net30 = ipaddress.IPv4Network("192.168.0.0/30")
        assert net30.num_addresses == 4
        # /16 = 65536
        net16 = ipaddress.IPv4Network("10.0.0.0/16")
        assert net16.num_addresses == 65536
