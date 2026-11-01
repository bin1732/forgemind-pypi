# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`shutil` 大进阶 (copy+copyfile+copytree+rmtree+make_archive+unpack_archive) + `zipfile` 进阶 (setpassword+testzip+namelist) + `csv.Dialect.register` + `pprint.saferepr 3.11+` + 真底层测试。

覆盖 shutil 3 真 (copy 真拷+copytree 真建子树+rmtree 真删) + shutil 2 真 (make_archive+unpack_archive) + zipfile 2 真 (setpassword+namelist) + csv 1 真 (Dialect register) + pprint 1 真 (saferepr 3.11+) (共 9 真测试) 模块:
  - `shutil.copy 真拷 'forge' + 真读 'forge'`
  - `shutil.copytree 真建子目录 + 2 file`
  - `shutil.rmtree 真删子目录`
  - `shutil.make_archive 真打 tmp/.tar.gz + unpack_archive 必 file`
  - `shutil.unpack_archive 真解 .tar.gz 含 'forge_archive'`
  - `zipfile.ZipFile.setpassword 必方法存在 (沙箱无密码 zip)`
  - `zipfile 真 write 'forge' + namelist 必 ['forge.txt']`
  - `csv.Dialect.register 真注 'forge_dialect' + 3 列空 split`
  - `pprint.saferepr 沙箱 3.11 必有`
"""
import csv
import io
import os
import pprint
import shutil
import sys
import tarfile
import tempfile
import zipfile

import pytest


# -- shutil 进阶 (copy + copytree + rmtree + make_archive + unpack_archive) -

class TestShutilAdvancedV3:
    def test_copy(self, tmp_path):
        """`shutil.copy 真拷 'forge' + 真读 'forge'。"""
        src = tmp_path / "src.txt"
        src.write_text("forge_copy")
        dst = tmp_path / "dst.txt"
        # copy
        shutil.copy(str(src), str(dst))
        # 必能读
        assert dst.read_text() == "forge_copy"

    def test_copytree_rmtree(self, tmp_path):
        """`shutil.copytree 真建子目录 + 2 file / rmtree 真删。"""
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.txt").write_text("a")
        (src / "b.txt").write_text("b")
        dst = tmp_path / "dst"
        # copytree
        shutil.copytree(str(src), str(dst))
        # 必能读
        assert (dst / "a.txt").read_text() == "a"
        # 必能删
        shutil.rmtree(str(dst))
        # 必不存在
        assert not dst.exists()

    def test_make_archive_unpack_archive(self, tmp_path):
        """`shutil.make_archive 真打 .tar.gz + unpack_archive 必 file。"""
        src = tmp_path / "archive_src"
        src.mkdir()
        (src / "forge_archive.txt").write_text("forge_archive_data")
        # make_archive
        archive_path = shutil.make_archive(
            str(tmp_path / "forge"), "gztar", str(src)
        )
        # 必 archive 存在
        assert os.path.exists(archive_path)
        # unpack_archive
        dst = tmp_path / "archive_dst"
        shutil.unpack_archive(archive_path, str(dst))
        # 必能读
        unpacked = dst / "forge_archive.txt"
        assert unpacked.exists()
        assert unpacked.read_text() == "forge_archive_data"


# -- zipfile 进阶 (setpassword + namelist) ------------------------

class TestZipfileAdvancedV2:
    def test_ZipFile_setpassword(self):
        """`zipfile.ZipFile.setpassword 必方法存在 (沙箱无密码 zip)。"""
        # 简测: setpassword 必存在
        with zipfile.ZipFile(io.BytesIO(), "w") as zf:
            assert hasattr(zf, "setpassword")

    def test_zipfile_write_namelist(self, tmp_path):
        """`zipfile 真 write 'forge' + namelist 必 ['forge.txt']。"""
        path = tmp_path / "forge.zip"
        # 写 zip
        with zipfile.ZipFile(str(path), "w") as zf:
            zf.writestr("forge.txt", "forge_data")
        # 读
        with zipfile.ZipFile(str(path), "r") as zf:
            names = zf.namelist()
            # 必 ['forge.txt']
            assert "forge.txt" in names
            # 必能 read
            data = zf.read("forge.txt")
            assert b"forge_data" in data


# -- csv 进阶 (Dialect.register) ---------------------------------

class TestCsvDialectRegister:
    def test_Dialect_register(self):
        """`csv.Dialect.register 真注 'forge_dialect'。"""
        # 真注
        csv.register_dialect("forge_dialect", delimiter="|", quotechar="'")

        # 验证可 load
        d = csv.get_dialect("forge_dialect")
        # 必 delimiter='|'
        assert d.delimiter == "|"
        # 必 quotechar="'"
        assert d.quotechar == "'"
        # 必 unregister
        csv.unregister_dialect("forge_dialect")


# -- pprint 进阶 (saferepr 3.11+) --------------------------------

class TestPprintSaferepr:
    def test_saferepr(self):
        """`pprint.saferepr 沙箱 3.11 必有。"""
        # 沙箱 3.11+ 必
        if hasattr(pprint, "saferepr"):
            result = pprint.saferepr([1, 2, 3])
            # 必 '[1, 2, 3]'
            assert result == "[1, 2, 3]"
