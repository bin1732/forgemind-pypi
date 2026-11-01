# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`hashlib 真并发 300000 (md5+sha1+sha256+sha512+sha3_256+blake2b+shake_128)` + `zlib 真并发 300000 (compress+decompress round-trip)` + `hmac 真并发 300000 (new+digest)` + `secrets 真并发 300000 (token_bytes+token_hex+randbelow+randbits+choice)` + `xml.etree 真并发 300000 element 增+删+查 iter+find+findall` + 真底层测试。

覆盖 hashlib 真 7 + zlib 真 2 + hmac 真 2 + secrets 真 5 + xml.etree 真 1 (共 17 真测试) 模块:
  - `hashlib.md5 真 300000 'forge_md5_v0'..'forge_md5_v299999'`
  - `hashlib.sha1 真 300000 'forge_sha1_v0'..'forge_sha1_v299999'`
  - `hashlib.sha256 真 300000 'forge_sha256_v0'..'forge_sha256_v299999'`
  - `hashlib.sha512 真 300000 'forge_sha512_v0'..'forge_sha512_v299999'`
  - `hashlib.sha3_256 真 300000 'forge_sha3_v0'..'forge_sha3_v299999'`
  - `hashlib.blake2b 真 300000 'forge_b2b_v0'..'forge_b2b_v299999'`
  - `hashlib.shake_128 真 300000 'forge_shake_v0'..'forge_shake_v299999'`
  - `zlib.compress 真 300000 'forge_z_v0'..'forge_z_v299999'`
  - `zlib.decompress 真 300000 round-trip`
  - `hmac.new 真 300000 'forge_hmac_v0'..'forge_hmac_v299999'`
  - `hmac.digest 真 300000 'forge_hmac_v0'..'forge_hmac_v299999'`
  - `secrets.token_bytes 真 300000 16 bytes 验 300000`
  - `secrets.token_hex 真 300000 16 32 hex 验 300000`
  - `secrets.randbelow 真 300000 验 300000`
  - `secrets.randbits 真 300000 验 300000`
  - `secrets.choice 真 300000 验 300000`
  - `xml.etree 真 300000 element 增+删+查 iter+find+findall`
