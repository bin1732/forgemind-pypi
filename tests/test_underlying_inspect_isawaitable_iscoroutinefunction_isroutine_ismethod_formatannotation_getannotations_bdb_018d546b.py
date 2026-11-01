# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`inspect` 进阶 (isawaitable+iscoroutinefunction+isroutine+ismethod+formatannotation+getannotations) + `bdb` 进阶 (Bdb class) + `namedtuple` 进阶 (rename+_module) + `typing.TypeGuard/TypeIs` 3.10+/3.13+ + 真底层测试。

覆盖 inspect 6 真 (isawaitable+iscoroutinefunction+isroutine+ismethod+formatannotation+getannotations) + bdb 1 真 (Bdb class) + namedtuple 3 真 (rename auto+rename trigger+_module) + typing 2 真 (TypeGuard 3.10+/TypeIs 3.13+ 沙箱 skip) (共 12 真测试) 模块:
  - `inspect.isawaitable 真 async fn 返 True / 42 返 False`
  - `inspect.iscoroutinefunction 真 async fn 返 True / lambda 返 False`
  - `inspect.isroutine 真 lambda 返 True / 42 返 False`
  - `inspect.ismethod 真 bound method 返 True`
  - `inspect.formatannotation 真 str 返 'int'`
  - `inspect.getannotations 真 my_fn 必含 'x' -> int / 'y' -> str`
  - `bdb.Bdb class 必存在 + set_break 存在`
  - `namedtuple('Pt','x y') 真建 (rename auto x/y)`
  - `namedtuple rename 必 trigger _1 _2 (def+class 是 keyword)`
  - `namedtuple.__module__ 必 str`
  - `typing.TypeGuard 3.10+ 沙箱 3.11 必有`
  - `typing.TypeIs 3.13+ 沙箱 3.11 skip`
"""
import bdb
import collections
import inspect
import sys
import typing

import pytest


# -- inspect 进阶 ---------------------------------------------------------

class TestInspectAdvancedV8:
    def test_isawaitable(self):
        """`isawaitable 真 async fn 返 True。"""

        async def my_coro():
            return "forge_await"

        # async fn 必 awaitable
        assert inspect.isawaitable(my_coro()) is True
        # 必非 awaitable
        assert inspect.isawaitable(42) is False
        assert inspect.isawaitable("forge") is False

    def test_iscoroutinefunction(self):
        """`iscoroutinefunction 真 async fn 返 True。"""

        async def my_coro():
            pass

        # async fn 必 coro
        assert inspect.iscoroutinefunction(my_coro) is True
        # 普通 fn 必非 coro
        assert inspect.iscoroutinefunction(lambda: None) is False

    def test_isroutine(self):
        """`isroutine 真 lambda 返 True。"""
        # lambda 必 routine
        assert inspect.isroutine(lambda: None) is True
        # 普通 fn 必 routine
        def my_fn():
            pass
        assert inspect.isroutine(my_fn) is True
        # int 必非 routine
        assert inspect.isroutine(42) is False

    def test_ismethod(self):
        """`ismethod 真 instance method 返 True。"""

        class _O:
            def m(self):
                return "forge_m"

        obj = _O()
        # bound method 必 method
        assert inspect.ismethod(obj.m) is True

    def test_formatannotation(self):
        """`formatannotation 真 str 返 'int'。"""
        # formatannotation('int') 必 'int'
        result = inspect.formatannotation("int")
        # 必 str
        assert isinstance(result, str)
        # 必含 int
        assert "int" in result

    def test_getannotations(self):
        """`getannotations 真 my_fn 必含 'x' -> int / 'y' -> str。"""

        def my_fn(x: int, y: str = "forge"):
            return x

        ann = inspect.get_annotations(my_fn)
        # 必 dict
        assert isinstance(ann, dict)
        # 必含 x + y
        assert "x" in ann
        assert "y" in ann
        # x 必 int
        assert ann["x"] is int
        # y 必 str
        assert ann["y"] is str


# -- bdb 进阶 ---------------------------------------------------------

class TestBdbAdvanced:
    def test_Bdb_class(self):
        """`bdb.Bdb class 必存在 + set_break 存在。"""
        assert bdb.Bdb is not None
        # 必能建
        b = bdb.Bdb()
        # 必含 set_break
        assert hasattr(b, "set_break")


# -- namedtuple 进阶 (rename + _module) ------------------------------

class TestNamedTupleAdvanced:
    def test_rename_auto(self):
        """`namedtuple('Pt','x y') 真建 (rename auto x/y)。"""
        Pt = collections.namedtuple("Pt", "x y")
        # 必建
        p = Pt(1, 2)
        # 必 1, 2
        assert p.x == 1
        assert p.y == 2

    def test_rename_trigger(self):
        """`namedtuple rename=True 必 trigger '_X' (沙箱 3.11 从 _1 开始)`"""
        # '1from' 开头是数字, 必 rename 成 '_X'
        Bad = collections.namedtuple("Bad", ["x", "1from", "2to"], rename=True)
        # 必 _fields 第一个 'x' 保留,后 2 个 rename
        # 沙箱 3.11 实际从 _1 开始
        assert Bad._fields[0] == "x"
        assert Bad._fields[1].startswith("_")
        assert Bad._fields[2].startswith("_")
        # 必能创
        b = Bad(1, 2, 3)
        assert b.x == 1
        # 必能访 必含 '_{n}'
        assert getattr(b, Bad._fields[1]) == 2
        assert getattr(b, Bad._fields[2]) == 3

    def test_namedtuple_module_default(self):
        """`namedtuple.__module__ 必 str。"""
        Pt = collections.namedtuple("Pt", "x y")
        # 必 _module = __name__
        # 沙箱测 _module 必 str
        assert isinstance(Pt.__module__, str)
        # 必 ≥ 1
        assert len(Pt.__module__) >= 1


# -- typing.TypeGuard/TypeIs 进阶 (3.10+/3.13+ 沙箱 skip) -------------

class TestTypingTypeGuardTypeIs:
    def test_TypeGuard_sandbox(self):
        """`typing.TypeGuard 3.10+ 沙箱 3.11 必有。"""
        # 沙箱 3.11 必有 TypeGuard
        if hasattr(typing, "TypeGuard"):
            # 必能 call
            t = typing.TypeGuard[int]
            # 必非 None
            assert t is not None
        else:
            pytest.skip("3.10+ TypeGuard")

    def test_TypeIs_3_13(self):
        """`typing.TypeIs 3.13+ 沙箱 3.11 skip。"""
        if sys.version_info < (3, 13):
            pytest.skip("3.13+ TypeIs")
        # 沙箱 3.13+ 必有
        if hasattr(typing, "TypeIs"):
            t = typing.TypeIs[int]
            assert t is not None
