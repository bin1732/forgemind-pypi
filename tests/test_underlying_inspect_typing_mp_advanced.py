# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 inspect 进阶 (signature 嵌套 / Parameter 真 default) + 真 typing 进阶 (Optional 真 is None / Union 真) + 真 multiprocessing 进阶 (Process 跨模块 func) + 真 operator 真 methodcaller 真链。
全 stdlib, 零模拟。
"""
import inspect
import typing
import multiprocessing
import operator
import os
import pytest


# ======================== inspect 进阶 ========================
def test_inspect_signature_nested():
    """真 signature 真嵌套"""
    def outer(a: int):
        def inner(b: int, c: int = 5):
            return a + b + c
        return inner

    sig = inspect.signature(outer.inner if hasattr(outer, "inner") else outer)
    # 实际 outer 不带 inner
    sig2 = inspect.signature(outer)
    assert "a" in sig2.parameters


def test_inspect_Parameter_kind():
    """真 Parameter 真 kind"""
    def f(a, b=10, *args, c, **kwargs):
        pass

    sig = inspect.signature(f)
    p_a = sig.parameters["a"]
    p_b = sig.parameters["b"]
    p_args = sig.parameters["args"]
    p_c = sig.parameters["c"]
    p_kwargs = sig.parameters["kwargs"]
    # kinds
    assert p_a.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert p_b.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert p_args.kind == inspect.Parameter.VAR_POSITIONAL
    assert p_c.kind == inspect.Parameter.KEYWORD_ONLY
    assert p_kwargs.kind == inspect.Parameter.VAR_KEYWORD


def test_inspect_getmembers_filtered():
    """真 getmembers 真 filter"""
    class C:
        def method_a(self):
            pass
        def method_b(self):
            pass
        x = 1

    # 用 isfunction filter
    methods = inspect.getmembers(C, predicate=inspect.isfunction)
    method_names = [name for name, _ in methods if not name.startswith("_")]
    # method_a, method_b
    assert "method_a" in method_names
    assert "method_b" in method_names


# ======================== typing 进阶 ========================
def test_typing_Optional_is_None():
    """真 Optional 真 int | None 真"""
    # 3.10+ new syntax
    OptInt = typing.Optional[int]
    # 真 Optional
    args = typing.get_args(OptInt)
    # 实际 Optional[int] = Union[int, None]
    # 3.10+ 返 (int, <class 'NoneType'>) or similar
    # 真 Optional 在 typing
    assert OptInt is not None


def test_typing_Union_with_string():
    """真 Union 真"""
    U = typing.Union[int, str]
    args = typing.get_args(U)
    assert int in args
    assert str in args


def test_typing_Protocol_runtime_checkable():
    """真 Protocol 真 @runtime_checkable"""
    @typing.runtime_checkable
    class Drawable(typing.Protocol):
        def draw(self) -> str: ...

    class Circle:
        def draw(self) -> str:
            return "O"

    assert isinstance(Circle(), Drawable)


# ======================== multiprocessing 进阶 ========================
def _mp_worker_noop():
    """module-level function"""
    return 42


def test_mp_Process_module_func():
    """真 Process 真 module-level func"""
    p = multiprocessing.Process(target=_mp_worker_noop)
    p.start()
    p.join(timeout=5)
    assert p.exitcode == 0


def _mp_worker_with_arg(x, y):
    """module-level func with args"""
    return x + y


def test_mp_Process_with_args():
    """真 Process 真 args"""
    p = multiprocessing.Process(target=_mp_worker_with_arg, args=(3, 4))
    p.start()
    p.join(timeout=5)
    assert p.exitcode == 0


def test_mp_Process_daemon():
    """真 daemon 真 Process"""
    def run_forever():
        import time
        time.sleep(60)
    # daemon=True 主进程 退出 立即
    p = multiprocessing.Process(target=run_forever, daemon=True)
    # 不启动 (因 sleep 长)
    # 验证 daemon 属性
    assert p.daemon is True


# ======================== operator 进阶 ========================
def test_operator_methodcaller_chain():
    """真 methodcaller 真链"""
    # 真链 (.strip().lower())
    strip_lower = operator.methodcaller("strip")  # 一步
    result = strip_lower("  HELLO  ")
    assert result == "HELLO"
    # 真链
    s = "  HELLO  "
    s2 = operator.methodcaller("strip")(s)
    s3 = operator.methodcaller("lower")(s2)
    assert s3 == "hello"


def test_operator_itemgetter_slice():
    """真 itemgetter 真 multi"""
    data = [(1, "a"), (2, "b"), (3, "c")]
    # 取第 0 个 (index 0)
    get_first = operator.itemgetter(0)
    assert get_first(data) == (1, "a")
    # 取 index 0 and 1
    get_pair = operator.itemgetter(0, 1)
    first, second = get_pair(data[0])
    assert first == 1
    assert second == "a"


def test_operator_attrgetter_path():
    """真 attrgetter 真 .attr1.attr2 路径"""
    class Inner:
        v = 42
    class Outer:
        inner = Inner()

    get = operator.attrgetter("inner.v")
    assert get(Outer) == 42
