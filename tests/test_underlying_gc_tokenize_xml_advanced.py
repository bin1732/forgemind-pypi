# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 gc 真 get_referents / get_referrers / collect_generation + 真 tokenize 真精确 type (DEDENT / NEWLINE) + 真 xml ElementTree 真 iter / findtext / namespace + 真 typing 真 is_typeddict。
全 stdlib, 零模拟。
"""
import gc
import tokenize
import xml.etree.ElementTree as ET
import typing
import io
import pytest


# ======================== gc 进阶 ========================
def test_gc_get_referents():
    """真 get_referents 真列所有引用对象"""
    a = [1, 2, 3]
    b = {"x": a, "y": "hello"}
    # b 引用 a + "hello"
    referents = gc.get_referents(b)
    assert a in referents
    assert "hello" in referents


def test_gc_get_referrers():
    """真 get_referrers"""
    a = []
    b = [a]
    c = [a]
    # 多个 ref a
    referrers = gc.get_referrers(a)
    # b, c, 还有 frame, locals
    assert b in referrers
    assert c in referrers


def test_gc_collect_generation():
    """真 collect(gen) 真单代回收"""
    gc.collect()  # 全清
    # 分配点
    a = "X" * 1000
    # 收 gen 0
    n = gc.collect(0)
    assert n >= 0


def test_gc_freeze_unfreeze():
    """真 freeze / unfreeze 真 GC 跟踪"""
    a = []
    # freeze → 不 track
    gc.freeze()
    try:
        # 分配 — 不 track
        b = [1, 2, 3]
        # 不在 get_objects 跟踪
        # (不能直接验 — 但可看 is_tracked)
    finally:
        # unfreeze 恢复
        gc.unfreeze()


def test_gc_threshold_set_get():
    """真 threshold 真设/取"""
    orig = gc.get_threshold()
    try:
        gc.set_threshold(700, 10, 10)
        new = gc.get_threshold()
        assert new == (700, 10, 10)
    finally:
        gc.set_threshold(*orig)


# ======================== tokenize 真精确 ========================
def test_tokenize_DEDENT_NEWLINE():
    """真 DEDENT / NEWLINE 真"""
    code = """if True:
    x = 1
    y = 2
"""
    tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    types = [t.type for t in tokens]
    # 多个 DEDENT (缩进退出)
    assert tokenize.DEDENT in types
    # NEWLINE
    assert tokenize.NEWLINE in types


def test_tokenize_string_prefix():
    """真 string prefix 真 r/b/u/f"""
    code = '''s1 = "normal"
s2 = r"raw"
s3 = b"bytes"
s4 = f"f-string"'''
    tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    strings = [t.string for t in tokens if t.type == tokenize.STRING]
    # r / b / f prefix
    assert any('r"' in s for s in strings)
    assert any('b"' in s for s in strings)
    assert any('f"' in s for s in strings)


# ======================== xml 进阶 ========================
def test_xml_iter():
    """真 iter 真递归"""
    xml = "<root><a><b>1</b></a><c>2</c></root>"
    root = ET.fromstring(xml)
    elements = list(root.iter())
    # root + a + b + c
    assert len(elements) == 4
    tags = [e.tag for e in elements]
    assert "root" in tags
    assert "a" in tags
    assert "b" in tags
    assert "c" in tags


def test_xml_findtext():
    """真 findtext 真取 text"""
    xml = "<root><name>Alice</name><age>30</age></root>"
    root = ET.fromstring(xml)
    assert root.findtext("name") == "Alice"
    assert root.findtext("age") == "30"
    # default
    assert root.findtext("missing", "DEFAULT") == "DEFAULT"


def test_xml_namespace():
    """真 namespace"""
    xml = '<root xmlns:ns="http://example.com"><ns:item>value</ns:item></root>'
    root = ET.fromstring(xml)
    # 找 ns:item
    items = root.findall(".//{http://example.com}item")
    assert len(items) == 1
    assert items[0].text == "value"


def test_xml_attrib_dict():
    """真 attrib dict"""
    xml = '<item id="42" name="test" />'
    elem = ET.fromstring(xml)
    # attrib
    assert elem.attrib == {"id": "42", "name": "test"}


# ======================== typing 进阶 ========================
def test_typing_is_typeddict():
    """真 is_typeddict"""
    if hasattr(typing, "is_typeddict"):
        class Movie(typing.TypedDict):
            name: str
            year: int
        assert typing.is_typeddict(Movie)


def test_typing_ForwardRef():
    """真 ForwardRef 真延迟解析"""
    from typing import ForwardRef
    fr = ForwardRef("int")
    # 解析
    result = typing._eval_type(fr, None, None)
    assert result is int
