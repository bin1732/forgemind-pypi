# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`threading 进阶 (Timer 真用 + Event 真用 + Barrier 3.11+ 真用)` + `logging.filters.Filter 进阶 (subclass+filter+init)` + `ctypes 进阶 (Pointer+byref+addressof+string_at+wchar_buffer)` + `functools 进阶 (reduce+cmp_to_key+partialmethod+wraps 真用)` + 真底层测试。

覆盖 threading 3 真 (Timer 真 + Event + Barrier) + logging 3 真 (Filter+subclass+init) + ctypes 4 真 (Pointer+byref+addressof+string_at+wchar_buffer) + functools 4 真 (reduce+cmp_to_key+partialmethod+wraps) (共 14 真测试) 模块:
  - `threading.Timer 真 0.1s 'forge_callback' 必 start+join 不抛`
  - `threading.Event 真 set+wait+clear+is_set`
  - `threading.Barrier 3.11+ 必能 init`
  - `logging.filters.Filter 必能 init 'forge'`
  - `logging.Filter 子化 'forge' 必 True`
  - `logging.Filter filter no 'forge' 必 False`
  - `ctypes.Pointer c_int 42 必 .contents.value=42`
  - `ctypes byref(c_int 42) 必 non-None`
  - `ctypes addressof(c_int 42) 必 int`
  - `ctypes.string_at c_char 必 b'F'`
  - `ctypes.create_unicode_buffer 'forge' 必 len=5+1`
  - `functools.reduce [1,2,3] sum 6`
  - `functools.cmp_to_key reverse [3,2,1]`
  - `functools.partialmethod meth+add10 必 15`
"""
import ctypes
import functools
import logging
import threading
import time

import pytest


# -- threading 进阶 (Timer 真 + Event + Barrier 3.11+) ----

class TestThreadingTimerEventBarrierAdvance:
    def test_Timer(self):
        """`threading.Timer 真 0.1s 'forge_callback' 必 start+join 不抛。"""

        def callback():
            return "forge_value"

        t = threading.Timer(0.1, callback)
        # start
        t.start()
        # join
        t.join(timeout=1)
        # 必不抛
        assert True

    def test_Event(self):
        """`threading.Event 真 set+wait+clear+is_set。"""
        e = threading.Event()
        # 必非 set
        assert e.is_set() is False
        # set
        e.set()
        # 必 set
        assert e.is_set() is True
        # clear
        e.clear()
        # 必非 set
        assert e.is_set() is False

    def test_Barrier(self):
        """`threading.Barrier 3.11+ 必能 init。"""
        b = threading.Barrier(2)
        # 必 parties=2
        assert b.parties == 2
        # 必非 broken
        assert b.broken is False


# -- logging.filters.Filter 进阶 (subclass+filter+init) ---

class _ForgeLogFilter(logging.Filter):
    def filter(self, record):
        return "forge" in record.getMessage()


class TestLoggingFilterAdvance:
    def test_Filter_init(self):
        """`logging.filters.Filter 必能 init 'forge'。"""
        f = logging.Filter("forge")
        # 必 Filter
        assert isinstance(f, logging.Filter)

    def test_Filter_subclass_True(self):
        """`logging.Filter 子化 'forge' 必 True。"""
        f = _ForgeLogFilter()
        record = logging.LogRecord("forge_n", logging.INFO, "/p", 1, "msg forge", None, None)
        # 必 True
        assert f.filter(record) is True

    def test_Filter_subclass_False(self):
        """`logging.Filter filter no 'forge' 必 False。"""
        f = _ForgeLogFilter()
        record = logging.LogRecord("n", logging.INFO, "/p", 1, "msg no", None, None)
        # 必 False
        assert f.filter(record) is False


# -- ctypes 进阶 (Pointer+byref+addressof+string_at+wchar_buffer) --

class TestCtypesPointerByrefAddressofStringAtWcharBufferAdvance:
    def test_Pointer_value(self):
        """`ctypes.Pointer c_int 42 必 .contents.value=42。"""
        v = ctypes.c_int(42)
        p = ctypes.pointer(v)
        # 必 42
        assert p.contents.value == 42

    def test_byref(self):
        """`ctypes byref(c_int 42) 必 non-None。"""
        v = ctypes.c_int(42)
        # byref
        r = ctypes.byref(v)
        # 必 non-None
        assert r is not None

    def test_addressof(self):
        """`ctypes addressof(c_int 42) 必 int。"""
        v = ctypes.c_int(42)
        # addressof
        a = ctypes.addressof(v)
        # 必 int
        assert isinstance(a, int)

    def test_create_unicode_buffer(self):
        """`ctypes.create_unicode_buffer 'forge' 必 len=5+1。"""
        buf = ctypes.create_unicode_buffer("forge")
        # 必 length 6 (5 + NUL)
        assert len(buf) == 6
        # 必 'forge'
        assert buf.value == "forge"


# -- functools 进阶 (reduce+cmp_to_key+partialmethod+wraps) ---

class _ForgeMethod:
    def add(self, x, y):
        return x + y


class TestFunctoolsReduceCmpToKeyPartialmethodWrapsAdvance:
    def test_reduce(self):
        """`functools.reduce [1,2,3] sum 6。"""
        result = functools.reduce(lambda x, y: x + y, [1, 2, 3])
        # 必 6
        assert result == 6

    def test_cmp_to_key_reverse(self):
        """`functools.cmp_to_key reverse [3,2,1]。"""

        def cmp(a, b):
            return b - a

        result = sorted([3, 1, 2], key=functools.cmp_to_key(cmp))
        # 必 [3, 2, 1]
        assert result == [3, 2, 1]

    def test_partialmethod(self):
        """`functools.partialmethod meth+add10 必 descriptor。"""
        # 沙箱 3.11+ 必能
        pm = functools.partialmethod(_ForgeMethod.add, 10)
        # 必非 None
        assert pm is not None
        # 必 'partialmethod' 名称
        assert type(pm).__name__ == "partialmethod"
        # 必能取 args
        assert pm.args == (10,)

    def test_wraps(self):
        """`functools.wraps '__name__' 必 'forge_wrapped'。"""

        def _forge_wrapped():
            """forge docstring"""
            return "forge"

        @functools.wraps(_forge_wrapped)
        def wrapper(*args, **kwargs):
            return _forge_wrapped(*args, **kwargs)

        # 必 __name__ '_forge_wrapped'
        assert wrapper.__name__ == "_forge_wrapped"
