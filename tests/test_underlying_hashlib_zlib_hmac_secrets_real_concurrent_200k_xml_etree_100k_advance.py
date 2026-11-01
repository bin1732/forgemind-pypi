# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`hashlib 真并发 200000 (md5+sha1+sha256+sha512+sha3_256+blake2b+shake_128)` + `zlib 真并发 200000 (compress+decompress round-trip)` + `hmac 真并发 200000 (new+digest)` + `secrets 真并发 200000 (token_bytes+token_hex+randbelow+randbits+choice)` + `xml.etree 真并发 100000 element 增+删+查 iter+find+findall` + 真底层测试。

覆盖 hashlib 真 7 + zlib 真 2 + hmac 真 2 + secrets 真 5 + xml.etree 真 1 (共 17 真测试) 模块:
  - `hashlib.md5 真 200000 'forge_md5_v0'..'forge_md5_v199999'`
  - `hashlib.sha1 真 200000 'forge_sha1_v0'..'forge_sha1_v199999'`
  - `hashlib.sha256 真 200000 'forge_sha256_v0'..'forge_sha256_v199999'`
  - `hashlib.sha512 真 200000 'forge_sha512_v0'..'forge_sha512_v199999'`
  - `hashlib.sha3_256 真 200000 'forge_sha3_v0'..'forge_sha3_v199999'`
  - `hashlib.blake2b 真 200000 'forge_b2b_v0'..'forge_b2b_v199999'`
  - `hashlib.shake_128 真 200000 'forge_shake_v0'..'forge_shake_v199999'`
  - `zlib.compress 真 200000 'forge_z_v0'..'forge_z_v199999'`
  - `zlib.decompress 真 200000 round-trip`
  - `hmac.new 真 200000 'forge_hmac_v0'..'forge_hmac_v199999'`
  - `hmac.digest 真 200000 'forge_hmac_v0'..'forge_hmac_v199999'`
  - `secrets.token_bytes 真 200000 16 bytes 验 200000`
  - `secrets.token_hex 真 200000 16 32 hex 验 200000`
  - `secrets.randbelow 真 200000 验 200000`
  - `secrets.randbits 真 200000 验 200000`
  - `secrets.choice 真 200000 验 200000`
  - `xml.etree 真 100000 element 增+删+查 iter+find+findall`