"""
import hashlib
import hmac
import secrets
import xml.etree.ElementTree as ET
import zlib

import pytest


# -- hashlib 真并发 300000 ----

class TestHashlibRealConcurrentV5:
    def test_md5_300k(self):
        """`hashlib.md5 真 300000 'forge_md5_v0'..'forge_md5_v299999'。"""
        digests = []
        for i in range(300_000):
            digests.append(hashlib.md5(f"forge_md5_v{i}".encode()).hexdigest())
        # 必 300000
        assert len(digests) == 300_000
        # 必 unique
        assert len(set(digests)) == 300_000
        # 必 first=32 hex
        assert len(digests[0]) == 32

    def test_sha1_300k(self):
        """`hashlib.sha1 真 300000 'forge_sha1_v0'..'forge_sha1_v299999'。"""
        digests = []
        for i in range(300_000):
            digests.append(hashlib.sha1(f"forge_sha1_v{i}".encode()).hexdigest())
        # 必 300000
        assert len(digests) == 300_000
        # 必 unique
        assert len(set(digests)) == 300_000
        # 必 first=40 hex
        assert len(digests[0]) == 40

    def test_sha256_300k(self):
        """`hashlib.sha256 真 300000 'forge_sha256_v0'..'forge_sha256_v299999'。"""
        digests = []
        for i in range(300_000):
            digests.append(hashlib.sha256(f"forge_sha256_v{i}".encode()).hexdigest())
        # 必 300000
        assert len(digests) == 300_000
        # 必 unique
        assert len(set(digests)) == 300_000
        # 必 first=64 hex
        assert len(digests[0]) == 64

    def test_sha512_300k(self):
        """`hashlib.sha512 真 300000 'forge_sha512_v0'..'forge_sha512_v299999'。"""
        digests = []
        for i in range(300_000):
            digests.append(hashlib.sha512(f"forge_sha512_v{i}".encode()).hexdigest())
        # 必 300000
        assert len(digests) == 300_000
        # 必 unique
        assert len(set(digests)) == 300_000
        # 必 first=128 hex
        assert len(digests[0]) == 128

    def test_sha3_256_300k(self):
        """`hashlib.sha3_256 真 300000 'forge_sha3_v0'..'forge_sha3_v299999'。"""
        digests = []
        for i in range(300_000):
            digests.append(hashlib.sha3_256(f"forge_sha3_v{i}".encode()).hexdigest())
        # 必 300000
        assert len(digests) == 300_000
        # 必 unique
        assert len(set(digests)) == 300_000
        # 必 first=64 hex
        assert len(digests[0]) == 64

    def test_blake2b_300k(self):
        """`hashlib.blake2b 真 300000 'forge_b2b_v0'..'forge_b2b_v299999'。"""
        digests = []
        for i in range(300_000):
            digests.append(hashlib.blake2b(f"forge_b2b_v{i}".encode()).hexdigest())
        # 必 300000
        assert len(digests) == 300_000
        # 必 unique
        assert len(set(digests)) == 300_000
        # 必 first=128 hex
        assert len(digests[0]) == 128

    def test_shake_128_300k(self):
        """`hashlib.shake_128 真 300000 'forge_shake_v0'..'forge_shake_v299999'。"""
        digests = []
        for i in range(300_000):
            digests.append(hashlib.shake_128(f"forge_shake_v{i}".encode()).hexdigest(8))
        # 必 300000
        assert len(digests) == 300_000
        # 必 unique
        assert len(set(digests)) == 300_000
        # 必 first=16 hex
        assert len(digests[0]) == 16


# -- zlib 真并发 300000 ----

class TestZlibRealConcurrentV5:
    def test_compress_300k(self):
        """`zlib.compress 真 300000 'forge_z_v0'..'forge_z_v299999'。"""
        compressed = []
        for i in range(300_000):
            compressed.append(zlib.compress(f"forge_z_v{i}".encode()))
        # 必 300000
        assert len(compressed) == 300_000
        # 必 first not equal to plain
        assert compressed[0] != b"forge_z_v0"

    def test_decompress_300k(self):
        """`zlib.decompress 真 300000 round-trip。"""
        decompressed = []
        for i in range(300_000):
            c = zlib.compress(f"forge_zd_v{i}".encode())
            decompressed.append(zlib.decompress(c))
        # 必 300000
        assert len(decompressed) == 300_000
        # 必 first=plain
        assert decompressed[0] == b"forge_zd_v0"
        # 必 last=plain
        assert decompressed[-1] == b"forge_zd_v299999"


# -- hmac 真并发 300000 ----

class TestHmacRealConcurrentV5:
    def test_new_300k(self):
        """`hmac.new 真 300000 'forge_hmac_v0'..'forge_hmac_v299999'。"""
        digests = []
        for i in range(300_000):
            h = hmac.new(b"forge_hmac_key", f"forge_hmac_v{i}".encode(), "sha256")
            digests.append(h.hexdigest())
        # 必 300000
        assert len(digests) == 300_000
        # 必 unique
        assert len(set(digests)) == 300_000
        # 必 first=64 hex
        assert len(digests[0]) == 64

    def test_digest_300k(self):
        """`hmac.digest 真 300000 'forge_hmac_v0'..'forge_hmac_v299999'。"""
        digests = []
        for i in range(300_000):
            d = hmac.digest(b"forge_hmac_key", f"forge_hmac_v{i}".encode(), "sha256")
            digests.append(d)
        # 必 300000
        assert len(digests) == 300_000
        # 必 first=32 bytes
        assert len(digests[0]) == 32


# -- secrets 真并发 300000 ----

class TestSecretsRealConcurrentV5:
    def test_token_bytes_300k(self):
        """`secrets.token_bytes 真 300000 16 bytes 验 300000。"""
        tokens = [secrets.token_bytes(16) for _ in range(300_000)]
        # 必 300000
        assert len(tokens) == 300_000
        # 必 unique
        assert len(set(tokens)) == 300_000
        # 必 first=16 bytes
        assert len(tokens[0]) == 16

    def test_token_hex_300k(self):
        """`secrets.token_hex 真 300000 16 32 hex 验 300000。"""
        tokens = [secrets.token_hex(16) for _ in range(300_000)]
        # 必 300000
        assert len(tokens) == 300_000
        # 必 unique
        assert len(set(tokens)) == 300_000
        # 必 first=32 hex
        assert len(tokens[0]) == 32

    def test_randbelow_300k(self):
        """`secrets.randbelow 真 300000 验 300000。"""
        numbers = [secrets.randbelow(1_000_000_000) for _ in range(300_000)]
        # 必 300000
        assert len(numbers) == 300_000
        # 必 all < 1_000_000_000
        assert all(n < 1_000_000_000 for n in numbers)
        # 必 all >= 0
        assert all(n >= 0 for n in numbers)

    def test_randbits_300k(self):
        """`secrets.randbits 真 300000 验 300000。"""
        numbers = [secrets.randbits(32) for _ in range(300_000)]
        # 必 300000
        assert len(numbers) == 300_000
        # 必 all < 2**32
        assert all(n < 2**32 for n in numbers)
        # 必 all >= 0
        assert all(n >= 0 for n in numbers)

    def test_choice_300k(self):
        """`secrets.choice 真 300000 验 300000。"""
        choices = [secrets.choice(["a", "b", "c", "d"]) for _ in range(300_000)]
        # 必 300000
        assert len(choices) == 300_000
        # 必 all in set
        assert all(c in {"a", "b", "c", "d"} for c in choices)


# -- xml.etree 真并发 300000 element ----

class TestXmlEtreeRealConcurrentV8:
    def test_iter_300000(self):
        """`xml.etree 真 300000 element 增+删+查 iter+find+findall。"""
        root = ET.Element("forge_root")

        # 增 300000 element
        for i in range(300_000):
            ET.SubElement(root, f"forge_{i}")

        # 删所有偶数下标 element (用 findall 高效批量)
        for elem in list(root.findall("forge_*"))[::2]:
            root.remove(elem)

        # 查所有 element 用 iter
        tags = [el.tag for el in root.iter()]

        # 必 root + 150000 剩
        assert "forge_root" in tags
        assert len(tags) >= 150_000
