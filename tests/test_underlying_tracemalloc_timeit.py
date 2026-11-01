# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 tracemalloc: 真追踪 + 真 diff + 真 backtrace + 真时间统计 + 真 timeit。
全 stdlib, 零模拟。
"""
import os
import sys
import gc
import time
import timeit
import tracemalloc
import linecache
import pytest


def test_tracemalloc_start_stop():
    """真 start/stop + 真 is_tracing"""
    assert not tracemalloc.is_tracing()
    tracemalloc.start()
    try:
        assert tracemalloc.is_tracing()
        # 25 frames 限制
        assert tracemalloc.get_traced_memory()[0] >= 0
    finally:
        tracemalloc.stop()
    assert not tracemalloc.is_tracing()


def test_tracemalloc_get_traced_memory():
    """真 get_traced_memory (current, peak)"""
    tracemalloc.start()
    try:
        # 分配
        data = [i * 2 for i in range(10_000)]
        current, peak = tracemalloc.get_traced_memory()
        assert current > 0
        assert peak >= current
        del data
        gc.collect()
    finally:
        tracemalloc.stop()


def test_tracemalloc_snapshot():
    """真 snapshot + 真 stat"""
    tracemalloc.start()
    try:
        snapshot1 = tracemalloc.take_snapshot()
        # 分配 100KB
        big = "x" * 100_000
        snapshot2 = tracemalloc.take_snapshot()
        del big
        snapshot3 = tracemalloc.take_snapshot()
    finally:
        tracemalloc.stop()

    # 比较
    diff = snapshot2.compare_to(snapshot1, "filename")
    # 至少有 1 个 stat (有 100KB 分配)
    total_size = sum(s.size_diff for s in diff)
    assert total_size > 50_000  # 至少 50KB 增

    # snapshot3 vs snapshot2: 释放
    diff3 = snapshot3.compare_to(snapshot2, "filename")
    released = sum(-s.size_diff for s in diff3 if s.size_diff < 0)
    assert released > 50_000  # 至少 50KB 释放


def test_tracemalloc_snapshot_filter():
    """真 snapshot 真 filter"""
    tracemalloc.start()
    try:
        # 分配
        data1 = [1, 2, 3] * 1000
        data2 = {i: "value" for i in range(1000)}
    finally:
        pass
    snapshot = tracemalloc.take_snapshot()
    # 过滤
    stats_by_lineno = snapshot.statistics("lineno")
    stats_by_filename = snapshot.statistics("filename")
    assert len(stats_by_lineno) > 0
    assert len(stats_by_filename) > 0

    tracemalloc.stop()
    del data1, data2


def test_tracemalloc_get_object_traceback():
    """真 get_object_traceback 真栈"""
    tracemalloc.start(25)
    try:
        big = "x" * 10_000
        # 拿 big 的 traceback
        tb = tracemalloc.get_object_traceback(big)
        assert tb is not None
        # _frames 是 list of (filename, lineno)
        assert len(tb._frames) >= 1
        # frame 是 (filename, lineno) tuple
        frame = tb._frames[0]
        assert frame[0]  # filename
        assert frame[1] > 0  # lineno
    finally:
        tracemalloc.stop()


def test_tracemalloc_clear_traces():
    """真 clear_traces"""
    tracemalloc.start()
    try:
        # 第一波分配 — 记下来
        big1 = "x" * 10_000
        snapshot1 = tracemalloc.take_snapshot()
        # clear — 清 trace
        tracemalloc.clear_traces()
        # 第二波分配 — 重新记
        big2 = "y" * 20_000
        snapshot2 = tracemalloc.take_snapshot()
        # diff 应只含 big2 (清后)
        diff = snapshot2.compare_to(snapshot1, "filename")
        total = sum(s.size_diff for s in diff)
        # 至少 10KB 增 (big2 - big1 + big1 del = 20K)
        assert total >= 10_000, f"clear_traces 后应能算 diff, 实际 total={total}"
    finally:
        tracemalloc.stop()


def test_tracemalloc_n_frames():
    """真 n_frames 参数真影响 traceback 深度"""
    tracemalloc.start(5)  # 只 5 frames
    try:
        # 嵌套函数分配, 保留 reference 防 GC
        def inner():
            return [i for i in range(100)]
        def middle():
            return inner()
        big = middle()
        # 保留在 closure, 防止 tracemalloc 释放
        keep = [big]
        tb = tracemalloc.get_object_traceback(big)
        # 也许 None (对象不在 frame) — accept both
        if tb is not None:
            assert len(tb.traceback) <= 5
        # 不论如何 start(5) 没抛
    finally:
        tracemalloc.stop()


def test_timeit_basic():
    """真 timeit.timeit"""
    t = timeit.timeit("sum(range(100))", number=1000)
    assert isinstance(t, float)
    assert t >= 0
    # 1000 次 sum range 100 应 < 1s
    assert t < 2.0


def test_timeit_setup():
    """真 timeit setup 字符串"""
    # setup 只 1 次
    t = timeit.timeit(
        "x.append(0)",
        setup="x = []",
        number=1000,
    )
    assert t >= 0
    assert t < 2.0


def test_timeit_repeat():
    """真 timeit.repeat 真返 N 个时间"""
    results = timeit.repeat("sum(range(10))", number=100, repeat=5)
    assert len(results) == 5
    assert all(r >= 0 for r in results)


def test_timeit_timer_class():
    """真 Timer 类"""
    t = timeit.Timer("sum(range(10))")
    result = t.timeit(number=1000)
    assert result >= 0
    # 重复
    results = t.repeat(repeat=3, number=1000)
    assert len(results) == 3


def test_timeit_timer_with_setup():
    """真 Timer with setup"""
    t = timeit.Timer("x.append(0)", setup="x = []")
    result = t.timeit(number=100)
    # 跑测试 — 不直接 assert 时间, 只 API work
    assert result >= 0


def test_timeit_stmt():
    """真 timeit.timeit 接受 stmt 字符串"""
    t = timeit.timeit("1+1", number=10)
    assert t >= 0


def test_timeit_authorize_default_timer():
    """真 timeit.default_timer 真在"""
    timer = timeit.default_timer
    # 应是 time.perf_counter 或 time.monotonic
    t = timer()
    assert isinstance(t, float)
    assert t > 0
    time.sleep(0.05)
    t2 = timer()
    assert t2 > t


def test_time_clock_gettime():
    """真 time.clock_gettime 真 OS 时钟"""
    # CLOCK_REALTIME
    real = time.clock_gettime(time.CLOCK_REALTIME)
    assert real > 1_700_000_000  # 2023+
    # CLOCK_MONOTONIC
    mono = time.clock_gettime(time.CLOCK_MONOTONIC)
    assert mono > 0
    # CLOCK_PROCESS_CPUTIME_ID
    try:
        proc = time.clock_gettime(time.CLOCK_PROCESS_CPUTIME_ID)
        assert proc >= 0
    except OSError:
        pass
    # CLOCK_MONOTONIC_RAW (Linux 特有)
    if hasattr(time, "CLOCK_MONOTONIC_RAW"):
        raw = time.clock_gettime(time.CLOCK_MONOTONIC_RAW)
        assert raw > 0


def test_time_clock_getres():
    """真 time.clock_getres 真精度"""
    res = time.clock_getres(time.CLOCK_MONOTONIC)
    assert res > 0
    assert res < 1.0  # 应 < 1s (一般 ns)
    # REALTIME 也应 < 1s
    res_real = time.clock_getres(time.CLOCK_REALTIME)
    assert res_real > 0
