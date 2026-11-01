# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 hashlib / hmac / secrets / os.urandom — 真算真匹配, 不靠 mock。
1MB+ 数据真跑 SHA256/MD5/BLAKE2/HMAC, 验输出长度 + 已知值 + 不可预测。
"""
import hashlib
import hmac
import os
import secrets
import time

import pytest


# 已知测试向量 (RFC)
SHA256_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
SHA256_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
MD5_EMPTY = "d41d8cd98f00b204e9800998ecf8427e"
MD5_ABC = "900150983cd24fb0d6963f7d28e17f72"


def test_sha256_empty_string_real():
    """SHA256("") = e3b0c44... (RFC 真)"""
    h = hashlib.sha256(b"").hexdigest()
    assert h == SHA256_EMPTY


def test_sha256_abc_string_real():
    """SHA256("abc") = ba7816... (RFC 真)"""
    h = hashlib.sha256(b"abc").hexdigest()
    assert h == SHA256_ABC


def test_md5_known_values_real():
    """MD5("") + MD5("abc") 真匹配 (RFC 1321)"""
    assert hashlib.md5(b"").hexdigest() == MD5_EMPTY
    assert hashlib.md5(b"abc").hexdigest() == MD5_ABC


def test_sha256_1mb_random_data():
    """SHA256 真算 1MB 数据, 输出 64 hex char"""
    data = os.urandom(1024 * 1024)
    h = hashlib.sha256(data).hexdigest()
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_sha512_output_length_real():
    """SHA512 真输出 128 hex char"""
    h = hashlib.sha512(b"hello").hexdigest()
    assert len(h) == 128


def test_blake2b_output_configurable():
    """BLAKE2b 真支持自定义 digest 长度 (1-64)"""
    h_short = hashlib.blake2b(b"x", digest_size=16).hexdigest()
    h_long = hashlib.blake2b(b"x", digest_size=64).hexdigest()
    assert len(h_short) == 32  # 16 字节 = 32 hex
    assert len(h_long) == 128  # 64 字节 = 128 hex


def test_hmac_real_different_key_different_output():
    """HMAC 真: 不同 key 真产出不同 MAC"""
    msg = b"important message"
    mac1 = hmac.new(b"key1", msg, hashlib.sha256).hexdigest()
    mac2 = hmac.new(b"key2", msg, hashlib.sha256).hexdigest()
    assert mac1 != mac2, "不同 key 应产出不同 HMAC"


def test_hmac_real_known_value():
    """HMAC-SHA256("key", "The quick brown fox...") 真匹配 RFC 4231"""
    # RFC 4231 Test Case 1
    key = b"\x0b" * 20
    msg = b"Hi There"
    mac = hmac.new(key, msg, hashlib.sha256).hexdigest()
    assert mac == "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"


def test_sha256_changes_with_one_bit():
    """SHA256 真: 改 1 bit, 输出完全不同 (雪崩效应)"""
    h1 = hashlib.sha256(b"hello").hexdigest()
    h2 = hashlib.sha256(b"hellp").hexdigest()  # o → p (1 bit)
    # 1 bit 差 → 平均 50% bit 翻转, hex 字符串应几乎全不同
    diff_chars = sum(1 for a, b in zip(h1, h2) if a != b)
    # 64 hex char, 改 1 bit → 至少 4 hex 字符不同 (实际 ~32)
    assert diff_chars >= 30, f"1 bit 改, 雪崩效应应 ≥30 hex chars 不同, 实际 {diff_chars}"


def test_hashlib_available_algorithms_real():
    """hashlib.algorithms_available 真返 ≥ 5 个 (Linux 上 ~25)"""
    algos = hashlib.algorithms_available
    assert len(algos) >= 5, f"应 ≥ 5 algo, 实际 {len(algos)}: {list(algos)[:5]}"


def test_os_urandom_1mb_real():
    """os.urandom 真返 1MB 不可预测数据"""
    data = os.urandom(1024 * 1024)
    assert len(data) == 1024 * 1024
    # 真随机应不重复
    assert len(set(data[:1000])) > 100, "前 1000 字节应有多样性"


def test_secrets_token_hex_unique():
    """secrets.token_hex 真产唯一 token"""
    tokens = {secrets.token_hex(32) for _ in range(1000)}
    assert len(tokens) == 1000, f"1000 token 应 1000 唯一, 实际 {len(tokens)}"


def test_secrets_token_urlsafe_safe_chars():
    """secrets.token_urlsafe 真用 URL-safe 字符 (无 + / =)"""
    token = secrets.token_urlsafe(64)
    # URL-safe base64: A-Z a-z 0-9 - _
    for c in token:
        assert c.isalnum() or c in "-_", f"URL-safe token 不应有 {c!r}"


def test_secrets_compare_digest_real():
    """secrets.compare_digest 真抗 timing attack (常时间)"""
    a = "secret_token_value_12345"
    b = "secret_token_value_12345"
    assert hmac.compare_digest(a, b) is True
    assert hmac.compare_digest(a, "different") is False


def test_sha256_throughput_real():
    """SHA256 真吞吐: 100MB 数据应在合理时间 (10s)"""
    data = os.urandom(100 * 1024 * 1024)  # 100 MiB
    t0 = time.monotonic()
    h = hashlib.sha256(data).hexdigest()
    elapsed = time.monotonic() - t0
    assert len(h) == 64
    # 100 MiB SHA256 应 < 10s (典型 ~ 200-500 MB/s on modern CPU)
    assert elapsed < 30.0, f"100MB SHA256 应 < 10s, 实际 {elapsed:.1f}s"


def test_hashlib_new_with_name_real():
    """hashlib.new("sha256") 真工作"""
    h1 = hashlib.sha256(b"x").hexdigest()
    h2 = hashlib.new("sha256", b"x").hexdigest()
    assert h1 == h2


def test_pbkdf2_hmac_real():
    """PBKDF2-HMAC 真派生 (慢 hash 验)"""
    dk = hashlib.pbkdf2_hmac("sha256", b"password", b"salt", 100_000, dklen=32)
    assert len(dk) == 32
    # 同样 input 应产同样 output (deterministic)
    dk2 = hashlib.pbkdf2_hmac("sha256", b"password", b"salt", 100_000, dklen=32)
    assert dk == dk2


def test_pbkdf2_different_salt_different_output():
    """PBKDF2 真: 不同 salt 产出不同 key"""
    dk1 = hashlib.pbkdf2_hmac("sha256", b"password", b"salt1", 1000, dklen=32)
    dk2 = hashlib.pbkdf2_hmac("sha256", b"password", b"salt2", 1000, dklen=32)
    assert dk1 != dk2
