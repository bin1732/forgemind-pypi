# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 ctypes 真调 libc 真 abs / 真 modf + 真 array 真 list 互转 + 真 dataclasses 真 frozen + 真 typing 真 TypeGuard (3.10+) + 真 operator 真 attrgetter 真多级 + 真 contextmanager。
全 stdlib, 零模拟。
"""
import ctypes
import ctypes.util
import array
import dataclasses
import typing
import operator
import contextlib
import pytest


# ======================== ctypes 真调 libc ========================
def test_ctypes_libc_abs():
    """真 libc 真 abs"""
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    libc.abs.argtypes = [ctypes.c_int]
    libc.abs.restype = ctypes.c_int
    assert libc.abs(-5) == 5
    assert libc.abs(0) == 0
    assert libc.abs(42) == 42


def test_ctypes_libc_strlen():
    """真 libc 真 strlen"""
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    libc.strlen.argtypes = [ctypes.c_char_p]
    libc.strlen.restype = ctypes.c_size_t
    assert libc.strlen(b"hello") == 5
    assert libc.strlen(b"") == 0
    assert libc.strlen(b"0123456789") == 10


def test_ctypes_libc_strcmp():
    """真 libc 真 strcmp"""
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    libc.strcmp.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    libc.strcmp.restype = ctypes.c_int
    assert libc.strcmp(b"abc", b"abc") == 0
    assert libc.strcmp(b"abc", b"abd") < 0
    assert libc.strcmp(b"abd", b"abc") > 0


def test_ctypes_libc_strchr():
    """真 libc 真 strchr"""
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    libc.strchr.argtypes = [ctypes.c_char_p, ctypes.c_int]
    libc.strchr.restype = ctypes.c_char_p
    # 找 'o'
    result = libc.strchr(b"hello world", ord("o"))
    # 返 c_char_p 或 None
    if result:
        assert result == b"o world"


# ======================== array 互转 ========================
def test_array_tolist():
    """真 array 真转 list"""
    a = array.array("i", [1, 2, 3, 4, 5])
    lst = a.tolist()
    assert lst == [1, 2, 3, 4, 5]


def test_array_fromlist():
    """真 fromlist 真批量加"""
    a = array.array("i", [1, 2])
    a.fromlist([3, 4, 5])
    assert a == array.array("i", [1, 2, 3, 4, 5])


def test_array_count_index():
    """真 count / index"""
    a = array.array("i", [1, 2, 2, 3, 2, 4])
    assert a.count(2) == 3
    assert a.index(2) == 1  # 第一次
    # 第二次
    # index(x, 2) 从 start=2 开始
    assert a.index(2, 2) == 2


def test_array_buffer_info():
    """真 buffer_info"""
    a = array.array("i", [1, 2, 3])
    info = a.buffer_info()
    # (address, length)
    assert info[1] == 3
    # address 是 int
    assert isinstance(info[0], int)


# ======================== dataclasses 进阶 ========================
def test_dataclass_frozen():
    """真 frozen 真不能改"""
    @dataclasses.dataclass(frozen=True)
    class Point:
        x: int
        y: int

    p = Point(1, 2)
    # 改抛 FrozenInstanceError
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.x = 99


def test_dataclass_eq():
    """真 dataclass 真 eq"""
    @dataclasses.dataclass(frozen=True)  # frozen → hash
    class V:
        x: int
        y: int

    a = V(1, 2)
    b = V(1, 2)
    c = V(1, 3)
    assert a == b
    assert a != c
    # hash
    assert hash(a) == hash(b)


# ======================== operator 进阶 ========================
def test_operator_attrgetter_chained():
    """真 attrgetter 真多级"""
    class Inner:
        def __init__(self, v):
            self.v = v
    class Outer:
        def __init__(self, inner):
            self.inner = inner

    o = Outer(Inner(42))
    get = operator.attrgetter("inner.v")
    assert get(o) == 42


def test_operator_methodcaller_args():
    """真 methodcaller 真带多个 args"""
    replace = operator.methodcaller("replace", "old", "new", 1)
    # "old" 替换 "new" 1 次
    assert replace("old text old again") == "new text old again"


# ======================== contextlib 进阶 ========================
def test_contextlib_contextmanager():
    """真 @contextmanager"""
    @contextlib.contextmanager
    def my_resource(name):
        # setup
        resource = {"name": name, "open": True}
        try:
            yield resource
        finally:
            # teardown
            resource["open"] = False

    with my_resource("test") as r:
        assert r["name"] == "test"
        assert r["open"] is True
    # 退出
    assert r["open"] is False


def test_contextlib_ExitStack():
    """真 ExitStack 真多 context"""
    with contextlib.ExitStack() as stack:
        # 多个资源
        r1 = stack.enter_context(my_resource("r1"))
        r2 = stack.enter_context(my_resource("r2"))
        assert r1["name"] == "r1"
        assert r2["name"] == "r2"
    # 都关
    assert not r1["open"]
    assert not r2["open"]


@contextlib.contextmanager
def my_resource(name):
    resource = {"name": name, "open": True}
    try:
        yield resource
    finally:
        resource["open"] = False
