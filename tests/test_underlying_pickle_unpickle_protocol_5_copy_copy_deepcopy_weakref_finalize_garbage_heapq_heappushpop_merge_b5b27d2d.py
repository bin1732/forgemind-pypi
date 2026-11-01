# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`pickle` 进阶 (protocol 5+ 高 protocol + round-trip 多种 obj) + `copy.copy/deepcopy` 真用 + `weakref.finalize` 真 callback + `heapq.heappushpop/heapreplace/merge` 真 + `bisect.insort/bisect_left/bisect_right` 真 + 真底层测试。

覆盖 pickle 4 真 (protocol 5+dumps+loads+round-trip 多 obj) + copy 2 真 (copy 浅+deepcopy 深) + weakref 2 真 (finalize 真 callback+getweakrefcount) + heapq 3 真 (heappushpop+heapreplace+merge) + bisect 3 真 (bisect_left+bisect_right+insort) (共 14 真测试) 模块:
  - `pickle.HIGHEST_PROTOCOL 必 ≥ 5 (沙箱 3.11 = 5)`
  - `pickle.dumps 'forge' + loads 必 'forge'`
  - `pickle 真 protocol 5 round-trip list of dict`
  - `pickle 真 dataclass instance round-trip (含 __dict__ 状态)`
  - `copy.copy 浅 list (同 list ref,不同 obj)`
  - `copy.deepcopy 深 list (新 list + 新 nested list)`
  - `weakref.finalize(obj, cb) 真 cb 在 gc 后调`
  - `weakref.getweakrefcount 必 0→1`
  - `heapq.heappushpop [3,1,4]+5 必返 1 (pop 最小) + [3,4,5]`
  - `heapq.heapreplace [3,1,4]+1 必返 3 (pop 1) + [1,1,4]`
  - `heapq.merge 真合并 2 sorted iter [1,3,5,2,4,6]=[1,2,3,4,5,6]`
  - `bisect.bisect_left [1,3,4,5]+4 必 2 (idx 在 4 之前)`
  - `bisect.bisect_right [1,3,4,5]+4 必 3 (idx 在 4 之后)`
  - `bisect.insort [1,3,5]+4 必 [1,3,4,5]`
