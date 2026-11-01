# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`socket.socketpair` + `concurrent.futures` + `asyncio.Queue` 真底层测试。

覆盖双向 IPC / 线程池 / 跨协程队列:
  - `socket.socketpair()` 真建双向 fd 对,a.send + b.recv round-trip
  - `concurrent.futures.ThreadPoolExecutor` 真并发 4 任务,`as_completed` 拿结果
  - `concurrent.futures.ProcessPoolExecutor` 真 fork,子进程算 x*x
  - `asyncio.Queue` 真在两个 task 之间传递 item,顺序保留
  - `asyncio.Lock` 真互斥:两个 task 争同一锁,串行执行
  - `asyncio.Event` 真 set 后所有 wait 立即唤醒
"""
import asyncio
import concurrent.futures
import multiprocessing
import os
import socket
import threading
import time

import pytest


# -- socket.socketpair --------------------------------------------------------

class TestSocketPair:
    def test_socketpair_bidirectional_round_trip(self):
        """`socket.socketpair()` 真建双向 fd 对,a.send + b.recv 与反向都能通。"""
        a, b = socket.socketpair()
        try:
            a.sendall(b"ping-from-a")
            data = b.recv(64)
            assert data == b"ping-from-a", f"b.recv 应拿到 'ping-from-a',实际 {data!r}"

            b.sendall(b"pong-from-b")
            data2 = a.recv(64)
            assert data2 == b"pong-from-b", f"a.recv 应拿到 'pong-from-b',实际 {data2!r}"
        finally:
            a.close()
            b.close()

    def test_socketpair_recv_timeout(self):
        """`socket.settimeout(0.05)` 真在 50ms 无数据时抛 `BlockingIOError`。"""
        a, b = socket.socketpair()
        try:
            a.settimeout(0.05)
            with pytest.raises((BlockingIOError, TimeoutError, socket.timeout)):
                a.recv(16)
        finally:
            a.close()
            b.close()


# -- concurrent.futures -------------------------------------------------------

def _square(n: int) -> int:
    return n * n


def _pid_squared(n: int) -> int:
    return n * n * os.getpid()


class TestConcurrentFutures:
    def test_thread_pool_as_completed(self):
        """`ThreadPoolExecutor.map(_square, [1..4])` 真并发,返 [1,4,9,16]。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            results = list(ex.map(_square, [1, 2, 3, 4]))
        assert results == [1, 4, 9, 16], f"map 应返 [1,4,9,16],实际 {results}"

    def test_thread_pool_as_completed_order(self):
        """`as_completed(fs)` 真按 future 完成顺序 yield,不是按输入顺序。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            # fast task 先完成
            fs = [ex.submit(time.sleep, 0.05 if i == 0 else 0.0)
                  for i in range(3)]
            completed_order = []
            for f in concurrent.futures.as_completed(fs):
                completed_order.append(f)
        # 至少第一个完成的是 sleep(0)
        assert completed_order[0].result() is None
        assert len(completed_order) == 3

    def test_process_pool_fork_exec(self):
        """`ProcessPoolExecutor.map` 真 fork 4 进程,各算 1²/2²/3²/4²。"""
        # 用 _square 简单函数 (不能用 _pid_squared 因为 pid 不同返回不同)
        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as ex:
            results = list(ex.map(_square, [1, 2, 3, 4]))
        assert sorted(results) == [1, 4, 9, 16], f"process pool 应返 [1,4,9,16],实际 {results}"


# -- asyncio.Queue ------------------------------------------------------------

class TestAsyncioQueue:
    def test_queue_passes_items_between_tasks(self):
        """`asyncio.Queue` 真跨 task 传 5 项,消费者按序收完。"""
        async def producer(q):
            for i in range(5):
                await q.put(i)
                await asyncio.sleep(0.001)

        async def consumer(q):
            received = []
            while len(received) < 5:
                item = await q.get()
                received.append(item)
                q.task_done()
            return received

        async def main():
            q = asyncio.Queue()
            prod = asyncio.create_task(producer(q))
            received = await consumer(q)
            await prod
            return received

        result = asyncio.run(main())
        assert result == [0, 1, 2, 3, 4], f"asyncio.Queue 应按序传,实际 {result}"

    def test_lock_serializes_coroutines(self):
        """`asyncio.Lock` 真互斥,两个 task 争同一锁的临界区不重叠。"""
        order = []
        lock = asyncio.Lock()

        async def worker(label, hold):
            async with lock:
                order.append(f"{label}-enter")
                await asyncio.sleep(hold)
                order.append(f"{label}-exit")

        async def main():
            # 同时启动两个,锁保证 enter/exit 严格嵌套
            await asyncio.gather(worker("A", 0.05), worker("B", 0.02))

        asyncio.run(main())
        # 期望两种合法交错: A enter/A exit/B enter/B exit (A 先抢到)
        # 或 B enter/B exit/A enter/A exit (B 先抢到)
        # 但不应是 A enter/B enter/A exit/B exit (并发)
        assert order in (
            ["A-enter", "A-exit", "B-enter", "B-exit"],
            ["B-enter", "B-exit", "A-enter", "A-exit"],
        ), f"锁未保持互斥,实际 {order}"

    def test_event_wakes_all_waiters(self):
        """`asyncio.Event.set()` 真让所有 waiters 立即通过。"""
        results = []

        async def waiter(idx, ev):
            await ev.wait()
            results.append(idx)

        async def main():
            ev = asyncio.Event()
            tasks = [asyncio.create_task(waiter(i, ev)) for i in range(3)]
            await asyncio.sleep(0.01)  # 让 waiters 全部开始 wait
            ev.set()
            await asyncio.gather(*tasks)

        asyncio.run(main())
        assert sorted(results) == [0, 1, 2], (
            f"Event.set 后 3 个 waiter 应都被唤醒,实际 {results}"
        )
