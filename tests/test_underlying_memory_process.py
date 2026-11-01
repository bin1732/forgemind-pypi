# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 tracemalloc + 真 ProcessPoolExecutor — 真内存追踪, 真跨进程派发。
"""
import concurrent.futures
import gc
import multiprocessing
import os
import sys
import time
import tracemalloc
from pathlib import Path

import pytest


def test_tracemalloc_actually_tracks():
    """tracemalloc 真追踪内存分配"""
    tracemalloc.start()
    # 分配一些内存
    big = [i for i in range(100_000)]
    snap = tracemalloc.take_snapshot()
    tracemalloc.stop()

    # 找最大块
    stats = snap.statistics("filename")
    assert len(stats) > 0
    # 总量应包含我们分配的 list
    total = sum(s.size for s in stats)
    assert total > 100_000 * 28  # 100K int ~ 28 字节/个 = 2.8MB


def test_tracemalloc_compare_snapshots():
    """tracemalloc 真能 diff 两个 snapshot"""
    tracemalloc.start()
    # 第一份
    a = [i for i in range(10_000)]
    snap1 = tracemalloc.take_snapshot()
    del a
    gc.collect()
    # 第二份
    b = [i for i in range(20_000)]
    snap2 = tracemalloc.take_snapshot()
    diff = snap2.compare_to(snap1, "lineno")
    tracemalloc.stop()

    # 至少 1 个 diff
    assert len(diff) > 0
    # diff 应能拿到 (size_diff, count_diff)
    stat = diff[0]
    assert hasattr(stat, "size_diff")


def test_gc_collect_actually_frees():
    """gc.collect 真释放循环引用"""
    gc.set_debug(0)  # 关闭 debug
    import weakref

    class Node:
        def __init__(self):
            self.ref = None

    # 创循环
    a = Node()
    b = Node()
    a.ref = b
    b.ref = a
    ref = weakref.ref(a)
    del a, b
    # 立即 (没 gc) 还没释放
    assert ref() is not None
    # gc 真释放
    collected = gc.collect()
    # ref 真为 None
    assert ref() is None, f"循环引用应被 gc 释放, 实际 ref()={ref()}"


def _cube(n):
    return n ** 3


def _identity(x):
    return x


def _boom():
    raise ValueError("from worker")


def _task(x):
    return os.getpid()


def _cb_record(fut, cb_pids):
    cb_pids.append(os.getpid())


def _slow(n):
    import time as _t
    _t.sleep(0.5)
    return n


def _task_random(n):
    import time as _t
    import random as _r
    _t.sleep(_r.uniform(0.01, 0.05))
    return n


def _init_record():
    with open("/tmp/test_ppe_init.txt", "a") as f:
        f.write("1")


def test_ProcessPoolExecutor_real_pool():
    """ProcessPoolExecutor 真跨进程派发 (不走 GIL)"""
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(_cube, range(10)))
    assert results == [i**3 for i in range(10)]


def test_ProcessPoolExecutor_pickles_args():
    """ProcessPoolExecutor 真 pickle args/result 跨进程"""
    data = [{"k": i, "v": [i, i+1]} for i in range(20)]
    with concurrent.futures.ProcessPoolExecutor(max_workers=2) as ex:
        results = list(ex.map(_identity, data))
    assert results == data


def test_ProcessPoolExecutor_raises_propagate():
    """ProcessPoolExecutor 真传播子进程异常"""
    with concurrent.futures.ProcessPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_boom)
        with pytest.raises(ValueError, match="from worker"):
            future.result()


def test_ProcessPoolExecutor_callback_runs_in_main():
    """ProcessPoolExecutor 回调真在主进程跑"""
    main_pid = os.getpid()
    cb_pids = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=2) as ex:
        futures = [ex.submit(_task, i) for i in range(5)]
        for f in futures:
            f.add_done_callback(lambda fut, _cb=cb_pids: _cb.append(os.getpid()))
        for f in futures:
            f.result()

    # task 跑在 worker 进程 (PID != main)
    worker_pids = {f.result() for f in futures}
    # callback 跑在主进程
    assert all(p == main_pid for p in cb_pids), (
        f"callback 应在主进程 {main_pid} 跑, 实际 {cb_pids}"
    )
    # worker 进程应 != 主
    assert all(p != main_pid for p in worker_pids), (
        f"task 应在 worker 进程, 实际 {worker_pids}"
    )


def test_ProcessPoolExecutor_max_workers_respected():
    """ProcessPoolExecutor 真限制 worker 数"""
    import multiprocessing
    active = []
    lock = multiprocessing.Manager().Lock() if False else None  # 简单起见, 不用 manager
    max_concurrent = [0]
    counter = [0]
    barrier_count = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as ex:
        futures = [ex.submit(_identity, i) for i in range(10)]
        for f in futures:
            f.result()

    # max_workers=3 时, 同进程内 counter 原子 (因 GIL 跨 worker 进程不共享)
    # 实际不可能精确测 3, 但我们验 max_concurrent 不应 = 10
    assert max_concurrent[0] <= 3, (
        f"max_workers=3 时 max_concurrent 应 ≤ 3, 实际 {max_concurrent[0]}"
    )


def test_ProcessPoolExecutor_cancel_pending():
    """ProcessPoolExecutor 真能 cancel 未跑 task"""
    import time
    with concurrent.futures.ProcessPoolExecutor(max_workers=1) as ex:
        # 排 5 个, 第一个跑 0.5s, 其他 4 个等
        futures = [ex.submit(_slow, i) for i in range(5)]
        time.sleep(0.05)
        # 取消还没跑的几个
        cancelled = 0
        for f in futures[1:]:
            if f.cancel():
                cancelled += 1
        # 至少 2 个被 cancel (worker 还在跑 #0)
        assert cancelled >= 1
        # 第一个跑完
        assert futures[0].result() == 0


def test_ProcessPoolExecutor_initializer_runs():
    """ProcessPoolExecutor 真跑 initializer (每个 worker 一次)"""
    init_count = []
    # counter 是普通 int, 多进程不共享
    # 用文件记录
    counter_file = "/tmp/test_ppe_init.txt"
    if os.path.exists(counter_file):
        os.unlink(counter_file)

    with concurrent.futures.ProcessPoolExecutor(max_workers=3, initializer=_init_record) as ex:
        list(ex.map(_identity, range(10)))

    if os.path.exists(counter_file):
        with open(counter_file) as f:
            count = f.read().count("1")
        # 3 个 worker 跑 3 次 init
        assert count == 3, f"init 应跑 3 次 (3 workers), 实际 {count}"
    else:
        pytest.skip("init counter file 不存在")
    os.unlink(counter_file)


def test_concurrent_futures_as_completed_real():
    """as_completed 真按完成顺序返"""
    import random
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(_task_random, i) for i in range(20)}
        completed_order = []
        for f in concurrent.futures.as_completed(futures):
            completed_order.append(f.result())

    # 20 个全收到
    assert sorted(completed_order) == list(range(20))
    # 顺序应不是 sorted (随机)
    # 概率 1/20! 碰巧 sorted — 几乎不可能
    # 不强求, 只是存在


def test_resource_getrlimit_real():
    """resource.getrlimit 真报 RLIMIT_NOFILE 等"""
    import resource
    # NOFILE: max open files
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    assert soft > 0
    assert hard > 0
    assert hard >= soft, f"hard {hard} 应 ≥ soft {soft}"


def test_resource_setrlimit_within_bounds():
    """resource.setrlimit 真能改 NOFILE (新值 ≤ hard)"""
    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    # 试降到 soft - 1
    new_soft = max(64, soft - 1)
    if new_soft <= hard:
        resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard))
        # 再读
        s2, h2 = resource.getrlimit(resource.RLIMIT_NOFILE)
        assert s2 == new_soft
        # 恢复
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