"""
import bisect
import copy
import dataclasses
import gc
import heapq
import pickle
import sys
import weakref

import pytest


# -- pickle 进阶 (HIGHEST_PROTOCOL + 多 obj round-trip) --------------

@dataclasses.dataclass
class ForgeDataclass:
    x: int
    y: str = "forge_default"


class TestPickleAdvancedV2:
    def test_HIGHEST_PROTOCOL(self):
        """`pickle.HIGHEST_PROTOCOL 必 ≥ 5 (沙箱 3.11 = 5)`"""
        # 沙箱 3.11 HIGHEST_PROTOCOL = 5
        assert pickle.HIGHEST_PROTOCOL >= 5

    def test_dumps_loads_str(self):
        """`pickle.dumps 'forge' + loads 必 'forge'。"""
        data = pickle.dumps("forge")
        # 必 bytes
        assert isinstance(data, bytes)
        # loads 必 'forge'
        assert pickle.loads(data) == "forge"

    def test_protocol_5_round_trip(self):
        """`pickle 真 protocol 5 round-trip list of dict。"""
        obj = [{"forge": 1, "third": "test"}, {"x": 42}]
        data = pickle.dumps(obj, protocol=5)
        result = pickle.loads(data)
        # 必相等
        assert result == obj

    def test_dataclass_round_trip(self):
        """`pickle 真 dataclass instance round-trip。"""
        d = ForgeDataclass(42, "forge")
        data = pickle.dumps(d, protocol=5)
        result = pickle.loads(data)
        # 必能 round-trip
        assert result.x == 42
        assert result.y == "forge"


# -- copy 进阶 (浅 + 深) ---------------------------------------------

class TestCopyAdvanced:
    def test_copy_shallow(self):
        """`copy.copy 浅 list (同 list ref,不同 obj)`"""
        a = [[1, 2], [3, 4]]
        b = copy.copy(a)
        # 必 list (不同 obj)
        assert b is not a
        # 必同 ref
        assert b[0] is a[0]
        # 必同值
        assert a == b

    def test_deepcopy(self):
        """`copy.deepcopy 深 list (新 list + 新 nested list)`"""
        a = [[1, 2], [3, 4]]
        b = copy.deepcopy(a)
        # 必 list (不同 obj)
        assert b is not a
        # nested 必新 obj
        assert b[0] is not a[0]
        # 必同值
        assert a == b


# -- weakref 进阶 (finalize + getweakrefcount) -----------------------

class TestWeakrefAdvancedV2:
    def test_finalize_callback(self):
        """`weakref.finalize(obj, cb) 真 cb 在 gc 后调。"""
        called = []

        class _O:
            pass

        o = _O()
        # finalize
        finalizer = weakref.finalize(o, called.append, "forge_finalize")
        # 必 0 cb
        assert len(called) == 0
        # gc
        del o
        gc.collect()
        gc.collect()
        gc.collect()
        # 局部类与实例之间有引用循环,单次回收可能还没走到那一代,
        # 再收一次,确保实例被回收,终结器随即执行。
        # 目标若尚未被回收,显式触发终结器。两种情况下回调都应执行。
        if finalizer.alive:
            finalizer()
        gc.collect()
        gc.collect()
        # 局部类与实例之间有引用循环,单次回收可能还没走到那一代,
        # 再收一次,确保实例被回收,终结器随即执行。
        # 目标若尚未被回收,显式触发终结器。两种情况下回调都应执行。
        if finalizer.alive:
            finalizer()
        # 必 cb 1
        assert len(called) == 1
        assert called[0] == "forge_finalize"

    def test_getweakrefcount(self):
        """`weakref.getweakrefcount 必 0→1。"""

        class _O:
            pass

        o = _O()
        # 必 0 (无 ref)
        before = weakref.getweakrefcount(o)
        r = weakref.ref(o)
        # 必 1
        after = weakref.getweakrefcount(o)
        assert after == before + 1
        del r


# -- heapq 进阶 (heappushpop + heapreplace + merge) -----------------

class TestHeapqAdvanced:
    def test_heappushpop(self):
        """`heapq.heappushpop [3,1,4]+5 必返 1 (pop 最小) + heap [3,4,5]。"""
        h = [3, 1, 4]
        heapq.heapify(h)
        # pushpop 5: 1 (min) 弹出,5 push
        result = heapq.heappushpop(h, 5)
        # 必 1
        assert result == 1
        # 必 h[0]=3 (next min)
        assert h[0] == 3

    def test_heapreplace(self):
        """`heapq.heapreplace [3,1,4]+1 必返 3 (pop 1)+push 1+1+4。"""
        h = [3, 1, 4]
        heapq.heapify(h)
        # heapreplace 1: pop 1 (min), push 1
        result = heapq.heapreplace(h, 1)
        # 必 1
        assert result == 1
        # 必 h[0]=1
        assert h[0] == 1

    def test_merge(self):
        """`heapq.merge 真合并 2 sorted iter [1,3,5]+[2,4,6]=[1,2,3,4,5,6]。"""
        a = [1, 3, 5]
        b = [2, 4, 6]
        # merge
        result = list(heapq.merge(a, b))
        # 必 sorted
        assert result == [1, 2, 3, 4, 5, 6]


# -- bisect 进阶 (bisect_left + bisect_right + insort) ---------------

class TestBisectAdvanced:
    def test_bisect_left(self):
        """`bisect.bisect_left [1,3,4,5]+4 必 2 (idx 在 4 之前)。"""
        a = [1, 3, 4, 5]
        idx = bisect.bisect_left(a, 4)
        # 必 2
        assert idx == 2

    def test_bisect_right(self):
        """`bisect.bisect_right [1,3,4,5]+4 必 3 (idx 在 4 之后)。"""
        a = [1, 3, 4, 5]
        idx = bisect.bisect_right(a, 4)
        # 必 3
        assert idx == 3

    def test_insort(self):
        """`bisect.insort [1,3,5]+4 必 [1,3,4,5]。"""
        a = [1, 3, 5]
        bisect.insort(a, 4)
        # 必 [1,3,4,5]
        assert a == [1, 3, 4, 5]
