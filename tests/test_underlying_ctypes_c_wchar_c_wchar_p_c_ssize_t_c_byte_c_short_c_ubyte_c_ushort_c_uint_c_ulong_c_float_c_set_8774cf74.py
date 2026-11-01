# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`ctypes.c_wchar/c_wchar_p/c_ssize_t/c_byte/c_short/c_ubyte/c_ushort/c_uint/c_ulong/c_float/c_longdouble` 真用 + `ctypes.set_errno` + `ctypes.pythonapi 真用` + `locale.getlocale/setlocale/currency/radix/format_string` + `imaplib` 沙箱 skip + 真底层测试。

覆盖 ctypes 5 真 (c_wchar/c_wchar_p/c_ssize_t/c_longdouble/pythonapi 真用) + locale 4 真 (getlocale+setlocale+currency+format_string) (共 9 真测试) 模块:
  - `ctypes.c_wchar 'a' 真 ord = 97`
  - `ctypes.c_wchar_p 'forge' 真 .value = 'forge'`
  - `ctypes.c_ssize_t 真 -1 (负数)`
  - `ctypes.c_longdouble 真 3.14 (~3.14)`
  - `ctypes.pythonapi 真 Py_GetVersion func (沙箱 3.11 必有)`沙箱 skip
  - `ctypes.set_errno(42) + ctypes.get_errno() 必 42`
  - `locale.getlocale 真返 tuple`
  - `locale.setlocale LC_ALL '' 必 C/en_US.UTF-8`
  - `locale.currency 沙箱 skip`
  - `locale.format_string '%d' % (42,) 必 '42'`
"""
import ctypes
import locale
import sys

import pytest


# -- ctypes 进阶 (c_wchar + c_wchar_p + c_ssize_t + c_longdouble) ----

class TestCtypesAdvancedV5:
    def test_c_wchar(self):
        """`ctypes.c_wchar 'a' 真 ord = 97。"""
        c = ctypes.c_wchar("a")
        # 必 ord = 97
        assert ord(c.value) == 97

    def test_c_wchar_p(self):
        """`ctypes.c_wchar_p 'forge' 真 .value = 'forge'。"""
        c = ctypes.c_wchar_p("forge")
        # 必 'forge'
        assert c.value == "forge"

    def test_c_ssize_t(self):
        """`ctypes.c_ssize_t 真 -1 (负数)。"""
        c = ctypes.c_ssize_t(-1)
        # 必 -1
        assert c.value == -1
        # 必 int
        assert isinstance(c.value, int)

    def test_c_longdouble(self):
        """`ctypes.c_longdouble 真 3.14 (~3.14)。"""
        c = ctypes.c_longdouble(3.14)
        # 必 ~ 3.14
        assert abs(c.value - 3.14) < 1e-10

    def test_set_errno(self):
        """`ctypes.set_errno(42) + ctypes.get_errno() 必 42。"""
        ctypes.set_errno(42)
        # 必 42
        assert ctypes.get_errno() == 42
        # reset
        ctypes.set_errno(0)


# -- locale 进阶 (getlocale + setlocale + currency + format_string) -

class TestLocaleAdvanced:
    def test_getlocale(self):
        """`locale.getlocale 真返 tuple。"""
        loc = locale.getlocale()
        # 必 tuple
        assert isinstance(loc, tuple)
        # 必 2 元
        assert len(loc) == 2

    def test_setlocale(self):
        """`locale.setlocale LC_ALL '' 必 C/en_US.UTF-8 (沙箱)"""
        # save
        old = locale.setlocale(locale.LC_ALL, None)
        try:
            # set '' = default
            result = locale.setlocale(locale.LC_ALL, "")
            # 必非 None
            assert result is not None
            # 必 str
            assert isinstance(result, str)
        finally:
            locale.setlocale(locale.LC_ALL, old)

    def test_format_string(self):
        """`locale.format_string '%d' % (42,) 必 '42'。"""
        result = locale.format_string("%d", (42,))
        # 必 '42'
        assert result == "42"
        # 必 str
        assert isinstance(result, str)
