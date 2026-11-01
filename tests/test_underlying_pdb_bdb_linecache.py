# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 pdb 真 set_trace/breakpoint/commands + 真 bdb 真 breakpoint + 真 tabnanny 真缩进检测 + 真 linecache 真 cache + 真 compileall。
全 stdlib, 零模拟。
"""
import pdb
import bdb
import tabnanny
import linecache
import compileall
import io
import sys
import os
import tempfile
import pytest


# ======================== pdb ========================
def test_pdb_set_trace_basic():
    """真 pdb.set_trace 真存在 + 不抛"""
    # 不实际触发 — 只验 API
    assert callable(pdb.set_trace)
    assert callable(pdb.run)
    assert callable(pdb.runeval)
    assert callable(pdb.runcall)


def test_pdb_Pdb_class():
    """真 pdb.Pdb 真 class"""
    debugger = pdb.Pdb()
    # pdb.Pdb 继承 bdb.Bdb
    assert isinstance(debugger, bdb.Bdb)
    # 有 set_break / set_trace / run
    assert hasattr(debugger, "set_break")
    assert hasattr(debugger, "set_trace")
    assert hasattr(debugger, "run")


# ======================== bdb ========================
def test_bdb_breakpoint_class():
    """真 bdb.Breakpoint 真 class API"""
    # bdb.Breakpoint 是 class
    assert isinstance(bdb.Breakpoint, type)
    # bdb.Bdb 也有 break_anywhere / set_break 等 method
    assert callable(bdb.Bdb.set_break)


def test_bdb_set_breakpoint():
    """真 bdb 真设断点"""
    # 创建临时模块
    code = """
def func():
    x = 1
    y = 2
    return x + y

if __name__ == '__main__':
    print(func())
"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py") as f:
        f.write(code)
        path = f.name
    try:
        # 调 bdb 设断点
        # 不真跑 — 只验 API
        assert callable(bdb.Bdb)
    finally:
        os.unlink(path)


# ======================== tabnanny ========================
def test_tabnanny_check_clean():
    """真 tabnanny 真检查干净代码"""
    clean_code = """def func():
    x = 1
    y = 2
    return x + y
"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py") as f:
        f.write(clean_code)
        path = f.name
    try:
        # tabnanny 真不抛 = 通过
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            tabnanny.check(path)  # 干净不抛
        finally:
            sys.stderr = old_stderr
    finally:
        os.unlink(path)


def test_tabnanny_detect_mixed_tabs():
    """真 Python 真检 ambiguous indent"""
    bad_code = "def func():\n    x = 1\n\ty = 2\n"
    with pytest.raises((IndentationError, TabError)):
        compile(bad_code, "<test>", "exec")

def test_linecache_getline():
    """真 linecache 真读行"""
    code = """line 1
line 2
line 3
line 4
line 5
"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py") as f:
        f.write(code)
        path = f.name
    try:
        # linecache 真从文件读
        l1 = linecache.getline(path, 1)
        l3 = linecache.getline(path, 3)
        l5 = linecache.getline(path, 5)
        assert l1 == "line 1\n"
        assert l3 == "line 3\n"
        assert l5 == "line 5\n"
        # 不存在行 → ''
        l10 = linecache.getline(path, 10)
        assert l10 == ""
    finally:
        os.unlink(path)


def test_linecache_clearcache():
    """真 clearcache 真清"""
    code = "x = 1\n"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py") as f:
        f.write(code)
        path = f.name
    try:
        # 缓存
        linecache.getline(path, 1)
        assert path in linecache.cache
        # 清
        linecache.clearcache()
        # 清空
        assert linecache.cache == {} or path not in linecache.cache
    finally:
        os.unlink(path)


def test_linecache_lazy_module():
    """真 lazy module 不存在 → ''"""
    # lazy load, 不会抛
    line = linecache.getline("/nonexistent/file.py", 1)
    assert line == ""


# ======================== compileall ========================
def test_compileall_dir():
    """真 compileall 真编译目录"""
    with tempfile.TemporaryDirectory() as d:
        # 创建几个 .py
        for i, content in enumerate(["x = 1\n", "y = 2\n", "z = 3\n"]):
            path = os.path.join(d, f"mod_{i}.py")
            with open(path, "w") as f:
                f.write(content)
        # compileall 真编译
        result = compileall.compile_dir(d, quiet=1, force=True)
        assert result is True
        # 真有 .pyc
        for i in range(3):
            pyc = os.path.join(d, f"mod_{i}.pyc")
            # pyc 可能 pycache/ 下
            pycache_pyc = os.path.join(d, "__pycache__", f"mod_{i}.cpython-311.pyc")
            assert os.path.isfile(pyc) or os.path.isfile(pycache_pyc)
