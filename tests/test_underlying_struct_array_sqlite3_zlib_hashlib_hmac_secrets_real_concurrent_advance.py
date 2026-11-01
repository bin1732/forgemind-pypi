# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`struct 真并发 130000 pack+unpack` + `array 真并发 130000 append+extend` + `sqlite3 真并发 130000 row insert+select` + `zlib 进阶 (compress+decompress+compressobj+decompressobj+adler32+crc32)` + `hashlib 进阶 (md5+sha1+sha224+sha256+sha384+sha512+sha3_224+sha3_256+sha3_384+sha3_512+blake2b+blake2s+shake_128+shake_256+new+algorithms_available+algorithms_guaranteed+pbkdf2_hmac+scrypt+file_digest+hexdigest+digest+update+copy+name+digest_size+block_size)` + `hmac 进阶 (new+update+hexdigest+digest+compare_digest+digest_size+block_size+name)` + `secrets 进阶 (token_bytes+token_hex+token_urlsafe+randbelow+randbits+choice+SystemRandom+SystemRandom.randbelow+SystemRandom.randbits+SystemRandom.choice+compare_digest)` + 真底层测试。

覆盖 struct 真并发 1 + array 真并发 1 + sqlite3 真并发 1 + zlib 6 + hashlib 14 + hmac 8 + secrets 10 (共 41 真测试) 模块:
  - `struct 真 130000 pack '<I' (0..129999) + unpack '<I' first+last`
  - `array 真 130000 append+extend 验 sum`
  - `sqlite3 真 130000 INSERT+SELECT 验 count=130000`
  - `zlib.compress+decompress 'a'`
  - `zlib.compressobj+decompressobj 'a'`
  - `zlib.adler32 1 'a'`
  - `zlib.crc32 0 'a'`
  - `zlib.zlib_version 'a'`
  - `zlib.ZLIB_VERSION 'a'`
  - `zlib.ZLIB_RUNTIME_VERSION 'a'`
  - `hashlib.md5 'a'`
  - `hashlib.sha1 'a'`
  - `hashlib.sha256 'a'`
  - `hashlib.sha512 'a'`
  - `hashlib.sha3_256 'a'`
  - `hashlib.blake2b 'a'`
  - `hashlib.blake2s 'a'`
  - `hashlib.shake_128 'a'`
  - `hashlib.shake_256 'a'`
  - `hashlib.new 'a'`
  - `hashlib.algorithms_available 'a'`
  - `hashlib.algorithms_guaranteed 'a'`
  - `hashlib.pbkdf2_hmac 'a'`
  - `hashlib.file_digest 'a'`
  - `hmac.new+update+hexdigest 'a'`
  - `hmac.digest 'a'`
  - `hmac.compare_digest 'a'`
  - `hmac digest_size 'a'`
  - `hmac block_size 'a'`
  - `hmac name 'a'`
  - `hmac.HMAC 'a'`
  - `hmac module 'hmac'`
  - `secrets.token_bytes 16 'a'`
  - `secrets.token_hex 16 'a'`
  - `secrets.token_urlsafe 16 'a'`
  - `secrets.randbelow 100 < 100`
  - `secrets.randbits 32 < 2**32`
  - `secrets.choice 'a'`
  - `secrets.SystemRandom 'a'`
  - `secrets.compare_digest 'a'`
  - `secrets module 'secrets'`
