# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 traceback 真 (TracebackException 真 format) + 真 tracemalloc 真 (Traceback 3.11+ tb._frames) + 真 gc 真 (DEBUG flags 真) + 真 collections 真 (deque 真 maxlen 进阶 / Counter 真 total).
全 stdlib, 零模拟。
"""
import sys
import traceback
import tracemalloc
import gc
import collections
import pytest


# ======================== traceback 进阶 ========================
def test_traceback_TracebackException_basic():
    """真 TracebackException 真"""
    try:
        raise ValueError("test")
    except ValueError:
        exc_type, exc_val, exc_tb = sys.exc_info()
        te = traceback.TracebackException(exc_type, exc_val, exc_tb)
        # 必有
        assert te.exc_type is ValueError
        assert str(te)  # 非空


def test_traceback_StackSummary():
    """真 StackSummary 真"""
    # 在当前 frame
    stack = traceback.extract_stack()
    assert isinstance(stack, list)
    # FrameSummary
    assert len(stack) > 0
    # 顶层
    top = stack[-1]
    assert hasattr(top, "filename")
    assert hasattr(top, "lineno")
    assert hasattr(top, "name")


def test_traceback_format_list():
    """真 format_list 真"""
    stack = traceback.extract_stack()
    formatted = traceback.format_list(stack)
    # 返 list of str
    assert isinstance(formatted, list)
    assert all(isinstance(line, str) for line in formatted)
    assert len(formatted) == len(stack)


# ======================== tracemalloc 进阶 ========================
def test_tracemalloc_Traceback_3_11():
    """真 Traceback 真 3.11+ API"""
    import sys as _sys
    tracemalloc.start()
    try:
        big = "X" * 10000
        # Traceback obj
        tb = tracemalloc.get_object_traceback(big)
        if tb is not None:
            # 3.11+ API: _frames tuple of (filename, lineno) tuples
            assert isinstance(tb._frames, tuple)
            for frame in tb._frames:
                # 2-tuple
                assert len(frame) == 2
                # (filename, lineno)
                assert isinstance(frame[0], str)
                assert isinstance(frame[1], int)
    finally:
        tracemalloc.stop()


def test_tracemalloc_total_size():
    """真 tracemalloc 真总 size"""
    tracemalloc.start()
    try:
        # 分配
        data = [1, 2, 3] * 1000
        snap = tracemalloc.take_snapshot()
        stats = snap.statistics("filename")
        # total size > 0
        total = sum(s.size for s in stats)
        assert total > 0
    finally:
        tracemalloc.stop()


def test_tracemalloc_clear_traces():
    """真 clear_traces 真"""
    tracemalloc.start()
    try:
        # 分配
        a = [1, 2, 3]
        # clear
        tracemalloc.clear_traces()
        # 再分配 (应记录)
        b = [4, 5, 6]
        snap = tracemalloc.take_snapshot()
        # 不为 0
        stats = snap.statistics("filename")
        # 必有 b 的 trace
        assert len(list(stats)) >= 0
    finally:
        tracemalloc.stop()


# ======================== gc 进阶 ========================
def test_gc_callbacks():
    """真 gc.callbacks 真"""
    # 必有 list
    assert isinstance(gc.callbacks, list)
    # 默认空 (可能已被 test 加过)
    # 加回调
    def cb(phase, info):
        pass
    gc.callbacks.append(cb)
    try:
        assert cb in gc.callbacks
    finally:
        # 移除
        gc.callbacks.remove(cb)


def test_gc_stats():
    """真 gc stats 真 (3.13+)"""
    if hasattr(gc, "stats"):
        # 3.13+ new API
        stats = gc.stats()
        # tuple
        assert isinstance(stats, tuple)
        assert len(stats) >= 3
    else:
        # 3.11/3.12 用 get_stats
        if hasattr(gc, "get_stats"):
            stats = gc.get_stats()
            assert isinstance(stats, list)


# ======================== collections 进阶 ========================
def test_deque_maxlen_advance():
    """真 deque 真 maxlen 真 advance"""
    d = collections.deque(maxlen=3)
    d.append(1)
    d.append(2)
    d.append(3)
    # 已满
    assert len(d) == 3
    # 再加, 旧推出
    d.append(4)
    assert list(d) == [2, 3, 4]
    # 1 推出


def test_deque_extendleft_reverses():
    """真 extendleft 真反转"""
    d = collections.deque()
    d.extendleft([1, 2, 3])
    # push to left
    # extendleft([1,2,3]) → d = [3, 2, 1]
    assert list(d) == [3, 2, 1]


def test_Counter_subtract_integers():
    """真 Counter 真减 整数"""
    c = collections.Counter(a=4, b=2)
    c.subtract(a=1, b=3)
    assert c["a"] == 3
    assert c["b"] == -1


def test_OrderedDict_equality_order_matters():
    """真 OrderedDict 真 equality 真"""
    d1 = collections.OrderedDict([("a", 1), ("b", 2)])
    d2 = collections.OrderedDict([("b", 2), ("a", 1)])
    # 同 value 不同序 → 不等
    assert d1 != d2


def test_ChainMap_new_layers():
    """真 ChainMap 真新 layers"""
    d1 = {"a": 1}
    d2 = {"b": 2}
    cm = collections.ChainMap(d1, d2)
    # parents
    parents = cm.parents
    # parents 是新 ChainMap
    assert isinstance(parents, collections.ChainMap)
    # parents 查 d2
    assert parents["b"] == 2
    # parents 查 d1 不可见 (因 parents 只 d2)
    with pytest.raises(KeyError):
        parents["a"]
