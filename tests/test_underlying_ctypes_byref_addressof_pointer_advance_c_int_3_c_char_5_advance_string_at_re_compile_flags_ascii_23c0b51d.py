# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`ctypes.byref/addressof/pointer` 进阶 (真 c_int 链) + `ctypes.c_int*3` 真数组 + `ctypes.c_char*5` 真 + `ctypes.string_at` 真用 + `re 进阶 (compile flags re.A ASCII)` + `string.capwords 进阶` + `string.ascii_letters 进阶` + 真底层测试。

覆盖 ctypes 5 真 (byref 真+addressof 真+pointer 真+c_int*3 真数组+c_char*5 真) + re 1 真 (compile flags re.A ASCII) + string 2 真 (capwords 进阶+ascii_letters 进阶) (共 8 真测试) 模块:
  - `ctypes.byref 真 c_int(42) -> byref 必非 c`
  - `ctypes.addressof 真 c_int(42) -> int > 0`
  - `ctypes.pointer 真 c_int(42) -> POINTER + contents.value = 42`
  - `ctypes.c_int*3 [1,2,3] 必 array[0]=1+array[2]=3`
  - `ctypes.c_char*5 'forge' 真 round-trip 5 bytes`
  - `ctypes.string_at(c_char_p 'forge') 必 b'forge'`
  - `re.compile r'\\d+' flags=re.A 必 Pattern + ASCII 真 match '123'`
  - `string.capwords 'forge the third' 必 'Forge The Third'`
"""
import ctypes
import re
import string
import sys

import pytest


# -- ctypes 进阶 (byref + addressof + pointer + c_int*3 + c_char*5) -

class TestCtypesAdvancedV6:
    def test_byref(self):
        """`ctypes.byref 真 c_int(42) -> byref。"""
        c = ctypes.c_int(42)
        # byref
        ref = ctypes.byref(c)
        # 必非 None
        assert ref is not None
        # 必非 c (different obj)
        assert ref is not c

    def test_addressof(self):
        """`ctypes.addressof 真 c_int(42) -> int > 0。"""
        c = ctypes.c_int(42)
        # addressof
        addr = ctypes.addressof(c)
        # 必 int
        assert isinstance(addr, int)
        # 必 > 0
        assert addr > 0

    def test_pointer(self):
        """`ctypes.pointer 真 c_int(42) -> POINTER + contents.value = 42。"""
        c = ctypes.c_int(42)
        # pointer
        p = ctypes.pointer(c)
        # 必 POINTER
        assert isinstance(p, ctypes.POINTER(ctypes.c_int))
        # contents.value 必 42
        assert p.contents.value == 42

    def test_c_int_3(self):
        """`ctypes.c_int*3 [1,2,3] 必 array[0]=1+array[2]=3。"""
        a = (ctypes.c_int * 3)(1, 2, 3)
        # 必能 index
        assert a[0] == 1
        assert a[2] == 3
        # 必 length 3
        assert len(a) == 3

    def test_c_char_5(self):
        """`ctypes.c_char*5 'forge' 真 round-trip 5 bytes。"""
        s = (ctypes.c_char * 5)()
        # assign
        s[:5] = b"forge"
        # 必 bytes
        assert bytes(s) == b"forge"

    def test_string_at(self):
        """`ctypes.string_at(c_char_p 'forge') 必 b'forge'。"""
        c = ctypes.c_char_p(b"forge")
        # string_at
        result = ctypes.string_at(c)
        # 必 b'forge'
        assert result == b"forge"


# -- re 进阶 (compile flags re.A ASCII) --------------------

class TestReAdvancedV4:
    def test_compile_flags_ascii(self):
        """`re.compile r'\\d+' flags=re.A 必 Pattern + ASCII 真 match。"""
        p = re.compile(r"\d+", flags=re.A)
        # 必 Pattern
        assert isinstance(p, re.Pattern)
        # match 'forge123'
        m = p.search("forge123")
        # 必能 find
        assert m is not None
        # group 必 '123'
        assert m.group() == "123"


# -- string 进阶 (capwords + ascii_letters) ----------------

class TestStringAdvancedV2:
    def test_capwords(self):
        """`string.capwords 'forge the third' 必 'Forge The Third'。"""
        result = string.capwords("forge the third")
        # 必 'Forge The Third'
        assert result == "Forge The Third"

    def test_ascii_letters(self):
        """`string.ascii_letters 必 52 chars。"""
        letters = string.ascii_letters
        # 必 52
        assert len(letters) == 52
        # 必含 'a' + 'Z'
        assert "a" in letters
        assert "Z" in letters