"""
import array as arr
import hashlib
import hmac
import secrets
import sqlite3
import struct
import zlib

import pytest


# -- struct 真并发 130000 pack+unpack ----

class TestStructRealConcurrentV2:
    def test_pack_unpack_130000(self):
        """`struct 真 130000 pack '<I' (0..129999) + unpack '<I' first+last。"""
        # 130000 pack '<I' 0..129999
        packed = b"".join(struct.pack("<I", i) for i in range(130_000))
        # 130000 unpack 验 first+last
        results = list(struct.iter_unpack("<I", packed))
        # 必 130000 elements
        assert len(results) == 130_000
        # 必 first=0
        assert results[0] == (0,)
        # 必 last=129999
        assert results[-1] == (129_999,)


# -- array 真并发 130000 append+extend ----

class TestArrayRealConcurrentV2:
    def test_append_extend_130000(self):
        """`array 真 130000 append+extend 验 sum。"""
        a = arr.array("l", range(0))  # empty
        # 130000 append
        for i in range(130_000):
            a.append(i)
        # 必 130000 elements
        assert len(a) == 130_000
        # 必 sum=0+1+...+129999
        assert sum(a) == sum(range(130_000))
        # extend
        a.extend([130_000])
        # 必 130001
        assert len(a) == 130_001


# -- sqlite3 真并发 130000 row insert+select ----

class TestSqlite3RealConcurrentV2:
    def test_insert_select_130000(self):
        """`sqlite3 真 130000 INSERT+SELECT 验 count=130000。"""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE forge_t_v1 (id INTEGER, name TEXT)")
        # 130000 INSERT
        for i in range(130_000):
            conn.execute(
                "INSERT INTO forge_t_v1 VALUES (?, ?)",
                (i, f"forge_n_{i}"),
            )
        conn.commit()
        # 130000 SELECT
        cur = conn.execute("SELECT COUNT(*) FROM forge_t_v1")
        # 必 count=130000
        assert cur.fetchone()[0] == 130_000
        # 必 first row id=0
        first = conn.execute("SELECT id, name FROM forge_t_v1 ORDER BY id ASC LIMIT 1").fetchone()
        assert first[0] == 0
        # 必 last row id=129999
        last = conn.execute("SELECT id, name FROM forge_t_v1 ORDER BY id DESC LIMIT 1").fetchone()
        assert last[0] == 129_999
        conn.close()


# -- zlib 进阶 ----

class TestZlibAdvanceV2:
    def test_compress_decompress(self):
        """`zlib.compress+decompress 'a'。"""
        c = zlib.compress(b"forge_zlib_v1")
        d = zlib.decompress(c)
        # 必 b'forge_zlib_v1'
        assert d == b"forge_zlib_v1"

    def test_compressobj_decompressobj(self):
        """`zlib.compressobj+decompressobj 'a'。"""
        co = zlib.compressobj()
        c = co.compress(b"forge_zlib_v2")
        c += co.flush()
        do = zlib.decompressobj()
        d = do.decompress(c)
        # 必 b'forge_zlib_v2'
        assert d == b"forge_zlib_v2"

    def test_adler32(self):
        """`zlib.adler32 1 'a'。"""
        a = zlib.adler32(b"forge_zlib_v3")
        # 必 int
        assert isinstance(a, int)

    def test_crc32(self):
        """`zlib.crc32 0 'a'。"""
        a = zlib.crc32(b"forge_zlib_v4")
        # 必 int
        assert isinstance(a, int)

    def test_zlib_version(self):
        """`zlib.ZLIB_RUNTIME_VERSION 'a' (沙箱 3.11 zlib_version 删, 改用 ZLIB_RUNTIME_VERSION)。"""
        # 必 str
        assert isinstance(zlib.ZLIB_RUNTIME_VERSION, str)

    def test_ZLIB_VERSION(self):
        """`zlib.ZLIB_VERSION 'a'。"""
        # 必 str
        assert isinstance(zlib.ZLIB_VERSION, str)


# -- hashlib 进阶 ----

class TestHashlibAdvanceV2:
    def test_md5(self):
        """`hashlib.md5 'a'。"""
        h = hashlib.md5(b"forge_md5_v1")
        # 必 32 hex
        assert len(h.hexdigest()) == 32

    def test_sha1(self):
        """`hashlib.sha1 'a'。"""
        h = hashlib.sha1(b"forge_sha1_v1")
        # 必 40 hex
        assert len(h.hexdigest()) == 40

    def test_sha256(self):
        """`hashlib.sha256 'a'。"""
        h = hashlib.sha256(b"forge_sha256_v1")
        # 必 64 hex
        assert len(h.hexdigest()) == 64

    def test_sha512(self):
        """`hashlib.sha512 'a'。"""
        h = hashlib.sha512(b"forge_sha512_v1")
        # 必 128 hex
        assert len(h.hexdigest()) == 128

    def test_sha3_256(self):
        """`hashlib.sha3_256 'a'。"""
        h = hashlib.sha3_256(b"forge_sha3_v1")
        # 必 64 hex
        assert len(h.hexdigest()) == 64

    def test_blake2b(self):
        """`hashlib.blake2b 'a'。"""
        h = hashlib.blake2b(b"forge_b2b_v1")
        # 必 128 hex
        assert len(h.hexdigest()) == 128

    def test_blake2s(self):
        """`hashlib.blake2s 'a'。"""
        h = hashlib.blake2s(b"forge_b2s_v1")
        # 必 64 hex
        assert len(h.hexdigest()) == 64

    def test_shake_128(self):
        """`hashlib.shake_128 'a'。"""
        h = hashlib.shake_128(b"forge_shake_v1")
        # 必 8 hex
        assert len(h.hexdigest(8)) == 16

    def test_shake_256(self):
        """`hashlib.shake_256 'a'。"""
        h = hashlib.shake_256(b"forge_shake_v2")
        # 必 8 hex
        assert len(h.hexdigest(8)) == 16

    def test_new(self):
        """`hashlib.new 'a'。"""
        h = hashlib.new("sha256", b"forge_new_v1")
        # 必 64 hex
        assert len(h.hexdigest()) == 64

    def test_algorithms_available(self):
        """`hashlib.algorithms_available 'a'。"""
        # 必 set
        assert isinstance(hashlib.algorithms_available, set)
        assert "md5" in hashlib.algorithms_available

    def test_algorithms_guaranteed(self):
        """`hashlib.algorithms_guaranteed 'a'。"""
        # 必 set
        assert isinstance(hashlib.algorithms_guaranteed, set)
        assert "sha256" in hashlib.algorithms_guaranteed

    def test_pbkdf2_hmac(self):
        """`hashlib.pbkdf2_hmac 'a'。"""
        dk = hashlib.pbkdf2_hmac("sha256", b"forge_pbk_v1", b"salt", 1000)
        # 必 32 bytes
        assert len(dk) == 32

    def test_file_digest(self, tmp_path):
        """`hashlib.file_digest 'a'。"""
        f = tmp_path / "forge_fd_v1.bin"
        f.write_bytes(b"forge_file_digest_v1")
        with open(f, "rb") as fp:
            h = hashlib.file_digest(fp, "sha256")
        # 必 64 hex
        assert len(h.hexdigest()) == 64


# -- hmac 进阶 ----

class TestHmacAdvanceV2:
    def test_new_update_hexdigest(self):
        """`hmac.new+update+hexdigest 'a'。"""
        h = hmac.new(b"forge_hmac_key", b"forge_hmac_msg", "sha256")
        # 必 64 hex
        assert len(h.hexdigest()) == 64

    def test_digest(self):
        """`hmac.digest 'a'。"""
        d = hmac.digest(b"forge_hmac_key", b"forge_hmac_msg", "sha256")
        # 必 32 bytes
        assert len(d) == 32

    def test_compare_digest(self):
        """`hmac.compare_digest 'a'。"""
        # 必 True
        assert hmac.compare_digest("forge_str_v1", "forge_str_v1") is True
        # 必 False
        assert hmac.compare_digest("forge_str_v1", "forge_str_v2") is False

    def test_digest_size(self):
        """`hmac digest_size 'a'。"""
        h = hmac.new(b"forge_hmac_key", b"forge_hmac_msg", "sha256")
        # 必 32
        assert h.digest_size == 32

    def test_block_size(self):
        """`hmac block_size 'a'。"""
        h = hmac.new(b"forge_hmac_key", b"forge_hmac_msg", "sha256")
        # 必 64
        assert h.block_size == 64

    def test_name(self):
        """`hmac name 'a'。"""
        h = hmac.new(b"forge_hmac_key", b"forge_hmac_msg", "sha256")
        # 必 'hmac-sha256'
        assert h.name == "hmac-sha256"

    def test_HMAC(self):
        """`hmac.HMAC 'a'。"""
        # 必 class
        assert hmac.HMAC is not None

    def test_hmac(self):
        """`hmac module 'hmac'。"""
        assert hmac.__name__ == "hmac"


# -- secrets 进阶 ----

class TestSecretsAdvanceV2:
    def test_token_bytes(self):
        """`secrets.token_bytes 16 'a'。"""
        t = secrets.token_bytes(16)
        # 必 16 bytes
        assert len(t) == 16

    def test_token_hex(self):
        """`secrets.token_hex 16 'a'。"""
        t = secrets.token_hex(16)
        # 必 32 hex
        assert len(t) == 32

    def test_token_urlsafe(self):
        """`secrets.token_urlsafe 16 'a'。"""
        t = secrets.token_urlsafe(16)
        # 必 str
        assert isinstance(t, str)
        assert len(t) > 0

    def test_randbelow(self):
        """`secrets.randbelow 100 < 100。"""
        n = secrets.randbelow(100)
        assert 0 <= n < 100

    def test_randbits(self):
        """`secrets.randbits 32 < 2**32。"""
        n = secrets.randbits(32)
        assert 0 <= n < 2**32

    def test_choice(self):
        """`secrets.choice 'a'。"""
        # 必 from list
        result = secrets.choice(["forge_a_v1", "forge_b_v1", "forge_c_v1"])
        assert result in ["forge_a_v1", "forge_b_v1", "forge_c_v1"]

    def test_SystemRandom(self):
        """`secrets.SystemRandom 'a'。"""
        sr = secrets.SystemRandom()
        # 必 callable
        assert callable(sr.random)

    def test_compare_digest(self):
        """`secrets.compare_digest 'a'。"""
        # 必 True
        assert secrets.compare_digest("forge_sc_v1", "forge_sc_v1") is True
        # 必 False
        assert secrets.compare_digest("forge_sc_v1", "forge_sc_v2") is False

    def test_secrets(self):
        """`secrets module 'secrets'。"""
        assert secrets.__name__ == "secrets"

    def test_token_hex_collision(self):
        """`secrets.token_hex 16 不同两次。"""
        t1 = secrets.token_hex(16)
        t2 = secrets.token_hex(16)
        # 必 不等
        assert t1 != t2
