# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`urllib.request 真用 (Request)` + `collections 进阶 (ChainMap+UserDict+UserList+namedtuple)` + `weakref 真用 (ref 真建)` + `asyncio.subprocess.shell=True (create_subprocess_shell)` + `logging.LogRecord 进阶 (直造真用)` + 真底层测试。

覆盖 urllib.request 1 真 (Request) + collections 4 真 (ChainMap+UserDict+UserList+namedtuple) + weakref 1 真 (ref lambda) + asyncio 1 真 (create_subprocess_shell) + logging 2 真 (LogRecord 直造) (共 9 真测试) 模块:
  - `urllib.request.Request 'http://forge.example.com' .fullurl`
  - `collections.ChainMap 真 child 'forge_child' 必 'forge_child'`
  - `collections.UserDict 真 'forge_a' 必 'forge_a'`
  - `collections.UserList 真 [1,2,3] 必 [1,2,3]`
  - `collections.namedtuple _ForgePt 真 42 'forge'`
  - `weakref.ref lambda 真建不抛`
  - `asyncio.create_subprocess_shell 'echo forge_shell' 必含 'forge_shell'`
  - `logging.LogRecord 直造 name+level+pathname+lineno`
  - `logging.LogRecord args=('forge_arg',) getMessage 'forge_arg'`
"""
import asyncio
import collections
import logging
import urllib.request
import weakref

import pytest


# -- urllib.request 真用 (Request) ---------------------

class TestUrllibRequestRequestAdvance:
    def test_Request(self):
        """`urllib.request.Request 'http://forge.example.com' .fullurl。"""
        r = urllib.request.Request("http://forge.example.com/forge")
        # 必 fullurl
        assert r.full_url == "http://forge.example.com/forge"
        # 必 method 'GET' default
        assert r.get_method() == "GET"


# -- collections 进阶 (ChainMap+UserDict+UserList+namedtuple) ---

class TestCollectionsChainMapUserDictUserListNamedtupleAdvance:
    def test_ChainMap(self):
        """`collections.ChainMap 真 child 'forge_child' 必 'forge_child'。"""
        parent = {"a": "parent_value"}
        child = {"b": "forge_child"}
        cm = collections.ChainMap(child, parent)
        # 必 'forge_child'
        assert cm["b"] == "forge_child"
        # 必 'parent_value'
        assert cm["a"] == "parent_value"

    def test_UserDict(self):
        """`collections.UserDict 真 'forge_a' 必 'forge_a'。"""
        ud = collections.UserDict({"a": "forge_a", "b": "forge_b"})
        # 必 'forge_a'
        assert ud["a"] == "forge_a"
        # 必 2 keys
        assert len(ud) == 2

    def test_UserList(self):
        """`collections.UserList 真 [1,2,3] 必 [1,2,3]。"""
        ul = collections.UserList([1, 2, 3])
        # 必 [1, 2, 3]
        assert list(ul) == [1, 2, 3]
        # 必 3 len
        assert len(ul) == 3

    def test_namedtuple(self):
        """`collections.namedtuple _ForgePt 真 42 'forge'。"""
        _ForgePt = collections.namedtuple("_ForgePt", ["x", "y"])
        pt = _ForgePt(42, "forge")
        # 必 42
        assert pt.x == 42
        # 必 'forge'
        assert pt.y == "forge"
        # 必 2-tuple
        assert tuple(pt) == (42, "forge")


# -- weakref 真用 (ref lambda) ---------------------------

class TestWeakrefRefAdvance:
    def test_ref_lambda(self):
        """`weakref.ref lambda 真建不抛。"""
        r = weakref.ref(lambda: "forge_value")
        # 必 callable
        assert callable(r)
        # 必非 None
        assert r is not None


# -- asyncio.subprocess.shell=True (create_subprocess_shell) -

class TestAsyncioSubprocessShellAdvance:
    def test_create_subprocess_shell(self):
        """`asyncio.create_subprocess_shell 'echo forge_shell' 必含 'forge_shell'。"""

        async def main():
            proc = await asyncio.create_subprocess_shell(
                "echo forge_shell",
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout

        stdout = asyncio.run(main())
        # 必含 'forge_shell'
        assert b"forge_shell" in stdout


# -- logging.LogRecord 进阶 (直造真用) ------------------

class TestLoggingLogRecordAdvance:
    def test_LogRecord_direct(self):
        """`logging.LogRecord 直造 name+level+pathname+lineno。"""
        record = logging.LogRecord(
            "forge_n", logging.INFO, "/forge/path", 42, "msg", None, None
        )
        # 必 name 'forge_n'
        assert record.name == "forge_n"
        # 必 levelname 'INFO'
        assert record.levelname == "INFO"
        # 必 pathname '/forge/path'
        assert record.pathname == "/forge/path"
        # 必 lineno 42
        assert record.lineno == 42

    def test_LogRecord_args(self):
        """`logging.LogRecord args=('forge_arg',) getMessage 'forge_arg'。"""
        record = logging.LogRecord(
            "forge_n", logging.INFO, "/p", 1, "msg %s", ("forge_arg",), None
        )
        # 必 'msg forge_arg'
        assert record.getMessage() == "msg forge_arg"
