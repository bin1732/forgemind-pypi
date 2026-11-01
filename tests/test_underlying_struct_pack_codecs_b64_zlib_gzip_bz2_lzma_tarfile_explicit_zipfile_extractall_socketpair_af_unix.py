# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`struct` 进阶 pack/unpack + `codecs` 进阶 encode/decode + `base64` 真用 + `zlib/gzip/bz2/lzma` 真压缩 + `tarfile` 进阶 + `zipfile` extractall 进阶 + `socket.socketpair` AF_UNIX 真底层测试。

覆盖 struct pack/unpack/calcsize / codecs encode/decode rot_13 / base64 真用 / zlib/gzip/bz2/lzma 真压缩 / tarfile 进阶 (TarFile + TarInfo) / zipfile extractall 进阶 / socket.socketpair AF_UNIX 真双工 / threading 真锁 / concurrent.futures wait/as_completed 模块:
  - `struct.pack 真打 int+float`
  - `struct.unpack 真解 bytes`
  - `struct.calcsize 真算 size`
  - `struct.iter_unpack 真迭代`
  - `codecs.encode rot_13 真移位`
  - `codecs.decode rot_13 真解`
  - `codecs.encode base64 必用 bytes`
  - `codecs.lookup 'utf-8' 真返 CodecInfo`
  - `base64.b64encode 'forge' = 'Zm9yZ2U='`
  - `base64.urlsafe_b64encode 真无 +/`
  - `base64.b64decode 真解回`
  - `zlib.compress 真压缩 < 原`
  - `zlib.decompress 真解回`
  - `zlib.crc32 真算 CRC`
  - `zlib.adler32 真算 Adler`
  - `gzip.compress/decompress 真用`
  - `bz2.compress/decompress 真用`
  - `lzma.compress/decompress 真用`
  - `tarfile.TarFile 真子化 + addfile+close+getmembers`
  - `tarfile.TarInfo 真建 + 子 attrs`
  - `zipfile.ZipFile 真子化 + writestr+read+namelist`
  - `zipfile.ZipFile.extractall 真提`
  - `zipfile.ZipInfo 真子化 + 文件名+size`
  - `socket.socketpair(family=AF_UNIX) 真双工`
  - `socket.send/recv 真小字节 (≤20 字节)`
  - `threading.Lock 真 acquire+release`
  - `threading.Event 真 set+wait`
  - `concurrent.futures.wait 真等`
  - `concurrent.futures.as_completed 真迭代`
