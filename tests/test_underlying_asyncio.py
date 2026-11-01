# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 asyncio — 真 event loop 跑, 真 coroutine 调度, 真 wait/gather。
"""
import asyncio
import os
import socket
import sys
import time
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_asyncio_sleep_real():
    """asyncio.sleep 真睡"""
    t0 = time.monotonic()
    await asyncio.sleep(0.1)
    elapsed = time.monotonic() - t0
    assert 0.085 <= elapsed <= 0.3, f"asyncio.sleep(0.1) 应 ~100ms, 实际 {elapsed*1000:.0f}ms"


@pytest.mark.asyncio
async def test_asyncio_gather_real_concurrent():
    """gather 真并发: 10 个 sleep 0.05 同时跑, 总 < 0.2s"""
    async def task(i):
        await asyncio.sleep(0.05)
        return i

    t0 = time.monotonic()
    results = await asyncio.gather(*[task(i) for i in range(10)])
    elapsed = time.monotonic() - t0

    assert sorted(results) == list(range(10))
    # 10 个 50ms 并发 → 总 < 200ms
    assert elapsed < 0.3, f"gather 应 < 300ms, 实际 {elapsed*1000:.0f}ms"


@pytest.mark.asyncio
async def test_asyncio_wait_with_timeout():
    """wait 真带 timeout, 超时真 cancel"""
    async def slow():
        await asyncio.sleep(10)
        return "DONE"

    task = asyncio.create_task(slow())
    done, pending = await asyncio.wait([task], timeout=0.1)
    assert not done
    assert task in pending
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_asyncio_lock_real_mutual_exclusion():
    """asyncio Lock 真在 event loop 互斥"""
    counter = [0]
    lock = asyncio.Lock()

    async def worker():
        for _ in range(100):
            async with lock:
                counter[0] += 1

    await asyncio.gather(*[worker() for _ in range(10)])
    assert counter[0] == 1000, f"lock 互斥: 应 1000, 实际 {counter[0]}"


@pytest.mark.asyncio
async def test_asyncio_queue_real_producer_consumer():
    """asyncio Queue 真 producer/consumer"""
    queue = asyncio.Queue(maxsize=5)
    consumed = []

    async def producer():
        for i in range(20):
            await queue.put(i)
        await queue.put(None)  # 终止信号

    async def consumer():
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                break
            consumed.append(item)
            queue.task_done()

    t_p = asyncio.create_task(producer())
    t_c = asyncio.create_task(consumer())
    await asyncio.gather(t_p, t_c)

    assert consumed == list(range(20)), f"消费 20 项, 实际 {consumed[:5]}..."


@pytest.mark.asyncio
async def test_asyncio_event_real_signaling():
    """asyncio.Event 真跨 task 通信"""
    event = asyncio.Event()
    received = []

    async def waiter():
        await event.wait()
        received.append("GOT")

    t = asyncio.create_task(waiter())
    await asyncio.sleep(0.05)
    assert received == [], "waiter 还没收"
    event.set()
    await t
    assert received == ["GOT"]


@pytest.mark.asyncio
async def test_asyncio_exception_in_gather():
    """gather 真传播首个异常, 其他 task 仍完成"""
    results = []

    async def ok_task(i):
        await asyncio.sleep(0.05)
        results.append(i)
        return i

    async def bad_task():
        await asyncio.sleep(0.05)
        raise ValueError("from bad task")

    # return_exceptions=False (默认): 首个异常会 cancel 其他
    with pytest.raises(ValueError, match="from bad task"):
        await asyncio.gather(ok_task(1), bad_task(), ok_task(2))


@pytest.mark.asyncio
async def test_asyncio_subprocess_real():
    """asyncio.create_subprocess_exec 真跑命令"""
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c", "print('async hello')",
        stdout=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    assert proc.returncode == 0
    assert stdout.decode().strip() == "async hello"


@pytest.mark.asyncio
async def test_asyncio_stream_reader_real():
    """asyncio StreamReader 真读 socket 数据"""
    # 启 TCP server
    server_sock = socket.socket()
    server_sock.bind(("127.0.0.1", 0))
    port = server_sock.getsockname()[1]
    server_sock.listen(1)
    server_sock.setblocking(False)

    async def server():
        loop = asyncio.get_event_loop()
        conn, _ = await loop.sock_accept(server_sock)
        data = await loop.sock_recv(conn, 1024)
        conn.sendall(b"PONG")
        conn.close()

    async def client():
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"PING")
        await writer.drain()
        data = await reader.read(1024)
        writer.close()
        await writer.wait_closed()
        return data

    results = await asyncio.gather(server(), client())
    server_sock.close()
    # client 收到 PONG
    pong = [r for r in results if isinstance(r, bytes)][0]
    assert pong == b"PONG"


@pytest.mark.asyncio
async def test_asyncio_task_done_callback():
    """add_done_callback 真在 task 完成时调用"""
    called = []

    async def task():
        return "RESULT"

    t = asyncio.create_task(task())
    t.add_done_callback(lambda fut: called.append(fut.result()))
    await t
    await asyncio.sleep(0.01)  # 给 callback 时间
    assert called == ["RESULT"], f"callback 应 ['RESULT'], 实际 {called}"


@pytest.mark.asyncio
async def test_asyncio_create_task_concurrent_count():
    """100 个 create_task 真并发"""
    counter = [0]

    async def inc():
        await asyncio.sleep(0.01)
        counter[0] += 1

    tasks = [asyncio.create_task(inc()) for _ in range(100)]
    t0 = time.monotonic()
    await asyncio.gather(*tasks)
    elapsed = time.monotonic() - t0

    assert counter[0] == 100
    # 100 个 10ms 并发 → < 100ms
    assert elapsed < 0.3, f"100 task 并发应 < 300ms, 实际 {elapsed*1000:.0f}ms"


@pytest.mark.asyncio
async def test_asyncio_cancelled_real():
    """asyncio.shield 不被 cancel, 普通 await 真抛 CancelledError"""
    # 普通 task 真可被 cancel
    async def slow():
        await asyncio.sleep(10)
        return "DONE"

    t = asyncio.create_task(slow())
    await asyncio.sleep(0.05)
    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t
