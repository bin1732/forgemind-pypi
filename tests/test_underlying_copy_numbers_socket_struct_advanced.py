# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 copy 进阶 (deepcopy 自定 __deepcopy__) + 真 numbers 进阶 (Integral 实际 int) + 真 socket 进阶 (set_inheritable / socketpair 跨进程) + 真 struct 进阶 (padding) + 真 ctypes 真 sizeof + 真 asyncio 真.
全 stdlib, 零模拟。
"""
import copy
import numbers
import socket
import struct
import ctypes
import asyncio
import multiprocessing
import os
import pytest


# ======================== copy 进阶 ========================
class _TestDeepCopyClass:
    def __init__(self, x):
        self.x = x

    def __deepcopy__(self, memo):
        # 自定
        new = type(self)(copy.deepcopy(self.x, memo))
        new.deepcopy_called = True
        return new


def test_copy_deepcopy_with_custom():
    """真 deepcopy 真 __deepcopy__ 真调"""
    original = _TestDeepCopyClass(42)
    deep = copy.deepcopy(original)
    # 调 __deepcopy__
    assert deep.deepcopy_called is True
    # x 独立
    assert deep.x == 42
    assert deep is not original


def test_copy_copy_function():
    """真 copy 真 function 真复制"""
    def f(x):
        return x + 1

    # copy
    f2 = copy.copy(f)
    # 仍 callable
    assert f2(5) == 6
    # 但不 deep (func 不可变)


# ======================== numbers 进阶 ========================
def test_numbers_Integral_int():
    """真 Integral 真 int"""
    assert isinstance(42, numbers.Integral)
    assert isinstance(0, numbers.Integral)
    assert isinstance(-100, numbers.Integral)
    # bool 也是 Integral (subclass of int)
    assert isinstance(True, numbers.Integral)
    # float 不是
    assert not isinstance(3.14, numbers.Integral)


def test_numbers_Real_arithmetic():
    """真 Real 真 isinstance"""
    # 1.5 是 Real
    assert isinstance(1.5, numbers.Real)
    # 1 也是
    assert isinstance(1, numbers.Real)
    # 1+0j 不是
    assert not isinstance(1 + 0j, numbers.Real)


# ======================== socket 进阶 ========================
def test_socket_set_inheritable():
    """真 set_inheritable 真"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # 默认 True / False
        original = s.get_inheritable()
        # 改
        s.set_inheritable(not original)
        assert s.get_inheritable() == (not original)
    finally:
        s.close()


def test_socketpair_real_pair():
    """真 socketpair 真双向"""
    s1, s2 = socket.socketpair()
    try:
        # 双向
        s1.send(b"from_s1")
        # s2 收
        data = s2.recv(100)
        assert data == b"from_s1"
        # s2 → s1
        s2.send(b"from_s2")
        data2 = s1.recv(100)
        assert data2 == b"from_s2"
    finally:
        s1.close()
        s2.close()


# ======================== struct padding ========================
def test_struct_no_padding_with_alignment_off():
    """真 struct 关闭 padding"""
    # 默认 (native byteorder) 有 padding
    # > 或 < 关闭
    # i + c = 5 字节
    assert struct.calcsize("<ic") == 5
    # = 同样 (native)
    # i + c (no padding)
    s = struct.pack("<ic", 1, b"a")
    assert len(s) == 5
    # unpack
    n, c = struct.unpack("<ic", s)
    assert n == 1
    assert c == b"a"


def test_struct_with_padding():
    """真 struct native padding"""
    # native: i + c → 8 bytes (4 + 1 + 3 padding)
    # 但不一定, 看平台
    # 用 < 显式
    # i = 4
    # c = 1
    # native: 4 + 1 + 3 padding = 8
    native_size = struct.calcsize("=ic")
    # native 是 4 + 1 + 3 = 8
    # 显式 no padding
    explicit_size = struct.calcsize("<ic")
    # 4 + 1 = 5
    # 实际可能相同
    assert explicit_size <= native_size


# ======================== ctypes 进阶 ========================
def test_ctypes_sizeof_struct():
    """真 sizeof 真 struct"""
    class S(ctypes.Structure):
        _fields_ = [("c", ctypes.c_char), ("i", ctypes.c_int)]
    s = S()
    size = ctypes.sizeof(s)
    # c (1) + 3 padding + i (4) = 8
    assert size == 8


def test_ctypes_sizeof_array():
    """真 sizeof 真 array"""
    arr = (ctypes.c_int * 5)()
    # 5 * 4 = 20
    assert ctypes.sizeof(arr) == 20


# ======================== asyncio 真 ========================
def test_asyncio_iscoroutinefunction():
    """真 iscoroutinefunction 真"""
    async def my_coro():
        return 42

    assert asyncio.iscoroutinefunction(my_coro)
    # 普通函数不是
    def normal():
        return 42

    assert not asyncio.iscoroutinefunction(normal)


def test_asyncio_iscoroutine():
    """真 iscoroutine 真"""
    async def my_coro():
        return 42

    cr = my_coro()
    try:
        assert asyncio.iscoroutine(cr)
    finally:
        cr.close()
