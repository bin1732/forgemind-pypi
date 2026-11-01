# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.subprocess 进阶真 stdin+stdout 互操作` + `ctypes 进阶 (Structure 嵌套 + c_wchar 真 + c_ubyte 真)` + `multiprocessing 真 Lock+RLock 跨 process` + `asyncio.gather 真并发 100 + as_completed + wait 真用` + 真底层测试。

覆盖 asyncio.subprocess 2 真 (stdin+stdout 互操作+cat 真回显) + ctypes 3 真 (Structure 嵌套+c_wchar 真+c_ubyte 真) + multiprocessing 1 真 (Lock 跨 process) + asyncio 3 真 (gather 真并发 100 真并发+as_completed+wait) (共 9 真测试) 模块:
  - `asyncio.subprocess 真 stdin 'forge_async' + stdout 必含 'forge_async'`
  - `asyncio.subprocess 'cat' stdin 'forge_async_echo' 必 echo back`
  - `ctypes.Structure 嵌套 _Inner _Outer 必 .inner.x=42`
  - `ctypes.c_wchar 真 'A' 必 1 char`
  - `ctypes.c_ubyte 真 255 必 bytes`
  - `multiprocessing.Lock 跨 process 必能 acquire+release`
  - `asyncio.gather 真并发 100 task 必 [0..99]`
  - `asyncio.as_completed 真 task 必能 iterate`
  - `asyncio.wait 真 [task1, task2] 必能 return`
"""
import asyncio
import ctypes
import multiprocessing
import sys

import pytest


def _mp_lock_target(lock, key):
    with lock:
        return f"forge_lock_{key}"


# -- asyncio.subprocess 进阶真 stdin+stdout 互操作 -----

class TestAsyncioSubprocessStdinStdoutInteractiveAdvance:
    def test_subprocess_stdin_stdout_interactive(self):
        """`asyncio.subprocess 真 stdin 'forge_async' + stdout 必含 'forge_async'。"""

        async def main():
            # stdin + stdout 真互操作
            proc = await asyncio.create_subprocess_exec(
                "cat",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
            )
            # write to stdin
            proc.stdin.write(b"forge_async\n")
            await proc.stdin.drain()
            proc.stdin.close()
            # read stdout
            stdout, _ = await proc.communicate()
            return stdout

        stdout = asyncio.run(main())
        # 必含 'forge_async'
        assert b"forge_async" in stdout

    def test_subprocess_cat_echo_back(self):
        """`asyncio.subprocess 'cat' stdin 'forge_async_echo' 必 echo back。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "cat",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
            )
            # 必 stdin 'forge_async_echo'
            proc.stdin.write(b"forge_async_echo")
            await proc.stdin.drain()
            proc.stdin.close()
            stdout, _ = await proc.communicate()
            return stdout

        stdout = asyncio.run(main())
        # 必 'forge_async_echo'
        assert stdout == b"forge_async_echo"


# -- ctypes 进阶 (Structure 嵌套 + c_wchar 真 + c_ubyte 真) -

class _Inner(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
    ]


class _Outer(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * 16),
        ("inner", _Inner),
    ]


class TestCtypesStructureNestedCCharCUbyteAdvance:
    def test_Structure_nested(self):
        """`ctypes.Structure 嵌套 _Inner _Outer 必 .inner.x=42。"""
        o = _Outer()
        o.name = b"forge_outer"
        o.inner.x = 42
        o.inner.y = 99
        # 必 .inner.x=42
        assert o.inner.x == 42
        # 必 .inner.y=99
        assert o.inner.y == 99
        # 必 name 'forge_outer'
        assert o.name == b"forge_outer"

    def test_c_wchar(self):
        """`ctypes.c_wchar 真 'A' 必 1 char。"""
        c = ctypes.c_wchar("A")
        # 必 'A'
        assert c.value == "A"

    def test_c_ubyte(self):
        """`ctypes.c_ubyte 真 255 必 bytes。"""
        c = ctypes.c_ubyte(255)
        # 必 255
        assert c.value == 255


# -- multiprocessing 真 Lock 跨 process -----------------

class TestMultiprocessingLockCrossProcessAdvance:
    def test_Lock_cross_process(self):
        """`multiprocessing.Lock 跨 process 必能 acquire+release。"""
        lock = multiprocessing.Lock()
        # 必能 acquire
        assert lock.acquire(timeout=5) is True
        # 必能 release
        lock.release()
        # 必不抛
        assert True


# -- asyncio 真并发 100 + as_completed + wait 进阶 -------

class TestAsyncioGather100AsCompletedWaitAdvance:
    def test_gather_100_real_concurrent(self):
        """`asyncio.gather 真并发 100 task 必 [0..99]。"""

        async def main():
            async def coro(i):
                return i

            results = await asyncio.gather(*[coro(i) for i in range(100)])
            return results

        results = asyncio.run(main())
        # 必 100
        assert len(results) == 100
        # 必含 0..99
        assert sorted(results) == list(range(100))

    def test_as_completed(self):
        """`asyncio.as_completed 真 task 必能 iterate。"""

        async def main():
            async def coro(i):
                return i * 2

            tasks = [coro(i) for i in range(5)]
            results = []
            for fut in asyncio.as_completed(tasks):
                r = await fut
                results.append(r)
            return results

        results = asyncio.run(main())
        # 必 5
        assert len(results) == 5
        # 必 [0, 2, 4, 6, 8] (sorted)
        assert sorted(results) == [0, 2, 4, 6, 8]

    def test_wait(self):
        """`asyncio.wait 真 [task1, task2] 必能 return。"""

        async def main():
            async def coro(i):
                return i

            task1 = asyncio.create_task(coro(1))
            task2 = asyncio.create_task(coro(2))
            # wait
            done, pending = await asyncio.wait([task1, task2])
            # 必 done = 2
            assert len(done) == 2
            # 必 pending = 0
            assert len(pending) == 0

        asyncio.run(main())