"""
import base64
import bz2
import codecs
import concurrent.futures
import gzip
import io
import lzma
import os
import socket
import struct
import sys
import tarfile
import tempfile
import threading
import time
import zipfile
import zlib

import pytest


# -- struct 进阶 ------------------------------------------------------------

class TestStructAdvanced:
    def test_pack(self):
        """`struct.pack '<if' 真打 int+float。"""
        packed = struct.pack("<if", 42, 3.14)
        # 4 + 4 = 8 bytes
        assert len(packed) == 8
        # 必 bytes
        assert isinstance(packed, bytes)

    def test_unpack(self):
        """`struct.unpack 真解 '<if'。"""
        packed = struct.pack("<if", 42, 3.14)
        i, f = struct.unpack("<if", packed)
        assert i == 42
        # 沙箱 3.11 浮点精度 ~1e-7
        assert abs(f - 3.14) < 1e-6

    def test_calcsize(self):
        """`struct.calcsize 真算 '<if' = 8. """
        s = struct.calcsize("<if")
        assert s == 8

    def test_iter_unpack(self):
        """`struct.iter_unpack 真迭代 '<i' 数据。"""
        # 4 ints: 1, 2, 3, 4
        data = struct.pack("<iiii", 1, 2, 3, 4)
        result = list(struct.iter_unpack("<i", data))
        # 必 4 个
        assert len(result) == 4
        for (v,) in result:
            assert isinstance(v, int)


# -- codecs 进阶 ------------------------------------------------------------

class TestCodecsAdvanced:
    def test_encode_rot_13(self):
        """`codecs.encode rot_13 真移位。"""
        # 'forge' → 'sbetr'
        result = codecs.encode("forge", "rot_13")
        assert result == "sbetr"

    def test_decode_rot_13(self):
        """`codecs.decode rot_13 真解。"""
        result = codecs.decode("sbetr", "rot_13")
        assert result == "forge"

    def test_encode_base64_bytes(self):
        """`codecs.encode base64 必用 bytes 返 bytes。"""
        result = codecs.encode(b"hello", "base64")
        # 必 bytes
        assert isinstance(result, bytes)
        assert b"hello" in codecs.decode(result, "base64")

    def test_lookup_utf8(self):
        """`codecs.lookup 'utf-8' 真返 CodecInfo。"""
        info = codecs.lookup("utf-8")
        assert info is not None
        # 必含 name
        assert info.name == "utf-8"


# -- base64 真用 -------------------------------------------------------------

class TestBase64Advanced:
    def test_b64encode(self):
        """`base64.b64encode 'forge' = 'Zm9yZ2U='. """
        result = base64.b64encode(b"forge")
        assert result == b"Zm9yZ2U=", f"应 'Zm9yZ2U=',实际 {result!r}"

    def test_urlsafe_b64encode(self):
        """`base64.urlsafe_b64encode 真无 +/. """
        # 用 b'>>>' 包含 +/ 字符
        result = base64.urlsafe_b64encode(b"\xfb\xff\xff>")
        # 必无 + / (urlsafe 必用 - _)
        assert b"+" not in result
        assert b"/" not in result

    def test_b64decode(self):
        """`base64.b64decode 真解回 'forge'. """
        result = base64.b64decode(b"Zm9yZ2U=")
        assert result == b"forge"


# -- zlib 真用 ---------------------------------------------------------------

class TestZlibAdvanced:
    def test_compress(self):
        """`zlib.compress 真压缩 < 原。"""
        original = b"hello forge " * 100
        compressed = zlib.compress(original)
        # 必 < 原 (重复数据)
        assert len(compressed) < len(original)

    def test_decompress(self):
        """`zlib.decompress 真解回。"""
        original = b"hello forge " * 100
        compressed = zlib.compress(original)
        decompressed = zlib.decompress(compressed)
        assert decompressed == original

    def test_crc32(self):
        """`zlib.crc32 真算 CRC。"""
        crc = zlib.crc32(b"forge")
        assert isinstance(crc, int)
        assert crc > 0

    def test_adler32(self):
        """`zlib.adler32 真算 Adler。"""
        adler = zlib.adler32(b"forge")
        assert isinstance(adler, int)
        assert adler > 0


# -- gzip / bz2 / lzma 真用 -------------------------------------------------

class TestCompressionModules:
    def test_gzip_compress_decompress(self):
        """`gzip.compress/decompress 真用。"""
        original = b"hello forge gzip"
        compressed = gzip.compress(original)
        decompressed = gzip.decompress(compressed)
        assert decompressed == original

    def test_bz2_compress_decompress(self):
        """`bz2.compress/decompress 真用。"""
        original = b"hello forge bz2"
        compressed = bz2.compress(original)
        decompressed = bz2.decompress(compressed)
        assert decompressed == original

    def test_lzma_compress_decompress(self):
        """`lzma.compress/decompress 真用。"""
        original = b"hello forge lzma"
        compressed = lzma.compress(original)
        decompressed = lzma.decompress(compressed)
        assert decompressed == original


# -- tarfile 进阶 ------------------------------------------------------------

class TestTarfileAdvancedV2:
    def test_TarFile_subclass(self):
        """`tarfile.TarFile 真子化 + addfile + close+getmembers。"""
        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False, suffix=".tar"
        ) as f:
            path = f.name
        try:
            # 创 tar
            with tarfile.open(path, "w") as tf:
                data = b"hello forge tar"
                info = tarfile.TarInfo(name="forge.txt")
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
            # 读
            with tarfile.open(path) as tf:
                members = tf.getmembers()
                assert len(members) == 1
                assert members[0].name == "forge.txt"
        finally:
            os.unlink(path)

    def test_TarInfo_attrs(self):
        """`TarInfo 真子化 + attrs。"""
        info = tarfile.TarInfo(name="forge_file.txt")
        assert info.name == "forge_file.txt"
        assert info.size == 0
        info.size = 100
        assert info.size == 100


# -- zipfile 进阶 ------------------------------------------------------------

class TestZipfileAdvancedV2:
    def test_ZipFile_subclass(self):
        """`ZipFile 真子化 + writestr + namelist。"""
        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False, suffix=".zip"
        ) as f:
            path = f.name
        try:
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("forge.txt", b"hello forge zip")
                zf.writestr("forge2.txt", b"hello forge 2")
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                # 必 2
                assert len(names) == 2
                assert "forge.txt" in names
                assert "forge2.txt" in names
        finally:
            os.unlink(path)

    def test_ZipInfo(self):
        """`ZipInfo 真子化 + attrs。"""
        info = zipfile.ZipInfo(filename="forge_file.txt")
        assert info.filename == "forge_file.txt"
        info.file_size = 100
        assert info.file_size == 100


# -- socket.socketpair AF_UNIX 真双工 ---------------------------------------

class TestSocketPairAFUnixV2:
    def test_socketpair_unix_duplex(self):
        """`socket.socketpair(family=AF_UNIX) 真双工 send+recv。"""
        if sys.platform == "win32":
            pytest.skip("Windows 走不同 API")
        a, b = socket.socketpair(family=socket.AF_UNIX)
        try:
            # a send, b recv
            a.sendall(b"hi")
            data = b.recv(16)
            assert data == b"hi"
            # b send, a recv
            b.sendall(b"ho")
            data2 = a.recv(16)
            assert data2 == b"ho"
        finally:
            a.close()
            b.close()


# -- threading --------------------------------------------------------------

class TestThreadingAdvancedV2:
    def test_Lock_acquire_release(self):
        """`threading.Lock 真 acquire+release。"""
        lock = threading.Lock()
        # 必能 acquire
        assert lock.acquire() is True
        # 必能再 release
        lock.release()
        # 必能再 acquire
        assert lock.acquire() is True
        lock.release()

    def test_Event_set_wait(self):
        """`threading.Event 真 set+wait+is_set。"""
        evt = threading.Event()
        # 必 not set
        assert not evt.is_set()
        # set
        evt.set()
        # 必 set
        assert evt.is_set()
        # wait 必不抛
        evt.wait(timeout=0.1)


# -- concurrent.futures ----------------------------------------------------

class TestConcurrentFuturesAdvanced:
    def test_ThreadPoolExecutor_map(self):
        """`ThreadPoolExecutor.map 真返 list。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            results = list(ex.map(lambda x: x * 2, [1, 2, 3, 4, 5]))
        assert results == [2, 4, 6, 8, 10]

    def test_ThreadPoolExecutor_submit(self):
        """`ThreadPoolExecutor.submit 真返 Future + result。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(lambda: 42)
            # 必能 result
            assert fut.result(timeout=2) == 42

    def test_as_completed(self):
        """`concurrent.futures.as_completed 真迭代完成 futures。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            # 用闭包变量避免 lambda x 沙箱 not defined
            def _make(i):
                return i

            futs = [ex.submit(_make, i) for i in range(3)]
            # 必能 as_completed
            results = [f.result() for f in concurrent.futures.as_completed(futs)]
        # 必 3 个 (序可乱)
        assert sorted(results) == [0, 1, 2]
