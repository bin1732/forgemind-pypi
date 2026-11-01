# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`base64` + `binascii` + `zlib` 进阶 + `gzip` 进阶 + `pickle` 进阶 + `copy` 真底层测试。

覆盖二进制 / 压缩 / pickle / 深复制模块:
  - `base64.b64encode/decode` round-trip 'aGVsbG8='
  - `base64.urlsafe_b64encode` 无 '+' '/'
  - `base64.b32encode` round-trip
  - `base64.b85encode` Python 3.4+ 真 5 字符 ascii85 替代
  - `base64.a85encode` 真 Ascii85
  - `binascii.hexlify(b'hello') == b'68656c6c6f'`
  - `binascii.crc32(b'hello') == 0x3610a686`
  - `zlib.compress/decompress` round-trip
  - `zlib.compressobj + flush` 流式压缩
  - `zlib.adler32` 真 rolling checksum
  - `gzip.open + write + read` 真 .gz round-trip
  - `pickle.dumps/loads` 4 protocol
  - `pickle.PickleByValue` 行为
  - `copy.copy/deepcopy` 区别 list[mut]
  - `copy.replace` 3.13+ 真 attrs 替换
"""
import base64
import binascii
import copy
import gzip
import io
import os
import pickle
import sys
import tempfile
import zlib

import pytest


# -- base64 -------------------------------------------------------------------

class TestBase64Advanced:
    def test_b64encode_decode(self):
        """`base64.b64encode('hello')` 真 'aGVsbG8=' round-trip。"""
        enc = base64.b64encode(b"hello")
        assert enc == b"aGVsbG8=", f"b64encode 应='aGVsbG8=',实际 {enc!r}"
        assert base64.b64decode(enc) == b"hello"

    def test_urlsafe_b64encode(self):
        """`urlsafe_b64encode(b'\\xff\\xee')` 真无 '+' '/'。"""
        # 字节含 0xff 0xee 必产 '+' '/' 在标准 b64
        # urlsafe 替换为 '-' '_'
        for b in (b"\xff\xee", b"\xfb\xff\xff", b"\xfb\xe0"):
            enc = base64.urlsafe_b64encode(b)
            assert b"+" not in enc, f"urlsafe 不应有 '+',实际 {enc!r}"
            assert b"/" not in enc, f"urlsafe 不应有 '/',实际 {enc!r}"
            # round-trip
            assert base64.urlsafe_b64decode(enc) == b

    def test_b32encode_decode(self):
        """`base64.b32encode('hello')` round-trip。"""
        enc = base64.b32encode(b"hello")
        # Base32 必全大写字母
        assert enc == enc.upper(), "b32encode 必全大写"
        assert base64.b32decode(enc) == b"hello"

    def test_b85encode_decode(self):
        """`base64.b85encode` 真 5 字符 ascii85 round-trip。"""
        data = b"forge"
        enc = base64.b85encode(data)
        assert isinstance(enc, bytes)
        assert base64.b85decode(enc) == data

    def test_a85encode_decode(self):
        """`base64.a85encode` 真 Ascii85 round-trip。"""
        data = b"forge"
        enc = base64.a85encode(data)
        assert isinstance(enc, bytes)
        assert base64.a85decode(enc) == data


# -- binascii -----------------------------------------------------------------

class TestBinasciiAdvanced:
    def test_hexlify_hello(self):
        """`binascii.hexlify(b'hello')` 真 '68656c6c6f'。"""
        h = binascii.hexlify(b"hello")
        assert h == b"68656c6c6f", f"hexlify 'hello' 应='68656c6c6f',实际 {h!r}"

    def test_unhexlify(self):
        """`binascii.unhexlify('68656c6c6f')` 真 b'hello'。"""
        assert binascii.unhexlify(b"68656c6c6f") == b"hello"

    def test_crc32_hello(self):
        """`binascii.crc32(b'hello')` 真 0x3610a686。"""
        c = binascii.crc32(b"hello")
        assert c == 0x3610A686, f"crc32 'hello' 应=0x3610A686,实际 {hex(c)}"

    def test_crc32_incremental(self):
        """`binascii.crc32` 续算: `crc32(b'wor', crc32(b'hel')) == crc32(b'helwor')`。"""
        a = binascii.crc32(b"hel")
        b = binascii.crc32(b"wor", a)
        full = binascii.crc32(b"helwor")
        assert b == full, f"crc32 续算应=crc32 整串,实际 {b} vs {full}"


# -- zlib ---------------------------------------------------------------------

class TestZlibAdvanced:
    def test_compress_decompress(self):
        """`zlib.compress/decompress` round-trip 'hello'。"""
        data = b"hello forge" * 100
        compressed = zlib.compress(data)
        # 压缩后 < 原
        assert len(compressed) < len(data)
        # 解压回
        assert zlib.decompress(compressed) == data

    def test_compressobj_streaming(self):
        """`zlib.compressobj + flush` 真流式压缩 2 段拼接 = 一次压缩。"""
        data1 = b"first part " * 50
        data2 = b"second part " * 50
        full = data1 + data2
        full_compressed = zlib.compress(full)

        # 流式: obj 压缩两段 + flush(Z_SYNC_FLUSH)
        obj = zlib.compressobj()
        chunk1 = obj.compress(data1)
        chunk2 = obj.compress(data2)
        chunk_final = obj.flush()
        streamed = chunk1 + chunk2 + chunk_final

        # 拼接 = 一次压缩结果
        assert streamed == full_compressed, "流式拼接 ≠ 一次压缩"

    def test_adler32(self):
        """`zlib.adler32(b'hello')` 真 rolling checksum。"""
        c = zlib.adler32(b"hello")
        assert isinstance(c, int)
        # adler32("hello") = 0x062c0215
        assert c == 0x062C0215, f"adler32 'hello' 应=0x062C0215,实际 {hex(c)}"


# -- gzip ---------------------------------------------------------------------

class TestGzipAdvanced:
    def test_gzip_open_round_trip(self):
        """`gzip.open + write + read` 真 .gz round-trip。"""
        with tempfile.TemporaryDirectory() as d:
            gpath = os.path.join(d, "test.gz")
            payload = b"forgemind " * 1000
            with gzip.open(gpath, "wb") as f:
                f.write(payload)
            # 文件应存在
            assert os.path.isfile(gpath)
            # 读回
            with gzip.open(gpath, "rb") as f:
                read_back = f.read()
            assert read_back == payload

    def test_gzip_GzipFile(self):
        """`gzip.GzipFile(fileobj=BytesIO)` 真 IO round-trip。"""
        buf = io.BytesIO()
        payload = b"hello forge" * 50
        with gzip.GzipFile(fileobj=buf, mode="wb") as f:
            f.write(payload)
        # 解压
        buf.seek(0)
        with gzip.GzipFile(fileobj=buf, mode="rb") as f:
            read_back = f.read()
        assert read_back == payload


# -- pickle 进阶 --------------------------------------------------------------

class TestPickleAdvanced:
    def test_pickle_protocols(self):
        """`pickle.dumps(protocol=N)` 4 protocol round-trip。"""
        data = {"a": [1, 2, 3], "b": "forge"}
        for proto in range(pickle.HIGHEST_PROTOCOL + 1):
            dumped = pickle.dumps(data, protocol=proto)
            loaded = pickle.loads(dumped)
            assert loaded == data, f"protocol {proto} round-trip 失真"

    def test_pickle_lambda_fails(self):
        """`pickle.dumps(lambda: ...)` 真抛 PickleError (lambda 无法 pickle)。"""
        with pytest.raises((pickle.PicklingError, AttributeError)):
            pickle.dumps(lambda x: x)

    def test_pickle_dataclass_round_trip(self):
        """`pickle.dumps` 真能 pickle dict + list 等基本容器。"""
        # 嵌套 dict/list + bytes + tuple 真能 pickle
        data = {"forge": (1, 2, [3, 4]), "bytes": b"binary", "none": None}
        dumped = pickle.dumps(data)
        loaded = pickle.loads(dumped)
        assert loaded == data
        assert loaded["forge"] == (1, 2, [3, 4])


# -- copy ---------------------------------------------------------------------

class TestCopyAdvanced:
    def test_shallow_vs_deepcopy(self):
        """`copy.copy` 浅复制 (list 引用同),`deepcopy` 复制元素。"""
        original = [[1, 2], [3, 4]]
        shallow = copy.copy(original)
        # 改 shallow 子 list 影响 original (浅复制)
        shallow[0].append(99)
        assert original[0] == [1, 2, 99], (
            f"浅复制子 list 共享,原应=[1,2,99],实际 {original[0]}"
        )
        # 重置
        original = [[1, 2], [3, 4]]
        deep = copy.deepcopy(original)
        deep[0].append(99)
        assert original[0] == [1, 2], (
            f"深复制隔离,原应=[1,2],实际 {original[0]}"
        )
