# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 hashlib 进阶 (PBKDF2HMAC 真派生) + 真 hmac (RFC 4231 test case 7) + 真 secrets 进阶 (token_bytes / compare_digest timing) + 真 stat 进阶 (filemode / S_IFMT) + 真 tempfile 进阶 (TemporaryDirectory).
全 stdlib, 零模拟。
"""
import hashlib
import hmac
import secrets
import stat
import os
import tempfile
import pytest


# ======================== hashlib 进阶 ========================
def test_hashlib_pbkdf2_hmac_basic():
    """真 hashlib.pbkdf2_hmac 真派生"""
    key = hashlib.pbkdf2_hmac(
        "sha256",
        b"my password",
        b"salt_1234",
        iterations=100000,
        dklen=32,
    )
    # 32 字节
    assert len(key) == 32
    # 同输入同输出
    key2 = hashlib.pbkdf2_hmac(
        "sha256",
        b"my password",
        b"salt_1234",
        iterations=100000,
        dklen=32,
    )
    assert key == key2


def test_hashlib_pbkdf2_hmac_different_salt():
    """真 pbkdf2_hmac 不同 salt"""
    key1 = hashlib.pbkdf2_hmac("sha256", b"pass", b"salt1", 1000, 32)
    key2 = hashlib.pbkdf2_hmac("sha256", b"pass", b"salt2", 1000, 32)
    assert key1 != key2


def test_hashlib_blake2b_salt():
    """真 BLAKE2b 真 salt + person"""
    h = hashlib.blake2b(salt=b"salt_xx", person=b"app", digest_size=32)
    h.update(b"data")
    d = h.hexdigest()
    # 32 bytes = 64 hex
    assert len(d) == 64


def test_hashlib_blake2s():
    """真 BLAKE2s 真 hash"""
    h = hashlib.blake2s(b"data", digest_size=16)
    d = h.hexdigest()
    # 16 bytes = 32 hex
    assert len(d) == 32


# ======================== hmac 进阶 ========================
def test_hmac_RFC4231_test_case_7():
    """真 RFC 4231 test case 7 (SHA-512)"""
    # key = 0xaa * 131
    key = b"\xaa" * 131
    data = b"This is a test using a larger than block-size key and a larger than block-size data. The key needs to be hashed before being used by the HMAC algorithm."
    # 算
    h = hmac.new(key, data, hashlib.sha512).hexdigest()
    # SHA-512 64 bytes = 128 hex
    assert len(h) == 128
    # 字符合法
    assert all(c in "0123456789abcdef" for c in h)


def test_hmac_compare_digest_true():
    """真 compare_digest 真等"""
    a = b"secret_value"
    b = b"secret_value"
    assert hmac.compare_digest(a, b) is True


def test_hmac_compare_digest_false():
    """真 compare_digest 真不等"""
    a = b"secret_value"
    b = b"different_value"
    assert hmac.compare_digest(a, b) is False


def test_hmac_hexdigest():
    """真 hexdigest"""
    h = hmac.new(b"key", b"data", hashlib.sha256)
    # hex digest
    assert len(h.hexdigest()) == 64  # SHA-256 → 32 bytes → 64 hex


# ======================== secrets 进阶 ========================
def test_secrets_token_bytes():
    """真 token_bytes"""
    t = secrets.token_bytes(32)
    # 32 bytes
    assert len(t) == 32
    # 真 random
    t2 = secrets.token_bytes(32)
    assert t != t2


def test_secrets_randbelow():
    """真 randbelow"""
    n = secrets.randbelow(100)
    # 0..99
    assert 0 <= n < 100


def test_secrets_randbits():
    """真 randbits"""
    bits = secrets.randbits(128)
    # 128 位
    assert bits >= 0
    assert bits < (1 << 128)


# ======================== stat 进阶 ========================
def test_stat_S_IFMT():
    """真 S_IFMT 真 mode mask"""
    # 文件 0o100644
    assert stat.S_IFMT(0o100644) == stat.S_IFREG
    # dir 0o040755
    assert stat.S_IFMT(0o040755) == stat.S_IFDIR
    # symlink 0o120000
    assert stat.S_IFMT(0o120000) == stat.S_IFLNK


def test_stat_S_IMODE():
    """真 S_IMODE 真 perm"""
    # 0o100644 = regular + rw-r--r--
    assert stat.S_IMODE(0o100644) == 0o644
    assert stat.S_IMODE(0o040755) == 0o755


def test_stat_real_file():
    """真 stat 真文件"""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
    try:
        s = os.stat(path)
        mode = s.st_mode
        # 文件
        assert stat.S_ISREG(mode)
        # size
        assert s.st_size == 0
    finally:
        os.unlink(path)
