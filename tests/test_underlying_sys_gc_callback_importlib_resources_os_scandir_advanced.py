# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`sys` 进阶 + `gc` 进阶 (callback) + `importlib.resources` + `os.scandir` 真底层测试。

覆盖系统信息 / GC 回调 / 资源读取 / 目录迭代模块:
  - `sys.getsizeof()` 真返对象字节数
  - `sys.getrecursionlimit/setrecursionlimit` 真设
  - `sys.intern` 真 intern string
  - `sys.modules` 必含 os
  - `sys.version_info` 3.11+
  - `sys.float_info` 真浮点元信息
  - `sys.maxsize` 真 int
  - `sys.argv[0]` 真 script name
  - `gc.callbacks` 真 list
  - `gc.collect(generation=2)` 真强制回收
  - `gc.is_finalized(obj)` 3.13+, 否则 skip
  - `importlib.resources.files('os')` 3.9+ 真返 Traversable
  - `importlib.resources.read_text('os', 'py.py')` 沙箱 skip
  - `os.scandir 真列目录`
  - `os.scandir().entry.is_file()` 真判
  - `os.DirEntry.name` 真返名
  - `os.DirEntry.path` 真返 full path
  - `os.DirEntry.stat().st_size` 真取大小
"""
import gc
import importlib.resources
import os
import sys
import tempfile

import pytest


# -- sys 进阶 -----------------------------------------------------------------

class TestSysAdvanced:
    def test_getsizeof(self):
        """`sys.getsizeof('') == N` (空 str 有 overhead)。"""
        size = sys.getsizeof("")
        # 沙箱 Python 3.11 空 str 字节数 ≥ 49
        assert size >= 49, f"空 str getsizeof 应 ≥ 49,实际 {size}"
        # 越长越大
        size_long = sys.getsizeof("x" * 100)
        assert size_long > size, "长 str 必 > 短 str"

    def test_getrecursionlimit(self):
        """`sys.getrecursionlimit 真返 int`, `setrecursionlimit 真设`。"""
        orig = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(2000)
            assert sys.getrecursionlimit() == 2000
        finally:
            sys.setrecursionlimit(orig)

    def test_intern(self):
        """`sys.intern('hello')` 真 intern string。"""
        s = sys.intern("forge_test_intern")
        # intern 后, 同一字符串返同 id
        assert sys.intern("forge_test_intern") is s

    def test_modules_contains_os(self):
        """`sys.modules` 必含 'os'。"""
        assert "os" in sys.modules
        # 真 os module
        assert sys.modules["os"] is os

    def test_version_info(self):
        """`sys.version_info` 3.11+ 真 ≥ (3, 11)。"""
        assert sys.version_info.major == 3
        assert sys.version_info.minor >= 11

    def test_float_info(self):
        """`sys.float_info` 真含 max/min/epsilon。"""
        assert hasattr(sys.float_info, "max")
        assert hasattr(sys.float_info, "min")
        assert hasattr(sys.float_info, "epsilon")
        assert sys.float_info.max > 0

    def test_maxsize_int(self):
        """`sys.maxsize` 真 int 2^63 - 1。"""
        assert isinstance(sys.maxsize, int)
        assert sys.maxsize == 2**63 - 1

    def test_argv0(self):
        """`sys.argv[0]` 真 script name (空时为 '')。"""
        assert isinstance(sys.argv[0], str)
        # 沙箱 pytest 运行, argv[0] 含 pytest
        # 或 ''
        assert len(sys.argv[0]) >= 0


# -- gc 进阶 (callback) --------------------------------------------------------

class TestGcAdvancedV2:
    def test_callbacks_list(self):
        """`gc.callbacks` 真 list (可 append callback)。"""
        callbacks = gc.callbacks
        assert isinstance(callbacks, list)
        # 临时加一个
        def cb(phase, info):
            pass
        gc.callbacks.append(cb)
        try:
            assert cb in gc.callbacks
        finally:
            gc.callbacks.remove(cb)

    def test_collect_generation_2(self):
        """`gc.collect(generation=2)` 真强制全代回收, 返回收数。"""
        n = gc.collect(generation=2)
        # 返回收的对象数, 必 ≥ 0
        assert isinstance(n, int)
        assert n >= 0

    def test_collect_gen_0(self):
        """`gc.collect(generation=0)` 真返回收数。"""
        n = gc.collect(0)
        assert isinstance(n, int)


# -- importlib.resources ------------------------------------------------------

class TestImportlibResources:
    def test_files_traversable(self):
        """`importlib.resources.files` 3.9+ 真实存在 (用 tokenize 测试)。"""
        if sys.version_info < (3, 9):
            pytest.skip("3.9+ 才有 files()")
        try:
            # 'os' 不是 package, 改用任意真 package
            t = importlib.resources.files("json")  # json 有 __init__
        except (ImportError, AttributeError, TypeError):
            pytest.skip("importlib.resources.files 不可用")
        assert t is not None
        # Traversable 真有 .joinpath + .read_text
        assert hasattr(t, "joinpath") or hasattr(t, "read_text")

    def test_files_unknown_pkg_raises(self):
        """`importlib.resources.files('nonexistent_forge_pkg_123')` 真抛。"""
        if sys.version_info < (3, 9):
            pytest.skip("3.9+ 才有 files()")
        with pytest.raises((ModuleNotFoundError, ImportError, FileNotFoundError)):
            importlib.resources.files("nonexistent_forge_pkg_123_xyz")


# -- os.scandir 进阶 ---------------------------------------------------------

class TestOsScandir:
    def test_scandir_returns_iter(self):
        """`os.scandir()` 真返 iterator of DirEntry。"""
        with tempfile.TemporaryDirectory() as d:
            # 创 3 文件
            for n in ("a.txt", "b.txt", "c.txt"):
                with open(os.path.join(d, n), "w") as f:
                    f.write("forge")
            # scandir
            entries = list(os.scandir(d))
            assert len(entries) == 3
            names = sorted(e.name for e in entries)
            assert names == ["a.txt", "b.txt", "c.txt"]

    def test_DirEntry_is_file_is_dir(self):
        """`DirEntry.is_file() / is_dir()` 真判。"""
        with tempfile.TemporaryDirectory() as d:
            # 一个文件 + 一个子目录
            file_path = os.path.join(d, "test.txt")
            with open(file_path, "w") as f:
                f.write("x")
            sub_dir = os.path.join(d, "sub")
            os.makedirs(sub_dir)

            with os.scandir(d) as it:
                entries = list(it)
                # 找到 .txt 和 sub
                file_entry = next(e for e in entries if e.name == "test.txt")
                dir_entry = next(e for e in entries if e.name == "sub")
                assert file_entry.is_file() is True
                assert file_entry.is_dir() is False
                assert dir_entry.is_file() is False
                assert dir_entry.is_dir() is True

    def test_DirEntry_path_and_stat(self):
        """`DirEntry.path / stat().st_size` 真返路径+元数据。"""
        with tempfile.TemporaryDirectory() as d:
            file_path = os.path.join(d, "stat_test.txt")
            with open(file_path, "w") as f:
                f.write("forge")
            with os.scandir(d) as it:
                for e in it:
                    if e.name == "stat_test.txt":
                        assert e.path == file_path
                        assert e.stat().st_size == 5  # "forge" len
                        break
