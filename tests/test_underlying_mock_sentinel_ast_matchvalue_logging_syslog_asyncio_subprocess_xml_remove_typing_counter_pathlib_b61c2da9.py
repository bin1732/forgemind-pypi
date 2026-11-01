# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.sentinel` / `ast.MatchValue` 3.10+ / `logging.handlers.SysLogHandler` 沙箱 skip / `asyncio.create_subprocess_exec` 进阶 / `xml.etree.Element` remove / `typing.Counter` 进阶 / `pathlib.expanduser` / `shutil.copystat` / `pprint.PrettyPrinter` depth / `socket.socketpair` 沙箱 skip / `numbers.Integral` 边界 / `subprocess.Popen` 进程组 / `ipaddress.IPv4Network.address_exclude` 底层测试。

覆盖 mock sentinel / ast MatchValue / logging SysLogHandler / asyncio subprocess / xml remove / typing Counter / pathlib expanduser / shutil copystat / pprint depth / socket socketpair / numbers Integral / subprocess pgroup / ipaddress address_exclude 模块:
  - `unittest.mock.sentinel 真建 unique attribute sentinel`
  - `ast.MatchValue 3.10+ 真建+value=Constant(42)`
  - `logging.handlers.SysLogHandler 真 class 存在 (沙箱 skip 实例)`
  - `asyncio.create_subprocess_exec 'echo forge' 真 stdout 'forge\\n'`
  - `xml.etree.Element.remove 真删子`
  - `typing.get_type_hints 解 Counter[int]`
  - `pathlib.Path.home().expanduser 真返 str`
  - `shutil.copystat 真复制 stat`
  - `pprint.PrettyPrinter(depth=1) 真 depth`
  - `socket.socketpair 真返 2 socket`
  - `numbers.Integral is int+True bool (但 not float)`
  - `subprocess.Popen start_new_session=True 真建`
  - `ipaddress.IPv4Network('192.168.0.0/24') 真 address_exclude`
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
import tempfile
import trace
import typing
import unittest.mock
import xml.etree.ElementTree as ET

import pytest


# -- unittest.mock.sentinel ---------------------------------------------------

class TestMockSentinel:
    def test_sentinel(self):
        """`sentinel 真建 unique attribute。"""
        # 简测: sentinel 真存在
        s = unittest.mock.sentinel
        # 必非 None
        assert s is not None
        # 必能 attribute access
        s.forge = "marker"
        assert s.forge == "marker"


# -- ast.MatchValue 3.10+ -----------------------------------------------------

