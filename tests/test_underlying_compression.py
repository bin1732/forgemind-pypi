# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真压缩 — zlib / gzip / bz2 / lzma / zipfile / tarfile 真压真解。
不走 mock, 1MB+ 随机数据走真算法, 验 100% 还原。
"""
import bz2
import gzip
import hashlib
import io
import lzma
import os
import random
import struct
import tarfile
import tempfile
import zipfile
import zlib
from pathlib import Path

import pytest


@pytest.fixture
def random_data():
    """1MB 真随机数据 (用 os.urandom, 不可压缩)"""
    return os.urandom(1024 * 1024)


def test_zlib_round_trip(random_data):
    """zlib 真压真解 1MB 随机数据 100% 还原"""
    compressed = zlib.compress(random_data, level=6)
    decompressed = zlib.decompress(compressed)
    assert decompressed == random_data, f"zlib round-trip 应 100%, 实际 {len(decompressed)}/{len(random_data)}"
    # 压缩比: 随机数据基本不压 (熵高), 压缩后应略大
    assert len(compressed) >= len(random_data) * 0.95


def test_gzip_file_round_trip(tmp_path, random_data):
    """gzip 真文件压 1MB + 真解"""
    src = tmp_path / "src.bin"
    gz = tmp_path / "dst.gz"
    src.write_bytes(random_data)
    with gzip.open(gz, "wb") as f:
        f.write(random_data)
    # 解
    with gzip.open(gz, "rb") as f:
        decompressed = f.read()
    assert decompressed == random_data


def test_gzip_real_file_extension(tmp_path, random_data):
    """gzip 文件真带 magic number (1f 8b)"""
    gz = tmp_path / "x.gz"
    with gzip.open(gz, "wb") as f:
        f.write(random_data)
    head = gz.read_bytes()[:2]
    assert head == b"\x1f\x8b", f"gzip magic 应 1f 8b, 实际 {head.hex()}"


def test_bz2_round_trip(random_data):
    """bz2 真压真解 1MB"""
    compressed = bz2.compress(random_data, compresslevel=9)
    decompressed = bz2.decompress(compressed)
    assert decompressed == random_data


def test_lzma_round_trip(random_data):
    """lzma 真压真解 1MB"""
    compressed = lzma.compress(random_data, preset=6)
    decompressed = lzma.decompress(compressed)
    assert decompressed == random_data


def test_compression_reduces_repetitive_data():
    """重复数据真能压到 10% 以下 (zlib 特点)"""
    repetitive = b"FORGEMIND" * 100_000  # 900KB 重复
    compressed = zlib.compress(repetitive, level=9)
    assert len(compressed) < len(repetitive) * 0.05, (
        f"重复数据应压到 <5%, 实际 {len(compressed)/len(repetitive):.1%}"
    )


def test_zipfile_round_trip(tmp_path, random_data):
    """zipfile 真压 + 真解 (含多个 file)"""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("file1.txt", random_data)
        zf.writestr("file2.txt", b"small text")
        zf.writestr("nested/dir/file3.bin", random_data[:1024])

    # 读
    with zipfile.ZipFile(zip_path, "r") as zf:
        assert "file1.txt" in zf.namelist()
        assert "file2.txt" in zf.namelist()
        assert "nested/dir/file3.bin" in zf.namelist()
        assert zf.read("file1.txt") == random_data
        assert zf.read("file2.txt") == b"small text"
        assert zf.read("nested/dir/file3.bin") == random_data[:1024]


def test_tarfile_round_trip(tmp_path, random_data):
    """tarfile 真打包 + 真解 (无压缩)"""
    tar_path = tmp_path / "test.tar"
    src1 = tmp_path / "src1.bin"
    src2 = tmp_path / "src2.txt"
    src1.write_bytes(random_data)
    src2.write_text("hello")
    with tarfile.open(tar_path, "w") as tf:
        tf.add(src1, arcname="data1.bin")
        tf.add(src2, arcname="readme.txt")

    # 解
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    with tarfile.open(tar_path, "r") as tf:
        tf.extractall(extract_dir)
    assert (extract_dir / "data1.bin").read_bytes() == random_data
    assert (extract_dir / "readme.txt").read_text() == "hello"


def test_tarfile_with_gz_compression(tmp_path, random_data):
    """tarfile + gzip 真压 + 真解"""
    tar_gz = tmp_path / "test.tar.gz"
    src = tmp_path / "src.bin"
    src.write_bytes(random_data)
    with tarfile.open(tar_gz, "w:gz") as tf:
        tf.add(src, arcname="data.bin")

    # 解
    with tarfile.open(tar_gz, "r:gz") as tf:
        members = tf.getnames()
        assert "data.bin" in members
        f = tf.extractfile("data.bin")
        assert f is not None
        extracted = f.read()
    assert extracted == random_data


def test_gzip_text_compresses_well():
    """真文本 gzip 应压到 30% 以下 (高重复)"""
    text = (b"the quick brown fox jumps over the lazy dog\n" * 1000)
    compressed = gzip.compress(text, compresslevel=6)
    assert len(compressed) < len(text) * 0.3, (
        f"文本应压到 <30%, 实际 {len(compressed)/len(text):.1%}"
    )


def test_hashlib_sha256_known_value():
    """sha256 真算已知字符串真匹配 (真 RFC)"""
    # SHA256("abc") = ba7816bf8f01cfea414140de5dae2223b04...
    h = hashlib.sha256(b"abc").hexdigest()
    assert h == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", (
        f"SHA256('abc') 应 = ba7816..., 实际 {h[:20]}"
    )


def test_md5_known_value():
    """md5 真算已知字符串真匹配"""
    h = hashlib.md5(b"abc").hexdigest()
    assert h == "900150983cd24fb0d6963f7d28e17f72", f"MD5('abc') 应 = 900150..., 实际 {h[:20]}"


def test_compression_incompressible_expands_slightly():
    """随机数据真不压 (zlib 头部开销, 略涨)"""
    rand = os.urandom(10240)
    compressed = zlib.compress(rand, level=1)  # 最低压缩
    # 头部 + 不压块 → 略大
    assert len(compressed) >= len(rand), (
        f"不压数据应略涨, 实际 {len(rand)} → {len(compressed)}"
    )
    # 但解回来 100% 一致
    assert zlib.decompress(compressed) == rand
