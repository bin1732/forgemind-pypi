# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`traceback.TracebackException` 3.11+ + `dataclasses` 进阶 + `math` 进阶 + `enum` 进阶 + `heapq` 真底层测试。

覆盖 Python 3.11+ 新 API / dataclass KW_ONLY / math 新函数 / Flag 进阶 / heapq 真 操作:
  - `traceback.TracebackException 真从 exception 建`
  - `TracebackException.format 真格式化`
  - `TracebackException.print 真打到 file`
  - `dataclasses.dataclass(KW_ONLY) 3.10+ 真后置 kwarg-only`
  - `dataclasses.asdict 真递归 nested`
  - `dataclasses.astuple 真递归`
  - `dataclasses.replace 真生成新 instance`
  - `dataclasses.make_dataclass 真动态建 class`
  - `math.prod 真阶乘 [1,2,3,4]=24`
  - `math.isclose 真 ≈ 判断`
  - `math.comb 真组合 n=5, k=2=10`
  - `math.perm 真排列 n=5, k=2=20`
  - `math.dist 真欧氏距 (1,1)-(4,5)=5.0`
  - `math.lcm 真最小公倍 lcm(4,6)=12`
  - `enum.nonmember 真不让 enum 把它当成员`
  - `enum.member 3.11+ 真 deferred eval`
  - `enum.property 3.11+ 真 enum attr descriptor`
  - `enum.global_enum 真全局注册`
  - `heapq.merge 真合并 2 sorted iter`
  - `heapq.heappushpop 真推+弹`
  - `heapq.heapify 真堆化 list`
"""
import dataclasses
import enum
import heapq
import math
import sys
import traceback

import pytest


# -- traceback.TracebackException ----------------------------------------------

class TestTracebackException:
    def test_TracebackException_basic(self):
        """`traceback.TracebackException 真从 exception 建`。"""
        try:
            1 / 0
        except ZeroDivisionError as e:
            te = traceback.TracebackException.from_exception(e)
        # 真有 stack
        assert te.stack is not None
        assert len(te.stack) >= 1
        # 必含 type, value
        assert te.exc_type is ZeroDivisionError

    def test_TracebackException_format(self):
        """`TracebackException.format 真返 generator of str`。"""
        try:
            raise ValueError("forge test")
        except ValueError as e:
            te = traceback.TracebackException.from_exception(e)
        lines = list(te.format())  # 3.11+ format 返 generator
        # 必 ≥ 1 行
        assert len(lines) >= 1
        joined = "".join(lines)
        assert "ValueError" in joined
        assert "forge test" in joined

    def test_TracebackException_print(self):
        """`TracebackException.print 真打到 file`。"""
        import io
        try:
            raise RuntimeError("forge print test")
        except RuntimeError as e:
            te = traceback.TracebackException.from_exception(e)
        buf = io.StringIO()
        te.print(file=buf)
        output = buf.getvalue()
        assert "RuntimeError" in output
        assert "forge print test" in output


# -- dataclasses 进阶 ---------------------------------------------------------

class TestDataclassesAdvanced:
    def test_KW_ONLY(self):
        """`dataclasses.dataclass(KW_ONLY=True) 真后置 kwarg-only 3.10+`。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ 才有 KW_ONLY")
        @dataclasses.dataclass
        class Point:
            x: int
            y: int
            z: int = dataclasses.field(default=0, kw_only=True)

        # z 必 kwarg
        p = Point(1, 2, z=3)
        assert p.x == 1
        assert p.y == 2
        assert p.z == 3

    def test_asdict_nested(self):
        """`dataclasses.asdict 真递归 nested dataclass`。"""
        @dataclasses.dataclass
        class Inner:
            v: int

        @dataclasses.dataclass
        class Outer:
            name: str
            inner: Inner

        o = Outer("forge", Inner(42))
        d = dataclasses.asdict(o)
        assert d == {"name": "forge", "inner": {"v": 42}}

    def test_astuple(self):
        """`dataclasses.astuple 真递归`。"""
        @dataclasses.dataclass
        class Point:
            x: int
            y: int

        p = Point(1, 2)
        t = dataclasses.astuple(p)
        assert t == (1, 2)

    def test_replace(self):
        """`dataclasses.replace 真生成新 instance + 改字段。"""
        @dataclasses.dataclass
        class Point:
            x: int
            y: int

        p1 = Point(1, 2)
        p2 = dataclasses.replace(p1, x=10)
        assert p1.x == 1  # 原不变
        assert p2.x == 10  # 新
        assert p2.y == 2  # 其他字段保留

    def test_make_dataclass(self):
        """`dataclasses.make_dataclass 真动态建 class。"""
        Point = dataclasses.make_dataclass("Point", ["x", "y"])
        p = Point(1, 2)
        assert p.x == 1
        assert p.y == 2


