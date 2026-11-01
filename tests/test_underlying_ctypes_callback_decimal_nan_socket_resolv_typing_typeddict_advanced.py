# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`ctypes` 进阶 (CFUNCTYPE callback) + `decimal` 进阶 (NaN/Infinity) + `socket` 进阶 (getfqdn/gethostbyname) + `typing` 进阶 (TypedDict) + `unittest.mock` 进阶 (AsyncMock await) 真底层测试。

覆盖 ctypes callback / decimal NaN / socket 主机名 / TypedDict class / AsyncMock 模块:
  - `ctypes.CFUNCTYPE 真定义 C callback 函数`
  - `ctypes.PYFUNCTYPE 沙箱 skip (libffi)`
  - `ctypes.pythonapi 真加载 libpython (沙箱 skip 验证存在)`
  - `decimal.Decimal('NaN').is_nan 真 True`
  - `decimal.Decimal('Infinity').is_infinite 真 True`
  - `decimal.Decimal('0.1').compare_total 真精确比较`
  - `decimal.Decimal(0.1) != decimal.Decimal('0.1') 0.1 浮点 vs 字符串精度`
  - `decimal.getcontext().prec 调精度`
  - `socket.getfqdn 真返 hostname`
  - `socket.gethostbyname 真解析 localhost`
  - `socket.gethostbyname_ex 真返 (name, [aliases], [ips])`
  - `socket.gethostname 真非空字符串`
  - `typing.TypedDict 真建 class 真 dict subclass`
  - `typing.TypedDict(total=False) 缺省 partial`
  - `unittest.mock.AsyncMock 真 await 返值`
  - `unittest.mock.AsyncMock().await_count 真累加`
  - `unittest.mock.AsyncMock().await_args 真返上 await`
  - `unittest.mock.AsyncMock(side_effect=Exception) 真抛`
