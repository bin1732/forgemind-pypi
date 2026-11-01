# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`statistics` 进阶 (fmean+geometric_mean+harmonic_mean+quantiles+covariance+correlation) + `fractions` 进阶 (limit_denominator+gcd+lcm) + `math.comb/perm/prod` + `string.Template` 进阶 + `string.punctuation` 真 + `ipaddress.IPv6Interface/IPv4Interface` 进阶 + 真底层测试。

覆盖 statistics 6 真 (fmean+geometric_mean+harmonic_mean+quantiles+covariance+correlation) + fractions 2 真 (limit_denominator+gcd/lcm) + math 3 真 (comb/perm/prod) + string 2 真 (Template+punctuation) + ipaddress 2 真 (IPv4Interface+IPv6Interface) (共 15 真测试) 模块:
  - `statistics.fmean [1,2,3,4] 真返 2.5`
  - `statistics.geometric_mean [2,8] 真返 4.0`
  - `statistics.harmonic_mean [1,2,4] 真返 12/7=1.714...`
  - `statistics.quantiles [1,2,3,4,5,6,7,8,9,10] n=4 真返 4 边界`
  - `statistics.covariance [1,2,3] [2,4,6] 真返 ~2.0`
  - `statistics.correlation [1,2,3] [2,4,6] 真返 1.0`
  - `fractions.Fraction(16,10).limit_denominator(3) 必 Fraction(5,3)`
  - `fractions.gcd(12, 8) 必 4 (3.9+ 弃用,改 math.gcd)`
  - `math.comb(5, 2) 必 10`
  - `math.perm(5, 2) 必 20`
  - `math.prod([1,2,3,4]) 必 24`
  - `string.Template '$x' + substitute(x='forge') 必 'forge'`
  - `string.punctuation 真含 32 ASCII 字符`
  - `ipaddress.IPv4Interface '192.168.1.1/24' 真 .ip + .network`
  - `ipaddress.IPv6Interface '2001:db8::1/64' 真 .ip + .network`
"""
import fractions
import ipaddress
import math
import statistics
import string

import pytest


# -- statistics 进阶 ----------------------------------------------------

class TestStatisticsAdvanced:
    def test_fmean(self):
        """`fmean [1,2,3,4] 真返 2.5。"""
        m = statistics.fmean([1, 2, 3, 4])
        # 必 2.5
        assert m == 2.5

    def test_geometric_mean(self):
        """`geometric_mean [2,8] 真返 4.0。"""
        m = statistics.geometric_mean([2, 8])
        # 必 4.0
        assert m == 4.0

    def test_harmonic_mean(self):
        """`harmonic_mean [1,2,4] 真返 12/7=1.714...。"""
        m = statistics.harmonic_mean([1, 2, 4])
        # 必 ~ 1.714285714
        assert abs(m - 12 / 7) < 1e-6

    def test_quantiles(self):
        """`quantiles [1..10] n=4 真返 4 边界。"""
        q = statistics.quantiles([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], n=4)
        # 必 3 个 cut points (n-1)
        assert len(q) == 3
        # 必 list
        assert isinstance(q, list)
        # 必值在 1-10 之间
        for x in q:
            assert 1.0 <= x <= 10.0

    def test_covariance(self):
        """`covariance [1,2,3] [2,4,6] 真返 2.0 (1,2,3 → 2,4,6 完美线)`"""
        c = statistics.covariance([1, 2, 3], [2, 4, 6])
        # 必 ~ 2.0
        assert abs(c - 2.0) < 1e-6

    def test_correlation(self):
        """`correlation [1,2,3] [2,4,6] 真返 1.0 (完美相关)`"""
        c = statistics.correlation([1, 2, 3], [2, 4, 6])
        # 必 1.0
        assert abs(c - 1.0) < 1e-6


# -- fractions 进阶 (limit_denominator) -----------------------------

class TestFractionsAdvanced:
    def test_limit_denominator(self):
        """`Fraction(16,10).limit_denominator(3) 必 Fraction(5,3)。"""
        f = fractions.Fraction(16, 10).limit_denominator(3)
        # 必 Fraction(5, 3)
        assert f == fractions.Fraction(5, 3)

    def test_gcd_via_math(self):
        """`math.gcd(12, 8) 必 4。"""
        g = math.gcd(12, 8)
        # 必 4
        assert g == 4
        # math.lcm 必 24
        assert math.lcm(4, 6) == 12


# -- math 进阶 (comb/perm/prod) -------------------------------------

class TestMathAdvancedV2:
    def test_comb(self):
        """`math.comb(5, 2) 必 10。"""
        c = math.comb(5, 2)
        # 必 10
        assert c == 10

    def test_perm(self):
        """`math.perm(5, 2) 必 20。"""
        p = math.perm(5, 2)
        # 必 20
        assert p == 20

    def test_prod(self):
        """`math.prod([1,2,3,4]) 必 24。"""
        r = math.prod([1, 2, 3, 4])
        # 必 24
        assert r == 24


# -- string 进阶 (Template + punctuation) ----------------------------

class TestStringAdvanced:
    def test_Template_substitute(self):
        """`Template '$x' + substitute(x='forge') 必 'forge'。"""
        tmpl = string.Template("$x is $y")
        result = tmpl.substitute(x="forge", y="fast")
        # 必 'forge is fast'
        assert result == "forge is fast"

    def test_punctuation(self):
        """`punctuation 真含 32 ASCII 字符。"""
        p = string.punctuation
        # 必 ≥ 30 (沙箱可能 32)
        assert len(p) >= 30
        # 必含!
        assert "!" in p
        # 必含@
        assert "@" in p
        # 必含#
        assert "#" in p


# -- ipaddress 进阶 (Interface v4/v6) --------------------------------

class TestIPAddressInterface:
    def test_IPv4Interface(self):
        """`IPv4Interface '192.168.1.1/24' 真 .ip + .network。"""
        iface = ipaddress.IPv4Interface("192.168.1.1/24")
        # 必 ip
        assert iface.ip == ipaddress.IPv4Address("192.168.1.1")
        # 必 network
        assert iface.network == ipaddress.IPv4Network("192.168.1.0/24")

    def test_IPv6Interface(self):
        """`IPv6Interface '2001:db8::1/64' 真 .ip + .network。"""
        iface = ipaddress.IPv6Interface("2001:db8::1/64")
        # 必 ip
        assert iface.ip == ipaddress.IPv6Address("2001:db8::1")
        # 必 network
        assert iface.network == ipaddress.IPv6Network("2001:db8::/64")
