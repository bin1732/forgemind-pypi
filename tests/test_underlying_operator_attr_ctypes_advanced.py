# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 operator 真 methodcaller + 真 attrgetter 进阶 + 真 ctypes 进阶 (结构体 / pointer) + 真 heapq 真 nlargest/nsmallest + 真 itertools 真 groupby/chain。
全 stdlib, 零模拟。
"""
import operator
import heapq
import itertools
import ctypes
import pytest


# ======================== operator ========================
def test_operator_methodcaller():
    """真 methodcaller 真调方法"""
    strip = operator.methodcaller("strip")
    assert strip("  hello  ") == "hello"
    # 带参数
    replace = operator.methodcaller("replace", "old", "new")
    assert replace("old text") == "new text"


def test_operator_attrgetter_nested():
    """真 attrgetter 真取嵌套属性"""
    class Inner:
        def __init__(self, v):
            self.v = v
    class Outer:
        def __init__(self, inner):
            self.inner = inner
            self.name = "outer"

    o = Outer(Inner(42))
    # nested attr
    get = operator.attrgetter("name", "inner.v")
    assert get(o) == ("outer", 42)


def test_operator_itemgetter_nested():
    """真 itemgetter 真取嵌套"""
    data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    get_a = operator.itemgetter("a")
    assert [get_a(d) for d in data] == [1, 3]


def test_operator_truth():
    """真 truth / is_ / is_not"""
    # truth(x) = bool(x)
    assert operator.truth(0) is False
    assert operator.truth(1) is True
    # is_
    a = [1, 2, 3]
    b = a
    assert operator.is_(a, b) is True
    # is_not
    c = [1, 2, 3]
    assert operator.is_not(a, c) is True


# ======================== heapq ========================
def test_heapq_heappush_pop():
    """真 heappush / heappop"""
    heap = []
    heapq.heappush(heap, 5)
    heapq.heappush(heap, 1)
    heapq.heappush(heap, 3)
    # 最小堆
    assert heapq.heappop(heap) == 1
    assert heapq.heappop(heap) == 3
    assert heapq.heappop(heap) == 5


def test_heapq_heappushpop():
    """真 heappushpop 真行为"""
    heap = [1, 3, 5]
    # 2 pushpop: 比 1 大, pop 1, 2 入堆
    result = heapq.heappushpop(heap, 2)
    assert result == 1
    assert heap[0] == 2  # 新堆


def test_heapq_nlargest_nsmallest():
    """真 nlargest / nsmallest"""
    data = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
    assert heapq.nlargest(3, data) == [9, 6, 5]
    assert heapq.nsmallest(3, data) == [1, 1, 2]


def test_heapq_nlargest_with_key():
    """真 nlargest 真带 key"""
    data = ["aaa", "b", "cc", "dddd"]
    # 按 len
    largest = heapq.nlargest(2, data, key=len)
    assert largest == ["dddd", "aaa"]


# ======================== itertools ========================
def test_itertools_chain():
    """真 chain 真链"""
    a = [1, 2, 3]
    b = [4, 5, 6]
    result = list(itertools.chain(a, b))
    assert result == [1, 2, 3, 4, 5, 6]


def test_itertools_groupby():
    """真 groupby 真分组"""
    data = [("a", 1), ("a", 2), ("b", 3), ("b", 4), ("c", 5)]
    groups = {k: [v for _, v in g] for k, g in itertools.groupby(data, key=lambda x: x[0])}
    assert groups == {"a": [1, 2], "b": [3, 4], "c": [5]}


def test_itertools_islice():
    """真 islice 真切片"""
    data = list(range(100))
    result = list(itertools.islice(data, 5, 10))
    assert result == [5, 6, 7, 8, 9]


def test_itertools_takewhile():
    """真 takewhile"""
    data = [1, 2, 3, 10, 4, 5]
    result = list(itertools.takewhile(lambda x: x < 5, data))
    assert result == [1, 2, 3]


def test_itertools_dropwhile():
    """真 dropwhile"""
    data = [1, 2, 3, 10, 4, 5]
    result = list(itertools.dropwhile(lambda x: x < 5, data))
    assert result == [10, 4, 5]


def test_itertools_permutations():
    """真 permutations"""
    perms = list(itertools.permutations([1, 2, 3], 2))
    # 6 个
    assert len(perms) == 6
    assert (1, 2) in perms
    assert (3, 2) in perms


# ======================== ctypes 进阶 ========================
def test_ctypes_structure():
    """真 ctypes Structure 真字段"""
    class Point(ctypes.Structure):
        _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int)]

    p = Point(3, 4)
    assert p.x == 3
    assert p.y == 4
    # size
    assert ctypes.sizeof(p) == 8  # 2 * 4 bytes


def test_ctypes_pointer():
    """真 ctypes pointer 真 deref"""
    i = ctypes.c_int(42)
    p = ctypes.pointer(i)
    # deref
    assert p.contents.value == 42
    # 改原值, 指针也变
    i.value = 99
    assert p.contents.value == 99


def test_ctypes_array():
    """真 ctypes Array"""
    arr = (ctypes.c_int * 5)(1, 2, 3, 4, 5)
    assert arr[0] == 1
    assert arr[4] == 5
    assert len(arr) == 5
    # 改
    arr[2] = 99
    assert arr[2] == 99
