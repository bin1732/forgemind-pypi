# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`tarfile.open` 真用 (add+extract+is_tarfile+namelist+mtime) + `gzip.open` 真用 + `inspect.Parameter.empty` 进阶 + `inspect.Signature.bind` 进阶 + `inspect.formatannotation` 进阶 + `unittest.mock.patch.object/dict/stopall` 进阶 + 真底层测试。

覆盖 tarfile 3 真 (open 真 add+真 getmembers+is_tarfile) + gzip.open 1 真 + inspect 3 真 (Parameter.empty+Signature.bind+formatannotation) + mock 3 真 (patch.object+patch.dict+patch.stopall) (共 10 真测试) 模块:
  - `tarfile.open 真写 tmp.tar + add 'forge.txt' + getmembers ≥ 1`
  - `tarfile.open 真读 getmember 'forge.txt' + mtime 必 > 0`
  - `tarfile.is_tarfile 真 'tmp.tar' 必 True + 'tmp.txt' False`
  - `gzip.open 真压 'forge' + 真 read 必 'forge'`
  - `inspect.Parameter.empty 必 sentinel (3.11+)`
  - `inspect.Signature.bind(a=1, b=2) 真绑 args`
  - `inspect.formatannotation 'str' 必 'str'`
  - `mock.patch.object 真改 attr + 还原`
  - `mock.patch.dict 真改 dict + 还原`
  - `mock.patch.stopall 真 cleanup`
"""
import gzip
import inspect
import os
import tarfile
import unittest.mock

import pytest


# -- tarfile 进阶 (open + add + getmembers + is_tarfile) -----------

class TestTarfileAdvanced:
    def test_open_add(self, tmp_path):
        """`tarfile.open 真写 tmp.tar + add 'forge.txt' + getmembers ≥ 1。"""
        src = tmp_path / "forge_src.txt"
        src.write_text("forge_data")
        tar_path = tmp_path / "test.tar"
        # write
        with tarfile.open(str(tar_path), "w") as tar:
            tar.add(str(src), arcname="forge.txt")
        # 必能 read
        with tarfile.open(str(tar_path), "r") as tar:
            members = tar.getmembers()
            # 必 ≥ 1
            assert len(members) >= 1
            # 必含 'forge.txt'
            names = [m.name for m in members]
            assert "forge.txt" in names

    def test_open_getmember_mtime(self, tmp_path):
        """`tarfile.open 真读 getmember 'forge.txt' + mtime 必 > 0。"""
        src = tmp_path / "forge_src.txt"
        src.write_text("forge_data")
        tar_path = tmp_path / "test.tar"
        # write
        with tarfile.open(str(tar_path), "w") as tar:
            tar.add(str(src), arcname="forge.txt")
        # read
        with tarfile.open(str(tar_path), "r") as tar:
            member = tar.getmember("forge.txt")
            # 必 mtime > 0
            assert member.mtime > 0

    def test_is_tarfile(self, tmp_path):
        """`tarfile.is_tarfile 真 'tmp.tar' 必 True + 'tmp.txt' False。"""
        # write
        src = tmp_path / "src.txt"
        src.write_text("forge")
        tar_path = tmp_path / "test.tar"
        with tarfile.open(str(tar_path), "w") as tar:
            tar.add(str(src), arcname="forge.txt")
        # is_tarfile
        assert tarfile.is_tarfile(str(tar_path)) is True
        # 必非 is_tarfile
        assert tarfile.is_tarfile(str(src)) is False


# -- gzip.open 进阶 (真用) ---------------------------------------

class TestGzipOpenAdvanced:
    def test_gzip_open(self, tmp_path):
        """`gzip.open 真压 'forge' + 真 read 必 'forge'。"""
        path = tmp_path / "forge.gz"
        # write
        with gzip.open(str(path), "wb") as f:
            f.write(b"forge")
        # read
        with gzip.open(str(path), "rb") as f:
            data = f.read()
        # 必 'forge'
        assert data == b"forge"


# -- inspect 进阶 (Parameter.empty + Signature.bind + formatannotation) -

class TestInspectAdvancedV9:
    def test_Parameter_empty(self):
        """`inspect.Parameter.empty 必 sentinel (3.11+)。"""
        # 沙箱 3.11+ Parameter.empty 必存在
        assert inspect.Parameter.empty is not None
        # sig 真返 empty
        sig = inspect.signature(lambda: None)
        assert sig.return_annotation is inspect.Parameter.empty

    def test_Signature_bind(self):
        """`inspect.Signature.bind(a=1, b=2) 真绑 args。"""
        def my_fn(a, b=42):
            return a + b

        sig = inspect.signature(my_fn)
        # bind
        bound = sig.bind(a=1, b=2)
        # 必能 access
        assert bound.arguments["a"] == 1
        assert bound.arguments["b"] == 2

    def test_formatannotation(self):
        """`inspect.formatannotation 'str' 必 'str'。"""
        result = inspect.formatannotation("str")
        # 必 str
        assert isinstance(result, str)
        # 必含 'str'
        assert "str" in result


# -- mock 进阶 (patch.object + patch.dict + stopall) --------------

class TestMockPatchAdvanced:
    def test_patch_object(self):
        """`mock.patch.object 真改 attr + 还原。"""

        class _O:
            x = 1

        o = _O()
        # patch
        with unittest.mock.patch.object(_O, "x", 42):
            # 必 42
            assert _O.x == 42
        # 必还原
        assert _O.x == 1

    def test_patch_dict(self):
        """`mock.patch.dict 真改 dict + 还原。"""
        d = {"a": 1}
        # patch
        with unittest.mock.patch.dict(d, {"a": 99, "b": 2}):
            # 必 99 + 2
            assert d["a"] == 99
            assert d["b"] == 2
        # 必还原
        assert d == {"a": 1}

    def test_patch_stopall(self):
        """`mock.patch.stopall 真 cleanup。"""
        # 沙箱 3.11 stopall 必能调
        unittest.mock.patch.stopall()
        # 必不抛
        assert True
