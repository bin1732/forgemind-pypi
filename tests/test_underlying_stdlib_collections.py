# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 stdlib collections — deque / Counter / OrderedDict / defaultdict / ChainMap / namedtuple。
"""
import collections
import heapq
from collections import Counter, OrderedDict, defaultdict, deque, namedtuple
from collections import ChainMap

import pytest


def test_deque_appendleft_popleft_real():
    """deque 真支持 popleft (list 不支持)"""
    d = deque([1, 2, 3])
    d.appendleft(0)
    assert list(d) == [0, 1, 2, 3]
    first = d.popleft()
    assert first == 0
    assert list(d) == [1, 2, 3]


def test_deque_maxlen_real_overflow():
    """deque 真 maxlen 限制, append 超 maxlen 自动丢老"""
    d = deque(maxlen=3)
    for i in range(10):
        d.append(i)
    assert list(d) == [7, 8, 9], f"maxlen=3 应留 [7,8,9], 实际: {list(d)}"


def test_deque_extendleft_reverses_order():
    """deque extendleft 真反转顺序 (push each to left)"""
    d = deque()
    d.extendleft([1, 2, 3])
    # extendleft([1,2,3]) → 1 入最左, 2 入最左, 3 入最左 → [3, 2, 1]
    assert list(d) == [3, 2, 1], f"extendleft 应得 [3,2,1], 实际: {list(d)}"


def test_counter_counts_correctly():
    """Counter 真数元素出现次数"""
    c = Counter("abracadabra")
    assert c["a"] == 5
    assert c["b"] == 2
    assert c["r"] == 2
    assert c["c"] == 1
    assert c["d"] == 1
    assert c["z"] == 0  # 不存在, 返 0


def test_counter_most_common_real():
    """Counter most_common 真按频次排序"""
    c = Counter("mississippi")
    top = c.most_common(3)
    assert top == [("i", 4), ("s", 4), ("p", 2)] or top == [("s", 4), ("i", 4), ("p", 2)]


def test_counter_arithmetic_real():
    """Counter 真支持加减"""
    c1 = Counter("aabbc")
    c2 = Counter("abbb")
    assert c1 + c2 == Counter({"a": 3, "b": 5, "c": 1})
    # c1 - c2 = {a:1, c:1} (b:2-3<0 舍)
    assert c1 - c2 == Counter({"a": 1, "c": 1})
    # intersection
    assert c1 & c2 == Counter("abb")


def test_ordereddict_preserves_order():
    """OrderedDict 真按插入顺序 (Python 3.7+ dict 也保序, 但 OrderedDict 有额外 API)"""
    od = OrderedDict()
    od["z"] = 1
    od["a"] = 2
    od["m"] = 3
    assert list(od.keys()) == ["z", "a", "m"]
    # move_to_end 真
    od.move_to_end("z")
    assert list(od.keys()) == ["a", "m", "z"]


def test_defaultdict_real_factory():
    """defaultdict 真在缺失 key 时调 factory"""
    dd = defaultdict(list)
    dd["a"].append(1)
    dd["a"].append(2)
    dd["b"].append(3)
    assert dd["a"] == [1, 2]
    assert dd["b"] == [3]
    assert dd["notexist"] == [], "defaultdict 缺 key 应返空 list"


def test_chainmap_real_lookup():
    """ChainMap 真按顺序查多个 dict, 第一个赢"""
    a = {"x": 1, "y": 2}
    b = {"y": 3, "z": 4}
    cm = ChainMap(a, b)
    # y 应 = a 的 2 (第一个 dict 优先)
    assert cm["y"] == 2
    assert cm["x"] == 1
    assert cm["z"] == 4
    # 写只影响第一个 dict
    cm["y"] = 99
    assert a["y"] == 99
    assert b["y"] == 3  # b 没改


def test_namedtuple_real():
    """namedtuple 真有 field name + 仍 tuple-like"""
    Point = namedtuple("Point", ["x", "y", "z"])
    p = Point(1, 2, 3)
    assert p.x == 1
    assert p.y == 2
    assert p.z == 3
    # 仍可解 tuple
    a, b, c = p
    assert (a, b, c) == (1, 2, 3)
    # 可索引
    assert p[0] == 1
    # 不可变
    with pytest.raises(AttributeError):
        p.x = 99


def test_heappush_heappop_real():
    """heapq 真产最小堆"""
    h = []
    heapq.heappush(h, 5)
    heapq.heappush(h, 1)
    heapq.heappush(h, 3)
    heapq.heappush(h, 2)
    sorted_vals = [heapq.heappop(h) for _ in range(4)]
    assert sorted_vals == [1, 2, 3, 5], f"heapq pop 应升序, 实际: {sorted_vals}"


def test_heapsort_real():
    """heapq.heapsort 真正实排序"""
    arr = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
    sorted_arr = heapq.nsmallest(len(arr), arr)
    assert sorted_arr == sorted(arr)


def test_counter_update_real():
    """Counter 真累加 (不替换)"""
    c = Counter("aab")
    c.update("aac")
    assert c["a"] == 4, f"update 应累加, 实际 a={c['a']}"
    assert c["b"] == 1
    assert c["c"] == 1
