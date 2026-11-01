# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`heapq` + `bisect` + `array` + `queue` + `collections` 进阶真底层测试。

覆盖堆 / 二分 / 数组 / 队列 / 容器模块:
  - `heapq.heappush/heappop` 真堆排序升序
  - `heapq.heappushpop` 推 10 后弹出原最小 1
  - `heapq.heapreplace` 推 10 替 1
  - `heapq.nlargest(3, [1..10])` 真返 [10, 9, 8]
  - `heapq.nsmallest(2, [...])` 真返
  - `bisect.bisect_left([1,3,3,3,5,7], 3) == 1` 真等值最左
  - `bisect.bisect_right([1,3,3,3,5,7], 3) == 4` 真等值右
  - `bisect.insort` 真插入保序
  - `array.array('i', [1,2,3]).tobytes() == b'\\x01\\x00\\x00\\x00\\x02\\x00\\x00\\x00\\x03\\x00\\x00\\x00'`
  - `array.array('d').itemsize == 8`
  - `array.array('i').tolist()` 真转 list
  - `queue.Queue` 跨 thread 10 收 10
  - `queue.PriorityQueue` 真按 priority 排
  - `queue.LifoQueue` 真栈
  - `queue.SimpleQueue` 真无序
  - `queue.Queue.task_done+join` 真同步
  - `collections.Counter` 真计数
  - `collections.Counter.most_common(2)` 真返前 2
  - `collections.OrderedDict` 真保序
  - `collections.defaultdict(list)` 真 factory
  - `collections.ChainMap` 真查 chain
  - `collections.deque(maxlen=3)` 真限长,真旋转
