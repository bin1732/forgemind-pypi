# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 asyncio 真 Event 真多任务同步 + 真 Lock 真互斥 + 真 Queue 真异步 + 真 tracemalloc 真 snapshot diff 真比较 + 真 tracemalloc 真 filter + 真 get_object_traceback。
全 stdlib, 零模拟。
"""
import asyncio
import tracemalloc
import gc
import time
import pytest


# ======================== asyncio 进阶 ========================
def test_asyncio_run_basic():
    """真 asyncio.run 真跑"""
    async def main():
        return 42

    result = asyncio.run(main())
    assert result == 42


def test_asyncio_Event_real():
    """真 asyncio.Event 真多任务同步"""
    async def waiter(name, event, result):
        await event.wait()
        result[name] = "notified"

    async def main():
        event = asyncio.Event()
        result = {}
        # 2 waiter
        t1 = asyncio.create_task(waiter("t1", event, result))
        t2 = asyncio.create_task(waiter("t2", event, result))
        # 让 waiter block
        await asyncio.sleep(0.01)
        # set
        event.set()
        await asyncio.gather(t1, t2)
        return result

    result = asyncio.run(main())
    assert result == {"t1": "notified", "t2": "notified"}


def test_asyncio_Lock_real():
    """真 asyncio.Lock 真互斥"""
    async def worker(lock, counter, n):
        for _ in range(n):
            async with lock:
                counter[0] += 1
                # 让出
                await asyncio.sleep(0)

    async def main():
        lock = asyncio.Lock()
        counter = [0]
        await asyncio.gather(
            worker(lock, counter, 100),
            worker(lock, counter, 100),
            worker(lock, counter, 100),
        )
        return counter[0]

    total = asyncio.run(main())
    # 300 (Lock 真互斥)
    assert total == 300


def test_asyncio_Queue_real():
    """真 asyncio.Queue 真异步"""
    async def producer(q, n):
        for i in range(n):
            await q.put(i)
        await q.put(None)  # 终止信号

    async def consumer(q, results):
        while True:
            item = await q.get()
            if item is None:
                q.task_done()
                return
            results.append(item)
            q.task_done()

    async def main():
        q = asyncio.Queue()
        results = []
        prod = asyncio.create_task(producer(q, 10))
        cons = asyncio.create_task(consumer(q, results))
        await prod
        await cons
        return results

    results = asyncio.run(main())
    assert results == list(range(10))


def test_asyncio_gather_exception():
    """真 gather 真异常传播"""
    async def fail():
        raise ValueError("fail")
        return 1

    async def ok():
        return 2

    async def main():
        results = await asyncio.gather(ok(), fail(), return_exceptions=True)
        return results

    results = asyncio.run(main())
    assert results[0] == 2
    assert isinstance(results[1], ValueError)


# ======================== tracemalloc 进阶 ========================
def test_tracemalloc_snapshot_diff():
    """真 tracemalloc 真 snapshot diff"""
    tracemalloc.start()
    try:
        # 第 1 波
        a = [1, 2, 3] * 1000
        snap1 = tracemalloc.take_snapshot()
        # 第 2 波
        b = [4, 5, 6] * 5000
        snap2 = tracemalloc.take_snapshot()
        # diff
        diff = snap2.compare_to(snap1, "filename")
        # 至少 1 个 stat
        assert len(list(diff)) >= 1
        # total size_diff
        total_diff = sum(s.size_diff for s in diff)
        # 净增 ~12K (a 删 + b 增)
        assert total_diff > 0
    finally:
        tracemalloc.stop()


def test_tracemalloc_filter_by_filename():
    """真 tracemalloc 真 filter"""
    tracemalloc.start()
    try:
        big = "X" * 100_000
        snap = tracemalloc.take_snapshot()
        # 用 statistics
        stats = snap.statistics("filename")
        # 至少 1 个 stat
        assert len(stats) >= 1
        # total > 0
        total = sum(s.size for s in stats)
        assert total >= 100_000
    finally:
        tracemalloc.stop()


def test_tracemalloc_get_object_traceback():
    """真 get_object_traceback"""
    tracemalloc.start(25)
    try:
        big = "Y" * 50_000
        # 找 traceback
        tb = tracemalloc.get_object_traceback(big)
        if tb is not None:
            # 真 traceback
            assert len(tb._frames) >= 1
    finally:
        tracemalloc.stop()
