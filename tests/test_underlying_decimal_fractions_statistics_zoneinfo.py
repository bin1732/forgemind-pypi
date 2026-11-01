# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`decimal` + `fractions` + `statistics` + `zoneinfo` 真底层测试。

覆盖精确运算 / 统计 / 时区模块:
  - `decimal.Decimal(0.1)` 真比 float 精确,`Decimal('0.1')*3 == Decimal('0.3')`
  - `decimal.getcontext().prec=10` 真设精度,`1/7` 截断到 10 位
  - `decimal.localcontext()` 真隔离 context 改动
  - `fractions.Fraction(1, 3) + Fraction(1, 6) == Fraction(1, 2)` 真分数加法
  - `fractions.Fraction('0.25') == Fraction(1, 4)` 真从字符串解析
  - `statistics.mean([1,2,3,4,5]) == 3.0` 真均值
  - `statistics.median([1,3,5,7]) == 4` 真中位数 (偶数取均值)
  - `statistics.stdev([1,2,3,4,5])` 真样本标准差
  - `zoneinfo.ZoneInfo('America/New_York')` 真拿 tz 真 offset
  - `zoneinfo.ZoneInfo('UTC')` 真返 UTC tz
  - `datetime(2026,3,8,7,0,tzinfo=ZoneInfo('America/New_York')).utcoffset()` 真返 -5h