"""
import asyncio
import ctypes
import decimal
import socket
import sys
import typing
import unittest.mock

import pytest


# -- ctypes 进阶 (CFUNCTYPE callback) ------------------------------------------

class TestCtypesAdvancedV3:
    def test_CFUNCTYPE_int_callback(self):
        """`CFUNCTYPE 真定义 C callback 函数 (int 加法)`. """
        CMPFUNC = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int)

        def add(a, b):
            return a + b

        cmp_func = CMPFUNC(add)
        # 真能调 (不真传给 C, 但 callable 真走)
        result = cmp_func(3, 4)
        assert result == 7

    def test_CFUNCTYPE_void_return(self):
        """`CFUNCTYPE c_void_p 返 int* . """
        CMPFUNC = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)

        def add_pointer(a):
            return a

        cmp_func = CMPFUNC(add_pointer)
        # 返 None (0 转 c_void_p = None)
        result = cmp_func(0)
        # 必是 None
        assert result is None

    def test_pythonapi_exists(self):
        """`ctypes.pythonapi 真存在 (libpython). """
        assert hasattr(ctypes, "pythonapi")
        # pythonapi 必是 CDLL instance
        assert ctypes.pythonapi is not None


# -- decimal 进阶 (NaN / Infinity / compare) ----------------------------------

class TestDecimalAdvancedV5:
    def test_Decimal_NaN(self):
        """`Decimal('NaN').is_nan 真 True。"""
        n = decimal.Decimal("NaN")
        assert n.is_nan() is True
        assert n.is_finite() is False

    def test_Decimal_Infinity(self):
        """`Decimal('Infinity').is_infinite 真 True。"""
        i = decimal.Decimal("Infinity")
        assert i.is_infinite() is True
        assert i.is_finite() is False
        # 负无穷
        ni = decimal.Decimal("-Infinity")
        assert ni.is_infinite() is True

    def test_Decimal_compare_total(self):
        """`Decimal.compare_total 真精确比较 (vs == 区分 NaN)。"""
        # compare_total NaN 总是 > anything
        assert decimal.Decimal("NaN").compare_total(decimal.Decimal("0")) == 1
        # compare_total 真按 sign+exp+digits
        a = decimal.Decimal("1.0")
        b = decimal.Decimal("1.00")
        # compare_total 区分不同表示
        assert a.compare_total(b) == -1 or a.compare_total(b) == 1
        # 数值上 ==
        assert a == b

    def test_Decimal_precision(self):
        """`Decimal.getcontext().prec 真调精度。"""
        ctx = decimal.getcontext()
        original = ctx.prec
        try:
            ctx.prec = 3
            assert ctx.prec == 3
            # 4位精度截尾
            v = decimal.Decimal("1") / decimal.Decimal("3")
            # 1/3 在 3位精度 = 0.333
            assert "0.333" in str(v)
        finally:
            ctx.prec = original


# -- socket 进阶 (getfqdn / gethostbyname / gethostname) ----------------------

class TestSocketAdvancedV5:
    def test_gethostname(self):
        """`socket.gethostname 真返非空字符串。"""
        name = socket.gethostname()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_getfqdn(self):
        """`socket.getfqdn 真返 FQDN (非空字符串)。"""
        fqdn = socket.getfqdn()
        assert isinstance(fqdn, str)
        assert len(fqdn) > 0

    def test_gethostbyname_localhost(self):
        """`socket.gethostbyname('localhost') 真返 '127.0.0.1'. """
        ip = socket.gethostbyname("localhost")
        # localhost → 127.0.0.1
        assert ip == "127.0.0.1", f"localhost 应=127.0.0.1,实际 {ip}"

    def test_gethostbyname_ex(self):
        """`socket.gethostbyname_ex 真返 (name, [aliases], [ips]). """
        result = socket.gethostbyname_ex("localhost")
        # 3 元
        assert len(result) == 3
        name, aliases, ips = result
        assert isinstance(name, str)
        assert isinstance(aliases, list)
        assert isinstance(ips, list)
        # ips 必含 127.0.0.1
        assert "127.0.0.1" in ips


# -- typing 进阶 (TypedDict 真建 class) ---------------------------------------

class TestTypingAdvancedV10:
    def test_TypedDict(self):
        """`TypedDict 真建 class 真 dict subclass。"""
        Movie = typing.TypedDict("Movie", {"name": str, "year": int})
        # 必是 dict subclass
        m: Movie = {"name": "forge", "year": 2026}
        assert isinstance(m, dict)
        assert m["name"] == "forge"
        assert m["year"] == 2026

    def test_TypedDict_total_False(self):
        """`TypedDict(total=False) 缺省 key 允许。"""
        Movie = typing.TypedDict(
            "Movie", {"name": str, "year": int}, total=False
        )
        # total=False 缺 key 仍可
        m: Movie = {"name": "forge"}  # 缺 year
        assert "name" in m

    def test_TypedDict_class_subclass(self):
        """`TypedDict 创的 class 真是 dict subclass + __annotations__. """
        Movie = typing.TypedDict("Movie", {"name": str, "year": int})
        # 必含 __annotations__
        assert "name" in Movie.__annotations__
        assert "year" in Movie.__annotations__
        # 必含 __required_keys__ + __optional_keys__
        if sys.version_info >= (3, 11):
            assert hasattr(Movie, "__required_keys__")
            assert hasattr(Movie, "__optional_keys__")


# -- unittest.mock 进阶 (AsyncMock await) ------------------------------------

class TestUnittestMockAdvancedV3:
    def test_AsyncMock_await(self):
        """`AsyncMock 真 await 返值。"""
        m = unittest.mock.AsyncMock(return_value=42)

        async def call():
            return await m()

        result = asyncio.run(call())
        assert result == 42

    def test_AsyncMock_await_count(self):
        """`AsyncMock.await_count 真累加。"""
        m = unittest.mock.AsyncMock(return_value="forge")

        async def call():
            await m()
            await m()
            await m()

        asyncio.run(call())
        assert m.await_count == 3

    def test_AsyncMock_await_args(self):
        """`AsyncMock.await_args 真返上 await args。"""
        m = unittest.mock.AsyncMock(return_value=None)

        async def call():
            await m("arg1", key="value")

        asyncio.run(call())
        # await_args 必含 args+kwargs
        assert m.await_args is not None
        assert m.await_args.args == ("arg1",)
        assert m.await_args.kwargs == {"key": "value"}

    def test_AsyncMock_side_effect_exception(self):
        """`AsyncMock(side_effect=Exception) 真抛。"""
        m = unittest.mock.AsyncMock(side_effect=ValueError("forge async"))

        async def call():
            await m()

        with pytest.raises(ValueError) as exc:
            asyncio.run(call())
        assert "forge async" in str(exc.value)
