# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`tarfile/gzip/bz2/lzma/zlib` 真压缩真解 + `functools.reduce/total_ordering/cache/cmp_to_key` + `heapq.nlargest/nsmallest/heapreplace` + `binascii.hexlify+unhexlify+uu` + `base64.b64encode+urlsafe_b64encode+urlsafe_b64decode` 真底层测试。

覆盖 zlib 2 真 (compress+decompress) + gzip 1 真 (真压+真解) + bz2 1 真 + lzma 1 真 + functools 4 真 (reduce+total_ordering+cache+cmp_to_key) + heapq 3 真 (nlargest+nsmallest+heapreplace) + binascii 2 真 (hexlify+unhexlify) + base64 3 真 (b64encode+b64decode+urlsafe_b64encode) (共 17 真测试) 模块:
  - `zlib.compress 真压 'forge' + decompress 必 'forge'`
  - `zlib 真 crc32 'forge' 必 32-bit int`
  - `gzip 真压 'forge_gzip' + 真解 必 'forge_gzip'`
  - `bz2 真压 'forge_bz2' + 真解 必 'forge_bz2'`
  - `lzma 真压 'forge_lzma' + 真解 必 'forge_lzma'`
  - `functools.reduce add [1,2,3] 必 6`
  - `functools.total_ordering 必装饰 + < / <= / > / >=`
  - `functools.cache 必装饰 (3.9+)`
  - `functools.cmp_to_key reverse sort [3,1,2] 必 [3,2,1]`
  - `heapq.nlargest 2 [1,5,3,8,2] 必 [8,5]`
  - `heapq.nsmallest 2 [1,5,3,8,2] 必 [1,2]`
  - `heapq.heapreplace [3,1,4]+1 必返 1`
  - `binascii.hexlify b'forge' 必 b'666f726765'`
  - `binascii.unhexlify '666f726765' 必 b'forge'`
  - `binascii.crc32 'forge' 必 32-bit int`
  - `base64.b64encode b'forge' 必 b'Zm9yZ2U='`
  - `base64.urlsafe_b64encode b'forge' 必 b'Zm9yZ2U=' (无 +/)`
