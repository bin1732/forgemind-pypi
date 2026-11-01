# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 logging 真 (LogRecord 真 属性) + 真 http.server 真 (SimpleHTTPRequestHandler 真 base) + 真 shutil 进阶 (register_unpack_format / make_archive list) + 真 dis 真 (findlinestarts) + 真 html 真 (escape 真) + 真 ast 真 (Module/ClassDef 进阶) + 真 copy 真 (deepcopy set).
全 stdlib, 零模拟。
"""
import logging
import http.server
import shutil
import dis
import html
import ast
import copy
import os
import io
import sys
import pytest


# ======================== logging 进阶 ========================
def test_logging_LogRecord_attributes():
    """真 LogRecord 真 attribute"""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="test message %s",
        args=("arg1",),
        exc_info=None,
    )
    # attributes
    assert record.name == "test"
    assert record.levelno == logging.INFO
    assert record.msg == "test message %s"
    # getMessage
    assert record.getMessage() == "test message arg1"
    # levelname
    assert record.levelname == "INFO"


def test_logging_getLogRecordFactory():
    """真 getLogRecordFactory / setLogRecordFactory 真 (custom factory 实例)"""
    original = logging.getLogRecordFactory()
    calls = []

    def custom_factory(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    logging.setLogRecordFactory(custom_factory)
    try:
        # 通过 log() 调用, 必走 factory
        logger = logging.getLogger("test_factory")
        logger.warning("test")
        # 1+ 调用
        assert len(calls) >= 1
    finally:
        logging.setLogRecordFactory(original)


# ======================== http.server 进阶 ========================
def test_httpserver_BaseHTTPRequestHandler():
    """真 BaseHTTPRequestHandler 真 base class"""
    # 必有
    assert hasattr(http.server.BaseHTTPRequestHandler, "handle_one_request")
    assert hasattr(http.server.BaseHTTPRequestHandler, "send_response")
    assert hasattr(http.server.BaseHTTPRequestHandler, "send_error")
    # protocol_version
    assert http.server.BaseHTTPRequestHandler.protocol_version == "HTTP/1.0"


def test_httpserver_SimpleHTTPRequestHandler():
    """真 SimpleHTTPRequestHandler 真"""
    # 必有 do_GET
    assert hasattr(http.server.SimpleHTTPRequestHandler, "do_GET")
    assert hasattr(http.server.SimpleHTTPRequestHandler, "do_HEAD")
    # extensions_map 必有 .gz
    em = http.server.SimpleHTTPRequestHandler.extensions_map
    assert ".gz" in em
    assert ".Z" in em


# ======================== shutil 进阶 ========================
def test_shutil_register_unpack_format():
    """真 register_unpack_format 真"""
    # list of (name, extensions, description)
    formats = shutil.get_unpack_formats()
    names = [name for name, _, _ in formats]
    # 必含 zip
    assert "zip" in names
    # 必含 gztar / tar
    assert "gztar" in names
    assert "tar" in names


def test_shutil_get_archive_formats():
    """真 get_archive_formats 真"""
    formats = shutil.get_archive_formats()
    # 必含 zip / gztar / tar
    names = [name for name, _ in formats]
    assert "zip" in names
    assert "gztar" in names
    assert "tar" in names


# ======================== dis 进阶 ========================
def test_dis_findlinestarts():
    """真 findlinestarts 真"""
    def f():
        x = 1
        y = 2
        return x + y

    # findlinestarts 返 iterator of (offset, lineno)
    lines = list(dis.findlinestarts(f.__code__))
    # 必有 ≥ 1 entry
    assert len(lines) >= 1
    # (offset, lineno) tuple
    for offset, lineno in lines:
        assert isinstance(offset, int)
        assert isinstance(lineno, int)
        assert lineno > 0


# ======================== html 真 ========================
def test_html_escape():
    """真 html.escape 真"""
    # < > & "
    text = "<a href='x'>\"y\" & z</a>"
    escaped = html.escape(text)
    # 必有 &lt; &gt; &amp; &quot;
    assert "&lt;" in escaped
    assert "&gt;" in escaped
    assert "&amp;" in escaped
    assert "&quot;" in escaped


def test_html_unescape():
    """真 html.unescape 真"""
    text = "&lt;a&gt;&amp;&quot;b&quot;&gt;"
    unescaped = html.unescape(text)
    assert unescaped == '<a>&"b">'


# ======================== ast 进阶 ========================
def test_ast_Module_ClassDef_进阶():
    """真 ast Module + ClassDef + Assign 进阶"""
    src = """
class MyClass:
    x = 1
    y = 2
    def method(self):
        return self.x + self.y
"""
    tree = ast.parse(src)
    # Module
    assert isinstance(tree, ast.Module)
    # 必有 1 ClassDef
    assert len(tree.body) == 1
    cls = tree.body[0]
    assert isinstance(cls, ast.ClassDef)
    assert cls.name == "MyClass"
    # 3 body items (x, y, method)
    assert len(cls.body) == 3


def test_ast_dump_进阶():
    """真 ast.dump 真"""
    src = "x = 1 + 2"
    tree = ast.parse(src)
    # dump
    dumped = ast.dump(tree)
    # 必有 Module, Assign, BinOp
    assert "Module" in dumped
    assert "Assign" in dumped
    assert "BinOp" in dumped


# ======================== copy 真 ========================
def test_copy_deepcopy_set():
    """真 deepcopy set"""
    s = {1, 2, 3, frozenset([4, 5])}
    s2 = copy.deepcopy(s)
    # 必等
    assert s2 == s
    # 不 is
    assert s2 is not s
    # 改原不影响
    s.add(99)
    assert 99 not in s2


def test_copy_deepcopy_dict_with_list():
    """真 deepcopy dict with list"""
    d = {"a": [1, 2, 3], "b": {"c": 4}}
    d2 = copy.deepcopy(d)
    # 必等
    assert d2 == d
    # 不 is
    assert d2["a"] is not d["a"]
    # 改不影响
    d["a"].append(99)
    assert 99 not in d2["a"]
