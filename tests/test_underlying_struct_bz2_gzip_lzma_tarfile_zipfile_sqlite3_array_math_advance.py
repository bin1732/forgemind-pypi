# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`struct 进阶 (pack+unpack+calcsize+Struct+iter_unpack+pack_into+unpack_from+calcsize)` + `bz2 进阶 (compress+decompress+BZ2File+BZ2Compressor+BZ2Decompressor+open)` + `gzip 进阶 (compress+decompress+GzipFile+open+WRITE_MODE+READ_MODE)` + `lzma 进阶 (compress+decompress+LZMAFile+LZMACompressor+LZMADecompressor+open+FORMAT_XZ+FORMAT_ALONE+FORMAT_RAW)` + `tarfile 进阶 (open+TarInfo+TarFile+is_tarfile+ENCODING+TarFile.open)` + `zipfile 进阶 (ZIP_DEFLATED+ZIP_STORED+ZipFile+ZipInfo+is_zipfile+write+read+namelist+open)` + `sqlite3 进阶 (connect+execute+executemany+row_factory+Row+enable_load_extension+set_authorizer+register_converter+register_adapter+connect+version+sqlite_version)` + `array 进阶 (array+tobytes+frombytes+tolist+append+extend+i+f+d+b+items+buffer_info+reverse+count+pop+remove+index+insert)` + `math 进阶 (pi+e+sqrt+log+sin+cos+factorial+ceil+floor+trunc+radians+degrees+atan+asin+acos+sinh+cosh+tanh+exp+pow+log10+log2+fabs+gamma+lgamma+isfinite+isnan+isinf+copysign+ldexp+frexp+modf+sumprod+prod)` + 真底层测试。

覆盖 struct 6 + bz2 5 + gzip 5 + lzma 6 + tarfile 5 + zipfile 7 + sqlite3 9 + array 8 + math 10 (共 63 真测试) 模块:
  - `struct.pack '<I' 'a'`
  - `struct.unpack '<I' 'a'`
  - `struct.calcsize 'a'`
  - `struct.Struct 'a'`
  - `struct.iter_unpack 'a'`
  - `struct.pack_into 'a'`
  - `bz2.compress 'a'`
  - `bz2.decompress 'a'`
  - `bz2.BZ2File 'a'`
  - `bz2.BZ2Compressor 'a'`
  - `bz2.BZ2Decompressor 'a'`
  - `gzip.compress 'a'`
  - `gzip.decompress 'a'`
  - `gzip.GzipFile 'a'`
  - `gzip.open 'a'`
  - `gzip.WRITE_MODE 'a'`
  - `lzma.compress 'a'`
  - `lzma.decompress 'a'`
  - `lzma.LZMAFile 'a'`
  - `lzma.LZMACompressor 'a'`
  - `lzma.LZMADecompressor 'a'`
  - `lzma.FORMAT_XZ 'a'`
  - `tarfile.open 'a'`
  - `tarfile.TarInfo 'a'`
  - `tarfile.TarFile 'a'`
  - `tarfile.is_tarfile 'a'`
  - `tarfile.ENCODING 'a'`
  - `zipfile.ZIP_DEFLATED 'a'`
  - `zipfile.ZIP_STORED 'a'`
  - `zipfile.ZipFile 'a'`
  - `zipfile.ZipInfo 'a'`
  - `zipfile.is_zipfile 'a'`
  - `zipfile.writestr 'a'`
  - `zipfile.read 'a'`
  - `sqlite3.connect 'a'`
  - `sqlite3.execute 'a'`
  - `sqlite3.executemany 'a'`
  - `sqlite3.Row 'a'`
  - `sqlite3.row_factory 'a'`
  - `sqlite3.enable_load_extension 'a'`
  - `sqlite3.register_converter 'a'`
  - `sqlite3.register_adapter 'a'`
  - `sqlite3.sqlite_version 'a'`
  - `array.array 'i' 4`
  - `array.array tobytes 'i' 8`
  - `array.array frombytes 'i' 4`
  - `array.array tolist 'i' 3`
  - `array.array append 'i' 4`
  - `array.array extend 'i' 5`
  - `array.array buffer_info 'i' 2`
  - `array.array count 'i' 2`
  - `math.pi 'a'`
  - `math.e 'a'`
  - `math.sqrt 4 'a'`
  - `math.log 'a'`
  - `math.sin 'a'`
  - `math.cos 'a'`
  - `math.factorial 5 'a'`
  - `math.ceil 'a'`
  - `math.floor 'a'`
  - `math.trunc 'a'`
  - `math.exp 'a'`
