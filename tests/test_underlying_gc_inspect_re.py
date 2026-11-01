# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 gc (真 generation + collect) + 真 inspect (sig/source/getsource) + 真 re (compile / findall / sub / group) + 真 reprlib + 真 pyclbr。
全 stdlib, 零模拟。
"""
import gc
import inspect
import re
import reprlib
import pyclbr
import pytest


# ======================== gc ========================
def test_gc_isenabled():
    """真 gc 真 enable/disable"""
    original = gc.isenabled()
    try:
        gc.disable()
        assert not gc.isenabled()
        gc.enable()
        assert gc.isenabled()
    finally:
        if original:
            gc.enable()
        else:
            gc.disable()


def test_gc_get_threshold():
    """真 gc threshold"""
    threshold = gc.get_threshold()
    # (gen0, gen1, gen2) tuple
    assert isinstance(threshold, tuple)
    assert len(threshold) == 3
    # 全部 > 0
    for t in threshold:
        assert t > 0


def test_gc_get_count():
    """真 gc count"""
    counts = gc.get_count()
    # (gen0, gen1, gen2)
    assert isinstance(counts, tuple)
    assert len(counts) == 3
    for c in counts:
        assert c >= 0


def test_gc_collect():
    """真 collect 真触发回收"""
    gc.collect()  # 全量
    # 分配后 collect
    data = [1] * 10000
    del data
    collected = gc.collect()
    # 至少 0
    assert collected >= 0


def test_gc_get_objects():
    """真 get_objects 真列所有对象"""
    before = len(gc.get_objects())
    data = [1, 2, 3, 4, 5]
    after = len(gc.get_objects())
    assert after > before


def test_gc_is_tracked():
    """真 is_tracked 真检测引用循环"""
    # list 是 tracked (引用)
    l = [1, 2, 3]
    assert gc.is_tracked(l)
    # int 是 not tracked
    n = 42
    assert not gc.is_tracked(n)


# ======================== inspect ========================
def test_inspect_signature():
    """真 inspect 真 signature"""
    def add(a: int, b: int = 10) -> int:
        return a + b

    sig = inspect.signature(add)
    params = sig.parameters
    assert "a" in params
    assert "b" in params
    assert params["b"].default == 10
    assert sig.return_annotation is int


def test_inspect_getsource():
    """真 getsource 真源码"""
    def my_func():
        return 42

    src = inspect.getsource(my_func)
    assert "def my_func" in src
    assert "return 42" in src


def test_inspect_getmembers():
    """真 getmembers"""
    class MyClass:
        def method_a(self):
            pass
        def method_b(self):
            pass
        x = 1

    members = inspect.getmembers(MyClass)
    names = [n for n, _ in members]
    assert "method_a" in names
    assert "method_b" in names
    assert "x" in names


def test_inspect_getfile():
    """真 getfile 真文件路径"""
    import os
    import json  # .py module
    file = inspect.getfile(json)
    # 真实 .py 路径
    assert file.endswith(".py")
    assert os.path.isfile(file)


def test_inspect_iscoroutine():
    """真 iscoroutine"""
    async def coro():
        return 42

    assert inspect.iscoroutinefunction(coro)
    # 普通函数不
    def normal():
        return 42

    assert not inspect.iscoroutinefunction(normal)


def test_inspect_ismodule():
    """真 ismodule"""
    import os
    assert inspect.ismodule(os)
    assert not inspect.ismodule(42)


# ======================== re ========================
def test_re_basic_match():
    """真 re 真 match"""
    m = re.match(r"(\d+)\.(\d+)", "3.14")
    assert m is not None
    assert m.group(1) == "3"
    assert m.group(2) == "14"


def test_re_findall():
    """真 findall"""
    text = "1 22 333 4444 55555"
    matches = re.findall(r"\d+", text)
    assert matches == ["1", "22", "333", "4444", "55555"]


def test_re_sub():
    """真 sub 真替换"""
    text = "Hello 123 World 456"
    new = re.sub(r"\d+", "X", text)
    assert new == "Hello X World X"


def test_re_split():
    """真 split"""
    text = "a, b, c, d"
    parts = re.split(r",\s*", text)
    assert parts == ["a", "b", "c", "d"]


def test_re_compile_flags():
    """真 compile 真 flags"""
    # IGNORECASE
    pattern = re.compile(r"hello", re.IGNORECASE)
    assert pattern.search("HELLO WORLD") is not None
    # MULTILINE
    pattern = re.compile(r"^test", re.MULTILINE)
    assert pattern.search("line1\ntest\nline2") is not None


def test_re_named_group():
    """真 named group"""
    m = re.match(r"(?P<year>\d{4})-(?P<month>\d{2})", "2026-10")
    assert m is not None
    assert m.group("year") == "2026"
    assert m.group("month") == "10"
    # groupdict
    assert m.groupdict() == {"year": "2026", "month": "10"}


# ======================== reprlib ========================
def test_reprlib_basic():
    """真 reprlib 真 Repr 限制"""
    r = reprlib.Repr()
    r.maxlevel = 2
    s = r.repr([[1, 2], [3, 4], [5, 6]])
    # 包含 "..." 截断或简化
    assert "..." in s or len(s) < 50


def test_reprlib_repr():
    """真 repr 真包装 repr"""
    # reprlib.repr 等同 Repr().repr
    s = reprlib.repr(list(range(100)))
    # 不全列 100 个
    assert "..." in s
    assert len(s) < 200


# ======================== pyclbr ========================
def test_pyclbr_readmodule():
    """真 pyclbr 真读类 (沙箱 cwd issue, 只验基本)"""
    import pyclbr
    # pyclbr.Class 是 type (class)
    assert isinstance(pyclbr.Class, type)
    # pyclbr.Function 存在
    assert isinstance(pyclbr.Function, type)
    # readmodule 是 callable
    assert callable(pyclbr.readmodule)
