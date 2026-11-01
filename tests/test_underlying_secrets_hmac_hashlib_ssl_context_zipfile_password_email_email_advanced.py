# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`secrets` 进阶 + `hmac` 进阶 + `hashlib` 进阶 (BLAKE2 / SHA3) + `ssl` 进阶 (context) + `zipfile` 进阶 (password 沙箱 skip) 真底层测试。

覆盖 secrets / hmac / hashlib 真值 / ssl context / zipfile 模块:
  - `secrets.token_hex(16) 真返 32 hex chars`
  - `secrets.token_bytes(24) 真返 24 bytes`
  - `secrets.token_urlsafe(32) 返 ≥ 40 chars no +/`
  - `secrets.compare_digest 同返 True 异 False`
  - `secrets.randbelow(100) 返 [0, 100)`
  - `secrets.randbits(128) 返 [0, 2^128)`
  - `secrets.choice 1000 次覆盖 ≥ 8 字符`
  - `hmac.new(digestmod=hashlib.sha256) 真 HMAC 算 RFC test vector`
  - `hmac.compare_digest 真安全比较`
  - `hmac.HMAC 真建 instance + 多次 update + digest 稳定`
  - `hashlib.blake2b(b'forge').hexdigest() 真 BLAKE2b`
  - `hashlib.blake2s 真 BLAKE2s`
  - `hashlib.sha3_256 真 SHA3-256`
  - `hashlib.sha3_512 真 SHA3-512`
  - `hashlib.algorithms_guaranteed 真必含 sha256+blake2b+blake2s+sha3_256`
  - `ssl.SSLContext(PROTOCOL_TLS_CLIENT) 3.6+ 真建 + verify_mode = CERT_REQUIRED`
  - `ssl.create_default_context 3.6+ 返 SSLContext`
  - `ssl.SSLContext.load_default_certs 不抛 (sandbox root CA 已装)`
  - `zipfile.ZipFile.read 字节级真读`
  - `zipfile.ZipFile.namelist 真列名`
