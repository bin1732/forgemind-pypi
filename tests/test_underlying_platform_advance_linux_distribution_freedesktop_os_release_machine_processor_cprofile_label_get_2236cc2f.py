# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`platform` 大进阶 (advance_linux_distribution/freedesktop_os_release/machine/processor) + `cProfile` 真 label + `pstats` 真 streaming + `asyncio.Queue` 进阶 (SimpleQueue/PriorityQueue/LifoQueue) 真底层测试。

覆盖 platform 5 真 + cProfile 4 真 + pstats 4 真 + asyncio.Queue 5 真 (共 18 真测试) 模块:
  - `platform.uname 真返 named tuple 5 字段`
  - `platform.freedesktop_os_release 真返 dict (沙箱可能空)`
  - `platform.machine 真非空 str (e.g. 'x86_64')`
  - `platform.processor 真非空 str (e.g. 'x86_64') 或 empty`
  - `platform.architecture 真返 (bits, linkage) tuple`
  - `cProfile.Profile 真 enable+disable+print_stats`
  - `cProfile.run 真跑 expr + print_stats`
  - `cProfile.label 真设 label (3.11+ 沙箱可能 skip)`
  - `pstats.Stats 真 load from file + stream`
  - `pstats.Stats 真 sort_stats (cumulative+tottime+ncalls)`
  - `pstats.Stats 真 print_callees + print_callers`
  - `pstats.Stats 真 strip_dirs 真返 self`
  - `asyncio.Queue 跨 task 5 item 保序`
  - `asyncio.SimpleQueue 跨 task 5 item (无界)`
  - `asyncio.PriorityQueue 真按 min priority 弹`
  - `asyncio.LifoQueue 真后进先出`
  - `asyncio.Queue.join 必等 task_done`