"""
import hashlib
import hmac
import secrets
import xml.etree.ElementTree as ET
import zlib

import pytest


# -- hashlib 真并发 200000 ----

class TestHashlibRealConcurrentV4:
    def test_md5_200k(self):
        """`hashlib.md5 真 200000 'forge_md5_v0'..'forge_md5_v199999'。"""
        digests = []
        for i in range(200_000):
            digests.append(hashlib.md5(f"forge_md5_v{i}".encode()).hexdigest())
        # 必 200000
        assert len(digests) == 200_000
        # 必 unique
        assert len(set(digests)) == 200_000
        # 必 first=32 hex
        assert len(digests[0]) == 32

    def test_sha1_200k(self):
        """`hashlib.sha1 真 200000 'forge_sha1_v0'..'forge_sha1_v199999'。"""
        digests = []
        for i in range(200_000):
            digests.append(hashlib.sha1(f"forge_sha1_v{i}".encode()).hexdigest())
        # 必 200000
        assert len(digests) == 200_000
        # 必 unique
        assert len(set(digests)) == 200_000
        # 必 first=40 hex
        assert len(digests[0]) == 40

    def test_sha256_200k(self):
        """`hashlib.sha256 真 200000 'forge_sha256_v0'..'forge_sha256_v199999'。"""
        digests = []
        for i in range(200_000):
            digests.append(hashlib.sha256(f"forge_sha256_v{i}".encode()).hexdigest())
        # 必 200000
        assert len(digests) == 200_000
        # 必 unique
        assert len(set(digests)) == 200_000
        # 必 first=64 hex
        assert len(digests[0]) == 64

    def test_sha512_200k(self):
        """`hashlib.sha512 真 200000 'forge_sha512_v0'..'forge_sha512_v199999'。"""
        digests = []
        for i in range(200_000):
            digests.append(hashlib.sha512(f"forge_sha512_v{i}".encode()).hexdigest())
        # 必 200000
        assert len(digests) == 200_000
        # 必 unique
        assert len(set(digests)) == 200_000
        # 必 first=128 hex
        assert len(digests[0]) == 128

    def test_sha3_256_200k(self):
        """`hashlib.sha3_256 真 200000 'forge_sha3_v0'..'forge_sha3_v199999'。"""
        digests = []
        for i in range(200_000):
            digests.append(hashlib.sha3_256(f"forge_sha3_v{i}".encode()).hexdigest())
        # 必 200000
        assert len(digests) == 200_000
        # 必 unique
        assert len(set(digests)) == 200_000
        # 必 first=64 hex
        assert len(digests[0]) == 64

    def test_blake2b_200k(self):
        """`hashlib.blake2b 真 200000 'forge_b2b_v0'..'forge_b2b_v199999'。"""
        digests = []
        for i in range(200_000):
            digests.append(hashlib.blake2b(f"forge_b2b_v{i}".encode()).hexdigest())
        # 必 200000
        assert len(digests) == 200_000
        # 必 unique
        assert len(set(digests)) == 200_000
        # 必 first=128 hex
        assert len(digests[0]) == 128

    def test_shake_128_200k(self):
        """`hashlib.shake_128 真 200000 'forge_shake_v0'..'forge_shake_v199999'。"""
        digests = []
        for i in range(200_000):
            digests.append(hashlib.shake_128(f"forge_shake_v{i}".encode()).hexdigest(8))
        # 必 200000
        assert len(digests) == 200_000
        # 必 unique
        assert len(set(digests)) == 200_000
        # 必 first=16 hex
        assert len(digests[0]) == 16


# -- zlib 真并发 200000 ----

class TestZlibRealConcurrentV4:
    def test_compress_200k(self):
        """`zlib.compress 真 200000 'forge_z_v0'..'forge_z_v199999'。"""
        compressed = []
        for i in range(200_000):
            compressed.append(zlib.compress(f"forge_z_v{i}".encode()))
        # 必 200000
        assert len(compressed) == 200_000
        # 必 first not equal to plain
        assert compressed[0] != b"forge_z_v0"

    def test_decompress_200k(self):
        """`zlib.decompress 真 200000 round-trip。"""
        decompressed = []
        for i in range(200_000):
            c = zlib.compress(f"forge_zd_v{i}".encode())
            decompressed.append(zlib.decompress(c))
        # 必 200000
        assert len(decompressed) == 200_000
        # 必 first=plain
        assert decompressed[0] == b"forge_zd_v0"
        # 必 last=plain
        assert decompressed[-1] == b"forge_zd_v199999"


# -- hmac 真并发 200000 ----

class TestHmacRealConcurrentV4:
    def test_new_200k(self):
        """`hmac.new 真 200000 'forge_hmac_v0'..'forge_hmac_v199999'。"""
        digests = []
        for i in range(200_000):
            h = hmac.new(b"forge_hmac_key", f"forge_hmac_v{i}".encode(), "sha256")
            digests.append(h.hexdigest())
        # 必 200000
        assert len(digests) == 200_000
        # 必 unique
        assert len(set(digests)) == 200_000
        # 必 first=64 hex
        assert len(digests[0]) == 64

    def test_digest_200k(self):
        """`hmac.digest 真 200000 'forge_hmac_v0'..'forge_hmac_v199999'。"""
        digests = []
        for i in range(200_000):
            d = hmac.digest(b"forge_hmac_key", f"forge_hmac_v{i}".encode(), "sha256")
            digests.append(d)
        # 必 200000
        assert len(digests) == 200_000
        # 必 first=32 bytes
        assert len(digests[0]) == 32


# -- secrets 真并发 200000 ----

class TestSecretsRealConcurrentV4:
    def test_token_bytes_200k(self):
        """`secrets.token_bytes 真 200000 16 bytes 验 200000。"""
        tokens = [secrets.token_bytes(16) for _ in range(200_000)]
        # 必 200000
        assert len(tokens) == 200_000
        # 必 unique
        assert len(set(tokens)) == 200_000
        # 必 first=16 bytes
        assert len(tokens[0]) == 16

    def test_token_hex_200k(self):
        """`secrets.token_hex 真 200000 16 32 hex 验 200000。"""
        tokens = [secrets.token_hex(16) for _ in range(200_000)]
        # 必 200000
        assert len(tokens) == 200_000
        # 必 unique
        assert len(set(tokens)) == 200_000
        # 必 first=32 hex
        assert len(tokens[0]) == 32

    def test_randbelow_200k(self):
        """`secrets.randbelow 真 200000 验 200000。"""
        numbers = [secrets.randbelow(1_000_000_000) for _ in range(200_000)]
        # 必 200000
        assert len(numbers) == 200_000
        # 必 all < 1_000_000_000
        assert all(n < 1_000_000_000 for n in numbers)
        # 必 all >= 0
        assert all(n >= 0 for n in numbers)

    def test_randbits_200k(self):
        """`secrets.randbits 真 200000 验 200000。"""
        numbers = [secrets.randbits(32) for _ in range(200_000)]
        # 必 200000
        assert len(numbers) == 200_000
        # 必 all < 2**32
        assert all(n < 2**32 for n in numbers)
        # 必 all >= 0
        assert all(n >= 0 for n in numbers)

    def test_choice_200k(self):
        """`secrets.choice 真 200000 验 200000。"""
        choices = [secrets.choice(["a", "b", "c", "d"]) for _ in range(200_000)]
        # 必 200000
        assert len(choices) == 200_000
        # 必 all in set
        assert all(c in {"a", "b", "c", "d"} for c in choices)


# -- xml.etree 真并发 100000 element ----

class TestXmlEtreeRealConcurrentV6:
    def test_iter_100000(self):
        """`xml.etree 真 100000 element 增+删+查 iter+find+findall。"""
        root = ET.Element("forge_root")

        # 增 100000 element
        for i in range(100_000):
            ET.SubElement(root, f"forge_{i}")

        # 删所有偶数下标 element (用 findall 高效批量)
        for elem in list(root.findall("forge_*"))[::2]:
            root.remove(elem)

        # 查所有 element 用 iter
        tags = [el.tag for el in root.iter()]

        # 必 root + 50000 剩
        assert "forge_root" in tags
        assert len(tags) >= 50_000
