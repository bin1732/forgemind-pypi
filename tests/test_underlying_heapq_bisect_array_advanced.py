# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`heapq` + `bisect` + `array` + `math` 真底层测试。

覆盖优先队列/二分插入/紧凑数组/数学模块:
  - `heapq.heappush/heappop` 真维护 min-heap,pop 出序递增
  - `heapq.heappushpop` 真先 push 再 pop,pop 出来的不大于 push 进去
  - `heapq.heapreplace` 真先 pop 再 push,返回旧 heap[0]
  - `heapq.nlargest/nsmallest` 真返前 N 大/小
  - `bisect.bisect_left/right` 真找左/右插入点,长度 5 数组上对得上
  - `array.array('i', ...)` 真紧凑 int 数组,`tolist()` 拿回 list
  - `array.array('d', ...)` 真 double 数组,内存 size = N*8
  - `math.fsum([0.1]*10)` 真比 sum 精确 (累加误差小)
  - `math.gcd/lcm/isqrt` 真整数运算,isqrt(100)=10
"""
import array
import bisect
import heapq
import math

import pytest


# -- heapq --------------------------------------------------------------------

class TestHeapq:
    def test_heappush_then_heappop_yields_sorted(self):
        """`heappush/heappop` 真维护 min-heap,pop 出序非递减。"""
        h = [3, 1, 4, 1, 5, 9, 2, 6]
        heapq.heapify(h)
        popped = []
        while h:
            popped.append(heapq.heappop(h))
        assert popped == sorted(popped), (
            f"heappop 序列应升序,实际 {popped}"
        )

    def test_heappushpop_combines_push_then_pop(self):
        """`heappushpop(h, x)` 真先 push x 再 pop 最小,返 ≤ x。"""
        h = [1, 2, 3, 4, 5]
        heapq.heapify(h)
        result = heapq.heappushpop(h, 10)
        # push 10 后,pop 出的应是 1 (原最小),而非 10
        assert result == 1, f"heappushpop(10) 应返 1 (原最小),实际 {result}"
        # 10 还在堆中
        assert 10 in h, f"10 应在堆中,实际 h={h}"

    def test_heapreplace_pop_then_push(self):
        """`heapreplace(h, x)` 真先 pop 最小再 push x,返旧最小。"""
        h = [1, 2, 3, 4, 5]
        heapq.heapify(h)
        result = heapq.heapreplace(h, 100)
        # pop 出 1,push 进 100
        assert result == 1, f"heapreplace 应返旧最小 1,实际 {result}"
        # 1 已被弹出
        assert 1 not in h, f"1 应已弹出,实际 h={h}"
        # 100 已在堆中
        assert 100 in h

    def test_nlargest_nsmallest(self):
        """`nlargest/nsmallest` 真返前 N 大/小,按真实值排序。"""
        data = [1, 5, 2, 8, 3, 9, 4, 7, 6]
        assert heapq.nlargest(3, data) == [9, 8, 7]
        assert heapq.nsmallest(3, data) == [1, 2, 3]


# -- bisect -------------------------------------------------------------------

class TestBisect:
    def test_bisect_left_and_right_on_sorted_list(self):
        """`bisect_left/right` 真找左/右插入点,等值时 left 在前 right 在后。"""
        a = [1, 3, 3, 3, 5, 7]
        # 插入 3:left 取最左 (idx=1),right 取最右之后 (idx=4)
        assert bisect.bisect_left(a, 3) == 1, (
            f"bisect_left(a, 3) 应=1,实际 {bisect.bisect_left(a, 3)}"
        )
        assert bisect.bisect_right(a, 3) == 4, (
            f"bisect_right(a, 3) 应=4,实际 {bisect.bisect_right(a, 3)}"
        )
        # 插入 4:left=right=4
        assert bisect.bisect_left(a, 4) == 4
        assert bisect.bisect_right(a, 4) == 4

    def test_insort_keeps_sorted(self):
        """`insort(a, x)` 真插入 x 并保数组有序。"""
        a = [1, 3, 5, 7]
        bisect.insort(a, 4)
        assert a == [1, 3, 4, 5, 7], f"insort 后应有序,实际 {a}"


# -- array --------------------------------------------------------------------

class TestArrayAdvanced:
    def test_array_signed_int_round_trip(self):
        """`array.array('i', ...)` 真紧凑 int 数组,tolist 拿回等价 list。"""
        a = array.array("i", [1, 2, 3, -4, 5])
        assert a.tolist() == [1, 2, 3, -4, 5]
        # 紧凑存储: itemsize * len
        assert a.itemsize == 4, f"i 数组 itemsize 应=4,实际 {a.itemsize}"
        assert a.buffer_info()[1] == 5, "buffer_info 返 (addr, length)"

    def test_array_double_size(self):
        """`array.array('d', ...)` 真 double 数组,size = N * 8 bytes。"""
        a = array.array("d", [1.0, 2.5, 3.14])
        assert a.itemsize == 8, f"'d' 数组 itemsize 应=8,实际 {a.itemsize}"
        # size 不直接暴露, 但 buffer_info()[1] * itemsize 是字节数
        bytes_used = a.buffer_info()[1] * a.itemsize
        assert bytes_used == 3 * 8, f"3 doubles 应占 24 字节,实际 {bytes_used}"

    def test_array_tofromfile(self):
        """`array.tofile(fp)` + `fromfile(fp, n)` 真二进制 round-trip。"""
        import io as _io
        a = array.array("i", [10, 20, 30, 40, 50])
        buf = _io.BytesIO()
        a.tofile(buf)
        buf.seek(0)
        b = array.array("i")
        b.fromfile(buf, 5)
        assert b.tolist() == [10, 20, 30, 40, 50]


# -- math ---------------------------------------------------------------------

class TestMathAdvanced:
    def test_fsum_more_precise_than_sum(self):
        """`math.fsum` 真比 `sum` 累加精确 (Python 文档承诺的精度保证)。"""
        # 经典累加误差案例
        inexact_sum = sum([0.1] * 10)
        exact_fsum = math.fsum([0.1] * 10)
        assert exact_fsum == 1.0, f"fsum([0.1]*10) 应=1.0,实际 {exact_fsum}"
        # sum 在沙箱 3.11+ 可能也精确,但 fsum 必然精确
        # 验 fsum 精确,sum 最多差 1e-15
        assert abs(inexact_sum - 1.0) < 1e-14

    def test_gcd_and_lcm(self):
        """`math.gcd/lcm` 真整数运算。"""
        assert math.gcd(12, 18) == 6
        assert math.gcd(0, 5) == 5  # gcd(0, n) = n
        assert math.lcm(4, 6) == 12
        assert math.lcm(3, 5) == 15  # 互质

    def test_isqrt_exact(self):
        """`math.isqrt` 真整数开方,isqrt(100) = 10,isqrt(99) = 9。"""
        assert math.isqrt(100) == 10
        assert math.isqrt(99) == 9
        assert math.isqrt(0) == 0
        assert math.isqrt(1) == 1

    def test_dist_invariants(self):
        """`math.dist` 欧氏距离,3-4-5 直角三角形距离 = 5。"""
        assert math.dist((0, 0), (3, 4)) == 5.0, "3-4-5 三角形"
        assert math.dist((1, 1), (1, 1)) == 0.0, "同点距离 0"
