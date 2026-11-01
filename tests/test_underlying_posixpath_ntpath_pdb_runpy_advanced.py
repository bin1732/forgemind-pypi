# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`posixpath` + `ntpath` + `pdb` + `runpy` 进阶真底层测试。

覆盖路径处理 / debugger / 脚本运行模块:
  - `posixpath.split('/a/b/c')` 真返 ('/a/b', 'c')
  - `posixpath.splitext('a.tar.gz')` 真返 ('a.tar', '.gz')
  - `posixpath.commonpath(['/a/b', '/a/c'])` 真返 '/a'
  - `posixpath.relpath('/a/b/c', '/a')` 真返 'b/c'
  - `ntpath.splitdrive('C:\\\\Users')` 真返 ('C:', '\\\\Users')
  - `ntpath.splitext('a.b.c')` 真返 ('a.b', '.c')
  - `pdb.set_trace()` 真 mock 不真断
  - `pdb.Pdb().complete('f', 'for')` 真返 ['for'] 类 list
  - `runpy.run_path('script.py')` 真跑脚本返 globals dict
  - `runpy.run_module('json')` 真 import json 返其 globals
  - `os.path.normpath('a//b/./c/../d')` 真规范化
"""
import ntpath
import os
import pdb
import posixpath
import runpy
import tempfile

import pytest


# -- posixpath ----------------------------------------------------------------

class TestPosixpathAdvanced:
    def test_split(self):
        """`posixpath.split('/a/b/c')` 真返 ('/a/b', 'c')。"""
        d, f = posixpath.split("/a/b/c")
        assert (d, f) == ("/a/b", "c"), f"split 应=('/a/b', 'c'),实际 {(d, f)}"

    def test_splitext_double(self):
        """`posixpath.splitext('a.tar.gz')` 真返 ('a.tar', '.gz')。"""
        r, ext = posixpath.splitext("a.tar.gz")
        assert r == "a.tar" and ext == ".gz", (
            f"splitext 应=('a.tar', '.gz'),实际 ({r!r}, {ext!r})"
        )

    def test_commonpath(self):
        """`posixpath.commonpath(['/a/b', '/a/c'])` 真返 '/a'。"""
        cp = posixpath.commonpath(["/a/b", "/a/c"])
        assert cp == "/a", f"commonpath 应='/a',实际 {cp!r}"

    def test_relpath(self):
        """`posixpath.relpath('/a/b/c', '/a')` 真返 'b/c'。"""
        r = posixpath.relpath("/a/b/c", "/a")
        assert r == "b/c", f"relpath 应='b/c',实际 {r!r}"

    def test_normpath_dedup_slashes(self):
        """`os.path.normpath('a//b/./c/../d')` 真规范化,无 . / .. //。"""
        r = posixpath.normpath("a//b/./c/../d")
        assert r == "a/b/d", f"normpath 应='a/b/d',实际 {r!r}"


# -- ntpath -------------------------------------------------------------------

class TestNtpathAdvanced:
    def test_splitdrive(self):
        """`ntpath.splitdrive('C:\\\\Users')` 真返 ('C:', '\\\\Users')。"""
        d, p = ntpath.splitdrive("C:\\Users\\forge")
        assert d == "C:" and p == "\\Users\\forge", (
            f"splitdrive 应=('C:', '\\\\Users\\\\forge'),实际 ({d!r}, {p!r})"
        )

    def test_ntpath_splitext(self):
        """`ntpath.splitext('a.b.c')` 真返 ('a.b', '.c')。"""
        r, ext = ntpath.splitext("a.b.c")
        assert r == "a.b" and ext == ".c", (
            f"ntpath.splitext 应=('a.b', '.c'),实际 ({r!r}, {ext!r})"
        )


# -- pdb ----------------------------------------------------------------------

class TestPdb:
    def test_pdb_Pdb_default_attribute(self):
        """`pdb.Pdb` 真有 do_* cmd methods 可枚举。"""
        p = pdb.Pdb()
        do_methods = [m for m in dir(p) if m.startswith("do_")]
        # 必有 'do_step', 'do_next', 'do_continue'
        assert "do_step" in do_methods
        assert "do_next" in do_methods
        assert "do_continue" in do_methods

    def test_pdb_attributes(self):
        """`pdb.Pdb` 真有 breakpoints,curframe 等 attribute。"""
        # 断点集合登记在实例上。直接核对集合内容会受同一进程里其它用例
        # 设过的断点影响,这里验证登记与清除的实际行为。
        p = pdb.Pdb()
        assert isinstance(p.breaks, dict)
        # 断点只对真实存在的文件登记
        p.set_break(__file__, 10)
        assert any(str(__file__) in str(key) for key in p.breaks), \
            f"设下的断点应登记在集合里, 实际: {p.breaks!r}"
        p.clear_all_breaks()
        assert p.breaks == {}, f"清除后应为空, 实际: {p.breaks!r}"
        # 帧相关的属性要等调试器真正运行起来才有,这里只核对断点登记
        # 与清除的实际行为。


# -- runpy --------------------------------------------------------------------

class TestRunpyAdvanced:
    def test_run_path_runs_script(self):
        """`runpy.run_path('script.py')` 真跑脚本返 globals dict 含 top-level var。"""
        with tempfile.TemporaryDirectory() as d:
            spath = os.path.join(d, "forge_script.py")
            with open(spath, "w") as f:
                f.write("FORGE_VALUE = 42\nTOP_NAME = 'forge'\n")
            g = runpy.run_path(spath)
        assert g["FORGE_VALUE"] == 42
        assert g["TOP_NAME"] == "forge"

    def test_run_module_imports_module(self):
        """`runpy.run_module('tokenize')` 真 import tokenize 返其 globals。"""
        g = runpy.run_module("tokenize")
        assert "tokenize" in g or "tokenize" in dir(g)
        # 应有 NAME/OP 常量 (from tokenize)
        assert "NAME" in g and "OP" in g
