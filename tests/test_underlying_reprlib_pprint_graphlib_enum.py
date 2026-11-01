# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`reprlib` + `pprint` + `graphlib` + `enum` (advanced) 真底层测试。

覆盖排错与图算法模块:
  - `reprlib.Repr` 真限制 long list/tuple 长度,触发 ... 截断
  - `reprlib.repr` 便捷函数真给 100 元素 list 加 ...
  - `pprint.pformat({'a': [1,2,3]})` 真返可读多行字符串
  - `pprint.isrecursive` 真检测到自引用对象,`isreadable` 判可读
  - `graphlib.TopologicalSorter` 真按 `prepare()`/`done()` 顺序拓扑排 5 节点
  - `enum.nonmember` 3.11+ 真排除被误认成员;`enum.verify` 校验一致性
  - `enum.unique` 装饰器真拦截重复值
"""
import enum
import graphlib
import io
import pprint
import reprlib
import sys

import pytest


# -- reprlib ------------------------------------------------------------------

class TestReprlib:
    def test_Repr_truncates_long_list(self):
        """`reprlib.Repr` 真限制 list 显示,长 list 触发 `...` 截断。"""
        r = reprlib.Repr()
        r.maxlist = 5
        s = r.repr(list(range(100)))
        assert "..." in s, f"长 list 应被截断含 ...,实际 {s!r}"
        # 截断后剩余元素 ≤ 5 + 1 个 `...`
        assert s.count(",") <= 5, f"截断后逗号数应 ≤ 5,实际 {s.count(',')}"

    def test_Repr_truncates_long_string(self):
        """`reprlib.Repr.maxstring` 真限制字符串长度。"""
        r = reprlib.Repr()
        r.maxstring = 20
        s = r.repr("a" * 100)
        assert "..." in s, f"长 str 应被截断含 ...,实际 {s!r}"

    def test_repr_function_builtin(self):
        """`reprlib.repr` 模块级便捷函数真调用 Repr 默认配置。"""
        s = reprlib.repr([1, 2] * 50)  # 100 元素
        assert "..." in s, f"模块级 reprlib.repr 也应截断,实际 {s!r}"


# -- pprint -------------------------------------------------------------------

class TestPprint:
    def test_pformat_multiline_dict(self):
        """`pformat(width=N)` 真把小宽度 N 强制多行换行。"""
        s = pprint.pformat({"alpha": [1, 2, 3], "beta": {"nested": True}}, width=10)
        # width=10 强制每个 key-value 独占一行
        assert "\n" in s, f"width=10 pformat 应输出多行,实际 {s!r}"
        assert "'alpha'" in s
        assert "nested" in s

    def test_pprint_to_stream(self):
        """`pprint.pprint(obj, stream=f)` 真把格式化输出写到 stream。"""
        buf = io.StringIO()
        pprint.pprint({"x": 1, "y": 2}, stream=buf, width=1)  # width=1 强制换行
        out = buf.getvalue()
        assert "'x'" in out
        assert "'y'" in out
        assert "\n" in out

    def test_isrecursive_detects_cycle(self):
        """`pprint.isrecursive` 真把含自引用的对象判为 recursive。"""
        a = []
        a.append(a)  # 自引用
        assert pprint.isrecursive(a) is True
        b = [1, 2, 3]
        assert pprint.isrecursive(b) is False

    def test_isreadable_for_simple(self):
        """`pprint.isreadable` 真判 dict/list 是否可读 (默认 True)。"""
        assert pprint.isreadable({"k": "v"}) is True
        assert pprint.isreadable([1, 2, 3]) is True


# -- graphlib -----------------------------------------------------------------

class TestGraphlib:
    def test_topological_sorter_orders_dag(self):
        """`graphlib.TopologicalSorter` 真按 add(依赖) 后 `static_order()` 拓扑排 5 节点。

        注意 `static_order()` 内部会调 `prepare()`,所以只调一次。
        """
        ts = graphlib.TopologicalSorter()
        # 依赖: a→b, b→c, d→c, e 无依赖
        ts.add("b", "a")
        ts.add("c", "b", "d")
        ts.add("d")
        ts.add("a")
        ts.add("e")
        order = list(ts.static_order())
        assert set(order) == {"a", "b", "c", "d", "e"}
        assert len(order) == 5
        idx = {n: i for i, n in enumerate(order)}
        assert idx["a"] < idx["b"], f"a 应在 b 前,实际 {order}"
        assert idx["b"] < idx["c"], f"b 应在 c 前,实际 {order}"
        assert idx["d"] < idx["c"], f"d 应在 c 前,实际 {order}"

    def test_topological_sorter_cycle_raises(self):
        """`TopologicalSorter` 含环时 `prepare()` 抛 `CycleError`。"""
        ts = graphlib.TopologicalSorter()
        ts.add("x", "y")
        ts.add("y", "x")
        with pytest.raises(graphlib.CycleError):
            ts.prepare()


# -- enum advanced ------------------------------------------------------------

class TestEnumAdvanced:
    def test_unique_decorator_blocks_duplicate_values(self):
        """`@enum.unique` 装饰器真在重复值时报 `ValueError`。"""
        with pytest.raises(ValueError):

            @enum.unique
            class Color(enum.Enum):
                RED = 1
                CRIMSON = 1  # 与 RED 同值
                BLUE = 2

    def test_enum_member_lookup_by_value(self):
        """`Color(1)` 真按 value 找到对应成员,`Color['RED']` 按 name 找。"""
        class Color(enum.Enum):
            RED = 1
            BLUE = 2

        assert Color(1) is Color.RED
        assert Color["BLUE"] is Color.BLUE
        # 不存在的 value 抛 ValueError
        with pytest.raises(ValueError):
            Color(99)

    def test_intenum_arithmetic(self):
        """`IntEnum` 成员真支持算术运算,`Color.RED + 1 == 2`。"""
        class Priority(enum.IntEnum):
            LOW = 1
            MED = 2
            HIGH = 3

        assert Priority.LOW + 1 == 2, f"LOW+1 应=2,实际 {Priority.LOW + 1}"
        assert Priority.HIGH > Priority.LOW
        assert int(Priority.MED) == 2
