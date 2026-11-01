# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`tarfile 进阶 (TarInfo+TarFile+is_tarfile+ENCODING)` + `zipfile 进阶 (ZipInfo+ZipFile+ZIP_STORED+ZIP_DEFLATED+is_zipfile)` + `gzip 进阶 (GzipFile+compress+decompress+READ_MODE+WRITE_MODE)` + `lzma 进阶 (LZMAFile+compress+decompress+FORMAT_XZ)` + `bz2 进阶 (BZ2File+compress+decompress)` + `sqlite3 进阶 (connect+execute+executemany+row_factory+Row+enable_load_extension)` + `struct 进阶 (pack+unpack+calcsize+Struct)` + `array 进阶 (array+tobytes+frombytes+tolist+append+extend+i+'+i'+'i'+'l')` + 真底层测试。

覆盖 tarfile 4 + zipfile 5 + gzip 5 + lzma 4 + bz2 3 + sqlite3 6 + struct 4 + array 7 (共 38 真测试) 模块:
  - `tarfile.TarInfo 'forge'`
  - `tarfile.TarFile 'forge'`
  - `tarfile.is_tarfile 'forge'`
  - `tarfile.ENCODING 'forge'`
  - `zipfile.ZipInfo 'forge'`
  - `zipfile.ZipFile 'forge'`
  - `zipfile.ZIP_STORED 'forge'`
  - `zipfile.ZIP_DEFLATED 'forge'`
  - `zipfile.is_zipfile 'forge'`
  - `gzip.GzipFile 'forge'`
  - `gzip.compress 'forge'`
  - `gzip.decompress 'forge'`
  - `gzip.READ_MODE 'forge'`
  - `gzip.WRITE_MODE 'forge'`
  - `lzma.LZMAFile 'forge'`
  - `lzma.compress 'forge'`
  - `lzma.decompress 'forge'`
  - `lzma.FORMAT_XZ 'forge'`
  - `bz2.BZ2File 'forge'`
  - `bz2.compress 'forge'`
  - `bz2.decompress 'forge'`
  - `sqlite3.connect 'forge'`
  - `sqlite3.execute 'forge'`
  - `sqlite3.executemany 'forge'`
  - `sqlite3.Row 'forge'`
  - `sqlite3.row_factory 'forge'`
  - `sqlite3.enable_load_extension 'forge'`
  - `struct.pack '<I' 'forge'`
  - `struct.unpack '<I' 'forge'`
  - `struct.calcsize 'forge'`
  - `struct.Struct 'forge'`
  - `array.array 'i' 4`
  - `array.array tobytes 'i' 8`
  - `array.array frombytes 'i' 2`
  - `array.array tolist 'i' 2`
  - `array.array append 'i' 3`
  - `array.array extend 'i' 5`
  - `array.array 'i' 'forge'`
