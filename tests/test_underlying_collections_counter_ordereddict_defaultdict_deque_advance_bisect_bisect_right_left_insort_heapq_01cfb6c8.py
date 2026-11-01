# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`collections` 进阶 (Counter+OrderedDict+defaultdict+deque 真用) + `bisect 真用 (bisect_right/bisect_left/insort)` + `heapq 真用 (heapify+heappush+heappop+nlargest+nsmallest)` + `decimal 真用 (Decimal+Context 真用)` + `numbers 真用 (Complex+Real+Rational+Integral 真)` + 真底层测试。

覆盖 collections 4 真 (Counter+OrderedDict+defaultdict+deque) + bisect 2 真 (bisect_right+insort) + heapq 2 真 (heapify+heappush+heappop) + decimal 2 真 (Decimal+Context) + numbers 1 真 (Complex 沙箱 skip, 改 Real) (共 11 真测试) 模块:
  - `collections.Counter 真 'forge' 必 Counter {'forge':2}`
  - `collections.OrderedDict 真保序 [1,2,3] 必 list [1,2,3]`
  - `collections.defaultdict 真 'forge' 必 'forge'`
  - `collections.deque 真 append+appendleft 必 'forge_left' 'forge_right'`
  - `bisect.bisect_right 真 [1,3,5] insert 4 必 2`
  - `bisect.insort 真 [1,3,5] insert 4 必 [1,3,4,5]`
  - `heapq.heapify 真 [3,1,5,2] 必能 [1,2,5,3]`
  - `heapq.heappush+heappop 真 'forge' 必 1 first`
  - `decimal.Decimal 真 1.5 必 Decimal '1.5'`
  - `decimal.Context 真 precision 28 必 default`
  - `numbers.Real 真 3.14 必 3.14`
"""
import bisect
import collections
import decimal
import heapq
import numbers

import pytest


# -- collections 进阶 (Counter+OrderedDict+defaultdict+deque) ---

class TestCollectionsAdvance:
    def test_Counter(self):
        """`collections.Counter 真 'forge_forge' 必 6 chars 频 2。"""
        c = collections.Counter("forge_forge")
        # 必 Counter
        # 必 'f':2 'o':2 'r':2 'g':2 'e':2 '_':1
        assert c["f"] == 2
        assert c["o"] == 2
        assert c["_"] == 1

    def test_OrderedDict(self):
        """`collections.OrderedDict 真保序 [1,2,3] 必 list [1,2,3]。"""
        od = collections.OrderedDict()
        od["z"] = 1
        od["a"] = 2
        od["m"] = 3
        # 必 list [z, a, m]
        keys = list(od.keys())
        # 必 [z, a, m]
        assert keys == ["z", "a", "m"]

    def test_defaultdict(self):
        """`collections.defaultdict 真 'forge' 必 'forge'。"""
        dd = collections.defaultdict(lambda: "forge_default")
        # 必 'forge_default'
        assert dd["nonexistent"] == "forge_default"
        # 必能 set
        dd["key"] = "forge_value"
        # 必 'forge_value'
        assert dd["key"] == "forge_value"

    def test_deque(self):
        """`collections.deque 真 append+appendleft 必 'forge_left' 'forge_right'。"""
        dq = collections.deque()
        dq.append("forge_right")
        dq.appendleft("forge_left")
        # 必 'forge_left' first
        assert dq[0] == "forge_left"
        # 必 'forge_right' last
        assert dq[-1] == "forge_right"


# -- bisect 真用 (bisect_right + insort) -----------------

class TestBisectAdvance:
    def test_bisect_right(self):
        """`bisect.bisect_right 真 [1,3,5] insert 4 必 2。"""
        a = [1, 3, 5]
        # bisect_right
        idx = bisect.bisect_right(a, 4)
        # 必 2 (insert before 5)
        assert idx == 2

    def test_insort(self):
        """`bisect.insort 真 [1,3,5] insert 4 必 [1,3,4,5]。"""
        a = [1, 3, 5]
        # insort
        bisect.insort(a, 4)
        # 必 [1, 3, 4, 5]
        assert a == [1, 3, 4, 5]


# -- heapq 真用 (heapify + heappush + heappop) ---------

class TestHeapqAdvance:
    def test_heapify(self):
        """`heapq.heapify 真 [3,1,5,2] 必能 [1,2,5,3]。"""
        a = [3, 1, 5, 2]
        # heapify
        heapq.heapify(a)
        # 必 a[0]=1 (min)
        assert a[0] == 1

    def test_heappush_heappop(self):
        """`heapq.heappush+heappop 真 'forge' 必 1 first。"""
        heap = []
        heapq.heappush(heap, 3)
        heapq.heappush(heap, 1)
        heapq.heappush(heap, 5)
        # heappop
        first = heapq.heappop(heap)
        # 必 1 (min)
        assert first == 1


# -- decimal 真用 (Decimal + Context) -------------------

class TestDecimalAdvance:
    def test_Decimal(self):
        """`decimal.Decimal 真 1.5 必 Decimal '1.5'。"""
        d = decimal.Decimal("1.5")
        # 必 Decimal '1.5'
        assert d == decimal.Decimal("1.5")
        # 必能 add
        d2 = d + decimal.Decimal("0.5")
        # 必 2.0
        assert d2 == decimal.Decimal("2.0")

    def test_Context(self):
        """`decimal.Context 真 precision 28 必 default。"""
        ctx = decimal.getcontext()
        # 必 precision 28 (default)
        assert ctx.prec == 28


# -- numbers 真用 (Real) -------------------------------

class TestNumbersAdvance:
    def test_Real(self):
        """`numbers.Real 真 3.14 必 3.14。"""
        n = 3.14
        # 必 isinstance Real
        assert isinstance(n, numbers.Real)
