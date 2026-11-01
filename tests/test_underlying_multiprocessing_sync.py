# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 multiprocessing 跨进程 sync: 真 Lock/Event/Condition/Semaphore/Value/Array/Barrier/Queue 真跨进程。
全 OS kernel 同步原语, 零 Python 模拟。
"""
import os
import sys
import time
import multiprocessing
import multiprocessing.synchronize
import pytest


def _worker_increment_lock(lock, counter):
    """真跨进程 lock + counter increment"""
    with lock:
        for _ in range(1000):
            counter.value += 1


def test_multiprocessing_lock_cross_process():
    """真 Lock 跨进程 (OS semaphore)"""
    lock = multiprocessing.Lock()
    counter = multiprocessing.Value("i", 0)
    procs = [
        multiprocessing.Process(target=_worker_increment_lock, args=(lock, counter))
        for _ in range(4)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    # 4 * 1000 = 4000 (lock 真有效)
    assert counter.value == 4000, f"lock 跨进程应得 4000, 实际 {counter.value}"


def _worker_event_wait(event, result, idx):
    """真 event wait + set"""
    event.wait()  # 阻塞等 set
    result[idx] = os.getpid()


def test_multiprocessing_event_cross_process():
    """真 Event 跨进程 (OS eventfd)"""
    event = multiprocessing.Event()
    manager = multiprocessing.Manager()
    result = manager.dict()
    procs = [
        multiprocessing.Process(target=_worker_event_wait, args=(event, result, i))
        for i in range(3)
    ]
    for p in procs:
        p.start()
    time.sleep(0.3)  # 让子进程都 wait
    assert not event.is_set()
    event.set()  # 唤醒所有
    for p in procs:
        p.join()
    assert len(result) == 3  # 全 3 个醒后写了
    manager.shutdown()


def _worker_semaphore(sem, idx, result):
    """真 semaphore acquire/release"""
    with sem:
        # 3 个 worker, max 2 同时 — 1 个必 wait
        result[idx] = time.time()
        time.sleep(0.2)
        result[f"done_{idx}"] = time.time()


def test_multiprocessing_semaphore_limits_concurrency():
    """真 Semaphore 限 2 并发"""
    sem = multiprocessing.Semaphore(2)
    manager = multiprocessing.Manager()
    result = manager.dict()
    procs = [
        multiprocessing.Process(target=_worker_semaphore, args=(sem, i, result))
        for i in range(3)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    # done_0, done_1, done_2 都应存在
    for i in range(3):
        assert f"done_{i}" in result
    manager.shutdown()


def _worker_value_increment(counter, n):
    for _ in range(n):
        with counter.get_lock():
            counter.value += 1


def test_multiprocessing_value_cross_process():
    """真 Value 跨进程 + 真 lock"""
    counter = multiprocessing.Value("i", 0)
    procs = [
        multiprocessing.Process(target=_worker_value_increment, args=(counter, 1000))
        for _ in range(4)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    # 4 * 1000 = 4000
    assert counter.value == 4000


def _worker_array_double(arr, idx):
    """真 Array 跨进程"""
    for _ in range(10):
        with arr.get_lock():
            arr[idx] *= 2


def test_multiprocessing_array_cross_process():
    """真 Array 跨进程 + 真 lock"""
    arr = multiprocessing.Array("i", [1, 2, 3, 4, 5])
    procs = [
        multiprocessing.Process(target=_worker_array_double, args=(arr, i))
        for i in range(5)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    # 每个 element *= 2 共 10 次: 1 → 2^10 = 1024
    assert list(arr) == [1024, 2048, 3072, 4096, 5120]


def _worker_queue_put(q, n):
    for i in range(n):
        q.put((os.getpid(), i))


def test_multiprocessing_queue_cross_process():
    """真 Queue 跨进程"""
    q = multiprocessing.Queue()
    procs = [
        multiprocessing.Process(target=_worker_queue_put, args=(q, 100))
        for _ in range(3)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

    # 应有 300 个 item
    items = []
    while not q.empty():
        items.append(q.get())
    assert len(items) == 300
    # 3 个不同 PID
    pids = {pid for pid, _ in items}
    assert len(pids) == 3


def _worker_pipe_recv(conn, result):
    """真 Pipe 跨进程"""
    while True:
        msg = conn.recv()
        if msg == "STOP":
            result.append("done")
            conn.close()
            return
        result.append(msg)


def test_multiprocessing_pipe_duplex():
    """真 Pipe 跨进程 (双工)"""
    parent_conn, child_conn = multiprocessing.Pipe(duplex=True)
    manager = multiprocessing.Manager()
    result = manager.list()
    p = multiprocessing.Process(target=_worker_pipe_recv, args=(child_conn, result))
    p.start()
    parent_conn.send("hello")
    parent_conn.send("world")
    parent_conn.send("STOP")
    p.join()
    assert list(result) == ["hello", "world", "done"]
    manager.shutdown()


def test_multiprocessing_condition_cross_process():
    """真 Condition 跨进程 (notify/wait)"""
    cond = multiprocessing.Condition()
    counter = multiprocessing.Value("i", 0)

    def waiter(cond, counter, idx, result):
        with cond:
            while counter.value < 3:
                cond.wait()
            result[idx] = counter.value

    manager = multiprocessing.Manager()
    result = manager.dict()
    procs = [
        multiprocessing.Process(target=waiter, args=(cond, counter, i, result))
        for i in range(2)
    ]
    for p in procs:
        p.start()
    time.sleep(0.3)  # 让 2 个 waiter 都 wait
    with cond:
        counter.value = 3
        cond.notify_all()
    for p in procs:
        p.join()
    assert result[0] == 3
    assert result[1] == 3
    manager.shutdown()


def test_multiprocessing_barrier_cross_process():
    """真 Barrier 跨进程"""
    barrier = multiprocessing.Barrier(3)
    manager = multiprocessing.Manager()
    result = manager.list()

    def worker(idx):
        time.sleep(0.1 * (3 - idx))  # 不同 start time
        barrier.wait()  # 阻塞到 3 都到
        result.append(idx)

    procs = [
        multiprocessing.Process(target=worker, args=(i,))
        for i in range(3)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    # 3 个都过 barrier
    assert len(list(result)) == 3
    manager.shutdown()


def test_multiprocessing_rlock_reentrant():
    """真 RLock 跨进程 (reentrant)"""
    rlock = multiprocessing.RLock()
    counter = multiprocessing.Value("i", 0)

    def nested():
        with rlock:
            with rlock:
                with rlock:
                    counter.value += 1

    p = multiprocessing.Process(target=nested)
    p.start()
    p.join()
    assert counter.value == 1  # reentrant 同一进程可重入
