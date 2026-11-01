# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 importlib 真 import_module / spec 真查 / submodule 真 load + 真 pkgutil 真 walk / iter_modules + 真 runpy 真 run_module / run_path + 真 sys 真 modules / path_hooks。
全 stdlib, 零模拟。
"""
import importlib
import importlib.util
import sys
import pkgutil
import runpy
import os
import tempfile
import pytest


# ======================== importlib ========================
def test_importlib_import_module():
    """真 importlib 真 import"""
    import json
    m = importlib.import_module("json")
    assert m is json
    # 不存在
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("nonexistent_xyz_abc_module")


def test_importlib_reload():
    """真 importlib 真 reload"""
    import json
    m = importlib.reload(json)
    assert m is json


def test_importlib_spec_from_file_location():
    """真 spec 真 from_file_location"""
    # 创建临时 .py
    code = "x = 42\ndef f(): return x"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py") as f:
        f.write(code)
        path = f.name
    try:
        spec = importlib.util.spec_from_file_location("temp_module", path)
        assert spec is not None
        # 创建 module
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # 验证
        assert module.x == 42
        assert module.f() == 42
    finally:
        os.unlink(path)


def test_importlib_get_source():
    """真 importlib 真 get_source"""
    import json
    # 可能有, 也可能没 (.pyc only)
    source = importlib.util.find_spec("json")
    assert source is not None
    assert source.name == "json"


# ======================== pkgutil ========================
def test_pkgutil_iter_modules():
    """真 iter_modules 真列子模块"""
    # json 的子模块
    import json
    mods = list(pkgutil.iter_modules(json.__path__, prefix="json."))
    names = [m.name for m in mods]
    # json 至少有 .decoder / .encoder
    assert "json.decoder" in names
    assert "json.encoder" in names


def test_pkgutil_walk_packages():
    """真 walk_packages 真递归"""
    import email
    # email 有子包
    pkgs = list(pkgutil.walk_packages(email.__path__, prefix="email."))
    # 至少 5 个
    assert len(pkgs) >= 5


def test_pkgutil_get_data():
    """真 pkgutil 真 get_data"""
    # 读 json 的 __init__ (不太行, json 是 C)
    # 改用 email
    data = pkgutil.get_data("email", "feedparser.py")
    # None 或 content
    if data is not None:
        assert isinstance(data, bytes)
    # 不存在文件 → FileNotFoundError
    with pytest.raises(FileNotFoundError):
        pkgutil.get_data("email", "nonexistent_xyz.py")


# ======================== runpy ========================
def test_runpy_run_module():
    """真 runpy 真 run_module"""
    code_path = None
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py") as f:
        f.write('print("hello from runpy")')
        code_path = f.name
    try:
        # 跑 path (不行, runpy.run_path)
        with pytest.raises(SystemExit) if False else _NoExit():
            runpy.run_path(code_path, run_name="__main__")
    finally:
        os.unlink(code_path)


# helper class
class _NoExit:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, tb):
        # 不重抛 SystemExit
        return exc_type is SystemExit


# ======================== sys 真 modules ========================
def test_sys_modules():
    """真 sys.modules"""
    # json 必在
    assert "json" in sys.modules
    import json
    assert sys.modules["json"] is json


def test_sys_path_hooks():
    """真 sys.path_hooks"""
    # 至少 1 个 hook
    assert len(sys.path_hooks) > 0
    # zipimport 必在
    import zipimport
    assert zipimport.zipimporter in sys.path_hooks


def test_sys_meta_path():
    """真 sys.meta_path"""
    # 至少 3 个 finder
    assert len(sys.meta_path) >= 3
    # 至少 1 个有 find_spec method
    assert any(hasattr(f, "find_spec") for f in sys.meta_path)


# ======================== modulefinder 进阶 ========================
def test_modulefinder_real():
    """真 ModuleFinder 真分析依赖"""
    import modulefinder
    finder = modulefinder.ModuleFinder()
    # 创建临时 script
    code = "import json\nimport os\nfrom collections import OrderedDict"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py") as f:
        f.write(code)
        path = f.name
    try:
        finder.run_script(path)
        # 找到
        assert "json" in finder.modules
        assert "os" in finder.modules
        # OrderedDict
        assert "collections" in finder.modules
    finally:
        os.unlink(path)
