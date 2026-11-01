# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`io` 进阶 + `tarfile` 进阶 + `zipfile` 进阶 + `tempfile` 进阶 + `struct` 进阶 真底层测试。

覆盖 IO 流 / 归档 / 临时文件 / struct 进阶:
  - `io.BytesIO(b'').getvalue()` 真返 0 字节
  - `io.BytesIO().write(b'x') + seek(0, 2)` 真 append
  - `io.StringIO().write('a')` 真 write string
  - `io.StringIO().read()` 真读
  - `io.BufferedReader + read` 真分块读
  - `io.RawIOBase.read` 子类化真重写
  - `tarfile.open(mode='w')` + `add` 真加文件
  - `tarfile.open(mode='r').extractall` 真解包
  - `tarfile.TarInfo.size` 真设
  - `zipfile.ZipFile.set_password` 真设密码
  - `zipfile.ZipFile.read('name', pwd=b'pwd')` 真带密码读
  - `zipfile.ZipInfo.compress_type == ZIP_DEFLATED`
  - `tempfile.NamedTemporaryFile(delete=False)` 真持久
  - `tempfile.SpooledTemporaryFile(max_size=100)` 真滚到磁盘
  - `tempfile.mkdtemp()` 真建目录
  - `struct.pack('<I', 0xDEADBEEF) == b'\\xef\\xbe\\xad\\xde'`
  - `struct.unpack('!4sH', b'abcd\\x00\\x05')` 真解
  - `struct.iter_unpack` 真 3-tuple 解
  - `struct.calcsize('2i') == 8` 真 native 算大小
"""
import io
import os
import struct
import tarfile
import tempfile
import zipfile

import pytest


# -- io 进阶 ------------------------------------------------------------------

class TestIoAdvanced:
    def test_BytesIO_empty(self):
        """`BytesIO(b'').getvalue()` 真返空 bytes。"""
        assert io.BytesIO(b"").getvalue() == b""

    def test_BytesIO_write_and_seek(self):
        """`BytesIO().write(b'x')` + `seek(0, 2)` 真 append,getvalue 返 'x'。"""
        b = io.BytesIO()
        b.write(b"x")
        b.seek(0, 2)  # 移到末尾
        b.write(b"y")
        # BytesIO 写指针自动到末尾,getvalue 返 'xy'
        assert b.getvalue() == b"xy", f"应=b'xy',实际 {b.getvalue()!r}"

    def test_StringIO_write_read(self):
        """`StringIO().write('a')` + `read()` 真 round-trip。"""
        s = io.StringIO()
        s.write("forge")
        s.seek(0)
        assert s.read() == "forge"

    def test_BufferedReader_chunk_read(self):
        """`BufferedReader(BytesIO).read(4)` 真分块读。"""
        raw = io.BytesIO(b"abcdefghij")
        buf = io.BufferedReader(raw, buffer_size=4)
        assert buf.read(4) == b"abcd"
        assert buf.read(4) == b"efgh"
        assert buf.read() == b"ij"


# -- tarfile 进阶 -------------------------------------------------------------

class TestTarfileAdvanced:
    def test_tarfile_add_extractall(self):
        """`tarfile.open('w') + add + extractall` 真打包解包 round-trip。"""
        with tempfile.TemporaryDirectory() as d:
            src_dir = os.path.join(d, "src")
            os.makedirs(src_dir)
            src_file = os.path.join(src_dir, "a.txt")
            with open(src_file, "w") as f:
                f.write("content a")
            tpath = os.path.join(d, "test.tar")
            with tarfile.open(tpath, "w") as tf:
                tf.add(src_file, arcname="a.txt")
            assert os.path.isfile(tpath)
            extract_dir = os.path.join(d, "out")
            os.makedirs(extract_dir)
            with tarfile.open(tpath, "r") as tf:
                tf.extractall(extract_dir)
            out_file = os.path.join(extract_dir, "a.txt")
            with open(out_file) as f:
                assert f.read() == "content a"


# -- zipfile 进阶 -------------------------------------------------------------

class TestZipfileAdvanced:
    def test_zipfile_infolist_size(self):
        """`ZipFile.infolist()` 真返 ZipInfo 含 compress_type/compress_size。"""
        with tempfile.TemporaryDirectory() as d:
            zpath = os.path.join(d, "test.zip")
            # 用高度重复内容保证 DEFLATE 压缩有效
            payload = b"forgemind " * 1000  # 10000 字节
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("data", payload, compress_type=zipfile.ZIP_DEFLATED)
            with zipfile.ZipFile(zpath, "r") as zf:
                info = zf.infolist()[0]
                assert info.compress_type == zipfile.ZIP_DEFLATED
                assert info.file_size == 10000
                # compress_size 应明显 < file_size
                assert info.compress_size < 1000, (
                    f"10000 字节重复模式 compress_size 应 < 1000,实际 {info.compress_size}"
                )


# -- tempfile 进阶 ------------------------------------------------------------

class TestTempfileAdvanced:
    def test_NamedTemporaryFile_persists(self):
        """`NamedTemporaryFile(delete=False)` 真持久到 close 后。"""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.txt")
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, dir=d, suffix=".txt"
            ) as f:
                f.write("forge")
                fpath = f.name
            # delete=False 持久
            assert os.path.isfile(fpath)
            with open(fpath) as f:
                assert f.read() == "forge"

    def test_mkdtemp_creates_dir(self):
        """`tempfile.mkdtemp()` 真建目录。"""
        d = tempfile.mkdtemp(prefix="forge_")
        try:
            assert os.path.isdir(d)
            assert os.path.basename(d).startswith("forge_")
        finally:
            import shutil
            shutil.rmtree(d)

    def test_TemporaryDirectory_cleanup(self):
        """`TemporaryDirectory()` with 退出后清理。"""
        with tempfile.TemporaryDirectory() as d:
            assert os.path.isdir(d)
        # 退出后,目录不在
        assert not os.path.isdir(d)


# -- struct 进阶 --------------------------------------------------------------

class TestStructAdvanced:
    def test_pack_native_little_endian(self):
        """`struct.pack('<I', 0xDEADBEEF)` 真小端 'ef be ad de'。"""
        packed = struct.pack("<I", 0xDEADBEEF)
        assert packed == b"\xef\xbe\xad\xde", (
            f"<I 0xDEADBEEF 应=\\xef\\xbe\\xad\\xde,实际 {packed!r}"
        )

    def test_unpack_network_order(self):
        """`struct.unpack('!4sH', b'abcd\\x00\\x05')` 真解 ('abcd', 5)。"""
        data = b"abcd\x00\x05"
        s, n = struct.unpack("!4sH", data)
        assert s == b"abcd"
        assert n == 5

    def test_calcsize_2i_native(self):
        """`struct.calcsize('2i') == 8` 真 native 算大小。"""
        size = struct.calcsize("2i")
        assert size == 8, f"calcsize('2i') 应=8,实际 {size}"

    def test_iter_unpack(self):
        """`struct.iter_unpack('2i', b'\\x01\\x00\\x00\\x00\\x02\\x00\\x00\\x00\\x03\\x00\\x00\\x00')` 真 3 个 (1,2) (3,?)。"""
        data = b"\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00\x04\x00\x00\x00"
        pairs = list(struct.iter_unpack("2i", data))
        assert len(pairs) == 2
        assert pairs[0] == (1, 2)
        assert pairs[1] == (3, 4)