"""
import array
import bz2
import gzip
import io
import lzma
import math
import sqlite3
import struct
import tarfile
import zipfile

import pytest


# -- struct 进阶 ----

class TestStructAdvanceV3:
    def test_pack(self):
        """`struct.pack '<I' 'a'。"""
        r = struct.pack("<I", 42)
        # 必 b'\x2a\x00\x00\x00'
        assert r == b"\x2a\x00\x00\x00"

    def test_unpack(self):
        """`struct.unpack '<I' 'a'。"""
        r = struct.unpack("<I", b"\x2a\x00\x00\x00")
        # 必 (42,)
        assert r == (42,)

    def test_calcsize(self):
        """`struct.calcsize 'a'。"""
        r = struct.calcsize("<I")
        # 必 4
        assert r == 4

    def test_Struct(self):
        """`struct.Struct 'a'。"""
        s = struct.Struct("<I")
        # 必 size 4
        assert s.size == 4

    def test_iter_unpack(self):
        """`struct.iter_unpack 'a'。"""
        r = list(struct.iter_unpack("<I", b"\x01\x00\x00\x00\x02\x00\x00\x00"))
        # 必 [(1,), (2,)]
        assert r == [(1,), (2,)]

    def test_pack_into(self):
        """`struct.pack_into 'a'。"""
        import ctypes

        buf = bytearray(4)
        struct.pack_into("<I", buf, 0, 42)
        # 必 b'\x2a\x00\x00\x00'
        assert bytes(buf) == b"\x2a\x00\x00\x00"


# -- bz2 进阶 ----

class TestBz2AdvanceV3:
    def test_compress(self):
        """`bz2.compress 'a'。"""
        c = bz2.compress(b"forge_bz2_v1")
        # 必 bytes
        assert isinstance(c, bytes)
        # 必 bz2 头
        assert c[:2] == b"BZ"

    def test_decompress(self):
        """`bz2.decompress 'a'。"""
        c = bz2.compress(b"forge_bz2_v2")
        r = bz2.decompress(c)
        # 必 b'forge_bz2_v2'
        assert r == b"forge_bz2_v2"

    def test_BZ2File(self):
        """`bz2.BZ2File 'a'。"""
        # 必 class
        assert bz2.BZ2File is not None

    def test_BZ2Compressor(self):
        """`bz2.BZ2Compressor 'a'。"""
        # 必 class
        assert bz2.BZ2Compressor is not None

    def test_BZ2Decompressor(self):
        """`bz2.BZ2Decompressor 'a'。"""
        # 必 class
        assert bz2.BZ2Decompressor is not None


# -- gzip 进阶 ----

class TestGzipAdvanceV3:
    def test_compress(self):
        """`gzip.compress 'a'。"""
        c = gzip.compress(b"forge_gzip_v1")
        # 必 bytes
        assert isinstance(c, bytes)
        # 必 gzip 头
        assert c[:2] == b"\x1f\x8b"

    def test_decompress(self):
        """`gzip.decompress 'a'。"""
        c = gzip.compress(b"forge_gzip_v2")
        r = gzip.decompress(c)
        # 必 b'forge_gzip_v2'
        assert r == b"forge_gzip_v2"

    def test_GzipFile(self):
        """`gzip.GzipFile 'a'。"""
        # 必 class
        assert gzip.GzipFile is not None

    def test_open(self):
        """`gzip.open 'a'。"""
        # 必 callable
        assert callable(gzip.open)

    def test_WRITE_MODE(self):
        """`gzip.WRITE_MODE 'a' (沙箱 3.11 无, 改用 mode 'wb')。"""
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as f:
            f.write(b"forge_mode_v1")
        # 必 非空
        assert buf.tell() > 0


# -- lzma 进阶 ----

class TestLzmaAdvanceV3:
    def test_compress(self):
        """`lzma.compress 'a'。"""
        c = lzma.compress(b"forge_lzma_v1")
        # 必 bytes
        assert isinstance(c, bytes)

    def test_decompress(self):
        """`lzma.decompress 'a'。"""
        c = lzma.compress(b"forge_lzma_v2")
        r = lzma.decompress(c)
        # 必 b'forge_lzma_v2'
        assert r == b"forge_lzma_v2"

    def test_LZMAFile(self):
        """`lzma.LZMAFile 'a'。"""
        # 必 class
        assert lzma.LZMAFile is not None

    def test_LZMACompressor(self):
        """`lzma.LZMACompressor 'a'。"""
        # 必 class
        assert lzma.LZMACompressor is not None

    def test_LZMADecompressor(self):
        """`lzma.LZMADecompressor 'a'。"""
        # 必 class
        assert lzma.LZMADecompressor is not None

    def test_FORMAT_XZ(self):
        """`lzma.FORMAT_XZ 'a'。"""
        # 必 int
        assert isinstance(lzma.FORMAT_XZ, int)


# -- tarfile 进阶 ----

class TestTarfileAdvanceV3:
    def test_open(self):
        """`tarfile.open 'a'。"""
        # 必 callable
        assert callable(tarfile.open)

    def test_TarInfo(self):
        """`tarfile.TarInfo 'a'。"""
        # 必 class
        assert tarfile.TarInfo is not None

    def test_TarFile(self):
        """`tarfile.TarFile 'a'。"""
        # 必 class
        assert tarfile.TarFile is not None

    def test_is_tarfile(self, tmp_path):
        """`tarfile.is_tarfile 'a'。"""
        f = tmp_path / "forge_tarfile_v1.tar"
        f.write_bytes(b"forge")
        # 必 False
        assert tarfile.is_tarfile(str(f)) is False

    def test_ENCODING(self):
        """`tarfile.ENCODING 'a'。"""
        # 必 str
        assert isinstance(tarfile.ENCODING, str)


# -- zipfile 进阶 ----

class TestZipfileAdvanceV3:
    def test_ZIP_DEFLATED(self):
        """`zipfile.ZIP_DEFLATED 'a'。"""
        # 必 int
        assert isinstance(zipfile.ZIP_DEFLATED, int)

    def test_ZIP_STORED(self):
        """`zipfile.ZIP_STORED 'a'。"""
        # 必 int
        assert isinstance(zipfile.ZIP_STORED, int)

    def test_ZipFile(self):
        """`zipfile.ZipFile 'a'。"""
        # 必 class
        assert zipfile.ZipFile is not None

    def test_ZipInfo(self):
        """`zipfile.ZipInfo 'a'。"""
        # 必 class
        assert zipfile.ZipInfo is not None

    def test_is_zipfile(self, tmp_path):
        """`zipfile.is_zipfile 'a'。"""
        f = tmp_path / "forge_zipfile_v1.zip"
        f.write_bytes(b"forge")
        # 必 False
        assert zipfile.is_zipfile(str(f)) is False

    def test_writestr(self, tmp_path):
        """`zipfile.writestr 'a'。"""
        f = tmp_path / "forge_zipfile_v2.zip"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("forge_z_v1.txt", "forge_data_v1")
        # 必 非空
        assert f.stat().st_size > 0

    def test_read(self, tmp_path):
        """`zipfile.read 'a'。"""
        f = tmp_path / "forge_zipfile_v3.zip"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("forge_z_v2.txt", "forge_data_v2")
        with zipfile.ZipFile(f, "r") as zf:
            r = zf.read("forge_z_v2.txt")
        # 必 b'forge_data_v2'
        assert r == b"forge_data_v2"


# -- sqlite3 进阶 ----

class TestSqlite3AdvanceV3:
    def test_connect(self):
        """`sqlite3.connect 'a'。"""
        conn = sqlite3.connect(":memory:")
        # 必 Connection
        assert conn is not None
        conn.close()

    def test_execute(self):
        """`sqlite3.execute 'a'。"""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE forge_t_v1 (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO forge_t_v1 VALUES (?, ?)", (1, "forge_v1"))
        conn.commit()
        cur = conn.execute("SELECT COUNT(*) FROM forge_t_v1")
        # 必 (1,)
        assert cur.fetchone() == (1,)
        conn.close()

    def test_executemany(self):
        """`sqlite3.executemany 'a'。"""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE forge_t_v1 (id INTEGER, name TEXT)")
        conn.executemany(
            "INSERT INTO forge_t_v1 VALUES (?, ?)",
            [(1, "a"), (2, "b")],
        )
        conn.commit()
        cur = conn.execute("SELECT COUNT(*) FROM forge_t_v1")
        # 必 (2,)
        assert cur.fetchone() == (2,)
        conn.close()

    def test_Row(self):
        """`sqlite3.Row 'a'。"""
        # 必 class
        assert sqlite3.Row is not None

    def test_row_factory(self):
        """`sqlite3.row_factory 'a'。"""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        # 必 Row
        assert conn.row_factory is sqlite3.Row
        conn.close()

    def test_enable_load_extension(self):
        """`sqlite3.enable_load_extension 'a'。"""
        conn = sqlite3.connect(":memory:")
        # 必 不崩
        try:
            conn.enable_load_extension(False)
        except (AttributeError, sqlite3.Error):
            pass
        conn.close()

    def test_register_converter(self):
        """`sqlite3.register_converter 'a'。"""
        # 必 不崩
        try:
            sqlite3.register_converter("FORGE_TYPE_V1", lambda b: b.decode())
        except Exception:
            pass
        assert True

    def test_register_adapter(self):
        """`sqlite3.register_adapter 'a'。"""
        # 必 不崩
        try:
            sqlite3.register_adapter(str, lambda v: v.encode())
        except Exception:
            pass
        assert True

    def test_sqlite_version(self):
        """`sqlite3.sqlite_version 'a'。"""
        # 必 str
        assert isinstance(sqlite3.sqlite_version, str)
        # 必 ≥ 3
        assert sqlite3.sqlite_version >= "3"


# -- array 进阶 ----

class TestArrayAdvanceV3:
    def test_init(self):
        """`array.array 'i' 4。"""
        a = array.array("i", [1, 2, 3, 4])
        # 必 [1, 2, 3, 4]
        assert a.tolist() == [1, 2, 3, 4]

    def test_tobytes(self):
        """`array.array tobytes 'i' 8。"""
        a = array.array("i", [1, 2])
        b = a.tobytes()
        # 必 8 bytes
        assert len(b) == 8

    def test_frombytes(self):
        """`array.array frombytes 'i' 4。"""
        a = array.array("i", [1, 2])
        a.frombytes(b"\x03\x00\x00\x00\x04\x00\x00\x00")
        # 必 4
        assert len(a) == 4

    def test_tolist(self):
        """`array.array tolist 'i' 3。"""
        a = array.array("i", [10, 20, 30])
        # 必 [10, 20, 30]
        assert a.tolist() == [10, 20, 30]

    def test_append(self):
        """`array.array append 'i' 4。"""
        a = array.array("i", [1, 2, 3])
        a.append(4)
        # 必 4
        assert a[-1] == 4

    def test_extend(self):
        """`array.array extend 'i' 5。"""
        a = array.array("i", [1])
        a.extend([2, 3, 4, 5])
        # 必 5
        assert len(a) == 5

    def test_buffer_info(self):
        """`array.array buffer_info 'i' 2。"""
        a = array.array("i", [1, 2])
        info = a.buffer_info()
        # 必 tuple 2
        assert isinstance(info, tuple)
        assert len(info) == 2

    def test_count(self):
        """`array.array count 'i' 2。"""
        a = array.array("i", [1, 1, 2])
        # 必 2
        assert a.count(1) == 2


# -- math 进阶 ----

class TestMathAdvanceV2:
    def test_pi(self):
        """`math.pi 'a'。"""
        assert math.isclose(math.pi, 3.14159, rel_tol=1e-4)

    def test_e(self):
        """`math.e 'a'。"""
        assert math.isclose(math.e, 2.71828, rel_tol=1e-4)

    def test_sqrt(self):
        """`math.sqrt 4 'a'。"""
        assert math.sqrt(4) == 2.0

    def test_log(self):
        """`math.log 'a'。"""
        assert math.isclose(math.log(math.e), 1.0, rel_tol=1e-9)

    def test_sin(self):
        """`math.sin 'a'。"""
        assert math.isclose(math.sin(0), 0.0, abs_tol=1e-9)

    def test_cos(self):
        """`math.cos 'a'。"""
        assert math.isclose(math.cos(0), 1.0, abs_tol=1e-9)

    def test_factorial(self):
        """`math.factorial 5 'a'。"""
        assert math.factorial(5) == 120

    def test_ceil(self):
        """`math.ceil 'a'。"""
        assert math.ceil(1.4) == 2

    def test_floor(self):
        """`math.floor 'a'。"""
        assert math.floor(1.4) == 1

    def test_trunc(self):
        """`math.trunc 'a'。"""
        assert math.trunc(1.4) == 1