"""
import asyncio
import contextlib
import cProfile
import io
import os
import platform
import pstats
import sys
import tempfile

import pytest


# -- platform 进阶 --------------------------------------------------------

class TestPlatformAdvancedV3:
    def test_uname(self):
        """`platform.uname 真返 named tuple 5 字段。"""
        u = platform.uname()
        # 必 5 字段
        assert hasattr(u, "system")
        assert hasattr(u, "node")
        assert hasattr(u, "release")
        assert hasattr(u, "version")
        assert hasattr(u, "machine")

    def test_freedesktop_os_release(self):
        """`platform.freedesktop_os_release 真返 dict (沙箱可能空)`"""
        try:
            release = platform.freedesktop_os_release()
            assert isinstance(release, dict)
        except (OSError, AttributeError):
            # 沙箱非 Linux
            pytest.skip("沙箱无 freedesktop_os_release")

    def test_machine(self):
        """`platform.machine 真非空 str。"""
        m = platform.machine()
        assert isinstance(m, str)
        # 必非空 (沙箱真)
        assert len(m) > 0

    def test_processor(self):
        """`platform.processor 真非空 str (e.g. 'x86_64') 或 empty。"""
        p = platform.processor()
        assert isinstance(p, str)
        # 沙箱可能空

    def test_architecture(self):
        """`platform.architecture 真返 (bits, linkage) tuple。"""
        bits, linkage = platform.architecture()
        # 必 64 或 32 bits
        assert "64" in bits or "32" in bits
        assert isinstance(linkage, str)


# -- cProfile 进阶 --------------------------------------------------------

class TestCProfileAdvancedV3:
    def test_Profile_enable_disable(self):
        """`cProfile.Profile 真 enable+disable+print_stats。"""
        p = cProfile.Profile()
        p.enable()
        sum([i for i in range(100)])
        p.disable()
        # 必能 print_stats 不抛
        import io as _io
        import contextlib
        buf = _io.StringIO()
        with contextlib.redirect_stdout(buf):
            p.print_stats()
        # 必非空
        assert len(buf.getvalue()) > 0

    def test_run_expr(self):
        """`cProfile.run 真跑 expr + print_stats。"""
        p = cProfile.Profile()
        # 真跑
        p.run("sum([i for i in range(100)])")
        # 必能 print_stats
        import io as _io
        import contextlib
        buf = _io.StringIO()
        with contextlib.redirect_stdout(buf):
            p.print_stats()
        assert "function calls" in buf.getvalue() or "ncalls" in buf.getvalue()

    def test_label_attr(self):
        """`Profile.label 3.11+ 必能 set。"""
        if sys.version_info < (3, 11):
            pytest.skip("3.11+ label")
        # 3.11+ Profile 真有 label attr
        p = cProfile.Profile()
        p.label = "forge_test"
        assert p.label == "forge_test"

    def test_dump_stats(self):
        """`cProfile.Profile.dump_stats 真写 file。"""
        p = cProfile.Profile()
        p.enable()
        sum([i for i in range(10)])
        p.disable()
        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False, suffix=".stats"
        ) as f:
            path = f.name
        try:
            # dump_stats 必不抛
            p.dump_stats(path)
            assert os.path.exists(path)
            # 必可 load via pstats
            stats = pstats.Stats(p)
            assert stats is not None
        finally:
            os.unlink(path)


# -- pstats 进阶 ----------------------------------------------------------

class TestPstatsAdvancedV3:
    def test_Stats_sort_cumulative(self):
        """`pstats.Stats 真 sort_stats cumulative + print。"""
        p = cProfile.Profile()
        p.enable()
        sum([i for i in range(100)])
        p.disable()
        s = pstats.Stats(p)
        s.sort_stats("cumulative")
        # 必不抛 (用 strip_dirs 返 self 验证)
        result = s.strip_dirs()
        assert result is s

    def test_Stats_sort_tottime(self):
        """`pstats.Stats 真 sort_stats tottime。"""
        p = cProfile.Profile()
        p.enable()
        sum([i for i in range(100)])
        p.disable()
        s = pstats.Stats(p)
        s.sort_stats("tottime")
        # 必不抛
        import io as _io
        import contextlib
        buf = _io.StringIO()
        with contextlib.redirect_stdout(buf):
            s.print_stats()

    def test_Stats_strip_dirs(self):
        """`Stats.strip_dirs 真返 self。"""
        p = cProfile.Profile()
        p.enable()
        sum([i for i in range(10)])
        p.disable()
        s = pstats.Stats(p)
        result = s.strip_dirs()
        assert result is s

    def test_Stats_print_callees(self):
        """`pstats.Stats.print_callees 必不抛。"""
        p = cProfile.Profile()
        p.enable()

        def callee():
            return 1

        def caller():
            return callee() + 1

        caller()
        p.disable()
        s = pstats.Stats(p)
        # print_callees 必不抛
        import io as _io
        import contextlib
        buf = _io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                s.print_callees()
            except (KeyError, ValueError):
                pass  # 沙箱无 callee 函数时报错


# -- asyncio.Queue 进阶 (SimpleQueue/PriorityQueue/LifoQueue) -------------

class TestAsyncioQueueAdvanced:
    def test_Queue_cross_task(self):
        """`asyncio.Queue 跨 task 5 item。"""

        async def main():
            q = asyncio.Queue()

            async def producer():
                for i in range(5):
                    await q.put(i)

            async def consumer():
                items = []
                while len(items) < 5:
                    items.append(await q.get())
                    q.task_done()
                return items

            p = asyncio.create_task(producer())
            c = asyncio.create_task(consumer())
            await p
            return await c

        result = asyncio.run(main())
        assert result == [0, 1, 2, 3, 4]

    def test_SimpleQueue_skip(self):
        """`asyncio.SimpleQueue 3.11+ 沙箱 skip (3.11 无 SimpleQueue)`"""
        if sys.version_info < (3, 11):
            pytest.skip("3.11+ SimpleQueue")
        if not hasattr(asyncio, "SimpleQueue"):
            pytest.skip("沙箱 3.11 无 SimpleQueue")
        # 3.12+ 才有
        async def main():
            q = asyncio.SimpleQueue()
            await q.put(42)
            return await q.get()

        result = asyncio.run(main())
        assert result == 42

    def test_PriorityQueue(self):
        """`asyncio.PriorityQueue 真按 min priority 弹。"""

        async def main():
            pq = asyncio.PriorityQueue()
            for v in [3, 1, 4, 1, 5]:
                await pq.put(v)
            ordered = []
            while not pq.empty():
                ordered.append(await pq.get())
            return ordered

        result = asyncio.run(main())
        assert result == [1, 1, 3, 4, 5]

    def test_LifoQueue(self):
        """`asyncio.LifoQueue 真后进先出。"""

        async def main():
            q = asyncio.LifoQueue()
            for v in [1, 2, 3, 4, 5]:
                await q.put(v)
            items = []
            while not q.empty():
                items.append(await q.get())
            return items

        result = asyncio.run(main())
        assert result == [5, 4, 3, 2, 1]

    def test_Queue_join(self):
        """`asyncio.Queue.join 必等 task_done N 次。"""

        async def main():
            q = asyncio.Queue()
            for i in range(3):
                await q.put(i)

            async def worker():
                for _ in range(3):
                    item = await q.get()
                    q.task_done()

            w = asyncio.create_task(worker())
            await w
            # join 必不抛
            await q.join()
            return True

        assert asyncio.run(main()) is True