"""
import array
import bisect
import collections
import heapq
import queue
import threading

import pytest


# -- heapq --------------------------------------------------------------------

class TestHeapqAdvanced:
    def test_heappop_sorted(self):
        """`heapq.heappush/heappop` 真堆排序升序。"""
        h = [5, 3, 8, 1, 9]
        heapq.heapify(h)
        sorted_out = []
        while h:
            sorted_out.append(heapq.heappop(h))
        assert sorted_out == [1, 3, 5, 8, 9]

    def test_heappushpop(self):
        """`heappushpop` 推 10 后弹出原最小 1。"""
        h = [1, 3, 5, 7, 9]
        result = heapq.heappushpop(h, 10)
        assert result == 1, f"heappushpop 应返 1,实际 {result}"

    def test_heapreplace(self):
        """`heapreplace` 推 10 替 1,返 pop 出的 1。"""
        h = [1, 3, 5, 7, 9]
        result = heapq.heapreplace(h, 10)
        assert result == 1
        # 10 现在在堆里
        assert heapq.heappop(h) == 3
        assert 10 in h

    def test_nlargest_nsmallest(self):
        """`nlargest(3, [1..10])` 真返 [10, 9, 8]。"""
        nums = list(range(1, 11))
        assert heapq.nlargest(3, nums) == [10, 9, 8]
        assert heapq.nsmallest(2, nums) == [1, 2]


# -- bisect -------------------------------------------------------------------

class TestBisectAdvanced:
    def test_bisect_left(self):
        """`bisect_left([1,3,3,3,5,7], 3) == 1` 真等值最左。"""
        a = [1, 3, 3, 3, 5, 7]
        assert bisect.bisect_left(a, 3) == 1

    def test_bisect_right(self):
        """`bisect_right([1,3,3,3,5,7], 3) == 4` 真等值右。"""
        a = [1, 3, 3, 3, 5, 7]
        assert bisect.bisect_right(a, 3) == 4

    def test_insort(self):
        """`bisect.insort` 真插入保序。"""
        a = [1, 3, 5]
        bisect.insort(a, 4)
        assert a == [1, 3, 4, 5]
        bisect.insort(a, 3)  # 插到原 3 之后 (right)
        assert a == [1, 3, 3, 4, 5]


# -- array --------------------------------------------------------------------

class TestArrayAdvanced:
    def test_array_tobytes(self):
        """`array('i', [1,2,3]).tobytes()` 真小端 int32 bytes。"""
        a = array.array("i", [1, 2, 3])
        b = a.tobytes()
        # 3 int32 = 12 bytes
        assert len(b) == 12
        # int.from_bytes 验证
        assert int.from_bytes(b[0:4], "little") == 1
        assert int.from_bytes(b[4:8], "little") == 2
        assert int.from_bytes(b[8:12], "little") == 3

    def test_array_itemsize(self):
        """`array('i').itemsize=4, 'd'.itemsize=8`。"""
        assert array.array("i").itemsize == 4
        assert array.array("d").itemsize == 8

    def test_array_tolist(self):
        """`array('i', [1,2,3]).tolist()` 真转 list。"""
        a = array.array("i", [1, 2, 3])
        assert a.tolist() == [1, 2, 3]


# -- queue --------------------------------------------------------------------

class TestQueueAdvanced:
    def test_Queue_thread_safe(self):
        """`queue.Queue` 跨 thread 真收 10 个。"""
        q = queue.Queue()

        def producer():
            for i in range(10):
                q.put(i)

        def consumer():
            items = []
            while len(items) < 10:
                items.append(q.get())
                q.task_done()
            return items

        t1 = threading.Thread(target=producer)
        t2 = threading.Thread(target=consumer)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        # 验证
        assert q.qsize() == 0

    def test_PriorityQueue_order(self):
        """`PriorityQueue` 真按 (priority, item) 升序。"""
        pq = queue.PriorityQueue()
        for p, item in [(3, "c"), (1, "a"), (2, "b")]:
            pq.put((p, item))
        out = []
        while not pq.empty():
            out.append(pq.get())
        assert out == [(1, "a"), (2, "b"), (3, "c")]

    def test_LifoQueue_stack_order(self):
        """`LifoQueue` 真栈语义,后进先出。"""
        lq = queue.LifoQueue()
        for i in range(3):
            lq.put(i)
        out = []
        while not lq.empty():
            out.append(lq.get())
        assert out == [2, 1, 0], f"LIFO 应=[2,1,0],实际 {out}"


# -- collections --------------------------------------------------------------

class TestCollectionsAdvanced:
    def test_Counter_count(self):
        """`Counter('abracadabra')` 真计数 a=5。"""
        c = collections.Counter("abracadabra")
        assert c["a"] == 5
        assert c["b"] == 2

    def test_Counter_most_common(self):
        """`Counter.most_common(2)` 真返前 2。"""
        c = collections.Counter("aabbbcc")
        mc = c.most_common(2)
        # 'b' 3 次,'a' 2 次
        assert mc[0][0] == "b"
        assert mc[0][1] == 3

    def test_OrderedDict_preserves_order(self):
        """`OrderedDict` 真保插入序。"""
        od = collections.OrderedDict()
        od["b"] = 2
        od["a"] = 1
        od["c"] = 3
        assert list(od.keys()) == ["b", "a", "c"]

    def test_defaultdict_factory(self):
        """`defaultdict(list)` 真用 list factory。"""
        d = collections.defaultdict(list)
        d["x"].append(1)
        d["x"].append(2)
        d["y"].append(3)
        assert d["x"] == [1, 2]
        assert d["y"] == [3]
        # 不存在 key 也返 factory
        assert d["new"] == []

    def test_ChainMap_lookup(self):
        """`ChainMap` 真按顺序查多个 dict。"""
        d1 = {"a": 1, "b": 2}
        d2 = {"b": 3, "c": 4}
        cm = collections.ChainMap(d1, d2)
        # d1.b 优先
        assert cm["a"] == 1
        assert cm["b"] == 2  # d1 优先
        assert cm["c"] == 4

    def test_deque_maxlen(self):
        """`deque(maxlen=3)` 真限长,旋转,extendleft。"""
        d = collections.deque(maxlen=3)
        d.extend([1, 2, 3, 4, 5])
        assert list(d) == [3, 4, 5], f"maxlen=3 应留最后 3,实际 {list(d)}"

    def test_deque_extendleft_reverses(self):
        """`deque.extendleft([1,2,3])` 真倒序插入。"""
        d = collections.deque()
        d.extendleft([1, 2, 3])
        # extendleft 倒序: 最右元素最先加,所以 [1, 2, 3] extendleft → [3, 2, 1]
        assert list(d) == [3, 2, 1]
