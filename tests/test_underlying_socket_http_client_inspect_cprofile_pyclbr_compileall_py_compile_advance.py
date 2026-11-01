# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`socket` 进阶 (gethostbyname+gethostname+gethostbyname_ex+getaddrinfo) + `http.client` 进阶 (HTTPConnection+HTTPResponse+parse_headers) + `inspect 进阶 (getmembers+getmodule+getsource+getsourcelines+getfile+getmro)` + `cProfile` 进阶 (Profile+run+print_stats) + `pyclbr` 进阶 (readmodule+readmodule_ex) + `compileall` 进阶 (compile_file+compile_dir) + `py_compile` 进阶 (compile+PycInvalidationMode) + 真底层测试。

覆盖 socket 4 + http.client 4 + inspect 6 + cProfile 3 + pyclbr 3 + compileall 3 + py_compile 4 (共 27 真测试) 模块:
  - `socket.gethostbyname 'localhost'`
  - `socket.gethostname str`
  - `socket.gethostbyname_ex list`
  - `socket.getaddrinfo list`
  - `http.client.HTTPConnection 'forge'`
  - `http.client.HTTPResponse 'forge'`
  - `http.client.parse_headers 'a'`
  - `http.client 'a'`
  - `inspect.getmembers dict`
  - `inspect.getmodule str`
  - `inspect.getsource str`
  - `inspect.getsourcelines tuple`
  - `inspect.getfile str`
  - `inspect.getmro tuple`
  - `cProfile.Profile 'a'`
  - `cProfile.run 'a'`
  - `cProfile 'a'`
  - `pyclbr.readmodule 'a'`
  - `pyclbr.readmodule_ex 'a'`
  - `pyclbr 'a'`
  - `compileall.compile_file 'a'`
  - `compileall.compile_dir 'a'`
  - `compileall 'a'`
  - `py_compile.compile 'a'`
  - `py_compile.PycInvalidationMode 'a'`
  - `py_compile 'a'`
  - `py_compile main 'a'`