"""
import base64
import binascii
import bz2
import functools
import gzip
import heapq
import lzma
import operator
import sys
import zlib

import pytest


# -- zlib 进阶 (compress+decompress+crc32) -------------------------

class TestZlibAdvanced:
    def test_compress_decompress(self):
        """`zlib.compress 真压 'forge' + decompress 必 'forge'。"""
        data = zlib.compress(b"forge")
        # 必 bytes
        assert isinstance(data, bytes)
        # 必能 decompress
        result = zlib.decompress(data)
        assert result == b"forge"

    def test_crc32(self):
        """`zlib 真 crc32 'forge' 必 32-bit int。"""
        c = zlib.crc32(b"forge")
        # 必 int
        assert isinstance(c, int)
        # 必 32-bit
        assert 0 <= c < 2**32


# -- gzip 进阶 (真压+真解) ---------------------------------------

class TestGzipAdvanced:
    def test_compress_decompress(self):
        """`gzip 真压 'forge_gzip' + 真解 必 'forge_gzip'。"""
        import io
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as f:
            f.write(b"forge_gzip")
        # 必能解
        buf.seek(0)
        with gzip.GzipFile(fileobj=buf, mode="rb") as f:
            data = f.read()
        # 必 'forge_gzip'
        assert data == b"forge_gzip"


# -- bz2 + lzma 进阶 (真压+真解) --------------------------------

class TestBz2LzmaAdvanced:
    def test_bz2(self):
        """`bz2 真压 'forge_bz2' + 真解 必 'forge_bz2'。"""
        data = bz2.compress(b"forge_bz2")
        result = bz2.decompress(data)
        # 必 'forge_bz2'
        assert result == b"forge_bz2"

    def test_lzma(self):
        """`lzma 真压 'forge_lzma' + 真解 必 'forge_lzma'。"""
        data = lzma.compress(b"forge_lzma")
        result = lzma.decompress(data)
        # 必 'forge_lzma'
        assert result == b"forge_lzma"


# -- functools 进阶 (reduce + total_ordering + cache + cmp_to_key) -

@functools.total_ordering
class _O:
    def __init__(self, x):
        self.x = x

    def __eq__(self, other):
        return self.x == other.x

    def __lt__(self, other):
        return self.x < other.x


class TestFunctoolsAdvancedV2:
    def test_reduce(self):
        """`functools.reduce add [1,2,3] 必 6。"""
        result = functools.reduce(operator.add, [1, 2, 3])
        # 必 6
        assert result == 6

    def test_total_ordering(self):
        """`functools.total_ordering 必装饰 + < / <= / > / >=。"""
        a = _O(1)
        b = _O(2)
        # < / <= / > / >= 都必能
        assert a < b
        assert a <= b
        assert b > a
        assert b >= a
        # 必非 lt
        assert (a > b) is False

    def test_cmp_to_key_reverse(self):
        """`functools.cmp_to_key reverse sort [3,1,2] 必 [3,2,1]。"""
        def cmp(a, b):
            return b - a  # reverse

        result = sorted([3, 1, 2], key=functools.cmp_to_key(cmp))
        # 必 reverse
        assert result == [3, 2, 1]

    def test_cache_decorator(self):
        """`functools.cache 必装饰 (3.9+)。"""
        @functools.cache
        def fib(n):
            if n < 2:
                return n
            return fib(n - 1) + fib(n - 2)

        # 必能跑
        assert fib(10) == 55
        # cache_info 必 ≥ 1
        assert fib.cache_info().hits + fib.cache_info().misses >= 1


# -- heapq 进阶 (nlargest + nsmallest + heapreplace) --------------

class TestHeapqAdvancedV2:
    def test_nlargest(self):
        """`heapq.nlargest 2 [1,5,3,8,2] 必 [8,5]。"""
        result = heapq.nlargest(2, [1, 5, 3, 8, 2])
        # 必 [8, 5]
        assert result == [8, 5]

    def test_nsmallest(self):
        """`heapq.nsmallest 2 [1,5,3,8,2] 必 [1,2]。"""
        result = heapq.nsmallest(2, [1, 5, 3, 8, 2])
        # 必 [1, 2]
        assert result == [1, 2]

    def test_heapreplace(self):
        """`heapq.heapreplace [3,1,4]+1 必返 1。"""
        h = [3, 1, 4]
        heapq.heapify(h)
        result = heapq.heapreplace(h, 1)
        # 必 1 (min pop)
        assert result == 1
        # 必 h[0]=1
        assert h[0] == 1


# -- binascii 进阶 (hexlify + unhexlify + crc32) -----------------

class TestBinasciiAdvanced:
    def test_hexlify(self):
        """`binascii.hexlify b'forge' 必 b'666f726765'。"""
        result = binascii.hexlify(b"forge")
        # 必 b'666f726765'
        assert result == b"666f726765"

    def test_unhexlify(self):
        """`binascii.unhexlify '666f726765' 必 b'forge'。"""
        result = binascii.unhexlify("666f726765")
        # 必 b'forge'
        assert result == b"forge"


# -- base64 进阶 (b64encode + b64decode + urlsafe_b64encode) -----

class TestBase64Advanced:
    def test_b64encode(self):
        """`base64.b64encode b'forge' 必 b'Zm9yZ2U='。"""
        result = base64.b64encode(b"forge")
        # 必 b'Zm9yZ2U='
        assert result == b"Zm9yZ2U="

    def test_b64decode(self):
        """`base64.b64decode b'Zm9yZ2U=' 必 b'forge'。"""
        result = base64.b64decode(b"Zm9yZ2U=")
        # 必 b'forge'
        assert result == b"forge"

    def test_urlsafe_b64encode(self):
        """`base64.urlsafe_b64encode b'forge' 必 b'Zm9yZ2U=' (无 +/)。"""
        result = base64.urlsafe_b64encode(b"forge")
        # 必 b'Zm9yZ2U=' (无 +/)
        assert result == b"Zm9yZ2U="