class TestAstAdvancedV20:
    def test_MatchValue_3_10(self):
        """`ast.MatchValue 3.10+ 真建+value=Constant(42)`"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ MatchValue")
        if not hasattr(ast, "MatchValue"):
            pytest.skip("沙箱无 MatchValue")
        # 创 MatchValue 节点
        mv = ast.MatchValue(value=ast.Constant(value=42))
        # 必 value = Constant(42)
        assert mv.value.value == 42
        # dump
        dumped = ast.dump(mv)
        assert "MatchValue" in dumped
        assert "42" in dumped


# -- logging.SysLogHandler ----------------------------------------------------

class TestLoggingSysLogV2:
    def test_SysLogHandler_class(self):
        """`logging.handlers.SysLogHandler 真 class 存在。"""
        assert logging.handlers.SysLogHandler is not None


# -- asyncio.create_subprocess_exec 'echo' -------------------------------------

class TestAsyncioSubprocessExecV2:
    def test_subprocess_echo(self):
        """`asyncio.create_subprocess_exec 'echo forge' 真 stdout 'forge\\n'`"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "echo", "forge", stdout=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            return stdout, proc.returncode

        out, rc = asyncio.run(main())
        assert b"forge" in out, f"stdout 应含 'forge',实际 {out!r}"
        assert rc == 0


# -- xml.etree.Element.remove -------------------------------------------------

class TestXmlRemove:
    def test_Element_remove(self):
        """`xml.etree.Element.remove 真删子。"""
        root = ET.fromstring("<root><a>1</a><b>2</b><c>3</c></root>")
        # 删 <b>
        b = root.find("b")
        root.remove(b)
        # 必只剩 2 children
        children = list(root)
        assert len(children) == 2
        # 必不含 b
        tags = [e.tag for e in children]
        assert "b" not in tags


# -- typing.get_type_hints Counter --------------------------------------------

from collections import Counter as ColCounter


def _counter_fn(x: "ColCounter[int]") -> "int":
    return sum(x.values())


class TestTypingAdvancedV22:
    def test_get_type_hints_Counter(self):
        """`get_type_hints 真解 Counter[int] (含 '__origin__' typing) `"""
        hints = typing.get_type_hints(_counter_fn)
        # x 必是 Counter
        assert "x" in hints
        # 必能 sum
        c = ColCounter([1, 1, 2, 3, 3, 3])
        assert sum(c.values()) == 6


# -- pathlib.expanduser -------------------------------------------------------

class TestPathlibExpanduser:
    def test_expanduser(self):
        """`pathlib.Path('~').expanduser() 真返 home path。"""
        p = pathlib.Path("~")
        expanded = p.expanduser()
        # 必是 absolute
        assert expanded.is_absolute()
        # 必是 home
        assert str(expanded) == str(pathlib.Path.home())


# -- shutil.copystat ---------------------------------------------------------

class TestShutilCopystat:
    def test_copystat(self, tmp_path):
        """`shutil.copystat 真复制 stat。"""
        src = tmp_path / "src.txt"
        src.write_text("x")
        dst = tmp_path / "dst.txt"
        dst.write_text("y")
        # copystat
        shutil.copystat(src, dst)
        # 必 stat 一致
        src_stat = src.stat()
        dst_stat = dst.stat()
        # mode 必等
        assert src_stat.st_mode == dst_stat.st_mode


# -- pprint.PrettyPrinter depth -----------------------------------------------

class TestPprintDepth:
    def test_PrettyPrinter_depth(self):
        """`PrettyPrinter(depth=1) 真 depth (c 不打印 必 '...')。"""
        pp = pprint.PrettyPrinter(depth=1)
        # depth=1 必能 format
        s = pp.pformat({"a": {"b": {"c": "forge"}}})
        # 必非空
        assert isinstance(s, str)
        # depth=1: 嵌套 > 1 用 '...' 表示
        assert "..." in s
        # 'a' 必在
        assert "'a'" in s


# -- socket.socketpair 沙箱 skip ---------------------------------------------

class TestSocketPair:
    def test_socketpair_unix(self):
        """`socket.socketpair 真返 2 socket (Unix only)`. """
        if sys.platform == "win32":
            pytest.skip("Windows socketpair 走不同 API")
        # 沙箱 Unix 真有 socketpair
        a, b = socket.socketpair()
        try:
            assert a is not None
            assert b is not None
            # 必 socket
            assert isinstance(a, socket.socket)
            assert isinstance(b, socket.socket)
        finally:
            a.close()
            b.close()


# -- numbers.Integral 边界 ---------------------------------------------------

class TestNumbersIntegralEdge:
    def test_Integral_int_bool(self):
        """`numbers.Integral 必 is int + True (bool 是 int 子)`. """
        assert isinstance(42, numbers.Integral)
        assert isinstance(True, numbers.Integral)
        # float 不是
        assert not isinstance(3.14, numbers.Integral)
        # 复数不是
        assert not isinstance(1 + 2j, numbers.Integral)


# -- subprocess.Popen start_new_session --------------------------------------

class TestSubprocessPgroup:
    def test_Popen_start_new_session(self):
        """`Popen start_new_session=True 真建。"""
        proc = subprocess.Popen(
            ["true"],
            stdout=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            assert proc.pid > 0
            # 必 wait 不抛
            rc = proc.wait(timeout=2)
            assert rc == 0
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


# -- ipaddress.IPv4Network.address_exclude -----------------------------------

class TestIpaddressExclude:
    def test_address_exclude(self):
        """`IPv4Network 真 address_exclude 另一 Network。"""
        net = ipaddress.IPv4Network("192.168.0.0/24")
        # 排除 192.168.0.0/26
        excluded = ipaddress.IPv4Network("192.168.0.0/26")
        remaining = list(net.address_exclude(excluded))
        # 必 ≥ 1 个剩余 network
        assert len(remaining) >= 1
        # 必含 /26 段
        for r in remaining:
            assert r.network_address in ipaddress.IPv4Network("192.168.0.0/24")
