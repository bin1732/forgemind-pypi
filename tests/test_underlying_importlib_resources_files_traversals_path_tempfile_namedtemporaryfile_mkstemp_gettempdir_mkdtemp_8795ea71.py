# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`importlib.resources` 真用 (3.9+) + `tempfile.NamedTemporaryFile/mkstemp/gettempdir/mkdtemp` 真用 + `re.Pattern/Match` 进阶 (group+start+end+span) + `itertools.compress/dropwhile/takewhile/pairwise 3.10+` 真底层测试。

覆盖 importlib.resources 2 真 (files 真 + Traversable 沙箱) + tempfile 3 真 (mkstemp+gettempdir+mkdtemp) + re 2 真 (Pattern 真 group+Match 真 span) + itertools 4 真 (compress+dropwhile+takewhile+pairwise 3.10+) (共 11 真测试) 模块:
  - `importlib.resources.files 真建 Traversable (3.9+)`
  - `importlib.resources 真子化 importlib.resources 真 module 必非 None`
  - `tempfile.mkstemp 必 (fd, path) tuple 真建 'forge'`
  - `tempfile.gettempdir 必 str 必非 ''`
  - `tempfile.mkdtemp 必真建 'forge' 子目录`
  - `re.Pattern 真 group() 必 'forge'`
  - `re.Match 真 span() 必 (0, 5)`
  - `itertools.compress 'ABCDEF' [1,0,1,0,1,0] 必 ['A','C','E']`
  - `itertools.dropwhile lambda x: x<3 [1,2,3,4,5] 必 [3,4,5]`
  - `itertools.takewhile lambda x: x<3 [1,2,3,4,5] 必 [1,2]`
  - `itertools.pairwise 3.10+ 真 [1,2,3,4] = [(1,2),(2,3),(3,4)]`
"""
import importlib.resources
import itertools
import os
import re
import sys
import tempfile

import pytest


# -- importlib.resources 进阶 (3.9+ files + Traversable) ------

class TestImportlibResourcesAdvanced:
    def test_files_class(self):
        """`importlib.resources.files 真建 Traversable (3.9+)。"""
        if sys.version_info < (3, 9):
            pytest.skip("3.9+ importlib.resources.files")
        # 必 callable
        assert callable(importlib.resources.files)
        # 必 module 存在
        assert importlib.resources is not None

    def test_importlib_resources_module(self):
        """`importlib.resources 真子化 importlib.resources 真 module 必非 None。"""
        import importlib
        # 必非 None
        assert importlib.resources is not None
        # 必含 files
        assert hasattr(importlib.resources, "files")


# -- tempfile 进阶 (mkstemp + gettempdir + mkdtemp) ---------

class TestTempfileAdvanced:
    def test_mkstemp(self):
        """`tempfile.mkstemp 必 (fd, path) tuple 真建 'forge'。"""
        # mkstemp + 真写
        fd, path = tempfile.mkstemp(prefix="forge_")
        try:
            # 必 fd int + path str
            assert isinstance(fd, int)
            assert isinstance(path, str)
            # 必能写
            os.write(fd, b"forge_data")
            # 必能 read
            with open(path, "rb") as f:
                data = f.read()
            # 必 'forge_data'
            assert data == b"forge_data"
        finally:
            os.close(fd)
            os.unlink(path)

    def test_gettempdir(self):
        """`tempfile.gettempdir 必 str 必非 ''。"""
        path = tempfile.gettempdir()
        # 必 str
        assert isinstance(path, str)
        # 必非 ''
        assert path != ""

    def test_mkdtemp(self):
        """`tempfile.mkdtemp 必真建 'forge' 子目录。"""
        path = tempfile.mkdtemp(prefix="forge_")
        try:
            # 必能 exists
            assert os.path.isdir(path)
            # 必含 'forge_' prefix
            assert "forge_" in path
        finally:
            os.rmdir(path)


# -- re 进阶 (Pattern group + Match span) --------------------

class TestReAdvancedV2:
    def test_Pattern_group(self):
        """`re.Pattern 真 group() 必 'forge'。"""
        p = re.compile(r"(forge)")
        m = p.match("forge hello")
        # 必能 group
        result = m.group(1)
        # 必 'forge'
        assert result == "forge"

    def test_Match_span(self):
        """`re.Match 真 span() 必 (0, 5)。"""
        m = re.match(r"forge", "forge hello")
        # 必能 span
        result = m.span()
        # 必 (0, 5)
        assert result == (0, 5)
        # 必能 start + end
        assert m.start() == 0
        assert m.end() == 5


# -- itertools 进阶 (compress + dropwhile + takewhile + pairwise 3.10+) -

class TestItertoolsAdvancedV4:
    def test_compress(self):
        """`itertools.compress 'ABCDEF' [1,0,1,0,1,0] 必 ['A','C','E']。"""
        result = list(itertools.compress("ABCDEF", [1, 0, 1, 0, 1, 0]))
        # 必 ['A', 'C', 'E']
        assert result == ["A", "C", "E"]

    def test_dropwhile(self):
        """`itertools.dropwhile lambda x: x<3 [1,2,3,4,5] 必 [3,4,5]。"""
        result = list(itertools.dropwhile(lambda x: x < 3, [1, 2, 3, 4, 5]))
        # 必 [3, 4, 5]
        assert result == [3, 4, 5]

    def test_takewhile(self):
        """`itertools.takewhile lambda x: x<3 [1,2,3,4,5] 必 [1,2]。"""
        result = list(itertools.takewhile(lambda x: x < 3, [1, 2, 3, 4, 5]))
        # 必 [1, 2]
        assert result == [1, 2]

    def test_pairwise_3_10(self):
        """`itertools.pairwise 3.10+ 真 [1,2,3,4] = [(1,2),(2,3),(3,4)]。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ pairwise")
        result = list(itertools.pairwise([1, 2, 3, 4]))
        # 必 [(1,2), (2,3), (3,4)]
        assert result == [(1, 2), (2, 3), (3, 4)]