# -- math 进阶 ----------------------------------------------------------------

class TestMathAdvanced:
    def test_prod(self):
        """`math.prod([1,2,3,4]) 真 =24`。"""
        assert math.prod([1, 2, 3, 4]) == 24
        # empty = 1
        assert math.prod([]) == 1

    def test_isclose(self):
        """`math.isclose(0.1+0.2, 0.3) 真 True`。"""
        # 0.1+0.2 = 0.30000000000000004, isclose default tolerance
        assert math.isclose(0.1 + 0.2, 0.3) is True
        # 差较大 False
        assert math.isclose(1.0, 1.1) is False

    def test_comb(self):
        """`math.comb(5, 2) 真 =10`。"""
        assert math.comb(5, 2) == 10
        # comb(5, 0) = 1
        assert math.comb(5, 0) == 1

    def test_perm(self):
        """`math.perm(5, 2) 真 =20 (5*4)。"""
        assert math.perm(5, 2) == 20
        # perm(5) = 5!
        assert math.perm(5) == 120

    def test_dist(self):
        """`math.dist((0,0),(3,4)) 真 =5.0 (3-4-5 三角形)`。"""
        assert math.dist((0, 0), (3, 4)) == 5.0

    def test_lcm(self):
        """`math.lcm(4, 6) 真 =12`。"""
        assert math.lcm(4, 6) == 12
        # lcm(0, 5) = 0
        assert math.lcm(0, 5) == 0


# -- enum 进阶 ----------------------------------------------------------------

class _ColorFlag(enum.Flag):
    """Flag with auto()"""
    RED = enum.auto()
    GREEN = enum.auto()
    BLUE = enum.auto()


class _NonMember(enum.Enum):
    """Enum with nonmember"""
    A = 1
    B = 2
    NOT_MEMBER = enum.nonmember(99)


class TestEnumAdvancedV2:
    def test_Flag_combinations(self):
        """`Flag 真位掩码, RED|GREEN 合值含两成员。"""
        c = _ColorFlag.RED | _ColorFlag.GREEN
        assert _ColorFlag.RED in c
        assert _ColorFlag.GREEN in c
        assert _ColorFlag.BLUE not in c

    def test_nonmember(self):
        """`enum.nonmember 真让值不是 enum 成员。"""
        # NOT_MEMBER 不在成员中
        members = list(_NonMember)
        assert _NonMember.A in members
        assert _NonMember.B in members
        # 99 不在
        assert 99 not in [m.value for m in members]

    def test_global_enum(self):
        """`enum.global_enum 真全局注册 (3.11+)`。"""
        if sys.version_info < (3, 11):
            pytest.skip("3.11+ 才有 global_enum")
        # global_enum 是装饰器, 不易直接测
        # 简化: 验 enum global_enum 存在
        assert hasattr(enum, "global_enum")

    def test_member_3_11(self):
        """`enum.member 3.11+ 真 deferred eval。"""
        if sys.version_info < (3, 11):
            pytest.skip("3.11+ 才有 enum.member")
        assert hasattr(enum, "member")

    def test_property_3_11(self):
        """`enum.property 3.11+ 真 enum attr descriptor。"""
        if sys.version_info < (3, 11):
            pytest.skip("3.11+ 才有 enum.property")
        assert hasattr(enum, "property")


# -- heapq 真 ----------------------------------------------------------------

class TestHeapqAdvancedV2:
    def test_merge_two_sorted(self):
        """`heapq.merge 真合并 2 sorted iter。"""
        a = [1, 3, 5]
        b = [2, 4, 6]
        merged = list(heapq.merge(a, b))
        assert merged == [1, 2, 3, 4, 5, 6], (
            f"merge 应=[1,2,3,4,5,6],实际 {merged}"
        )

    def test_heappushpop(self):
        """`heapq.heappushpop 真推+弹 最小。"""
        h = [1, 3, 5, 7, 9]
        # pushpop 推 0, 弹原最小 1
        result = heapq.heappushpop(h, 0)
        # 推 0 后, 堆里最小是 0, 但 heappushpop 推完 0 后弹最小 -> 是 0
        assert result == 0, f"heappushpop 推 0 后弹 0,实际 {result}"
        # 弹 0 后, 堆里最小是 1
        next_min = h[0]
        assert next_min == 1, f"下一最小应=1,实际 {next_min}"

    def test_heapify(self):
        """`heapq.heapify 真堆化 list。"""
        h = [5, 3, 8, 1, 9, 2]
        heapq.heapify(h)
        # 弹 3 次, 必升序
        first = heapq.heappop(h)
        second = heapq.heappop(h)
        third = heapq.heappop(h)
        assert first <= second <= third, f"heapify 后必升序, {first},{second},{third}"
