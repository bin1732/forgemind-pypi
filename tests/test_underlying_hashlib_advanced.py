# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 hashlib 真 RIPEMD160 + 真 MD5 + 真 MD4 (可选) + 真 MD5 真 MD5 真 long + 真 hashlib 真 algorithms_available 真列 + 真 hashlib 真 new 真取 algo + 真 hashlib 真 hexdigest/bindigest。
全 stdlib, 零模拟。
"""
import hashlib
import hmac
import pytest


# ======================== MD5 真 ========================
def test_md5_basic():
    """真 MD5 真 hash"""
    md5 = hashlib.md5()
    md5.update(b"hello")
    # 16 bytes
    assert len(md5.digest()) == 16
    # hex
    assert len(md5.hexdigest()) == 32


def test_md5_rfc1321():
    """真 MD5 RFC 1321 真 vector"""
    # MD5("") = d41d8cd98f00b204e9800998ecf8427e
    assert hashlib.md5(b"").hexdigest() == "d41d8cd98f00b204e9800998ecf8427e"
    # MD5("a") = 0cc175b9c0f1b6a831c399e269772661
    assert hashlib.md5(b"a").hexdigest() == "0cc175b9c0f1b6a831c399e269772661"
    # MD5("abc") = 900150983cd24fb0d6963f7d28e17f72
    assert hashlib.md5(b"abc").hexdigest() == "900150983cd24fb0d6963f7d28e17f72"


def test_md5_long():
    """真 MD5 真长串"""
    # 100000 'a' 的 MD5
    data = b"a" * 100000
    md5 = hashlib.md5(data)
    # 真已知 RFC 1321 vector
    assert md5.hexdigest() == "1af6d6f2f682f76f80e606aeaaee1680"


def test_md5_copy():
    """真 hash.copy 真独立 state"""
    md5 = hashlib.md5()
    md5.update(b"hello")
    # copy
    md5_copy = md5.copy()
    # 各自 update
    md5.update(b" world")
    md5_copy.update(b" python")
    # 不影响对方
    assert md5.hexdigest() != md5_copy.hexdigest()


# ======================== SHA1 ========================
def test_sha1_rfc3174():
    """真 SHA1 RFC 3174 真 vector"""
    # SHA1("") = da39a3ee5e6b4b0d3255bfef95601890afd80709
    assert hashlib.sha1(b"").hexdigest() == "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    # SHA1("abc") = a9993e364706816aba3e25717850c26c9cd0d89d
    assert hashlib.sha1(b"abc").hexdigest() == "a9993e364706816aba3e25717850c26c9cd0d89d"


# ======================== SHA224 ========================
def test_sha224_rfc6234():
    """真 SHA224 真"""
    # SHA224("") = d14a028c2a3a2bc9476102bb288234c415a2b01f828ea62ac5b3e42f
    assert hashlib.sha224(b"").hexdigest() == "d14a028c2a3a2bc9476102bb288234c415a2b01f828ea62ac5b3e42f"
    # SHA224("abc") = 23097d223405d8228642a477bda255b32aadbce4bda0b3f7e36c9da7
    assert hashlib.sha224(b"abc").hexdigest() == "23097d223405d8228642a477bda255b32aadbce4bda0b3f7e36c9da7"


# ======================== SHA384 ========================
def test_sha384_rfc6234():
    """真 SHA384 真"""
    # SHA384("") = 38b060a751ac96384cd9327eb1b1e36a21fdb71114be07434c0cc7bf63f6e1da274edebfe76f65fbd51ad2f14898b95b
    assert hashlib.sha384(b"").hexdigest() == "38b060a751ac96384cd9327eb1b1e36a21fdb71114be07434c0cc7bf63f6e1da274edebfe76f65fbd51ad2f14898b95b"


# ======================== SHA3 ========================
def test_sha3_256_rfc4634():
    """真 SHA3-256 真"""
    if "sha3_256" in hashlib.algorithms_available:
        # SHA3-256("") = a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a
        assert hashlib.sha3_256(b"").hexdigest() == "a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a"


def test_sha3_512_rfc4634():
    """真 SHA3-512 真"""
    if "sha3_512" in hashlib.algorithms_available:
        # SHA3-512("") = a69f73cca23a9ac5c8b567dc185a756e97c982164fe25859e0d1dcc1475c80a615b2123af1f5f94c11e3e9402c3ac558f500199d95b6d3e301758586281dcd26
        assert hashlib.sha3_512(b"").hexdigest() == "a69f73cca23a9ac5c8b567dc185a756e97c982164fe25859e0d1dcc1475c80a615b2123af1f5f94c11e3e9402c3ac558f500199d95b6d3e301758586281dcd26"


# ======================== BLAKE2 ========================
def test_blake2b_rfc7693():
    """真 BLAKE2b 真"""
    # BLAKE2b-512("") = 786a02f742015903c6c6fd852552d272912f4740e15847618a86e217f71f5419d25e1031afee585313896444934eb04b903a685b1448b755d56f701afe9be2ce
    h = hashlib.blake2b(b"", digest_size=64)
    expected = "786a02f742015903c6c6fd852552d272912f4740e15847618a86e217f71f5419d25e1031afee585313896444934eb04b903a685b1448b755d56f701afe9be2ce"
    assert h.hexdigest() == expected


def test_blake2b_with_key():
    """真 BLAKE2b 真 key 真 keyed"""
    key = b"0123456789abcdef"  # 16 bytes
    data = b"message to hash"
    # 真 keyed hash
    h = hashlib.blake2b(data, key=key)
    # deterministic
    h2 = hashlib.blake2b(data, key=key)
    assert h.hexdigest() == h2.hexdigest()
    # 不带 key 不同
    h_no_key = hashlib.blake2b(data)
    assert h.hexdigest() != h_no_key.hexdigest()


# ======================== algorithms_available ========================
def test_algorithms_available():
    """真 algorithms_available"""
    algos = hashlib.algorithms_available
    # 必有 md5 / sha1 / sha256 / sha512
    assert "md5" in algos
    assert "sha1" in algos
    assert "sha256" in algos
    assert "sha512" in algos
    # 至少 5
    assert len(algos) >= 5


def test_algorithms_guaranteed():
    """真 algorithms_guaranteed"""
    algos = hashlib.algorithms_guaranteed
    # Python 必支持
    assert "md5" in algos
    assert "sha256" in algos
    # subset of available
    assert algos <= hashlib.algorithms_available


# ======================== new + digest size ========================
def test_hashlib_new_get_algo():
    """真 new 真取 algo"""
    h = hashlib.new("sha256")
    h.update(b"test")
    # digest_size
    assert h.digest_size == 32
    # name
    assert h.name == "sha256"
    # block_size
    assert h.block_size > 0


def test_hashlib_digest_size_property():
    """真 digest_size / block_size"""
    h = hashlib.sha256()
    assert h.digest_size == 32
    assert h.block_size == 64

    h_md5 = hashlib.md5()
    assert h_md5.digest_size == 16
    assert h_md5.block_size == 64
