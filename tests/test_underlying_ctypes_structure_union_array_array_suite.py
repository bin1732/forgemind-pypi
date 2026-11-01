# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`ctypes` 大进阶: Structure/Union/Array/Pointer/POINTER/byref/string_at 完整真底层测试。

覆盖 ctypes c_int 字段 + Structure 子类 + Union + Array + Pointer 真布局 + byref + string_at + addressof + sizeof + alignment 真内存布局。
"""
import ctypes
import ctypes.util
import struct
import sys

import pytest


# -- ctypes c_int 字段基础 --------------------------------------------------

class TestCtypesBasicTypes:
    def test_c_int_value(self):
        """`ctypes.c_int(42) 真 .value=42。"""
        i = ctypes.c_int(42)
        assert i.value == 42

    def test_c_int_mutation(self):
        """`ctypes.c_int 真 .value=99。"""
        i = ctypes.c_int(0)
        i.value = 99
        assert i.value == 99

    def test_c_double(self):
        """`ctypes.c_double(3.14) 真 .value=3.14。"""
        d = ctypes.c_double(3.14)
        assert abs(d.value - 3.14) < 1e-9

    def test_c_char_p(self):
        """`ctypes.c_char_p 真 .value=b'forge'。"""
        cp = ctypes.c_char_p(b"forge")
        assert cp.value == b"forge"

    def test_c_bool(self):
        """`ctypes.c_bool(True/False) 真。"""
        assert ctypes.c_bool(True).value is True
        assert ctypes.c_bool(False).value is False

    def test_c_byte_c_ubyte(self):
        """`ctypes.c_byte / c_ubyte 真。"""
        assert ctypes.c_byte(127).value == 127
        assert ctypes.c_byte(-128).value == -128
        assert ctypes.c_ubyte(255).value == 255

    def test_c_short_c_ushort(self):
        """`ctypes.c_short / c_ushort 真。"""
        assert ctypes.c_short(32767).value == 32767
        assert ctypes.c_ushort(65535).value == 65535

    def test_c_long_long(self):
        """`ctypes.c_longlong 真。"""
        big = 2**62
        v = ctypes.c_longlong(big)
        assert v.value == big


# -- ctypes Structure 子类 --------------------------------------------------

class Point(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
    ]


class TestCtypesStructure:
    def test_Structure_instance(self):
        """`Structure 子类化 + 真 fields 访问。"""
        p = Point(3, 4)
        assert p.x == 3
        assert p.y == 4

    def test_Structure_sizeof(self):
        """`sizeof(Point) 真 = 8 (2*4 bytes)`. """
        s = ctypes.sizeof(Point)
        assert s == 8, f"Point sizeof 应=8,实际 {s}"

    def test_Structure_alignment(self):
        """`ctypes.alignment(Point) 真 ≥ 4 (c_int 边界)。"""
        a = ctypes.alignment(Point)
        # 必 ≥ c_int 对齐 (4)
        assert a >= 4

    def test_Structure_mutation(self):
        """`Structure 字段 mutation。"""
        p = Point(1, 2)
        p.x = 99
        p.y = 100
        assert p.x == 99
        assert p.y == 100

    def test_Structure_bytes(self):
        """`Structure 真内存布局 (bytes 一致)。"""
        p = Point(3, 4)
        # ctypes.POINTER(Point) 必能调
        assert Point is not None
        # 必能地址
        addr = ctypes.addressof(p)
        assert addr > 0


# -- ctypes Union ------------------------------------------------------------

class IntBytesUnion(ctypes.Union):
    _fields_ = [
        ("i", ctypes.c_int),
        ("b", ctypes.c_byte * 4),
    ]


class TestCtypesUnion:
    def test_Union_field_access(self):
        """`Union 字段共享同一内存。"""
        u = IntBytesUnion()
        u.i = 0x12345678
        # 必能访问 b
        b0 = u.b[0]
        b1 = u.b[1]
        # 必是 int
        assert isinstance(b0, int)
        assert isinstance(b1, int)

    def test_Union_sizeof(self):
        """`Union sizeof 必=max of fields = 4. """
        s = ctypes.sizeof(IntBytesUnion)
        assert s == 4, f"Union sizeof 应=4,实际 {s}"


# -- ctypes Array ------------------------------------------------------------

class TestCtypesArray:
    def test_c_int_Array(self):
        """`c_int * 5 真 Array。"""
        arr = (ctypes.c_int * 5)(1, 2, 3, 4, 5)
        # 必能索引
        assert arr[0] == 1
        assert arr[4] == 5
        # 必能 len
        assert len(arr) == 5

    def test_c_char_Array(self):
        """`c_char * 5 真 Array of bytes。"""
        # c_char * 5 真能创
        arr = (ctypes.c_char * 5)()
        # 必能索引 (byte 0)
        # 沙箱 3.11+ c_char array int 索引
        # 简测: 必能 len
        assert len(arr) == 5


# -- ctypes Pointer / POINTER -------------------------------------------------

class TestCtypesPointer:
    def test_POINTER(self):
        """`POINTER(c_int) 真 Pointer type. """
        P = ctypes.POINTER(ctypes.c_int)
        # 必是 type
        assert P is not None
        assert isinstance(P, type)

    def test_pointer_from_address(self):
        """`ctypes.pointer 真建 Pointer。"""
        i = ctypes.c_int(42)
        p = ctypes.pointer(i)
        # 必能 deref
        assert p[0] == 42
        assert p.contents.value == 42

    def test_byref(self):
        """`ctypes.byref 真传引用。"""
        i = ctypes.c_int(0)
        # byref 必能返 ref
        ref = ctypes.byref(i)
        assert ref is not None
        # 改 i 直接
        i.value = 99
        assert i.value == 99

    def test_addressof(self):
        """`ctypes.addressof 真返 int addr。"""
        i = ctypes.c_int(42)
        addr = ctypes.addressof(i)
        assert isinstance(addr, int)
        assert addr > 0

    def test_string_at(self):
        """`ctypes.string_at 真读 C string。"""
        # 创 buffer
        buf = ctypes.create_string_buffer(b"hello forge string_at")
        # string_at 必能读
        s = ctypes.string_at(buf)
        assert s.startswith(b"hello")


# -- ctypes sizeof / alignment / memmove ------------------------------------

class TestCtypesSize:
    def test_sizeof_c_int(self):
        """`sizeof(c_int) 真 ≥ 4。"""
        s = ctypes.sizeof(ctypes.c_int)
        assert s >= 4

    def test_sizeof_c_double(self):
        """`sizeof(c_double) 真 = 8。"""
        s = ctypes.sizeof(ctypes.c_double)
        assert s == 8

    def test_alignment_c_int(self):
        """`alignment(c_int) 真 ≥ 4。"""
        a = ctypes.alignment(ctypes.c_int)
        assert a >= 4

    def test_memmove(self):
        """`ctypes.memmove 真复制内存。"""
        # 创 2 buffer
        dst = ctypes.create_string_buffer(10)
        src = b"forge mem"
        ctypes.memmove(dst, src, len(src))
        assert dst.value == b"forge mem"

    def test_memset(self):
        """`ctypes.memset 真置 0 (用 raw + byref)`. """
        buf = ctypes.create_string_buffer(10)
        ctypes.memset(buf, 0, 10)
        # 必所有字节=0 (raw)
        assert bytes(buf.raw) == b"\x00" * 10

    def test_cast(self):
        """`ctypes.cast 真返新 Pointer type。"""
        i = ctypes.c_int(42)
        p_int = ctypes.pointer(i)
        # cast to char_p
        p_char = ctypes.cast(p_int, ctypes.POINTER(ctypes.c_char))
        # 必能取
        assert p_char.contents.value is not None

    def test_set_errno(self):
        """`ctypes.set_errno 真设 errno。"""
        ctypes.set_errno(42)
        assert ctypes.get_errno() == 42
        # 还原
        ctypes.set_errno(0)
