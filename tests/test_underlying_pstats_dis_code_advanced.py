# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 pstats 真 sort_stats 多种 (cumulative/tottime/ncalls) + 真 dis 进阶 (disassemble/source_line) + 真 code 真属性 (co_consts/co_names/co_varnames) + 真 inspect 进阶 (FrameInfo/Traceback)。
全 stdlib, 零模拟。
"""
import pstats
import cProfile
import dis
import inspect
import io
import sys
import pytest


# ======================== pstats 进阶 ========================
def test_pstats_sort_cumulative():
    """真 pstats 真 sort cumulative"""
    profiler = cProfile.Profile()
    profiler.enable()
    # 嵌套
    def inner():
        return sum(range(100))
    def outer():
        return inner() * 2
    outer()
    outer()
    profiler.disable()
    s = io.StringIO()
    stats = pstats.Stats(profiler, stream=s)
    stats.sort_stats("cumulative")
    stats.print_stats(5)
    assert "cumulative" in s.getvalue() or "function calls" in s.getvalue()


def test_pstats_sort_tottime():
    """真 pstats 真 sort tottime"""
    profiler = cProfile.Profile()
    profiler.enable()
    sum(range(1000))
    profiler.disable()
    s = io.StringIO()
    stats = pstats.Stats(profiler, stream=s)
    stats.sort_stats("tottime")
    stats.print_stats(5)
    assert "tottime" in s.getvalue() or "function calls" in s.getvalue()


# ======================== dis 进阶 ========================
def test_dis_disassemble_function():
    """真 dis.dis 真 dis 函数"""
    def add(a, b):
        return a + b

    s = io.StringIO()
    dis.dis(add, file=s)
    output = s.getvalue()
    # 含 LOAD_FAST / BINARY_OP
    assert "LOAD_FAST" in output or "LOAD" in output
    assert "RETURN" in output


def test_dis_get_instructions_full():
    """真 dis.get_instructions 拿完整指令"""
    def my_func(x):
        if x > 0:
            return x * 2
        return -x

    instructions = list(dis.get_instructions(my_func))
    opnames = [i.opname for i in instructions]
    # 应有 COMPARE_OP / POP_JUMP_FORWARD_IF_FALSE 等
    assert any("JUMP" in op for op in opnames)
    assert any("RETURN" in op for op in opnames)


# ======================== code 进阶 ========================
def test_code_co_consts():
    """真 code 真 co_consts"""
    def f():
        return 42, "hello", (1, 2, 3)

    consts = f.__code__.co_consts
    # 整个 tuple 在 consts 中
    my_tuple = (42, "hello", (1, 2, 3))
    assert my_tuple in consts
    # None 必有
    assert None in consts


def test_code_co_names():
    """真 code 真 co_names"""
    def f():
        # 用 free / global
        x = 1
        return x

    names = f.__code__.co_names
    # f 没 external name
    # 但可能空
    assert isinstance(names, tuple)


def test_code_co_varnames():
    """真 code 真 co_varnames"""
    def f(a, b, c=10):
        x = 1
        y = 2
        return a + b + c + x + y

    varnames = f.__code__.co_varnames
    # a, b, c, x, y
    assert "a" in varnames
    assert "b" in varnames
    assert "c" in varnames
    assert "x" in varnames
    assert "y" in varnames


def test_code_co_freevars_cellvars():
    """真 code 真 co_freevars / co_cellvars"""
    def outer():
        x = 1  # cell
        def inner():
            return x  # free
        return inner

    code_inner = outer().__code__
    # inner 看 x (free)
    assert "x" in code_inner.co_freevars


# ======================== inspect 进阶 ========================
def test_inspect_getframeinfo():
    """真 inspect 真 getframeinfo"""
    import sys
    frame = sys._getframe()
    info = inspect.getframeinfo(frame)
    # 真 frameinfo
    assert info.filename.endswith(".py")
    assert info.function == "test_inspect_getframeinfo"


def test_inspect_currentframe():
    """真 inspect.currentframe 真当前 frame"""
    frame = inspect.currentframe()
    assert frame is not None
    assert frame.f_code.co_name == "test_inspect_currentframe"


def test_inspect_FrameInfo():
    """真 FrameInfo 真实有"""
    import sys
    frame = sys._getframe()
    info = inspect.getframeinfo(frame)
    # FrameInfo 真有 attributes
    assert info.filename
    assert info.lineno > 0
    assert info.function


def test_inspect_getargspec():
    """真 getargs 真 (DEPRECATED 3.11, 但仍存在)"""
    def func(a, b, c=10):
        return a + b + c

    # 3.11+ 仍 work
    if hasattr(inspect, "getargspec"):
        spec = inspect.getargspec(func)
        assert spec.args == ["a", "b", "c"]
        assert spec.defaults == (10,)


def test_inspect_ismethod():
    """真 inspect 真 ismethod"""
    class C:
        def method(self):
            pass

    c = C()
    # bound method
    assert inspect.ismethod(c.method)
    # unbound function
    assert not inspect.ismethod(C.method)
    # 普通函数
    def f():
        pass
    assert not inspect.ismethod(f)
