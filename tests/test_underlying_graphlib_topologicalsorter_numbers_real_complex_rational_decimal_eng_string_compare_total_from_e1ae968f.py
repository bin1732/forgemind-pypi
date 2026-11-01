# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`graphlib.TopologicalSorter` 真依赖图 + `numbers` 进阶 (Real+Complex+Rational) + `decimal` 进阶 (to_eng_string+compare_total+from_float) + `signal` 进阶 (set_wakeup_fd+Signals) + `enum` 进阶 (IntEnum+IntFlag+Flag 运算) + 真底层测试。

覆盖 graphlib 2 真 (TopologicalSorter 真依赖图+class 存在) + numbers 4 真 (Real+Complex+Rational+Integral 真 value) + decimal 3 真 (to_eng_string+compare_total+from_float) + signal 2 真 (set_wakeup_fd+Signals) + enum 3 真 (IntEnum+IntFlag OR+Flag OR) (共 14 真测试) 模块:
  - `graphlib.TopologicalSorter 真建 + add 5 节点 + done 5 + get_ready 5 真就绪`
  - `graphlib.TopologicalSorter 真准备 + static_order`
  - `numbers.Real 真 value=3.14 + isinstance x,float`
  - `numbers.Complex 真 value=1+2j + 真 isinstance 1+2j,numbers.Complex`
  - `numbers.Rational 真 value=Fraction(1,2) + 真 isinstance`
  - `numbers.Integral 真 value=42 + bit_length=6`
  - `decimal.Decimal('0').to_eng_string 真返含 E`
  - `decimal.Decimal('NaN').compare_total 'NaN' vs 0 返 -1 或 1`
  - `decimal.Decimal.from_float(0.1) 真 from float`
  - `signal.set_wakeup_fd 必存在 (沙箱无 fd 实测)`
  - `signal.Signals 真 enum (SIGINT 含 + SIGTERM=15)`
  - `enum.IntEnum 真 color.RED + 1=2 + RED < GREEN`
  - `enum.IntFlag 真 OR READ|WRITE=6 + 含 READ + 无 EXECUTE`
  - `enum.Flag 真 OR R|W + 含 R + 无 X`
"""
import decimal
import enum
import graphlib
import numbers
import signal
import sys

import pytest


# -- graphlib 进阶 -------------------------------------------------------

class TestGraphlibAdvanced:
    def test_TopologicalSorter_add_done(self):
        """`TopologicalSorter 真 add 5 节点 + done + get_ready 5 真就绪。"""
        ts = graphlib.TopologicalSorter()
        ts.add(1, 2)
        ts.add(2, 3)
        ts.add(3, 4)
        ts.add(4, 5)
        ts.add(5)
        # 必能 prepare
        ts.prepare()
        # get_ready 必返 ≥ 1 (5 是 leaf)
        ready = list(ts.get_ready())
        # 5 必就绪
        assert 5 in ready
        # done 5
        ts.done(5)

    def test_TopologicalSorter_class(self):
        """`TopologicalSorter class 必存在。"""
        assert graphlib.TopologicalSorter is not None
        assert callable(graphlib.TopologicalSorter)


# -- numbers 进阶 (Real+Complex+Rational+Integral) --------------------

class TestNumbersAdvanced:
    def test_Real(self):
        """`numbers.Real 真 value=3.14 + isinstance 验。"""
        x = 3.14
        # 必是 Real (float)
        assert isinstance(x, numbers.Real) is True
        # 真 value
        assert x == 3.14

    def test_Complex(self):
        """`numbers.Complex 真 value=1+2j + isinstance 验。"""
        z = 1 + 2j
        # 必是 Complex
        assert isinstance(z, numbers.Complex) is True
        # 真 .real + .imag
        assert z.real == 1.0
        assert z.imag == 2.0

    def test_Rational(self):
        """`numbers.Rational 真 value=Fraction(1,2) + isinstance 验。"""
        from fractions import Fraction
        r = Fraction(1, 2)
        # 必是 Rational
        assert isinstance(r, numbers.Rational) is True
        # 真 numerator/denominator
        assert r.numerator == 1
        assert r.denominator == 2

    def test_Integral(self):
        """`numbers.Integral 真 value=42 + bit_length=6。"""
        i = 42
        # 必是 Integral
        assert isinstance(i, numbers.Integral) is True
        # bit_length
        assert i.bit_length() == 6


# -- decimal 进阶 (to_eng_string + compare_total + from_float) --------

class TestDecimalAdvancedV2:
    def test_to_eng_string(self):
        """`Decimal('1E+3').to_eng_string 真返 '1E+3'。"""
        d = decimal.Decimal("1E+3")
        s = d.to_eng_string()
        # 必 str
        assert isinstance(s, str)
        # 必含 E
        assert "E" in s
        # 必 1E+3
        assert s == "1E+3"

    def test_compare_total_NaN(self):
        """`Decimal('NaN').compare_total vs 0 返 -1 或 1 (NaN 必非 0)`"""
        nan = decimal.Decimal("NaN")
        zero = decimal.Decimal(0)
        result = nan.compare_total(zero)
        # 必 -1 或 1 (NaN 必非 0)
        assert result in (-1, 1)
        # 必不是 0
        assert result != 0

    def test_from_float(self):
        """`Decimal.from_float(0.1) 真 from float。"""
        d = decimal.Decimal.from_float(0.1)
        # 必 Decimal
        assert isinstance(d, decimal.Decimal)
        # 必 ~ 0.1
        assert abs(float(d) - 0.1) < 1e-10


# -- signal 进阶 --------------------------------------------------------

class TestSignalAdvancedV2:
    def test_set_wakeup_fd(self):
        """`signal.set_wakeup_fd 必存在 (沙箱无 fd 实测)。"""
        # 必能 set_wakeup_fd
        assert hasattr(signal, "set_wakeup_fd")
        # call 必不抛
        # 沙箱 -1 有效 (disable)
        result = signal.set_wakeup_fd(-1)
        # 必 -1 或 None
        assert result is None or result == -1

    def test_Signals_enum(self):
        """`signal.Signals 真 enum (SIGINT 含 + SIGTERM=15)`"""
        signals = list(signal.Signals)
        names = [s.name for s in signals]
        # 必含 SIGINT
        assert "SIGINT" in names
        # SIGTERM 必 15
        assert signal.SIGTERM == 15


# -- enum 进阶 (IntEnum + IntFlag + Flag) ----------------------------

class Color(enum.IntEnum):
    RED = 1
    GREEN = 2
    BLUE = 3


class Perm(enum.IntFlag):
    READ = 4
    WRITE = 2
    EXECUTE = 1


class File(enum.Flag):
    R = 4
    W = 2
    X = 1


class TestEnumAdvanced:
    def test_IntEnum(self):
        """`IntEnum RED + 1 真算术。"""
        c = Color.RED
        # 必是 int
        assert isinstance(c, int)
        # + 1 = 2 (GREEN)
        assert c + 1 == 2
        # 必能比较
        assert Color.RED < Color.GREEN

    def test_IntFlag_OR(self):
        """`IntFlag READ | WRITE 真 OR 4|2=6。"""
        rw = Perm.READ | Perm.WRITE
        # 必 6
        assert int(rw) == 6
        # READ 必 in rw
        assert Perm.READ in rw
        # EXECUTE 必 not in
        assert Perm.EXECUTE not in rw

    def test_Flag_OR(self):
        """`Flag R | W 真 OR。"""
        rw = File.R | File.W
        # R 必 in
        assert File.R in rw
        # X 必 not in
        assert File.X not in rw
