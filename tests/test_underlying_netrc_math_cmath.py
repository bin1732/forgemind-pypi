# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 netrc (真 .netrc 解析) + 真 math 进阶 (gcd/lcm/comb/perm) + 真 cmath (复数 math) + 真 random 进阶 (SystemRandom 真 OS entropy) + 真 secrets。
全 stdlib, 零模拟。
"""
import netrc
import math
import cmath
import random
import secrets
import os
import tempfile
import pytest


# ======================== netrc ========================
def test_netrc_parse():
    """真 netrc 真解析 .netrc 文件"""
    content = """machine example.com
login alice
password secret123

machine api.test.com
login bob
password abcdef
"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        # 0o600 模式让 netrc 接受
        os.chmod(path, 0o600)
        n = netrc.netrc(path)
        # 查 machine (login, account, password)
        auth = n.authenticators("example.com")
        assert auth[0] == "alice"
        assert auth[2] == "secret123"
        auth2 = n.authenticators("api.test.com")
        assert auth2[0] == "bob"
        assert auth2[2] == "abcdef"
    finally:
        os.unlink(path)


def test_netrc_hosts():
    """真 netrc 真列 hosts"""
    content = """machine a.com login u1 password p1
machine b.com login u2 password p2
"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        os.chmod(path, 0o600)
        n = netrc.netrc(path)
        hosts = n.hosts
        assert "a.com" in hosts
        assert "b.com" in hosts
    finally:
        os.unlink(path)


# ======================== math 进阶 ========================
def test_math_gcd_lcm():
    """真 gcd / lcm"""
    assert math.gcd(12, 18) == 6
    assert math.gcd(0, 5) == 5
    # lcm
    assert math.lcm(4, 6) == 12
    assert math.lcm(3, 5) == 15


def test_math_comb_perm():
    """真 comb / perm"""
    # C(5, 2) = 10
    assert math.comb(5, 2) == 10
    # P(5, 2) = 20
    assert math.perm(5, 2) == 20


def test_math_factorial():
    """真 factorial"""
    assert math.factorial(5) == 120
    assert math.factorial(0) == 1
    assert math.factorial(1) == 1


def test_math_hypot():
    """真 hypot 真 sqrt(x^2 + y^2)"""
    # 3-4-5
    assert math.hypot(3, 4) == 5
    # 3D
    assert math.hypot(1, 2, 2) == 3


def test_math_infs():
    """真 inf / nan"""
    assert math.isinf(math.inf)
    assert not math.isfinite(math.inf)
    assert math.isnan(math.nan)
    assert not math.isnan(0.0)


def test_math_constants():
    """真数学常数"""
    assert math.pi == 3.141592653589793
    assert math.e == 2.718281828459045
    assert math.tau == 6.283185307179586


# ======================== cmath ========================
def test_cmath_complex_arithmetic():
    """真 cmath 真复数算"""
    z = complex(3, 4)
    assert abs(z) == 5  # sqrt(3^2 + 4^2)
    # cmath 函
    # cmath.phase 不在 cmath 模块, 用 math.atan2
    assert cmath.phase(z) == math.atan2(4, 3)
    # 极坐标
    r, theta = cmath.polar(z)
    assert abs(r - 5) < 1e-10
    # 重建
    z2 = cmath.rect(r, theta)
    assert abs(z2 - z) < 1e-10


def test_cmath_log_sqrt():
    """真 cmath 真对数开方"""
    z = complex(-1, 0)  # -1
    # sqrt(-1) = 1j
    s = cmath.sqrt(z)
    assert abs(s - 1j) < 1e-10
    # log(-1) = pi*j
    l = cmath.log(z)
    assert abs(l - cmath.pi * 1j) < 1e-10


def test_cmath_euler():
    """真 cmath 真欧拉公式"""
    z = complex(0, math.pi)  # pi*j
    # e^(pi*j) = -1
    e = cmath.exp(z)
    assert abs(e - (-1)) < 1e-10


# ======================== random 进阶 ========================
def test_random_SystemRandom():
    """真 SystemRandom 真 OS entropy"""
    sr = random.SystemRandom()
    # 真 OS entropy, 不 same seed
    a = sr.randint(1, 1000000)
    b = sr.randint(1, 1000000)
    # 高概率不同
    # (不严格, 但 OS entropy 不会 same)
    assert 1 <= a <= 1000000
    assert 1 <= b <= 1000000


def test_random_seed_reproducible():
    """真 random 真 reproducible"""
    random.seed(42)
    a = random.random()
    b = random.random()
    # 重 seed
    random.seed(42)
    a2 = random.random()
    b2 = random.random()
    assert a == a2
    assert b == b2


def test_random_sample_choices():
    """真 sample / choices"""
    data = [1, 2, 3, 4, 5]
    # sample 无重复
    s = random.sample(data, 3)
    assert len(s) == 3
    assert len(set(s)) == 3  # 无重复
    # choices 有重复
    c = random.choices(data, k=10)
    assert len(c) == 10


# ======================== secrets ========================
def test_secrets_token_hex():
    """真 secrets 真 token"""
    t = secrets.token_hex(16)
    # 16 bytes = 32 hex
    assert len(t) == 32
    # 仅 hex
    int(t, 16)  # 必能 parse


def test_secrets_token_urlsafe():
    """真 token_urlsafe"""
    t = secrets.token_urlsafe(16)
    # urlsafe 字符
    assert isinstance(t, str)
    assert len(t) >= 16


def test_secrets_compare_digest():
    """真 compare_digest"""
    a = "secret_value"
    b = "secret_value"
    c = "different_value"
    assert secrets.compare_digest(a, b) is True
    assert secrets.compare_digest(a, c) is False


def test_secrets_choice():
    """真 choice"""
    data = list(range(100))
    chosen = secrets.choice(data)
    assert chosen in data
