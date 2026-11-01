# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.subprocess.create_subprocess_exec 真用 进阶` + `logging 进阶 (isEnabledFor+getEffectiveLevel+setLevel)` + `ctypes 进阶 (Structure 嵌套 + byref+addressof+c_void_p)` + `functools 进阶 (lru_cache fib 真用)` + `pickle 进阶 (Pickler+Unpickler+dispatch_table 真用)` + 真底层测试。

覆盖 asyncio.subprocess 2 真 + logging 3 真 + ctypes 4 真 + functools 3 真 + pickle 3 真 (共 15 真测试) 模块:
  - `asyncio.create_subprocess_exec 'echo forge_async_exec'`
  - `asyncio.create_subprocess_exec 'cat' stdin 'forge_async_cat'`
  - `logging.isEnabledFor INFO True`
  - `logging.getEffectiveLevel int`
  - `logging.setLevel DEBUG level=10`
  - `ctypes.Structure 嵌套 .inner.x=42`
  - `ctypes byref(c_int 42)`
  - `ctypes addressof(c_int 42)`
  - `ctypes c_void_p 0 → None`
  - `functools.lru_cache fib(5)=5`
  - `functools.lru_cache hits ≥ 1`
  - `functools.lru_cache currsize ≥ 1`
  - `pickle Pickler protocol 5 'forge'`
  - `pickle Unpickler load 'forge'`
  - `pickle.dispatch_table copy ≥ 1`
"""
import asyncio
import ctypes
import functools
import io
import logging
import pickle

import pytest


@functools.lru_cache(maxsize=128)
def _fib_cached(n):
    if n < 2:
        return n
    return _fib_cached(n - 1) + _fib_cached(n - 2)


# -- asyncio.subprocess.create_subprocess_exec 进阶 ----

class TestAsyncioSubprocessCreateSubprocessExecAdvanceV2:
    def test_create_subprocess_exec_echo(self):
        """`asyncio.create_subprocess_exec 'echo forge_async_exec' 必含 'forge_async_exec'。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "echo", "forge_async_exec",
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout

        stdout = asyncio.run(main())
        # 必含 'forge_async_exec'
        assert b"forge_async_exec" in stdout

    def test_create_subprocess_exec_cat(self):
        """`asyncio.create_subprocess_exec 'cat' stdin 'forge_async_cat' 必含 'forge_async_cat'。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "cat",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
            )
            proc.stdin.write(b"forge_async_cat\n")
            await proc.stdin.drain()
            proc.stdin.close()
            stdout, _ = await proc.communicate()
            return stdout

        stdout = asyncio.run(main())
        # 必含 'forge_async_cat'
        assert b"forge_async_cat" in stdout


# -- logging 进阶 (isEnabledFor+getEffectiveLevel+setLevel) -

class TestLoggingLoggerIsEnabledForGetEffectiveLevelSetLevelAdvance:
    def test_isEnabledFor(self):
        """`logging.isEnabledFor INFO 必 True。"""
        logger = logging.getLogger("forge_isenabledfor")
        # setLevel
        logger.setLevel(logging.INFO)
        # 必 True
        assert logger.isEnabledFor(logging.INFO) is True

    def test_getEffectiveLevel(self):
        """`logging.getEffectiveLevel 必 int。"""
        logger = logging.getLogger("forge_geteffectivelevel")
        # 必 int
        assert isinstance(logger.getEffectiveLevel(), int)

    def test_setLevel(self):
        """`logging.setLevel DEBUG 必 level=10。"""
        logger = logging.getLogger("forge_setlevel")
        # setLevel
        logger.setLevel(logging.DEBUG)
        # 必 10
        assert logger.level == 10


# -- ctypes 进阶 (Structure 嵌套 + byref+addressof+c_void_p) --

class _Inner2(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int),
    ]


class _Outer2(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * 16),
        ("inner", _Inner2),
    ]


class TestCtypesAdvanceV3:
    def test_Structure_nested(self):
        """`ctypes.Structure 嵌套 .inner.x=42。"""
        o = _Outer2()
        o.name = b"forge_outer"
        o.inner.x = 42
        # 必 42
        assert o.inner.x == 42

    def test_byref(self):
        """`ctypes byref(c_int 42) 必 non-None。"""
        v = ctypes.c_int(42)
        # byref
        r = ctypes.byref(v)
        # 必 non-None
        assert r is not None

    def test_addressof(self):
        """`ctypes addressof(c_int 42) 必 int。"""
        v = ctypes.c_int(42)
        # addressof
        a = ctypes.addressof(v)
        # 必 int
        assert isinstance(a, int)

    def test_c_void_p_None(self):
        """`ctypes c_void_p 0 → None。"""
        # 沙箱 3.11+ c_void_p 0 → None
        v = ctypes.c_void_p(0)
        # 必 None
        assert v.value is None


# -- functools 进阶 (lru_cache fib 真用) -------------

class TestFunctoolsLruCacheFibAdvance:
    def test_fib_5(self):
        """`functools.lru_cache fib(5)=5。"""
        # 必 5
        assert _fib_cached(5) == 5

    def test_hits(self):
        """`functools.lru_cache hits ≥ 1。"""
        # 必能 cache hit
        _fib_cached(99)
        _fib_cached(99)
        info = _fib_cached.cache_info()
        # 必 ≥ 1 hit
        assert info.hits >= 1

    def test_currsize(self):
        """`functools.lru_cache currsize ≥ 1。"""
        # 必能 cache
        info = _fib_cached.cache_info()
        # 必 ≥ 1 currsize
        assert info.currsize >= 1


# -- pickle 进阶 (Pickler+Unpickler+dispatch_table) ----

class TestPickleAdvanceV3:
    def test_Pickler(self):
        """`pickle Pickler protocol 5 'forge'。"""
        buf = io.BytesIO()
        # Pickler
        p = pickle.Pickler(buf, protocol=5)
        p.dump("forge")
        # 必 必能
        assert buf.tell() > 0

    def test_Unpickler(self):
        """`pickle Unpickler load 'forge'。"""
        # dump first
        encoded = pickle.dumps("forge", protocol=5)
        # Unpickler
        up = pickle.Unpickler(io.BytesIO(encoded))
        # 必 'forge'
        assert up.load() == "forge"

    def test_dispatch_table(self):
        """`pickle.dispatch_table copy 必 len ≥ 1。"""
        dt = pickle.dispatch_table.copy()
        # 必 dict ≥ 1
        assert isinstance(dt, dict)
        assert len(dt) >= 1
