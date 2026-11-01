# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 tarfile 进阶 (多 mode / u/g/bz2/lzma/xz) + 真 zipfile 进阶 (compression level / add real file) + 真 gzip 进阶 (compresslevel / mtime) + 真 bz2 进阶 (compresslevel) + 真 lzma 真多 filter。
全 stdlib, 零模拟。
"""
import tarfile
import zipfile
import gzip
import bz2
import lzma
import os
import tempfile
import pytest


# ======================== tarfile 进阶 ========================
def test_tarfile_mode_gz():
    """真 tarfile 真 gz 模式"""
    with tempfile.TemporaryDirectory() as d:
        # 创 .tar.gz
        src = os.path.join(d, "data.txt")
        with open(src, "w") as f:
            f.write("compressible " * 100)
        tar_path = os.path.join(d, "archive.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(src, arcname="data.txt")
        # 真有 .gz
        assert os.path.getsize(tar_path) < os.path.getsize(src)
        # 读
        with tarfile.open(tar_path, "r:gz") as tar:
            members = tar.getmembers()
            assert len(members) == 1
            assert members[0].name == "data.txt"


def test_tarfile_mode_bz2():
    """真 tarfile 真 bz2 模式"""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "data.txt")
        with open(src, "w") as f:
            f.write("compressible " * 100)
        tar_path = os.path.join(d, "archive.tar.bz2")
        with tarfile.open(tar_path, "w:bz2") as tar:
            tar.add(src, arcname="data.txt")
        # 读
        with tarfile.open(tar_path, "r:bz2") as tar:
            members = tar.getmembers()
            assert members[0].name == "data.txt"


def test_tarfile_mode_xz():
    """真 tarfile 真 xz 模式"""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "data.txt")
        with open(src, "w") as f:
            f.write("compressible " * 100)
        tar_path = os.path.join(d, "archive.tar.xz")
        with tarfile.open(tar_path, "w:xz") as tar:
            tar.add(src, arcname="data.txt")
        with tarfile.open(tar_path, "r:xz") as tar:
            members = tar.getmembers()
            assert members[0].name == "data.txt"


def test_tarfile_extractfile():
    """真 extractfile 真读"""
    with tempfile.TemporaryDirectory() as d:
        # 创
        src = os.path.join(d, "content.txt")
        with open(src, "w") as f:
            f.write("file content here")
        tar_path = os.path.join(d, "test.tar")
        with tarfile.open(tar_path, "w") as tar:
            tar.add(src, arcname="content.txt")
        # 读 extractfile
        with tarfile.open(tar_path, "r") as tar:
            member = tar.getmember("content.txt")
            extracted = tar.extractfile(member)
            content = extracted.read().decode()
            assert content == "file content here"


# ======================== zipfile 进阶 ========================
def test_zipfile_compresslevel_high():
    """真 zipfile 真 compresslevel=9"""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "data.txt")
        with open(src, "w") as f:
            f.write("X" * 10000)
        zip_path = os.path.join(d, "high.zip")
        # level 9
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            zf.write(src, arcname="data.txt")
        # level 1
        zip_path_low = os.path.join(d, "low.zip")
        with zipfile.ZipFile(zip_path_low, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
            zf.write(src, arcname="data.txt")
        # 高压缩应 ≤ 低压缩
        assert os.path.getsize(zip_path) <= os.path.getsize(zip_path_low) + 100


def test_zipfile_add_file_real():
    """真 zipfile 真 add 真文件"""
    with tempfile.TemporaryDirectory() as d:
        # 创多个文件
        for i in range(3):
            with open(os.path.join(d, f"f{i}.txt"), "w") as f:
                f.write(f"file {i}")
        zip_path = os.path.join(d, "multi.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for i in range(3):
                zf.write(os.path.join(d, f"f{i}.txt"), arcname=f"f{i}.txt")
        # 验
        with zipfile.ZipFile(zip_path, "r") as zf:
            assert len(zf.namelist()) == 3


def test_zipfile_namelist_sorted():
    """真 namelist 真列"""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        path = f.name
    try:
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("z.txt", "z")
            zf.writestr("a.txt", "a")
            zf.writestr("m.txt", "m")
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            # 顺序保持写入顺序
            assert names == ["z.txt", "a.txt", "m.txt"]
    finally:
        os.unlink(path)


# ======================== gzip 进阶 ========================
def test_gzip_compresslevel():
    """真 gzip 真 compresslevel"""
    data = b"X" * 10000
    # level 1
    g1 = gzip.compress(data, compresslevel=1)
    # level 9
    g9 = gzip.compress(data, compresslevel=9)
    # 9 应 ≤ 1
    assert len(g9) <= len(g1)
    # round-trip
    assert gzip.decompress(g1) == data
    assert gzip.decompress(g9) == data


def test_gzip_mtime():
    """真 gzip 真 mtime 验证 header"""
    import struct
    data = b"data with mtime"
    # compress 接受 mtime
    compressed = gzip.compress(data, mtime=1234567890)
    # 直接 parse header (gzip 4-7 bytes 是 mtime little-endian)
    mtime_in_header = struct.unpack("<I", compressed[4:8])[0]
    assert mtime_in_header == 1234567890
    # round-trip
    assert gzip.decompress(compressed) == data


# ======================== bz2 进阶 ========================
def test_bz2_compresslevel():
    """真 bz2 真 compresslevel"""
    data = b"X" * 10000
    # level 1
    b1 = bz2.compress(data, compresslevel=1)
    # level 9
    b9 = bz2.compress(data, compresslevel=9)
    # 9 应 ≤ 1 (高压缩)
    assert len(b9) <= len(b1) + 100
    # round-trip
    assert bz2.decompress(b1) == data
    assert bz2.decompress(b9) == data


# ======================== lzma 真多 filter ========================
def test_lzma_filters():
    """真 lzma 真多 filter"""
    data = b"X" * 1000
    # LZMA2
    filters = [{"id": lzma.FILTER_LZMA2, "preset": 6}]
    compressed = lzma.compress(data, format=lzma.FORMAT_RAW, filters=filters)
    # round-trip
    assert lzma.decompress(compressed, format=lzma.FORMAT_RAW, filters=filters) == data
    # 压缩 < 原始
    assert len(compressed) < len(data)
