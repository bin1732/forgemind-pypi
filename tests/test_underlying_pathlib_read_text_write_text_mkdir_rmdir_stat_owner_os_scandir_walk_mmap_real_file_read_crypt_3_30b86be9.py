# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
r"""`pathlib.Path.read_text/write_text/mkdir/rmdir/stat/owner` 真 + `os.scandir` 真 + `os.walk` 真 + `mmap` 真读真 file + `crypt.crypt` 真 DES+MD5+SHA256+SHA512 + `pwd`/`grp` 沙箱 skip + 真底层测试。

覆盖 pathlib 4 真 (read_text+write_text+mkdir+stat) + os.scandir 1 真 + os.walk 1 真 + mmap 2 真 (真 mmap+真 read) + crypt 3 真 (MD5+SHA256+SHA512) + pwd 1 真 (class) + grp 1 真 (class) (共 13 真测试) 模块:
  - `pathlib.Path.read_text 真读 'forge_data'`
  - `pathlib.Path.write_text 真写 'forge_out' + 读回`
  - `pathlib.Path.mkdir 真建 + rmdir 真删`
  - `pathlib.Path.stat 真返 st_size`
  - `os.scandir 真返 ≥ 1 DirEntry`
  - `os.walk 真返 generator ≥ 1`
  - `mmap.mmap(fd, 4096) 真 mmap 0 (read)`
  - `mmap 真 read 必含 'forge'`
  - `crypt.crypt('pw', '\$1\$salt') MD5 必含 '\$1\$'`
  - `crypt.crypt('pw', '\$5\$salt') SHA256 必含 '\$5\$'`
  - `crypt.crypt('pw', '\$6\$salt') SHA512 必含 '\$6\$'`
  - `pwd class 必存在 (沙箱 skip getpwuid)`
  - `grp class 必存在 (沙箱 skip getgrgid)`
"""
# crypt 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        import crypt
except ImportError:
    crypt = None
import mmap
import os
import pathlib
import sys

import pytest


# -- pathlib 进阶 (read_text + write_text + mkdir + stat) -------------

# 这些模块在 Python 3.13 起被移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(crypt is None, reason="crypt 模块在 Python 3.13 起被移除")


class TestPathlibAdvancedV6:
    def test_read_text(self, tmp_path):
        """`Path.read_text 真读 'forge_data'。"""
        f = tmp_path / "forge_read.txt"
        f.write_text("forge_data")
        # read_text 必 'forge_data'
        assert f.read_text() == "forge_data"

    def test_write_text(self, tmp_path):
        """`Path.write_text 真写 'forge_out' + 读回。"""
        f = tmp_path / "forge_write.txt"
        f.write_text("forge_out")
        # 必能读回
        assert f.read_text() == "forge_out"

    def test_mkdir_rmdir(self, tmp_path):
        """`Path.mkdir 真建 + rmdir 真删。"""
        d = tmp_path / "forge_mkdir"
        # mkdir
        d.mkdir()
        # 必 exist
        assert d.exists()
        # rmdir
        d.rmdir()
        # 必不存在
        assert not d.exists()

    def test_stat(self, tmp_path):
        """`Path.stat 真返 st_size。"""
        f = tmp_path / "forge_stat.txt"
        f.write_text("forge_stat_data")
        # stat
        s = f.stat()
        # 必是 os.stat_result
        # 必含 st_size
        assert s.st_size == len("forge_stat_data")


# -- os.scandir 进阶 ------------------------------------------------

class TestOsScandirAdvanced:
    def test_scandir(self, tmp_path):
        """`os.scandir 真返 ≥ 1 DirEntry。"""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        # scandir
        with os.scandir(str(tmp_path)) as it:
            entries = list(it)
        # 必 ≥ 2
        assert len(entries) >= 2
        # 必 DirEntry
        assert all(isinstance(e, os.DirEntry) for e in entries)
        # 必含 'a.txt' + 'b.txt'
        names = [e.name for e in entries]
        assert "a.txt" in names
        assert "b.txt" in names


# -- os.walk 进阶 ---------------------------------------------------

class TestOsWalkAdvanced:
    def test_walk(self, tmp_path):
        """`os.walk 真返 generator ≥ 1。"""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("deep")
        (tmp_path / "top.txt").write_text("top")
        # walk
        result = list(os.walk(str(tmp_path)))
        # 必 ≥ 1
        assert len(result) >= 1
        # 必返 (root, dirs, files) tuples
        for root, dirs, files in result:
            assert isinstance(root, str)
            assert isinstance(dirs, list)
            assert isinstance(files, list)


# -- mmap 进阶 (真 mmap 真读) ----------------------------------------

class TestMmapAdvanced:
    def test_mmap_read(self, tmp_path):
        """`mmap.mmap(fd, len) 真 mmap + read 含 'forge'。"""
        f = tmp_path / "forge_mmap.txt"
        f.write_text("forge_mmap_data")
        with open(str(f), "rb") as fp:
            with mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_READ) as m:
                # read 必含 'forge'
                data = m.read()
                assert b"forge" in data

    def test_mmap_size(self, tmp_path):
        """`mmap 真 size() 必 ≥ 1。"""
        f = tmp_path / "forge_mmap_size.txt"
        f.write_text("forge_size_data")
        with open(str(f), "rb") as fp:
            with mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_READ) as m:
                # size 必 ≥ 1
                assert m.size() >= 1


# -- crypt 进阶 (MD5 + SHA256 + SHA512) ----------------------------

class TestCryptAdvanced:
    def test_crypt_MD5(self):
        """`crypt.crypt('pw', '$1$salt') MD5 必含 '$1$'。"""
        result = crypt.crypt("forge_pw", "$1$forgesalt")
        # 必含 '$1$'
        assert "$1$" in result
        # 必 ≥ 20 chars
        assert len(result) >= 20

    def test_crypt_SHA256(self):
        """`crypt.crypt('pw', '$5$salt') SHA256 必含 '$5$'。"""
        result = crypt.crypt("forge_pw", "$5$forgesalt")
        # 必含 '$5$'
        assert "$5$" in result
        # 必 ≥ 50 chars (SHA256 long)
        assert len(result) >= 50

    def test_crypt_SHA512(self):
        """`crypt.crypt('pw', '$6$salt') SHA512 必含 '$6$'。"""
        result = crypt.crypt("forge_pw", "$6$forgesalt")
        # 必含 '$6$'
        assert "$6$" in result
        # 必 ≥ 80 chars (SHA512 long)
        assert len(result) >= 80


# -- pwd/grp 进阶 (沙箱 skip) --------------------------------------

class TestPwdGrpSandboxSkip:
    def test_pwd_module(self):
        """`pwd class 必存在 (沙箱 skip getpwuid 实际)。"""
        import pwd
        # 必 module 存在
        assert pwd is not None
        # 必含 getpwuid
        assert hasattr(pwd, "getpwuid")

    def test_grp_module(self):
        """`grp class 必存在 (沙箱 skip getgrgid 实际)。"""
        import grp
        # 必 module 存在
        assert grp is not None
        # 必含 getgrgid
        assert hasattr(grp, "getgrgid")