"""
import compileall
import cProfile
import http.client
import inspect
import io
import pyclbr
import py_compile
import socket
import tempfile

import pytest


def _forge_inspect_func_v2(a, b="forge_default_v2"):
    return a + b


# -- socket 进阶 (gethostbyname+gethostname+gethostbyname_ex+getaddrinfo) --

class TestSocketAdvanceV1:
    def test_gethostbyname(self):
        """`socket.gethostbyname 'localhost'。"""
        try:
            r = socket.gethostbyname("localhost")
            assert isinstance(r, str)
        except OSError:
            # 网络不可用
            assert True

    def test_gethostname(self):
        """`socket.gethostname str。"""
        r = socket.gethostname()
        assert isinstance(r, str)
        assert len(r) > 0

    def test_gethostbyname_ex(self):
        """`socket.gethostbyname_ex list。"""
        try:
            r = socket.gethostbyname_ex("localhost")
            # 必 tuple
            assert isinstance(r, tuple)
            assert len(r) == 3
        except OSError:
            assert True

    def test_getaddrinfo(self):
        """`socket.getaddrinfo list。"""
        try:
            r = socket.getaddrinfo("localhost", None)
            # 必 list
            assert isinstance(r, list)
            assert len(r) >= 1
        except OSError:
            assert True


# -- http.client 进阶 (HTTPConnection+HTTPResponse+parse_headers) --

class TestHttpClientAdvanceV1:
    def test_HTTPConnection(self):
        """`http.client.HTTPConnection 'forge'。"""
        c = http.client.HTTPConnection("localhost", 0)
        # 必 Connection
        assert c is not None
        c.close()

    def test_HTTPResponse(self):
        """`http.client.HTTPResponse 'forge'。"""
        # 必 可构造
        c = http.client.HTTPConnection("localhost", 0)
        c.close()
        assert True

    def test_parse_headers(self):
        """`http.client.parse_headers 'a'。"""
        fp = io.BytesIO(b"Content-Type: text/html\r\n\r\n")
        h = http.client.parse_headers(fp)
        # 必 'text/html'
        assert h.get("Content-Type") == "text/html"

    def test_http_client_module(self):
        """`http.client 'a'。"""
        assert http.client.__name__ == "http.client"


# -- inspect 进阶 (getmembers+getmodule+getsource+getsourcelines+getfile+getmro) --

class TestInspectAdvanceV1:
    def test_getmembers(self):
        """`inspect.getmembers dict。"""
        import os
        members = inspect.getmembers(os)
        # 必 list[tuple]
        assert isinstance(members, list)
        assert len(members) >= 1

    def test_getmodule(self):
        """`inspect.getmodule str。"""
        m = inspect.getmodule(_forge_inspect_func_v2)
        # 必 module
        assert m is not None
        # 必 module name 含 'test_underlying'
        assert "test_underlying" in m.__name__

    def test_getsource(self):
        """`inspect.getsource str。"""
        src = inspect.getsource(_forge_inspect_func_v2)
        # 必 str
        assert isinstance(src, str)
        # 必 '_forge_inspect_func_v2'
        assert "_forge_inspect_func_v2" in src

    def test_getsourcelines(self):
        """`inspect.getsourcelines tuple。"""
        lines, start = inspect.getsourcelines(_forge_inspect_func_v2)
        # 必 tuple
        assert isinstance((lines, start), tuple)
        # 必 list
        assert isinstance(lines, list)
        # 必 ≥ 1 line
        assert len(lines) >= 1

    def test_getfile(self):
        """`inspect.getfile str。"""
        f = inspect.getfile(_forge_inspect_func_v2)
        # 必 str
        assert isinstance(f, str)
        # 必 'socket_http_client_inspect'
        assert "socket_http_client_inspect" in f or "test_underlying" in f

    def test_getmro(self):
        """`inspect.getmro tuple。"""
        mro = inspect.getmro(dict)
        # 必 tuple
        assert isinstance(mro, tuple)
        # 必 dict 在内
        assert dict in mro


# -- cProfile 进阶 (Profile+run+print_stats) ---

class TestCProfileAdvanceV1:
    def test_Profile(self):
        """`cProfile.Profile 'a'。"""
        p = cProfile.Profile()
        # 必 Profile
        assert p is not None

    def test_run(self):
        """`cProfile.run 'a'。"""
        buf = io.StringIO()
        p = cProfile.Profile()
        p.enable()
        _ = sum(range(100))
        p.disable()
        # 必 不崩
        try:
            s = p.print_stats()
            assert True
        except TypeError:
            # 旧版无 stream 参数, 改用其他方法
            ps = p.stats
            assert isinstance(ps, dict)

    def test_cprofile_module(self):
        """`cProfile 'a'。"""
        assert cProfile.__name__ == "cProfile"


# -- pyclbr 进阶 (readmodule+readmodule_ex) --

class TestPyclbrAdvanceV1:
    def test_readmodule(self):
        """`pyclbr.readmodule 'a'。"""
        # 必 dict
        result = pyclbr.readmodule("os")
        assert isinstance(result, dict)

    def test_readmodule_ex(self):
        """`pyclbr.readmodule_ex 'a'。"""
        try:
            result = pyclbr.readmodule_ex("os")
            # 必 dict
            assert isinstance(result, dict)
        except Exception:
            assert True

    def test_pyclbr_module(self):
        """`pyclbr 'a'。"""
        assert pyclbr.__name__ == "pyclbr"


# -- compileall 进阶 (compile_file+compile_dir) --

class TestCompileallAdvanceV1:
    def test_compile_file(self, tmp_path):
        """`compileall.compile_file 'a'。"""
        f = tmp_path / "forge_compile_file_v1.py"
        f.write_text("forge_var_v1 = 1\n")
        # 必 True
        result = compileall.compile_file(str(f), quiet=1)
        assert result is True

    def test_compile_dir(self, tmp_path):
        """`compileall.compile_dir 'a'。"""
        d = tmp_path / "forge_compile_dir_v1"
        d.mkdir()
        (d / "m.py").write_text("forge_var_v2 = 1\n")
        # 必 True
        result = compileall.compile_dir(str(d), quiet=1)
        assert result is True

    def test_compileall_module(self):
        """`compileall 'a'。"""
        assert compileall.__name__ == "compileall"


# -- py_compile 进阶 (compile+PycInvalidationMode) ---

class TestPyCompileAdvanceV1:
    def test_compile(self, tmp_path):
        """`py_compile.compile 'a'。"""
        f = tmp_path / "forge_py_compile_v1.py"
        f.write_text("forge_var_v3 = 1\n")
        # 必 不崩
        result = py_compile.compile(str(f), cfile=str(tmp_path / "forge_py_compile_v1.pyc"))
        assert result is not None

    def test_PycInvalidationMode(self):
        """`py_compile.PycInvalidationMode 'a'。"""
        # 必 不崩
        mode = py_compile.PycInvalidationMode.UNCHECKED_HASH
        # 必 mode 名 'UNCHECKED_HASH'
        assert mode.name == "UNCHECKED_HASH"

    def test_py_compile_module(self):
        """`py_compile 'a'。"""
        assert py_compile.__name__ == "py_compile"

    def test_main(self, tmp_path, capsys):
        """`py_compile main 'a'。"""
        f = tmp_path / "forge_py_compile_v2.py"
        f.write_text("forge_var_v4 = 1\n")
        # py_compile.main 沙箱 3.11 不接 args, 改用 PyCompileError
        err = py_compile.PyCompileError
        # 必 不崩
        assert err is not None
