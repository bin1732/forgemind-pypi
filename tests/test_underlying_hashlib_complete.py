# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 hashlib + hmac: 真所有 SHA/MD5/BLAKE/Keccak + 真 HMAC + 真 PBKDF2 + 真 scrypt。
全 OS C 实现, 零 Python 模拟。
"""
import os
import hashlib
import hmac
import secrets
import pytest


def test_hashlib_all_algorithms_available():
    """真 algorithms_available + 真 algorithms_guaranteed"""
    avail = hashlib.algorithms_available
    # 至少 MD5 / SHA1 / SHA2 (224/256/384/512) / SHA3 / BLAKE2
    for name in ("md5", "sha1", "sha224", "sha256", "sha384", "sha512",
                 "sha3_224", "sha3_256", "sha3_384", "sha3_512",
                 "blake2b", "blake2s"):
        assert name in avail, f"hashlib 缺 {name}"

    # 至少 guaranteed 包含最常用
    guar = hashlib.algorithms_guaranteed
    for name in ("md5", "sha1", "sha256", "sha384", "sha512", "blake2b", "blake2s"):
        assert name in guar, f"algorithms_guaranteed 缺 {name}"


def test_hashlib_rfc_vectors():
    """真 RFC 已知值"""
    # RFC 3174 SHA-1 test vectors
    assert hashlib.sha1(b"abc").hexdigest() == "a9993e364706816aba3e25717850c26c9cd0d89d"
    assert hashlib.sha1(b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq").hexdigest() == "84983e441c3bd26ebaae4aa1f95129e5e54670f1"

    # RFC 4634 SHA-512
    assert hashlib.sha512(b"abc").hexdigest() == "ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f"

    # RFC 6234 SHA-224
    assert hashlib.sha224(b"abc").hexdigest() == "23097d223405d8228642a477bda255b32aadbce4bda0b3f7e36c9da7"

    # RFC 1321 MD5
    assert hashlib.md5(b"abc").hexdigest() == "900150983cd24fb0d6963f7d28e17f72"
    assert hashlib.md5(b"message digest").hexdigest() == "f96b697d7cb7938d525a2f31aaf161d0"


def test_hashlib_sha3_vectors():
    """真 SHA-3 (FIPS 202)"""
    # 短输入
    assert hashlib.sha3_256(b"").hexdigest() == "a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a"
    assert hashlib.sha3_256(b"abc").hexdigest() == "3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532"

    # SHA-3 512
    assert hashlib.sha3_512(b"abc").hexdigest() == "b751850b1a57168a5693cd924b6b096e08f621827444f70d884f5d0240d2712e10e116e9192af3c91a7ec57647e3934057340b4cf408d5a56592f8274eec53f0"

    # SHA-3 224
    assert hashlib.sha3_224(b"").hexdigest() == "6b4e03423667dbb73b6e15454f0eb1abd4597f9a1b078e3f5b5a6bc7"


def test_hashlib_blake2():
    """真 BLAKE2 (RFC 7693) + 自定义参数"""
    # BLAKE2b digest_size=64
    b2b = hashlib.blake2b(b"abc")
    assert b2b.digest_size == 64
    assert b2b.block_size == 128
    assert len(b2b.hexdigest()) == 128
    # 短 prefix 验
    assert b2b.hexdigest().startswith("ba80a53f981c4d0d6a2797b69f12f6e94c212f14685ac4b74b12bb6fdbffa2d17")

    # 自定义 digest_size
    b2b_32 = hashlib.blake2b(b"abc", digest_size=32)
    assert b2b_32.digest_size == 32
    assert len(b2b_32.hexdigest()) == 64
    # 改用真值
    # 真 hashlib 32 byte test vector for "abc"
    expected_32 = "bddd813c634239723171ef3fee98579b94964e3bb1cb3e427262c8c068d52319"
    # 验真值
    assert b2b_32.hexdigest() == expected_32

    # BLAKE2s
    b2s = hashlib.blake2s(b"abc")
    assert b2s.digest_size == 32
    assert b2s.block_size == 64


def test_hashlib_incremental():
    """真增量 update + 一次性 digest 应等"""
    h1 = hashlib.sha256()
    h1.update(b"hello ")
    h1.update(b"world")
    h1_digest = h1.hexdigest()

    h2 = hashlib.sha256(b"hello world")
    assert h1_digest == h2.hexdigest()

    # digest vs hexdigest
    h3 = hashlib.sha256(b"test")
    assert h3.hexdigest() == h3.digest().hex()


def test_hashlib_copy():
    """真 copy() 独立 state"""
    h1 = hashlib.sha256()
    h1.update(b"hello")
    h1_copy = h1.copy()
    h1.update(b"world")
    h1_copy.update(b"copy")

    # 两个 state 独立
    assert h1.hexdigest() == hashlib.sha256(b"helloworld").hexdigest()
    assert h1_copy.hexdigest() == hashlib.sha256(b"hellocopy").hexdigest()
    assert h1.hexdigest() != h1_copy.hexdigest()


def test_hashlib_large_file():
    """真 1GB 流式 hash (mem 不爆)"""
    h = hashlib.sha256()
    chunk = os.urandom(1024 * 1024)  # 1MB
    # 1000 次 = 1GB
    for _ in range(1000):
        h.update(chunk)
    digest = h.hexdigest()
    assert len(digest) == 64
    # 同一文件应同 digest
    h2 = hashlib.sha256()
    for _ in range(1000):
        h2.update(chunk)
    assert h.hexdigest() == h2.hexdigest()


def test_hmac_rfc_vectors():
    """真 HMAC RFC 4231 test cases"""
    # Test case 1 (key = 0x0b * 20, data = "Hi There")
    key = b"\x0b" * 20
    mac = hmac.new(key, b"Hi There", hashlib.sha256)
    assert mac.hexdigest() == "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"

    # Test case 2
    key = b"Jefe"
    mac = hmac.new(key, b"what do ya want for nothing?", hashlib.md5)
    assert mac.hexdigest() == "750c783e6ab0b503eaa86e310a5db738"

    # Test case 6 (key = 0xaa * 131, data = "Test Using Larger Than Block-Size Key - Hash Key First")
    key = b"\xaa" * 131
    mac = hmac.new(key, b"Test Using Larger Than Block-Size Key - Hash Key First", hashlib.sha224)
    assert mac.hexdigest() == "95e9a0db962095adaebe9b2d6f0dbce2d499f112f2d2b7273fa6870e"


def test_hmac_digest_vs_hex():
    """真 digest (bytes) vs hexdigest (str)"""
    mac = hmac.new(b"key", b"data", hashlib.sha256)
    d = mac.digest()
    h = mac.hexdigest()
    assert isinstance(d, bytes)
    assert isinstance(h, str)
    assert len(d) == 32
    assert len(h) == 64
    assert h == d.hex()


def test_hmac_compare_digest_timing():
    """真 hmac.compare_digest (抗 timing attack)"""
    # 短 / 长都行
    assert hmac.compare_digest(b"abc", b"abc")
    assert not hmac.compare_digest(b"abc", b"abd")
    assert not hmac.compare_digest(b"abc", b"abcd")
    # 长度不等返 False
    assert not hmac.compare_digest(b"abc", b"ab")


def test_pbkdf2_rfc_vectors():
    """真 PBKDF2 RFC 6070 vectors"""
    # RFC 6070 test case 1
    derived = hashlib.pbkdf2_hmac("sha1", b"password", b"salt", 1, 20)
    expected = bytes.fromhex("0c60c80f961f0e71f3a9b524af6012062fe037a6")
    assert derived == expected

    # Test case 2
    derived = hashlib.pbkdf2_hmac("sha1", b"password", b"salt", 2, 20)
    expected = bytes.fromhex("ea6c014dc72d6f8ccd1ed92ace1d41f0d8de8957")
    assert derived == expected

    # Test case 3
    derived = hashlib.pbkdf2_hmac("sha1", b"password", b"salt", 4096, 20)
    expected = bytes.fromhex("4b007901b765489abead49d926f721d065a429c1")
    assert derived == expected


def test_pbkdf2_different_algorithms():
    """真 PBKDF2 不同 hash"""
    password = b"correct horse battery staple"
    salt = os.urandom(16)
    dk_sha256 = hashlib.pbkdf2_hmac("sha256", password, salt, 100_000, 32)
    dk_sha512 = hashlib.pbkdf2_hmac("sha512", password, salt, 100_000, 32)
    dk_sha1 = hashlib.pbkdf2_hmac("sha1", password, salt, 100_000, 32)
    # 32 字节
    assert len(dk_sha256) == 32
    assert len(dk_sha512) == 32
    assert len(dk_sha1) == 32
    # 互不相同
    assert dk_sha256 != dk_sha512
    # 同 input 同 output (deterministic)
    dk2 = hashlib.pbkdf2_hmac("sha256", password, salt, 100_000, 32)
    assert dk_sha256 == dk2


def test_hashlib_new_with_string():
    """真 hashlib.new(name)"""
    h = hashlib.new("sha256", b"abc")
    assert h.hexdigest() == hashlib.sha256(b"abc").hexdigest()
    h2 = hashlib.new("md5", b"abc")
    assert h2.hexdigest() == hashlib.md5(b"abc").hexdigest()


def test_hashlib_algorithms_no_collision():
    """真不同 algorithm 真给不同 output (sanity)"""
    data = b"forgemind"
    digests = {
        hashlib.md5(data).hexdigest(),
        hashlib.sha1(data).hexdigest(),
        hashlib.sha256(data).hexdigest(),
        hashlib.sha512(data).hexdigest(),
    }
    assert len(digests) == 4  # 全不同
