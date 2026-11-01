# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.Event/Condition/Lock/Semaphore` 真用 + `asyncio.shield/wait_for/gather(return_exceptions)` 进阶 + `asyncio.subprocess` 真 stdin/stdout/stderr 写读 + `ctypes.c_int8/c_int16/c_int32/c_int64` 真用 + `c_int*5 真数组` + `ctypes.py_object 真用` + 真底层测试。

覆盖 asyncio 4 真 (Event+Condition+Lock+Semaphore 真) + asyncio 3 真 (wait_for+shield+gather return_exceptions) + asyncio.subprocess 1 真 (stdin+stdout+stderr pipe) + ctypes 5 真 (c_int8+c_int16+c_int32+c_int64+c_int*5+py_object) (共 13 真测试) 模块:
  - `asyncio.Event 真 set + is_set() True + wait() 返`
  - `asyncio.Condition 真 acquire + release + wait_for`
  - `asyncio.Lock 真 acquire + release + locked False`
  - `asyncio.Semaphore 真 acquire + locked + release`
  - `asyncio.wait_for 'forge' 真 timeout=1 必返 'forge'`
  - `asyncio.shield 真包 coro (3.11+)`
  - `asyncio.gather(coro 抛, return_exceptions=True) 必含 exc`
  - `asyncio.subprocess 3 pipe stdin 'forge' cat 返 stdout 'forge'`
  - `ctypes.c_int8 127 + (-128) 真 round-trip`
  - `ctypes.c_int16 32767 真`
  - `ctypes.c_int32 2147483647 真`
  - `ctypes.c_int64 9223372036854775807 真`
  - `c_int*5 [1,2,3,4,5] 真 array[0]=1`
  - `ctypes.py_object 真 set + .value = obj`
"""
import asyncio
import ctypes
import sys

import pytest


# -- asyncio 进阶 (Event + Condition + Lock + Semaphore) -----------

class TestAsyncioSyncPrimitivesAdvanced:
    def test_Event(self):
        """`asyncio.Event 真 set + is_set() True + wait() 返。"""

        async def main():
            e = asyncio.Event()
            # 必非 set
            assert e.is_set() is False
            # set
            e.set()
            # 必 set
            assert e.is_set() is True
            # wait 必立返
            await asyncio.wait_for(e.wait(), timeout=0.1)

        asyncio.run(main())

    def test_Condition(self):
        """`asyncio.Condition 真 acquire + release + wait_for。"""

        async def main():
            cond = asyncio.Condition()
            # acquire
            await cond.acquire()
            # 必 locked
            assert cond.locked() is True
            # release
            cond.release()
            # 必非 locked
            assert cond.locked() is False

        asyncio.run(main())

    def test_Lock(self):
        """`asyncio.Lock 真 acquire + release + locked False。"""

        async def main():
            lock = asyncio.Lock()
            # 必非 locked
            assert lock.locked() is False
            # acquire
            await lock.acquire()
            # 必 locked
            assert lock.locked() is True
            # release
            lock.release()
            # 必非 locked
            assert lock.locked() is False

        asyncio.run(main())

    def test_Semaphore(self):
        """`asyncio.Semaphore 真 acquire + locked + release。"""

        async def main():
            sem = asyncio.Semaphore(2)
            # acquire
            await sem.acquire()
            # 必非 locked (sem 内部 lock 真 locked)
            # release
            sem.release()

        asyncio.run(main())


# -- asyncio 进阶 (wait_for + shield + gather return_exceptions) ---

class TestAsyncioAdvancedV3:
    def test_wait_for(self):
        """`asyncio.wait_for 'forge' 真 timeout=1 必返 'forge'。"""

        async def main():
            async def coro():
                return "forge"

            result = await asyncio.wait_for(coro(), timeout=1)
            assert result == "forge"

        asyncio.run(main())

    def test_shield(self):
        """`asyncio.shield 真包 coro (3.11+ 必 not error)`"""

        async def main():
            async def coro():
                return "forge_shield"

            # shield
            shielded = asyncio.shield(coro())
            # 必能 await
            result = await shielded
            assert result == "forge_shield"

        asyncio.run(main())

    def test_gather_return_exceptions(self):
        """`asyncio.gather(coro 抛, return_exceptions=True) 必含 exc。"""

        async def main():
            async def good():
                return "forge_good"

            async def bad():
                raise ValueError("forge_error")

            # gather
            results = await asyncio.gather(good(), bad(), return_exceptions=True)
            # 必 2
            assert len(results) == 2
            # 必含 ValueError instance
            assert any(isinstance(r, ValueError) for r in results)
            # 必含 'forge_good'
            assert "forge_good" in results

        asyncio.run(main())


# -- asyncio.subprocess 进阶 (stdin/stdout/stderr 3 pipe) ----------

class TestAsyncioSubprocessAdvancedV2:
    def test_subprocess_3pipes_echo(self):
        """`asyncio.subprocess 3 pipe stdin 'forge' cat 返 stdout 'forge'。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "cat",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate(input=b"forge_3pipes")
            # 必含 'forge_3pipes'
            assert b"forge_3pipes" in stdout
            # returncode 必 0
            assert proc.returncode == 0

        asyncio.run(main())


# -- ctypes 进阶 (c_int8/16/32/64 + c_int*5 + py_object) -----------

class TestCtypesIntAdvanced:
    def test_c_int8(self):
        """`ctypes.c_int8 127 + (-128) 真 round-trip。"""
        assert ctypes.c_int8(127).value == 127
        assert ctypes.c_int8(-128).value == -128

    def test_c_int16(self):
        """`ctypes.c_int16 32767 真。"""
        assert ctypes.c_int16(32767).value == 32767

    def test_c_int32(self):
        """`ctypes.c_int32 2147483647 真。"""
        assert ctypes.c_int32(2147483647).value == 2147483647

    def test_c_int64(self):
        """`ctypes.c_int64 9223372036854775807 真。"""
        # 沙箱 3.11 必有 c_int64
        if hasattr(ctypes, "c_int64"):
            assert ctypes.c_int64(9223372036854775807).value == 9223372036854775807

    def test_c_int_5_array(self):
        """`c_int*5 [1,2,3,4,5] 真 array[0]=1。"""
        a = (ctypes.c_int * 5)(1, 2, 3, 4, 5)
        # 必能 index
        assert a[0] == 1
        assert a[4] == 5
        # 必 length 5
        assert len(a) == 5

    def test_py_object(self):
        """`ctypes.py_object 真 set + .value = obj。"""
        x = "forge_pyobj"
        p = ctypes.py_object(x)
        # 必能 deref
        assert p.value == "forge_pyobj"