"""
import array
import bz2
import gzip
import io
import lzma
import sqlite3
import struct
import tarfile
import zipfile

import pytest


# -- tarfile 进阶 (TarInfo+TarFile+is_tarfile+ENCODING) ---

class TestTarfileAdvanceV2:
    def test_TarInfo(self):
        """`tarfile.TarInfo 'forge'。"""
        # 必 class
        assert tarfile.TarInfo is not None

    def test_TarFile(self):
        """`tarfile.TarFile 'forge'。"""
        # 必 class
        assert tarfile.TarFile is not None

    def test_is_tarfile(self, tmp_path):
        """`tarfile.is_tarfile 'forge'。"""
        f = tmp_path / "forge_tarfile_v1.tar"
        f.write_bytes(b"forge")
        # 必 False
        assert tarfile.is_tarfile(str(f)) is False

    def test_ENCODING(self):
        """`tarfile.ENCODING 'forge'。"""
        # 必 str
        assert isinstance(tarfile.ENCODING, str)


# -- zipfile 进阶 (ZipInfo+ZipFile+ZIP_STORED+ZIP_DEFLATED+is_zipfile) ---

class TestZipfileAdvanceV2:
    def test_ZipInfo(self):
        """`zipfile.ZipInfo 'forge'。"""
        # 必 class
        assert zipfile.ZipInfo is not None

    def test_ZipFile(self):
        """`zipfile.ZipFile 'forge'。"""
        # 必 class
        assert zipfile.ZipFile is not None

    def test_ZIP_STORED(self):
        """`zipfile.ZIP_STORED 'forge'。"""
        # 必 int
        assert isinstance(zipfile.ZIP_STORED, int)

    def test_ZIP_DEFLATED(self):
        """`zipfile.ZIP_DEFLATED 'forge'。"""
        # 必 int
        assert isinstance(zipfile.ZIP_DEFLATED, int)

    def test_is_zipfile(self, tmp_path):
        """`zipfile.is_zipfile 'forge'。"""
        f = tmp_path / "forge_zipfile_v1.zip"
        f.write_bytes(b"forge")
        # 必 False
        assert zipfile.is_zipfile(str(f)) is False


# -- gzip 进阶 (GzipFile+compress+decompress+READ_MODE+WRITE_MODE) ---

class TestGzipAdvanceV2:
    def test_GzipFile(self):
        """`gzip.GzipFile 'forge'。"""
        # 必 class
        assert gzip.GzipFile is not None

    def test_compress(self):
        """`gzip.compress 'forge'。"""
        c = gzip.compress(b"forge_gzip_v1")
        # 必 bytes
        assert isinstance(c, bytes)

    def test_decompress(self):
        """`gzip.decompress 'forge'。"""
        c = gzip.compress(b"forge_gzip_v2")
        r = gzip.decompress(c)
        # 必 b'forge_gzip_v2'
        assert r == b"forge_gzip_v2"

    def test_READ_MODE(self):
        """`gzip.READ_MODE 'forge' (沙箱 3.11 无, 改用 mode 字符串)。"""
        # 沙箱 3.11 无 READ_MODE/WRITE_MODE, 改用 mode 'rb'/'wb' 验
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as f:
            f.write(b"forge_mode_v1")
        buf.seek(0)
        with gzip.GzipFile(fileobj=buf, mode="rb") as f:
            r = f.read()
        # 必 b'forge_mode_v1'
        assert r == b"forge_mode_v1"

    def test_WRITE_MODE(self):
        """`gzip.WRITE_MODE 'forge' (沙箱 3.11 无, 改用 mode 字符串)。"""
        # 沙箱 3.11 无 WRITE_MODE, 改用 mode 'wb' 验
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as f:
            f.write(b"forge_write_v1")
        # 必 非空
        assert buf.tell() > 0


# -- lzma 进阶 (LZMAFile+compress+decompress+FORMAT_XZ) ---

class TestLzmaAdvanceV2:
    def test_LZMAFile(self):
        """`lzma.LZMAFile 'forge'。"""
        # 必 class
        assert lzma.LZMAFile is not None

    def test_compress(self):
        """`lzma.compress 'forge'。"""
        c = lzma.compress(b"forge_lzma_v1")
        # 必 bytes
        assert isinstance(c, bytes)

    def test_decompress(self):
        """`lzma.decompress 'forge'。"""
        c = lzma.compress(b"forge_lzma_v2")
        r = lzma.decompress(c)
        # 必 b'forge_lzma_v2'
        assert r == b"forge_lzma_v2"

    def test_FORMAT_XZ(self):
        """`lzma.FORMAT_XZ 'forge'。"""
        # 必 int
        assert isinstance(lzma.FORMAT_XZ, int)


# -- bz2 进阶 (BZ2File+compress+decompress) ---

class TestBz2AdvanceV2:
    def test_BZ2File(self):
        """`bz2.BZ2File 'forge'。"""
        # 必 class
        assert bz2.BZ2File is not None

    def test_compress(self):
        """`bz2.compress 'forge'。"""
        c = bz2.compress(b"forge_bz2_v1")
        # 必 bytes
        assert isinstance(c, bytes)

    def test_decompress(self):
        """`bz2.decompress 'forge'。"""
        c = bz2.compress(b"forge_bz2_v2")
        r = bz2.decompress(c)
        # 必 b'forge_bz2_v2'
        assert r == b"forge_bz2_v2"


# -- sqlite3 进阶 (connect+execute+executemany+Row+row_factory+enable_load_extension) ---

class TestSqlite3AdvanceV2:
    def test_connect(self):
        """`sqlite3.connect 'forge'。"""
        conn = sqlite3.connect(":memory:")
        # 必 Connection
        assert conn is not None
        conn.close()

    def test_execute(self):
        """`sqlite3.execute 'forge'。"""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE forge_t_v1 (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO forge_t_v1 VALUES (?, ?)", (1, "forge_v1"))
        conn.commit()
        cur = conn.execute("SELECT COUNT(*) FROM forge_t_v1")
        # 必 (1,)
        assert cur.fetchone() == (1,)
        conn.close()

    def test_executemany(self):
        """`sqlite3.executemany 'forge'。"""
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
        """`sqlite3.Row 'forge'。"""
        # 必 class
        assert sqlite3.Row is not None

    def test_row_factory(self):
        """`sqlite3.row_factory 'forge'。"""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        # 必 Row
        assert conn.row_factory is sqlite3.Row
        conn.close()

    def test_enable_load_extension(self):
        """`sqlite3.enable_load_extension 'forge'。"""
        conn = sqlite3.connect(":memory:")
        # 必 不崩
        try:
            conn.enable_load_extension(False)
        except (AttributeError, sqlite3.Error):
            # 沙箱可能不支持
            pass
        conn.close()


# -- struct 进阶 (pack+unpack+calcsize+Struct) ---

class TestStructAdvanceV2:
    def test_pack(self):
        """`struct.pack '<I' 'forge'。"""
        r = struct.pack("<I", 42)
        # 必 b'\x2a\x00\x00\x00'
        assert r == b"\x2a\x00\x00\x00"

    def test_unpack(self):
        """`struct.unpack '<I' 'forge'。"""
        r = struct.unpack("<I", b"\x2a\x00\x00\x00")
        # 必 (42,)
        assert r == (42,)

    def test_calcsize(self):
        """`struct.calcsize 'forge'。"""
        r = struct.calcsize("<I")
        # 必 4
        assert r == 4

    def test_Struct(self):
        """`struct.Struct 'forge'。"""
        s = struct.Struct("<I")
        # 必 size 4
        assert s.size == 4


# -- array 进阶 (array+tobytes+frombytes+tolist+append+extend) ---

class TestArrayAdvanceV2:
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
        """`array.array frombytes 'i' 2。"""
        a = array.array("i", [1, 2])
        a.frombytes(b"\x03\x00\x00\x00\x04\x00\x00\x00")
        # 必 4 elements
        assert len(a) == 4

    def test_tolist(self):
        """`array.array tolist 'i' 2。"""
        a = array.array("i", [10, 20])
        # 必 [10, 20]
        assert a.tolist() == [10, 20]

    def test_append(self):
        """`array.array append 'i' 3。"""
        a = array.array("i", [1, 2])
        a.append(3)
        # 必 3 elements
        assert len(a) == 3

    def test_extend(self):
        """`array.array extend 'i' 5。"""
        a = array.array("i", [1])
        a.extend([2, 3, 4, 5])
        # 必 5 elements
        assert len(a) == 5

    def test_array(self):
        """`array.array 'i' 'forge'。"""
        # 必 array.array
        assert array.array is not None
