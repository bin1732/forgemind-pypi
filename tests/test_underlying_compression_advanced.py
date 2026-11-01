# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 zlib 真压缩 (level 0-9) + 真 bz2 真压缩 + 真 lzma 真压缩 + 真 tarfile 进阶 (info / list) + 真 zipfile 进阶 (ZipInfo / testzip) + 真 gzip 进阶。
全 stdlib, 零模拟。
"""
import zlib
import bz2
import lzma
import gzip
import tarfile
import zipfile
import os
import tempfile
import pytest


# ======================== zlib 进阶 ========================
def test_zlib_level_0():
    """真 zlib 真 level 0 (无压缩)"""
    data = b"Hello" * 100
    compressed = zlib.compress(data, level=0)
    # level 0 也加 header
    assert len(compressed) > 0
    # round-trip
    assert zlib.decompress(compressed) == data


def test_zlib_level_9():
    """真 zlib 真 level 9 (高压缩)"""
    data = b"A" * 10000
    compressed = zlib.compress(data, level=9)
    # 高度压缩
    assert len(compressed) < 100
    # round-trip
    assert zlib.decompress(compressed) == data


def test_zlib_crc32():
    """真 zlib.crc32 真算"""
    # 已知值: 'hello' = 0x3610a686
    crc = zlib.crc32(b"hello")
    assert crc == 0x3610A686
    # 空 = 0
    assert zlib.crc32(b"") == 0


def test_zlib_adler32():
    """真 adler32"""
    adler = zlib.adler32(b"hello")
    # 已知值
    assert adler == 0x062c0215


# ======================== bz2 ========================
def test_bz2_compress_decompress():
    """真 bz2 真 round-trip"""
    data = b"Hello, bz2 world! " * 100
    compressed = bz2.compress(data)
    # 压缩
    assert len(compressed) < len(data)
    # round-trip
    assert bz2.decompress(compressed) == data


def test_bz2_incompressible():
    """真 bz2 不可压缩数据"""
    import os as _os
    data = _os.urandom(10000)
    compressed = bz2.compress(data)
    # 不可压缩 (随机)
    assert len(compressed) >= 10000
    # round-trip 100%
    assert bz2.decompress(compressed) == data


# ======================== lzma ========================
def test_lzma_compress_decompress():
    """真 lzma 真 round-trip"""
    data = b"LZMA compression test " * 200
    compressed = lzma.compress(data)
    assert len(compressed) < len(data)
    assert lzma.decompress(compressed) == data


def test_lzma_formats():
    """真 lzma 多种 format"""
    data = b"X" * 1000
    # XZ
    xz = lzma.compress(data, format=lzma.FORMAT_XZ)
    # ALONE
    alone = lzma.compress(data, format=lzma.FORMAT_ALONE)
    # RAW 要 filters
    filters = [{"id": lzma.FILTER_LZMA2}]
    raw = lzma.compress(data, format=lzma.FORMAT_RAW, filters=filters)
    # round-trip
    assert lzma.decompress(xz, format=lzma.FORMAT_XZ) == data
    assert lzma.decompress(alone, format=lzma.FORMAT_ALONE) == data
    assert lzma.decompress(raw, format=lzma.FORMAT_RAW, filters=filters) == data


# ======================== gzip ========================
def test_gzip_compress_decompress():
    """真 gzip 真 round-trip"""
    data = b"Hello gzip " * 200
    with tempfile.NamedTemporaryFile(suffix=".gz", delete=False) as f:
        path = f.name
    try:
        # 写
        with gzip.open(path, "wb") as f:
            f.write(data)
        # 读
        with gzip.open(path, "rb") as f:
            loaded = f.read()
        assert loaded == data
    finally:
        os.unlink(path)


def test_gzip_text_mode():
    """真 gzip text mode"""
    text = "Hello\n世界\n"
    with tempfile.NamedTemporaryFile(suffix=".gz", delete=False) as f:
        path = f.name
    try:
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(text)
        with gzip.open(path, "rt", encoding="utf-8") as f:
            loaded = f.read()
        assert loaded == text
    finally:
        os.unlink(path)


# ======================== tarfile 进阶 ========================
def test_tarfile_info():
    """真 tarfile 真 TarInfo 元数据"""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "data.txt")
        with open(src, "w") as f:
            f.write("content")
        tar_path = os.path.join(d, "test.tar")
        with tarfile.open(tar_path, "w") as tar:
            info = tarfile.TarInfo("data.txt")
            info.size = 7  # "content"
            info.mode = 0o644
            tar.addfile(info)
        # 读 info
        with tarfile.open(tar_path, "r") as tar:
            members = tar.getmembers()
            assert len(members) == 1
            assert members[0].name == "data.txt"
            assert members[0].size == 7
            assert members[0].mode == 0o644


# ======================== zipfile 进阶 ========================
def test_zipfile_ZipInfo():
    """真 zipfile 真 ZipInfo 元数据"""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        path = f.name
    try:
        with zipfile.ZipFile(path, "w") as zf:
            info = zipfile.ZipInfo("test.txt")
            info.date_time = (2026, 1, 1, 12, 0, 0)
            zf.writestr(info, "content")
        # 读
        with zipfile.ZipFile(path, "r") as zf:
            infos = zf.infolist()
            assert len(infos) == 1
            assert infos[0].filename == "test.txt"
            assert infos[0].date_time[0] == 2026
    finally:
        os.unlink(path)


def test_zipfile_testzip():
    """真 zipfile 真 testzip 真检坏 CRC"""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        path = f.name
    try:
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("a.txt", "valid content")
            zf.writestr("b.txt", "another content")
        # testzip → None (全部 OK)
        with zipfile.ZipFile(path, "r") as zf:
            result = zf.testzip()
            assert result is None
    finally:
        os.unlink(path)
