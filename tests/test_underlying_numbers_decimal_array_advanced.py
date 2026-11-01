# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 numbers 真 ABC 进阶 (Number 真抽象) + 真 decimal 真 context manager 嵌套 + 真 array 真 signed int 边界 (INT_MIN/INT_MAX) + 真 pathlib 真 file 真读写 + 真 inspect 真 signature 真返回类型。
全 stdlib, 零模拟。
"""
import numbers
import decimal
import array
import pathlib
import inspect
import ctypes
import os
import tempfile
import pytest


# ======================== numbers 进阶 ========================
def test_numbers_ABC_Number():
    """真 Number 真抽象"""
    # Number 是最顶 ABC
    assert isinstance(1, numbers.Number)
    assert isinstance(1.5, numbers.Number)
    assert isinstance(1 + 2j, numbers.Number)
    assert isinstance(decimal.Decimal("1.5"), numbers.Number)
    assert isinstance(2j, numbers.Number)
    # 字符串 不是
    assert not isinstance("hello", numbers.Number)


def test_numbers_Complex_methods():
    """真 Complex 真 method"""
    # __abs__ / __conjugate__ / __complex__
    z = 3 + 4j
    assert z.__abs__() == 5
    assert z.conjugate() == 3 - 4j
    assert complex(z) == z


def test_numbers_Rational_fraction():
    """真 Rational 实际"""
    from fractions import Fraction
    # int 是 Rational
    assert isinstance(42, numbers.Rational)
    # Fraction 是
    assert isinstance(Fraction(1, 3), numbers.Rational)
    # float 不是
    assert not isinstance(3.14, numbers.Rational)
    # Decimal 不是 Rational (不同)
    assert not isinstance(decimal.Decimal("3.14"), numbers.Rational)


def test_numbers_Real_int_float():
    """真 Real"""
    assert isinstance(1, numbers.Real)
    assert isinstance(1.5, numbers.Real)
    # Fraction 是
    from fractions import Fraction
    assert isinstance(Fraction(1, 2), numbers.Real)
    # Decimal 不是 Real (单独类)


# ======================== decimal 进阶 ========================
def test_decimal_nested_localcontext():
    """真 nested localcontext 真嵌套"""
    with decimal.localcontext() as ctx1:
        ctx1.prec = 10
        with decimal.localcontext() as ctx2:
            ctx2.prec = 3
            # 内部 3 位
            assert ctx2.prec == 3
            # 外层 10 位
            assert ctx1.prec == 10
        # 退出内
        assert ctx1.prec == 10


def test_decimal_to_integral_value():
    """真 to_integral_value"""
    with decimal.localcontext() as ctx:
        ctx.prec = 10
        d = decimal.Decimal("3.7")
        # 舍到 int (不同 rounding)
        ctx.rounding = decimal.ROUND_DOWN
        assert d.to_integral_value() == 3
        ctx.rounding = decimal.ROUND_UP
        assert d.to_integral_value() == 4


def test_decimal_comparison_lt_gt():
    """真 Decimal 真比较"""
    a = decimal.Decimal("1.5")
    b = decimal.Decimal("2.5")
    c = decimal.Decimal("1.5")
    assert a < b
    assert b > a
    assert a == c
    # 用 cmp (3.11+ deprecated)
    # 用 compare
    assert a.compare(b) < 0
    assert b.compare(a) > 0
    assert a.compare(c) == 0


def test_decimal_normalize():
    """真 normalize 真去 trailing zeros"""
    d = decimal.Decimal("1.50000")
    # normalize
    n = d.normalize()
    # 1.5
    assert n == decimal.Decimal("1.5")
    # 但仍 5 sig figs
    assert str(n) == "1.5"


# ======================== array signed int 边界 ========================
def test_array_signed_int_max():
    """真 signed int 真 max/min"""
    # 2^31 - 1 / -2^31
    a = array.array("i", [2**31 - 1, -(2**31)])
    assert a[0] == 2147483647
    assert a[1] == -2147483648


def test_array_unsigned_int_max():
    """真 unsigned int 真 max"""
    # 2^32 - 1
    a = array.array("I", [2**32 - 1])
    assert a[0] == 4294967295
    # 0 必 OK
    a.append(0)
    assert a[1] == 0


def test_array_short_max():
    """真 short (16-bit) 真 max"""
    a = array.array("h", [32767])  # max signed short
    assert a[0] == 32767
    a.append(-32768)  # min
    assert a[1] == -32768


def test_array_oversize_overflow():
    """真 overflow 真值"""
    # 'b' (signed char) -128..127
    a = array.array("b", [127])
    # 128 超出 → 抛 OverflowError
    with pytest.raises(OverflowError):
        a.append(128)


# ======================== pathlib 真 file ========================
def test_pathlib_read_text():
    """真 read_text / write_text"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        path = f.name
    try:
        p = pathlib.Path(path)
        # write
        p.write_text("hello pathlib\nline 2")
        # read
        assert p.read_text() == "hello pathlib\nline 2"
    finally:
        os.unlink(path)


def test_pathlib_read_bytes():
    """真 read_bytes / write_bytes"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        path = f.name
    try:
        p = pathlib.Path(path)
        # write
        p.write_bytes(b"\x00\xff\x10\x80binary")
        # read
        assert p.read_bytes() == b"\x00\xff\x10\x80binary"
    finally:
        os.unlink(path)


def test_pathlib_touch_exists():
    """真 touch 真建"""
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "new_file.txt"
        # 不存在
        assert not p.exists()
        # touch
        p.touch()
        assert p.exists()
        # touch exist_ok=True
        p.touch(exist_ok=True)


# ======================== inspect 真 signature ========================
def test_inspect_signature_return_annotation():
    """真 signature 真返 annotation"""
    def f(x: int) -> str:
        return str(x)

    sig = inspect.signature(f)
    assert sig.return_annotation is str
    assert sig.parameters["x"].annotation is int


def test_inspect_signature_bind():
    """真 signature.bind 真绑定"""
    def f(a, b, c=10):
        return a + b + c

    sig = inspect.signature(f)
    bound = sig.bind(1, 2)
    bound.apply_defaults()
    # bound.arguments
    assert bound.arguments["a"] == 1
    assert bound.arguments["b"] == 2
    assert bound.arguments["c"] == 10
