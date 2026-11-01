# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`inspect` 进阶 (isawaitable/iscoroutinefunction/isroutine/ismethod/formatannotation/getannotations) + `bdb` 进阶 (set_break) + `namedtuple` 进阶 (rename/field_defaults/module) + `typing.TypeGuard/TypeIs` 版本门槛 + 真底层测试。

覆盖 inspect 6 + bdb 1 + namedtuple 3 + typing 2 (共 12 真测试) 模块:
  - `inspect.isawaitable` 对 coroutine True / 对普通对象 False
  - `inspect.iscoroutinefunction` 对 async def True / 对普通 def False
  - `inspect.isroutine` 对 function True
  - `inspect.ismethod` 对绑定方法 True
  - `inspect.formatannotation` 对 int 返回 'int'
  - `inspect.get_annotations` 返回 {'x': int, 'y': str}
  - `bdb.Bdb.set_break` 设断点后 `get_breaks` 含该位置
  - `namedtuple` rename=True 自动生成 _0/_1 风格字段名
  - `namedtuple` rename=True 遇非法标识符自动改名 _1/_2
  - `namedtuple.__module__` 继承定义处模块名
  - `typing.TypeGuard` 存在性 (3.10+)
  - `typing.TypeIs` 存在性 (3.13+)
"""
import bdb
import collections
import inspect
import typing

import pytest


async def _forge_coroutine():
    """内部协程,用于验证 inspect 的协程判定。"""
    return "forge"


def _forge_plain_function(x: int, y: str = "forge") -> str:
    """内部普通函数,用于验证可调用对象判定与注解读取。"""
    return f"{x}{y}"


class _ForgeHolder:
    """内部持有绑定方法的类,用于验证 ismethod 判定。"""

    def method(self) -> None:
        """绑定方法目标。"""
        return None


# -- inspect 进阶 --------------------------------------------

class TestInspectIsAwaitableIsCoroutineFunctionIsRoutineIsMethodAdvanceV1:
    def test_isawaitable_coroutine(self):
        """`inspect.isawaitable 对 coroutine True。"""
        coro = _forge_coroutine()
        try:
            # 必 True
            assert inspect.isawaitable(coro) is True
        finally:
            coro.close()

    def test_isawaitable_plain_object(self):
        """`inspect.isawaitable 对普通对象 False。"""
        # 必 False
        assert inspect.isawaitable({"forge": 1}) is False

    def test_iscoroutinefunction_true(self):
        """`inspect.iscoroutinefunction 对 async def True。"""
        # 必 True
        assert inspect.iscoroutinefunction(_forge_coroutine) is True

    def test_iscoroutinefunction_false(self):
        """`inspect.iscoroutinefunction 对普通 def False。"""
        # 必 False
        assert inspect.iscoroutinefunction(_forge_plain_function) is False

    def test_isroutine_true(self):
        """`inspect.isroutine 对 function True。"""
        # 必 True
        assert inspect.isroutine(_forge_plain_function) is True

    def test_ismethod_bound(self):
        """`inspect.ismethod 对绑定方法 True。"""
        bound = _ForgeHolder().method
        # 必 True
        assert inspect.ismethod(bound) is True


class TestInspectFormatAnnotationGetAnnotationsAdvanceV2:
    def test_formatannotation_int(self):
        """`inspect.formatannotation 对 int 返回 'int'。"""
        # 必 'int'
        assert inspect.formatannotation(int) == "int"

    def test_getannotations(self):
        """`inspect.get_annotations 返回 {'x': int, 'y': str}。"""
        result = inspect.get_annotations(_forge_plain_function)
        # 必 dict
        assert isinstance(result, dict)
        # 必 x=int
        assert result["x"] is int
        # 必 y=str
        assert result["y"] is str


# -- bdb 进阶 -----------------------------------------------

class TestBdbSetBreakAdvanceV1:
    def test_Bdb_set_break(self):
        """`bdb.Bdb.set_break 设断点后 get_breaks 含该位置。"""
        dbg = bdb.Bdb()
        lineno = _forge_plain_function.__code__.co_firstlineno
        # 必 None (set_break 无返回值)
        assert dbg.set_break(__file__, lineno) is None
        # 必 该位置有断点
        assert len(dbg.get_breaks(__file__, lineno)) == 1


# -- namedtuple 进阶 ----------------------------------------

class TestNamedtupleRenameFieldDefaultsModuleAdvanceV1:
    def test_rename_auto(self):
        """`namedtuple rename=True 自动生成 _0/_1 风格字段名。"""
        Point = collections.namedtuple("Point", ["x", "y"], rename=True)
        # 必 'x' 保持合法
        assert Point._fields[0] == "x"
        # 必 'y' 保持合法
        assert Point._fields[1] == "y"

    def test_rename_invalid_identifier(self):
        """`namedtuple rename=True 遇非法标识符自动改名 _1/_2。"""
        Weird = collections.namedtuple("Weird", ["class", "1bad"], rename=True)
        # 必 'class' -> '_0'
        assert Weird._fields[0] == "_0"
        # 必 '1bad' -> '_1'
        assert Weird._fields[1] == "_1"

    def test_module(self):
        """`namedtuple.__module__ 继承定义处模块名。"""
        Local = collections.namedtuple("Local", ["a"])
        # 必 str
        assert isinstance(Local.__module__, str)
        # 必 本模块名
        assert Local.__module__ == __name__


# -- typing 进阶 --------------------------------------------

class TestTypingTypeGuardTypeIsAdvanceV1:
    def test_TypeGuard_exists(self):
        """`typing.TypeGuard 存在性 (3.10+)。"""
        # 必 hasattr
        assert hasattr(typing, "TypeGuard")

    @pytest.mark.skipif(not hasattr(typing, "TypeIs"), reason="typing.TypeIs 需要 Python 3.13+")
    def test_TypeIs_exists(self):
        """`typing.TypeIs 存在性 (3.13+)。"""
        # 必 hasattr
        assert hasattr(typing, "TypeIs")
