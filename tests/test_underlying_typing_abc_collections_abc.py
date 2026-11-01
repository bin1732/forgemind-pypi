# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 abc 真 ABCMeta 抽象基类 + 真 collections.abc 真 mapping/mutablemapping + 真 typing 进阶 (cast/overload) + 真 io 进阶 (BytesIO/StringIO 真 seek/tell) + 真 contextlib。
全 stdlib, 零模拟。
"""
import abc
import collections.abc
import typing
import io
import contextlib
import pytest


# ======================== abc ========================
def test_abc_ABCMeta_subclass():
    """真 ABCMeta 真抽象基类"""
    class MyABC(metaclass=abc.ABCMeta):
        @abc.abstractmethod
        def my_method(self):
            pass

    # 实例化抛 TypeError
    with pytest.raises(TypeError):
        MyABC()


def test_abc_abstract_method_register():
    """真 register 绕过抽象"""
    class MyABC(metaclass=abc.ABCMeta):
        @abc.abstractmethod
        def my_method(self):
            pass

    class MyImpl:
        def my_method(self):
            return 42

    MyABC.register(MyImpl)
    # 现在 isinstance 算
    assert isinstance(MyImpl(), MyABC)


def test_abc_concrete_subclass():
    """真 concrete subclass 真可实例化"""
    class MyABC(metaclass=abc.ABCMeta):
        @abc.abstractmethod
        def my_method(self):
            pass

    class MyImpl(MyABC):
        def my_method(self):
            return "concrete"

    obj = MyImpl()
    assert obj.my_method() == "concrete"


# ======================== collections.abc ========================
def test_collections_abc_Mapping():
    """真 Mapping 真 ABC"""
    # dict 是 Mapping
    d = {"a": 1, "b": 2}
    assert isinstance(d, collections.abc.Mapping)
    # custom Mapping
    class MyMap(collections.abc.Mapping):
        def __init__(self):
            self._d = {"x": 1}
        def __getitem__(self, k):
            return self._d[k]
        def __iter__(self):
            return iter(self._d)
        def __len__(self):
            return len(self._d)
    m = MyMap()
    assert isinstance(m, collections.abc.Mapping)
    assert m["x"] == 1


def test_collections_abc_Sized():
    """真 Sized"""
    assert isinstance([1, 2, 3], collections.abc.Sized)
    assert isinstance("hello", collections.abc.Sized)
    assert isinstance({"a": 1}, collections.abc.Sized)


def test_collections_abc_Iterable():
    """真 Iterable"""
    assert isinstance([1, 2], collections.abc.Iterable)
    assert isinstance(range(10), collections.abc.Iterable)
    # 5 不是 Iterable
    assert not isinstance(5, collections.abc.Iterable)


def test_collections_abc_Hashable():
    """真 Hashable"""
    assert isinstance("hello", collections.abc.Hashable)
    assert isinstance((1, 2, 3), collections.abc.Hashable)
    # list 不是 hashable
    assert not isinstance([1, 2], collections.abc.Hashable)


# ======================== typing 进阶 ========================
def test_typing_cast():
    """真 cast"""
    x = typing.cast(typing.Any, "hello")
    # 仍是 str
    assert isinstance(x, str)
    assert x == "hello"


def test_typing_overload():
    """真 @overload 真存在"""
    @typing.overload
    def process(x: int) -> int: ...
    @typing.overload
    def process(x: str) -> str: ...
    def process(x):
        if isinstance(x, int):
            return x * 2
        return x.upper()
    assert process(5) == 10
    assert process("hi") == "HI"


def test_typing_type_checking():
    """真 TYPE_CHECKING 运行时 False"""
    assert typing.TYPE_CHECKING is False


def test_typing_get_args():
    """真 get_args 真提取 type args"""
    T = typing.Optional[typing.List[int]]
    args = typing.get_args(T)
    # 嵌套
    assert int in args or any(int in typing.get_args(a) for a in args if hasattr(typing, "get_args"))


# ======================== io 进阶 ========================
def test_io_BytesIO_seek_tell():
    """真 BytesIO 真 seek/tell"""
    buf = io.BytesIO(b"Hello, World!")
    assert buf.tell() == 0
    # seek
    buf.seek(7)
    assert buf.tell() == 7
    # read
    assert buf.read() == b"World!"
    # seek 回
    buf.seek(0)
    assert buf.read() == b"Hello, World!"


def test_io_StringIO():
    """真 StringIO"""
    s = io.StringIO()
    s.write("line 1\n")
    s.write("line 2\n")
    s.seek(0)
    assert s.read() == "line 1\nline 2\n"


def test_io_getvalue():
    """真 getvalue"""
    buf = io.BytesIO()
    buf.write(b"data")
    # 不用 seek
    assert buf.getvalue() == b"data"


# ======================== contextlib ========================
def test_contextlib_suppress():
    """真 contextlib.suppress"""
    with contextlib.suppress(FileNotFoundError):
        open("/nonexistent_xyz_abc")
    # 不抛 = 通过


def test_contextlib_redirect_stdout():
    """真 redirect_stdout"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print("captured")
    assert "captured" in buf.getvalue()


def test_contextlib_closing():
    """真 closing 真 close"""
    class Resource:
        def __init__(self):
            self.closed = False
        def close(self):
            self.closed = True

    r = Resource()
    with contextlib.closing(r) as res:
        assert res is r
        assert not res.closed
    # 退出后 close
    assert r.closed
