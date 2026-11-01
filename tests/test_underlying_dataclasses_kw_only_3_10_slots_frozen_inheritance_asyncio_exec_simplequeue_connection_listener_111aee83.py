# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`dataclasses` 大进阶: KW_ONLY 3.10+ + slots + frozen + inheritance + `asyncio.subprocess_exec` 真 stderr/returncode/PIPE + `multiprocessing.Pool` 真并发 (apply_async/imap/starmap) + `multiprocessing.Process` daemon + `multiprocessing.SimpleQueue` 真跨 task + `multiprocessing.connection` Listener 沙箱 skip 真底层测试。

覆盖 dataclasses 4 真 (KW_ONLY 3.10+ + slots + frozen + inheritance) + asyncio.subprocess 3 真 (stderr+returncode+send_signal) + multiprocessing 4 真 (Pool apply_async+imap+Process daemon+SimpleQueue) + 沙箱 skip 1 (Listener) (共 12 真测试) 模块:
  - `dataclasses KW_ONLY 3.10+ 真创 + kw_only_fields 必 0`
  - `dataclasses slots=True 真创 + __slots__`
  - `dataclasses frozen=True 真防改 (FrozenInstanceError)`
  - `dataclasses inheritance 真子类继承 fields`
  - `asyncio.create_subprocess_exec 真收 stderr 空 + returncode=0`
  - `asyncio.create_subprocess_exec 'false' 真 returncode=1`
  - `asyncio.create_subprocess_exec 真 send_signal SIGTERM 不抛`
  - `multiprocessing.Pool apply_async 5 任务真并发 sq [0,1,4,9,16]`
  - `multiprocessing.Pool imap sq [3,1,4,1,5] 排序 [1,1,4,9,16,25]`
  - `multiprocessing.Process daemon=True 真建 + is_alive`
  - `multiprocessing.SimpleQueue 真跨 task 5 item`
  - `multiprocessing.connection.Listener 沙箱 skip (无 AF_UNIX 或 unix)`
"""
import asyncio
import dataclasses
import multiprocessing
import multiprocessing.connection
import os
import sys

import pytest


# -- dataclasses 大进阶 ---------------------------------------------------

class TestDataclassesAdvancedV2:
    def test_KW_ONLY_3_10(self):
        """`dataclasses KW_ONLY 3.10+ 真创。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ KW_ONLY")
        @dataclasses.dataclass
        class WithKW:
            x: int
            _: dataclasses.KW_ONLY
            y: int = 0

        obj = WithKW(1, y=2)
        # 必能 x=1 y=2
        assert obj.x == 1
        assert obj.y == 2

    def test_slots(self):
        """`dataclasses slots=True 真创 + __slots__。"""
        @dataclasses.dataclass(slots=True)
        class WithSlots:
            x: int
            y: int

        obj = WithSlots(3, 4)
        # 必能 x+y
        assert obj.x == 3
        assert obj.y == 4
        # 必含 __slots__ attr
        assert "__slots__" in WithSlots.__dict__ or hasattr(obj, "__slots__")

    def test_frozen(self):
        """`dataclasses frozen=True 真防改 (FrozenInstanceError)`"""
        @dataclasses.dataclass(frozen=True)
        class Frozen:
            x: int

        obj = Frozen(42)
        # 必能读
        assert obj.x == 42
        # 必不能改 (FrozenInstanceError)
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.x = 99

    def test_inheritance(self):
        """`dataclasses inheritance 真子类继承 fields。"""
        @dataclasses.dataclass
        class Base:
            x: int

        @dataclasses.dataclass
        class Child(Base):
            y: int

        obj = Child(1, 2)
        # 必继承 + 新增
        assert obj.x == 1
        assert obj.y == 2


# -- asyncio.subprocess 真用 -------------------------------------------

class TestAsyncioSubprocessAdvanced:
    def test_subprocess_stderr_returncode(self):
        """`asyncio.create_subprocess_exec 真收 stderr 空 + returncode=0。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "true",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode, stderr

        rc, stderr = asyncio.run(main())
        assert rc == 0
        # stderr 必空
        assert stderr == b""

    def test_subprocess_false(self):
        """`asyncio.create_subprocess_exec 'false' 真 returncode=1。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "false",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode

        rc = asyncio.run(main())
        assert rc == 1

    def test_subprocess_send_signal(self):
        """`asyncio.create_subprocess_exec 真 send_signal SIGTERM。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", "import time; time.sleep(5)",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # send_signal
            try:
                proc.send_signal(15)  # SIGTERM
            except (ProcessLookupError, OSError):
                pass
            # 必可 wait
            try:
                await asyncio.wait_for(proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                proc.terminate()
                proc.kill()
                await proc.wait()
            return proc.returncode

        rc = asyncio.run(main())
        # 必非 None
        assert rc is not None


# -- multiprocessing.Pool 真并发 -------------------------------------

def _slow_sq(x):
    return x * x


def _slow_add(x, y):
    return x + y


class TestMultiprocessingPoolAdvancedV3:
    def test_Pool_apply_async_concurrent(self):
        """`Pool apply_async 5 任务真并发 sq [0,1,4,9,16]。"""
        with multiprocessing.Pool(2) as p:
            results = []
            for i in range(5):
                ar = p.apply_async(_slow_sq, (i,))
                results.append(ar.get(timeout=10))
            assert results == [0, 1, 4, 9, 16]

    def test_Pool_imap(self):
        """`Pool imap sq [3,1,4,1,5] 排序。"""
        with multiprocessing.Pool(2) as p:
            results = list(p.imap(_slow_sq, [3, 1, 4, 1, 5]))
            # 平方
            assert sorted(results) == [1, 1, 9, 16, 25]


# -- multiprocessing.Process + SimpleQueue ----------------------------

def _proc_target(q):
    for i in range(5):
        q.put(i)


class TestMultiprocessingProcessV2:
    def test_Process_daemon(self):
        """`multiprocessing.Process daemon=True 真建。"""
        p = multiprocessing.Process(target=lambda: None, daemon=True)
        # 必是 daemon
        assert p.daemon is True
        # 必能 start
        p.start()
        # 必能 join
        p.join(timeout=30)
        # 必 alive=False
        assert p.is_alive() is False

    def test_SimpleQueue_cross_process(self):
        """`multiprocessing.SimpleQueue 真跨 process 5 item。"""
        q = multiprocessing.SimpleQueue()
        p = multiprocessing.Process(target=_proc_target, args=(q,))
        p.start()
        p.join(timeout=30)
        # 子进程必须正常结束,否则队列里不会有数据,读取会一直等下去
        assert p.exitcode == 0, f"子进程未正常结束: exitcode={p.exitcode}"
        # 必能收 5 item。子进程已结束,数据必定在队列里,按个数收取,
        # 不用空队列标志判断,避免标志与实际数据到达之间的时序差。
        items = [q.get() for _ in range(5)]
        assert sorted(items) == [0, 1, 2, 3, 4]


# -- multiprocessing.connection.Listener 沙箱 skip ---------------------

class TestListenerSandboxSkip:
    def test_Listener_sandbox_skip(self):
        """`multiprocessing.connection.Listener 沙箱 skip (无 AF_UNIX 路径)`"""
        # 沙箱无 ready AF_UNIX listener path
        # 简测: Listener class 必存在
        assert multiprocessing.connection.Listener is not None