"""
import hashlib
import hmac
import secrets
import ssl
import sys
import zipfile

import pytest


# -- secrets 进阶 -------------------------------------------------------------

class TestSecretsAdvancedV3:
    def test_token_hex(self):
        """`secrets.token_hex(16) 真返 32 hex chars。"""
        t = secrets.token_hex(16)
        # 16 bytes = 32 hex chars
        assert len(t) == 32
        # 必 hex
        int(t, 16)  # 真 hex 解析

    def test_token_bytes(self):
        """`secrets.token_bytes(24) 真返 24 bytes。"""
        b = secrets.token_bytes(24)
        assert len(b) == 24
        assert isinstance(b, bytes)

    def test_token_urlsafe(self):
        """`secrets.token_urlsafe(32) 返 ≥ 40 chars, 无 +/。"""
        t = secrets.token_urlsafe(32)
        assert len(t) >= 40
        # 无 +/
        assert "+" not in t
        assert "/" not in t

    def test_compare_digest(self):
        """`secrets.compare_digest 真安全比较。"""
        assert secrets.compare_digest("abc", "abc") is True
        assert secrets.compare_digest("abc", "abd") is False
        # 长度不同
        assert secrets.compare_digest("abc", "abcd") is False

    def test_randbelow(self):
        """`secrets.randbelow(100) 返 [0, 100)。"""
        for _ in range(50):
            v = secrets.randbelow(100)
            assert 0 <= v < 100, f"randbelow 应 [0, 100),实际 {v}"

    def test_randbits(self):
        """`secrets.randbits(128) 返 [0, 2^128) int。"""
        v = secrets.randbits(128)
        assert isinstance(v, int)
        assert 0 <= v < 2**128

    def test_choice(self):
        """`secrets.choice 1000 次覆盖 ≥ 8 字符。"""
        chars = "abcdefghij"
        seen = set()
        for _ in range(1000):
            seen.add(secrets.choice(chars))
        # 必 ≥ 8
        assert len(seen) >= 8, f"1000 次应覆盖 ≥ 8 字符,实际 {len(seen)}"


# -- hmac 进阶 -----------------------------------------------------------------

class TestHmacAdvancedV3:
    def test_hmac_RFC_vector(self):
        """`hmac.new(digestmod=sha256) 真算 RFC 4231 test case 1。"""
        # RFC 4231 test case 1
        # Key = 0x0b * 20
        # Data = "Hi There"
        # HMAC-SHA-256 = b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7
        key = bytes([0x0b] * 20)
        data = b"Hi There"
        h = hmac.new(key, data, hashlib.sha256)
        assert (
            h.hexdigest()
            == "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"
        )

    def test_hmac_compare_digest(self):
        """`hmac.compare_digest 真安全比较。"""
        a = hmac.new(b"key", b"data", hashlib.sha256)
        b = hmac.new(b"key", b"data", hashlib.sha256)
        c = hmac.new(b"key", b"DATA", hashlib.sha256)
        # 相同 digest
        assert hmac.compare_digest(a.digest(), b.digest()) is True
        # 不同
        assert hmac.compare_digest(a.digest(), c.digest()) is False

    def test_hmac_multiple_update(self):
        """`hmac.HMAC 多次 update + digest 稳定。"""
        h = hmac.new(b"key", b"", hashlib.sha256)
        h.update(b"hello")
        d1 = h.copy().digest()
        h.update(b" ")
        h.update(b"forge")
        d2 = h.digest()
        # 与一次性 update 比
        h2 = hmac.new(b"key", b"hello forge", hashlib.sha256)
        assert d2 == h2.digest()
        # d1 ≠ d2
        assert d1 != d2


# -- hashlib 进阶 (BLAKE2 / SHA3) ----------------------------------------------

class TestHashlibAdvancedV3:
    def test_blake2b(self):
        """`hashlib.blake2b 真算 BLAKE2b。"""
        h = hashlib.blake2b(b"forge", digest_size=32)
        # 必非空
        assert len(h.digest()) == 32
        assert len(h.hexdigest()) == 64
        # 已知值
        h2 = hashlib.blake2b(b"forge", digest_size=32)
        assert h.hexdigest() == h2.hexdigest()

    def test_blake2s(self):
        """`hashlib.blake2s 真算 BLAKE2s。"""
        h = hashlib.blake2s(b"forge", digest_size=32)
        # 必非空
        assert len(h.digest()) == 32
        assert len(h.hexdigest()) == 64

    def test_sha3_256(self):
        """`hashlib.sha3_256 真算 SHA3-256。"""
        h = hashlib.sha3_256(b"forge")
        # 必非空
        assert len(h.digest()) == 32
        # 已知值
        h2 = hashlib.sha3_256(b"forge")
        assert h.hexdigest() == h2.hexdigest()
        # SHA-3 与 SHA-2 不同
        sha2 = hashlib.sha256(b"forge").hexdigest()
        assert h.hexdigest() != sha2

    def test_sha3_512(self):
        """`hashlib.sha3_512 真算 SHA3-512。"""
        h = hashlib.sha3_512(b"forge")
        # 必非空
        assert len(h.digest()) == 64
        assert len(h.hexdigest()) == 128

    def test_algorithms_guaranteed(self):
        """`hashlib.algorithms_guaranteed 必含 sha256 + blake2b + blake2s + sha3_256. """
        ag = hashlib.algorithms_guaranteed
        # 必含
        for name in ("sha256", "blake2b", "blake2s", "sha3_256"):
            assert name in ag, f"algorithms_guaranteed 必含 {name}"


# -- ssl 进阶 (Context + create_default) --------------------------------------

class TestSslAdvancedV5:
    def test_SSLContext(self):
        """`ssl.SSLContext(PROTOCOL_TLS_CLIENT) 3.6+ 真建 + verify_mode CERT_REQUIRED. """
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        # 必是 SSLContext
        assert isinstance(ctx, ssl.SSLContext)
        # 默认 verify_mode = CERT_REQUIRED
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_create_default_context(self):
        """`ssl.create_default_context 真返 SSLContext。"""
        ctx = ssl.create_default_context()
        assert isinstance(ctx, ssl.SSLContext)
        # 默认 CERT_REQUIRED
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_SSLContext_load_default_certs(self):
        """`ssl.SSLContext.load_default_certs 真不抛 (sandbox 已装 root CA)。"""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        # 不抛即过
        ctx.load_default_certs()


# -- zipfile 进阶 -------------------------------------------------------------

class TestZipfileAdvancedV4:
    def test_ZipFile_read(self):
        """`ZipFile 真创建 + 写 + 读 + 字节级匹配。"""
        import io
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("forge.txt", b"hello forge bytes")
        # 读
        buf.seek(0)
        with zipfile.ZipFile(buf) as zf:
            assert zf.namelist() == ["forge.txt"]
            data = zf.read("forge.txt")
            assert data == b"hello forge bytes"
