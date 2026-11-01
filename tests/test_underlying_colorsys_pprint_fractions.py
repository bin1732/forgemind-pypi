# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 colorsys (RGB/HSV 转换) + 真 pprint (pformat / PrettyPrinter) + 真 fractions (Fraction 真分数算) + 真 numbers (Complex / Real / Rational) + 真 dataclasses 进阶。
全 stdlib, 零模拟。
"""
import colorsys
import pprint
import fractions
import numbers
import dataclasses
import pytest


# ======================== colorsys ========================
def test_colorsys_rgb_to_hsv():
    """真 RGB → HSV"""
    # 纯红 (1, 0, 0) = HSV (0, 1, 1)
    h, s, v = colorsys.rgb_to_hsv(1, 0, 0)
    assert h == 0
    assert s == 1
    assert v == 1


def test_colorsys_hsv_to_rgb():
    """真 HSV → RGB"""
    r, g, b = colorsys.hsv_to_rgb(0, 1, 1)
    assert r == 1
    assert g == 0
    assert b == 0


def test_colorsys_roundtrip():
    """真 round-trip"""
    rgb = (0.5, 0.3, 0.7)
    h, s, v = colorsys.rgb_to_hsv(*rgb)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    assert abs(r - rgb[0]) < 1e-10
    assert abs(g - rgb[1]) < 1e-10
    assert abs(b - rgb[2]) < 1e-10


def test_colorsys_hls():
    """真 HLS 真转"""
    h, l, s = colorsys.rgb_to_hls(1, 1, 1)  # 白
    assert l == 1
    assert s == 0


def test_colorsys_yiq():
    """真 YIQ 真转"""
    y, i, q = colorsys.rgb_to_yiq(0, 0, 0)  # 黑
    assert y == 0
    assert i == 0
    assert q == 0


# ======================== pprint ========================
def test_pprint_basic():
    """真 pformat"""
    data = {"a": [1, 2, 3], "b": {"c": "long string value here"}}
    s = pprint.pformat(data)
    # 含 {a: [...]}
    assert "a" in s
    assert "long string" in s


def test_pprint_width():
    """真 width 真控制"""
    data = list(range(20))
    pp = pprint.PrettyPrinter(width=40)
    s = pp.pformat(data)
    # 多行 (width 限制)
    assert "\n" in s


def test_pprint_sort_dict():
    """真 sort_dicts"""
    data = {"b": 1, "a": 2, "c": 3}
    s = pprint.pformat(data, sort_dicts=True)
    # a 在 b 前
    assert s.index("'a'") < s.index("'b'")


def test_pprint_custom_class():
    """真自定义类"""
    class Box:
        def __repr__(self):
            return "<Box>"

    pp = pprint.PrettyPrinter()
    s = pp.pformat([Box(), Box()])
    assert "<Box>" in s


# ======================== fractions ========================
def test_fractions_basic():
    """真 Fraction 分数算"""
    a = fractions.Fraction(1, 3)
    b = fractions.Fraction(2, 3)
    s = a + b
    assert s == 1  # 3/3 = 1
    assert isinstance(s, fractions.Fraction)


def test_fractions_from_float():
    """真 Fraction 从 float 精确化"""
    f = fractions.Fraction(0.5)
    assert f == fractions.Fraction(1, 2)


def test_fractions_from_decimal():
    """真 Fraction 从 Decimal"""
    from decimal import Decimal
    f = fractions.Fraction(Decimal("0.25"))
    assert f == fractions.Fraction(1, 4)


def test_fractions_arithmetic():
    """真 Fractions 真算术"""
    a = fractions.Fraction(3, 4)
    b = fractions.Fraction(1, 2)
    # 加
    assert a + b == fractions.Fraction(5, 4)
    # 减
    assert a - b == fractions.Fraction(1, 4)
    # 乘
    assert a * b == fractions.Fraction(3, 8)
    # 除
    assert a / b == fractions.Fraction(3, 2)


def test_fractions_comparison():
    """真 Fraction 比较"""
    a = fractions.Fraction(1, 2)
    b = fractions.Fraction(2, 4)
    assert a == b  # 同值
    assert a <= b
    assert a >= b
    # 不同
    c = fractions.Fraction(1, 3)
    assert a > c
    assert c < a


# ======================== numbers ========================
def test_numbers_complex():
    """真 Complex 是 Complex"""
    assert isinstance(1 + 2j, numbers.Complex)
    # abs / conjugate
    c = 3 + 4j
    assert abs(c) == 5
    assert c.conjugate() == 3 - 4j


def test_numbers_real():
    """真 Real 是 Real"""
    assert isinstance(3.14, numbers.Real)
    assert isinstance(42, numbers.Real)
    # int 是 Real
    assert isinstance(1, numbers.Real)
    # complex 不是 Real
    assert not isinstance(1 + 0j, numbers.Real)


def test_numbers_rational():
    """真 Rational 是 Rational"""
    f = fractions.Fraction(1, 2)
    assert isinstance(f, numbers.Rational)
    assert isinstance(1, numbers.Rational)  # int 也是 Rational


def test_numbers_integral():
    """真 Integral 是 Integral"""
    assert isinstance(42, numbers.Integral)
    assert not isinstance(3.14, numbers.Integral)
    assert not isinstance(fractions.Fraction(1, 2), numbers.Integral)


# ======================== dataclasses 进阶 ========================
def test_dataclass_field_default_factory():
    """真 default_factory 真每实例新"""
    @dataclasses.dataclass
    class Box:
        items: list = dataclasses.field(default_factory=list)

    b1 = Box()
    b2 = Box()
    b1.items.append(1)
    # b2 不受 b1 影响
    assert b2.items == []


def test_dataclass_post_init():
    """真 __post_init__ 真跑"""
    @dataclasses.dataclass
    class Range:
        lo: int
        hi: int

        def __post_init__(self):
            if self.lo > self.hi:
                self.lo, self.hi = self.hi, self.lo

    r = Range(10, 1)
    # post_init 真交换
    assert r.lo == 1
    assert r.hi == 10


def test_dataclass_asdict():
    """真 asdict 真递归"""
    @dataclasses.dataclass
    class Point:
        x: int
        y: int

    @dataclasses.dataclass
    class Line:
        start: Point
        end: Point

    line = Line(Point(1, 2), Point(3, 4))
    d = dataclasses.asdict(line)
    assert d == {"start": {"x": 1, "y": 2}, "end": {"x": 3, "y": 4}}


def test_dataclass_replace():
    """真 replace 真新实例"""
    @dataclasses.dataclass(frozen=True)
    class Point:
        x: int
        y: int

    p1 = Point(1, 2)
    p2 = dataclasses.replace(p1, x=99)
    assert p1.x == 1
    assert p2.x == 99