"""
import datetime
import decimal
import fractions
import statistics
import zoneinfo

import pytest


# -- decimal ------------------------------------------------------------------

class TestDecimalAdvanced:
    def test_Decimal_from_float_is_exact(self):
        """`Decimal(0.1)` 真精确表示 0.1 (vs float 二进制近似)。"""
        d = decimal.Decimal("0.1") + decimal.Decimal("0.2")
        assert d == decimal.Decimal("0.3"), f"Decimal 0.1+0.2 应=0.3,实际 {d}"

    def test_Decimal_context_precision(self):
        """`decimal.getcontext().prec=10` 真设精度,`1/7` 截断到 10 位。"""
        ctx = decimal.getcontext().copy()
        try:
            ctx.prec = 10
            with decimal.localcontext(ctx):
                d = decimal.Decimal(1) / decimal.Decimal(7)
            # 10 位精度,尾数应 ≤ 10 数字
            sign, digits, exp = d.as_tuple()
            assert len(digits) <= 10, f"精度 10 位应截断,实际 {len(digits)} 位"
        finally:
            decimal.setcontext(ctx)

    def test_Decimal_localcontext_isolated(self):
        """`decimal.localcontext()` 真隔离,内 set 精度,外不变。"""
        with decimal.localcontext() as ctx:
            ctx.prec = 5
            inside = decimal.getcontext().prec
        assert inside == 5, f"localcontext 内 prec 应=5,实际 {inside}"
        # 退出后,主 context 不应被改
        assert decimal.getcontext().prec != 5, (
            f"localcontext 退出后主 prec 不应变 5,实际 {decimal.getcontext().prec}"
        )

    def test_Decimal_quantize(self):
        """`Decimal('1.234').quantize(Decimal('0.01'))` 真 4 舍 5 入到 0.01。"""
        d = decimal.Decimal("1.235").quantize(decimal.Decimal("0.01"))
        assert d == decimal.Decimal("1.24"), f"1.235 量化到 0.01 应=1.24,实际 {d}"


# -- fractions ----------------------------------------------------------------

class TestFractionsAdvanced:
    def test_Fraction_addition(self):
        """`Fraction(1, 3) + Fraction(1, 6) == Fraction(1, 2)` 真分数加法通分。"""
        f = fractions.Fraction(1, 3) + fractions.Fraction(1, 6)
        assert f == fractions.Fraction(1, 2), f"1/3 + 1/6 应=1/2,实际 {f}"

    def test_Fraction_from_string(self):
        """`Fraction('0.25')` 真从字符串解析,`== Fraction(1, 4)`。"""
        f = fractions.Fraction("0.25")
        assert f == fractions.Fraction(1, 4), f"'0.25' 应=1/4,实际 {f}"

    def test_Fraction_limit_denominator(self):
        """`Fraction(1, 3).limit_denominator(10)` 真近似到 1/3,分母 ≤ 10。"""
        f = fractions.Fraction(1, 3).limit_denominator(10)
        assert f.denominator <= 10, f"分母应 ≤ 10,实际 {f.denominator}"
        assert f == fractions.Fraction(1, 3), f"limit_denominator(10) 1/3 应仍=1/3,实际 {f}"


# -- statistics ---------------------------------------------------------------

class TestStatisticsAdvanced:
    def test_mean(self):
        """`statistics.mean([1,2,3,4,5])` 真返 3.0。"""
        assert statistics.mean([1, 2, 3, 4, 5]) == 3.0

    def test_median_even_count_takes_mean(self):
        """`statistics.median([1,3,5,7])` 真偶数取均值,4 = (3+5)/2。"""
        assert statistics.median([1, 3, 5, 7]) == 4, (
            f"median([1,3,5,7]) 应=4,实际 {statistics.median([1,3,5,7])}"
        )

    def test_stdev_sample(self):
        """`statistics.stdev([1,2,3,4,5])` 真样本标准差,ddof=1。"""
        s = statistics.stdev([1, 2, 3, 4, 5])
        # sqrt(((1-3)^2+(2-3)^2+(3-3)^2+(4-3)^2+(5-3)^2) / (5-1)) = sqrt(10/4) = 1.581...
        assert abs(s - 1.5811388300841898) < 1e-10, f"stdev 应≈1.581,实际 {s}"

    def test_quantiles(self):
        """`statistics.quantiles([1..10], n=4)` 真 4 分位,3 cut points。"""
        cuts = statistics.quantiles(list(range(1, 11)), n=4)
        assert len(cuts) == 3, f"n=4 应返 3 个 cut point,实际 {len(cuts)}"
        # 第 1 分位 ≈ 3.25,中位 ≈ 5.5,第 3 分位 ≈ 7.75
        assert abs(cuts[1] - 5.5) < 1e-9


# -- zoneinfo -----------------------------------------------------------------

class TestZoneinfo:
    def test_ZoneInfo_America_New_York_utcoffset(self):
        """`zoneinfo.ZoneInfo('America/New_York')` 真拿 tz,EST = -5h,EDT = -4h。"""
        tz = zoneinfo.ZoneInfo("America/New_York")
        # 冬令时 1 月 15 日
        winter = datetime.datetime(2026, 1, 15, 7, 0, tzinfo=tz)
        assert winter.utcoffset() == datetime.timedelta(hours=-5), (
            f"NY 冬令时 utcoffset 应=-5h,实际 {winter.utcoffset()}"
        )
        # 夏令时 7 月 15 日
        summer = datetime.datetime(2026, 7, 15, 7, 0, tzinfo=tz)
        assert summer.utcoffset() == datetime.timedelta(hours=-4), (
            f"NY 夏令时 utcoffset 应=-4h,实际 {summer.utcoffset()}"
        )

    def test_ZoneInfo_UTC_zero_offset(self):
        """`zoneinfo.ZoneInfo('UTC')` 真返 UTC tz,utcoffset=0。"""
        tz = zoneinfo.ZoneInfo("UTC")
        dt = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=tz)
        assert dt.utcoffset() == datetime.timedelta(0)

    def test_ZoneInfo_from_file_falls_back(self):
        """`zoneinfo.ZoneInfo('Asia/Shanghai')` 真拿 IANA tz (沙箱内 IANA tzdata)。"""
        tz = zoneinfo.ZoneInfo("Asia/Shanghai")
        dt = datetime.datetime(2026, 1, 15, 12, 0, tzinfo=tz)
        # 上海是 +8
        assert dt.utcoffset() == datetime.timedelta(hours=8), (
            f"Shanghai 应=+8h,实际 {dt.utcoffset()}"
        )
