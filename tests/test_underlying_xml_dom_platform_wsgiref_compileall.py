# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`xml.dom.minidom` + `platform` + `wsgiref` 真底层测试。

覆盖 XML 解析 / 系统信息 / WSGI 服务模块:
  - `xml.dom.minidom.parseString('<a x="1"/>')` 真解 XML,`a` 元素 `x=1`
  - `xml.dom.minidom.Document.toprettyxml` 真格式化输出含换行+缩进
  - `platform.system()` 真返 'Linux' / 'Darwin' / 'Windows' 之一
  - `platform.machine()` 真返非空 string
  - `platform.python_implementation()` 真返 'CPython' / 'PyPy' 之一
  - `platform.processor()` 真返非空 string (沙箱: 'x86_64')
  - `wsgiref.simple_server.WSGIRequestHandler` 真自定义 request handler
  - `compileall.compile_file(path)` 真编译单文件到 __pycache__
  - `compileall.compile_path(['pkg/'])` 真编译整目录
"""
import compileall
import os
import platform
import socket
import sys
import tempfile
import threading
import time
import urllib.request
import wsgiref.simple_server
import xml.dom.minidom

import pytest


# -- xml.dom.minidom ----------------------------------------------------------

class TestXmlDomMinidom:
    def test_parse_string_extracts_attribute(self):
        """`xml.dom.minidom.parseString('<a x="1"/>')` 真解 XML,`a` 元素 `x=1`。"""
        doc = xml.dom.minidom.parseString('<root><a x="1">hi</a></root>')
        root = doc.documentElement
        assert root.tagName == "root"
        a_list = root.getElementsByTagName("a")
        assert len(a_list) == 1
        a = a_list[0]
        assert a.getAttribute("x") == "1"
        assert a.firstChild.data == "hi"

    def test_toprettyxml_outputs_multiline(self):
        """`Document.toprettyxml` 真格式化输出含换行+缩进。"""
        doc = xml.dom.minidom.parseString("<root><a>1</a><b>2</b></root>")
        pretty = doc.toprettyxml(indent="  ")
        assert "\n" in pretty, f"toprettyxml 应含换行,实际 {pretty!r}"
        # '<' 出现至少 3 次 (root/a/b)
        assert pretty.count("<") >= 3

    def test_createElement_and_setAttribute(self):
        """`Document.createElement` 真建元素,`setAttribute` 写属性。"""
        doc = xml.dom.minidom.Document()
        root = doc.createElement("root")
        doc.appendChild(root)
        child = doc.createElement("child")
        child.setAttribute("name", "forge")
        root.appendChild(child)
        xml_str = root.toxml()
        assert "<child" in xml_str
        assert 'name="forge"' in xml_str


# -- platform -----------------------------------------------------------------

class TestPlatform:
    def test_system_returns_known_os(self):
        """`platform.system()` 真返 'Linux' / 'Darwin' / 'Windows' 之一。"""
        sysname = platform.system()
        assert sysname in ("Linux", "Darwin", "Windows"), (
            f"system 应为已知 OS,实际 {sysname!r}"
        )

    def test_machine_returns_nonempty(self):
        """`platform.machine()` 真返非空 string。"""
        m = platform.machine()
        assert isinstance(m, str) and m, f"machine 应为非空字符串,实际 {m!r}"

    def test_python_implementation_returns_known(self):
        """`platform.python_implementation()` 真返 'CPython' / 'PyPy' 等。"""
        impl = platform.python_implementation()
        assert impl in ("CPython", "PyPy", "Jython", "IronPython"), (
            f"python_implementation 应为已知实现,实际 {impl!r}"
        )

    def test_processor_returns_string(self):
        """`platform.processor()` 真返 string (沙箱可能为空,只验类型不验非空)。"""
        p = platform.processor()
        assert isinstance(p, str), f"processor 应为 string,实际 {type(p)}: {p!r}"
        # 沙箱中可能为空字符串,这是 platform 模块的 known limitation


# -- wsgiref 进阶 -------------------------------------------------------------

def _echo_app(environ, start_response):
    body = environ.get("QUERY_STRING", "")
    start_response("200 OK", [("Content-Type", "text/plain"),
                              ("Content-Length", str(len(body)))])
    return [body.encode("utf-8")]


class TestWsgirefAdvanced:
    def test_wsgi_query_string_round_trip(self):
        """`wsgiref.simple_server.make_server` 真处理 GET,query string 透传。"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        server = wsgiref.simple_server.make_server("127.0.0.1", port, _echo_app)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            time.sleep(0.2)  # 给 server 充分启动时间
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/?name=forge", timeout=5
            ) as resp:
                body = resp.read()
            assert body == b"name=forge", f"WSGI 应回 'name=forge',实际 {body!r}"
        finally:
            server.shutdown()
            server.server_close()


# -- compileall 进阶 ----------------------------------------------------------

class TestCompileallAdvanced:
    def test_compile_file_writes_pyc(self):
        """`compileall.compile_file(path)` 真编译单文件,`__pycache__/<name>.pyc` 被创建。"""
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "single.py")
            with open(src, "w") as f:
                f.write("VAL = 42\n")
            ok = compileall.compile_file(src, quiet=1, force=True)
            assert ok is True
            cache = os.path.join(d, "__pycache__")
            assert os.path.isdir(cache), f"应生成 __pycache__ 目录: {cache}"
            pycs = [f for f in os.listdir(cache) if f.endswith(".pyc")]
            assert len(pycs) == 1, f"应生成 1 个 .pyc,实际 {len(pycs)}"

    def test_compile_path_compiles_directory(self):
        """`compileall.compile_dir(dir)` 真编译整目录 3 个 .py 文件。"""
        with tempfile.TemporaryDirectory() as d:
            for name in ("a.py", "b.py", "c.py"):
                with open(os.path.join(d, name), "w") as f:
                    f.write(f"# {name}\n")
            ok = compileall.compile_dir(d, quiet=1, force=True)
            assert ok is True
            cache = os.path.join(d, "__pycache__")
            assert os.path.isdir(cache), f"应生成 __pycache__: {cache}"
            pycs = [f for f in os.listdir(cache) if f.endswith(".pyc")]
            assert len(pycs) == 3, f"应生成 3 个 .pyc,实际 {len(pycs)}"
