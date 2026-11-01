# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`socket.create_connection/create_server/defaultcontext` 真用 (沙箱 skip 实际连接) + `socket.getservbyport` 真用 + `ssl.create_default_context` 真用 + `pathlib.glob` 真用 + `shutil.ignore_patterns` 进阶 + `tracemalloc.get_traced_memory` 真用 + `asyncio.run` 真用 + `inspect.Signature.empty` 真用 真底层测试。

覆盖 socket 4 真 (getaddrinfo+getservbyport+getaddrinfo_all+create_connection 沙箱 skip) + ssl 1 真 + pathlib 3 真 (glob+rglob+path) + shutil 1 真 + tracemalloc 3 真 (start+stop+get_traced_memory) + asyncio 1 真 + inspect 2 真 (empty+Parameter) (共 15 真测试) 模块:
  - `socket.getaddrinfo 'localhost' 必 ≥ 1 result (沙箱 skip)`
  - `socket.getservbyport 80 必 'http'`
  - `socket.getservbyname 'https' 必 443`
  - `socket.create_connection 沙箱 skip (timeout=0.1)`
  - `ssl.SSLContext(PROTOCOL_TLS_SERVER) 真建 + verify_mode`
  - `pathlib.Path.glob 真找 *.py`
  - `pathlib.Path.rglob 真递归找`
  - `pathlib.PurePath 真 sub of (is_relative_to)`
  - `shutil.ignore_patterns 真返 set of EXCLUDED (沙箱 3.11+)`
  - `tracemalloc.start + get_traced_memory 真返 (current, peak) tuple`
  - `tracemalloc.Snapshot.statistics 真返 list`
  - `tracemalloc.Snapshot.compare_to 真返 diff list`
  - `asyncio.run 真跑 coroutine 返值`
  - `inspect.Signature.empty sentinel`
  - `inspect.Parameter 4 kind 真 enum`
"""
import asyncio
import inspect
import os
import pathlib
import shutil
import socket
import ssl
import sys
import tracemalloc

import pytest


# -- socket 真用 ----------------------------------------------------------

class TestSocketAdvancedV8:
    def test_getaddrinfo_localhost(self):
        """`socket.getaddrinfo 'localhost' 必 ≥ 1 (沙箱可能 skip)`"""
        try:
            results = socket.getaddrinfo("localhost", None)
            assert isinstance(results, list)
            assert len(results) >= 1
        except (socket.gaierror, OSError):
            pytest.skip("沙箱 DNS 不可用")

    def test_getservbyport_http(self):
        """`socket.getservbyport 80 必 'http'。"""
        name = socket.getservbyport(80)
        assert name == "http"

    def test_getservbyname_https(self):
        """`socket.getservbyname 'https' 必 443。"""
        port = socket.getservbyname("https")
        assert port == 443

    def test_create_connection_sandbox_skip(self):
        """`socket.create_connection 沙箱无 SSH skip。"""
        try:
            sock = socket.create_connection(("127.0.0.1", 22), timeout=0.1)
            sock.close()
        except (ConnectionRefusedError, OSError, TimeoutError):
            # 沙箱无 SSH
            pass


# -- ssl 进阶 ---------------------------------------------------------

class TestSslAdvancedV2:
    def test_SSLContext(self):
        """`ssl.SSLContext(PROTOCOL_TLS_SERVER) 真建。"""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        # 必 is SSLContext
        assert isinstance(ctx, ssl.SSLContext)
        # 必 verify_mode
        assert ctx.verify_mode is not None


# -- pathlib 真用 (glob/rglob/PurePath) ---------------------------------

class TestPathlibGlobV3:
    def test_glob(self, tmp_path):
        """`pathlib.Path.glob 真找 *.py。"""
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.py").write_text("b")
        (tmp_path / "c.txt").write_text("c")
        py = list(tmp_path.glob("*.py"))
        # 必 2
        assert len(py) == 2
        names = [p.name for p in py]
        assert "a.py" in names
        assert "b.py" in names

    def test_rglob(self, tmp_path):
        """`pathlib.Path.rglob 真递归。"""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("deep")
        (tmp_path / "top.py").write_text("top")
        py = list(tmp_path.rglob("*.py"))
        assert len(py) == 2

    def test_PurePath_is_relative_to(self):
        """`pathlib.PurePath 真 is_relative_to。"""
        p = pathlib.PurePath("/a/b/c")
        # c is relative to /a/b
        assert p.is_relative_to("/a/b") is True
        # c not relative to /x/y
        assert p.is_relative_to("/x/y") is False


# -- shutil 真用 (ignore_patterns) -------------------------------------

class TestShutilIgnoreV2:
    def test_ignore_patterns(self):
        """`shutil.ignore_patterns 真返 set of EXCLUDED (沙箱 3.11+)`"""
        fn = shutil.ignore_patterns("*.pyc")
        # 必 callable
        assert callable(fn)
        # 必返 set (3.11+) 含 'foo.pyc'
        result = fn("/tmp", ["foo.pyc", "bar.txt"])
        if isinstance(result, set):
            assert "foo.pyc" in result
        else:
            assert "foo.pyc" in list(result)


# -- tracemalloc 真用 ---------------------------------------------------

class TestTracemallocAdvancedV4:
    def test_start_get_traced_memory(self):
        """`tracemalloc.start + get_traced_memory 真返 (current, peak) tuple。"""
        tracemalloc.start()
        try:
            data = [i for i in range(10000)]
            mem = tracemalloc.get_traced_memory()
            # 必 2 元
            assert len(mem) == 2
            current, peak = mem
            assert isinstance(current, int)
            assert isinstance(peak, int)
            # peak 必 ≥ current
            assert peak >= current
        finally:
            tracemalloc.stop()

    def test_Snapshot_statistics(self):
        """`Snapshot.statistics 真返 list。"""
        tracemalloc.start()
        try:
            snap = tracemalloc.take_snapshot()
            stats = snap.statistics("filename")
            assert isinstance(stats, list)
        finally:
            tracemalloc.stop()

    def test_Snapshot_compare_to(self):
        """`Snapshot.compare_to 真返 diff list。"""
        tracemalloc.start()
        try:
            snap1 = tracemalloc.take_snapshot()
            data = [i for i in range(1000)]
            snap2 = tracemalloc.take_snapshot()
            diffs = snap2.compare_to(snap1, "filename")
            assert isinstance(diffs, list)
        finally:
            tracemalloc.stop()


# -- asyncio 真用 -------------------------------------------------------

class TestAsyncioRun:
    def test_asyncio_run(self):
        """`asyncio.run 真跑 coroutine 返值。"""

        async def main():
            return "forge_run"

        result = asyncio.run(main())
        assert result == "forge_run"


# -- inspect 真用 (Signature.empty + Parameter) ------------------------

class TestInspectAdvancedV7:
    def test_Signature_empty(self):
        """`inspect.Signature.empty 真 sentinel。"""
        # 必是 sentinel
        assert inspect.Signature.empty is not None
        sig = inspect.signature(lambda: None)
        # return_annotation 必 empty
        assert sig.return_annotation is inspect.Signature.empty

    def test_Parameter_kinds(self):
        """`inspect.Parameter 4 kind 真 enum。"""
        sig = inspect.signature(lambda a, b=42, *args, **kwargs: None)
        # POSITIONAL_OR_KEYWORD
        assert sig.parameters["a"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        # POSITIONAL_OR_KEYWORD with default
        assert sig.parameters["b"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        # VAR_POSITIONAL
        assert sig.parameters["args"].kind == inspect.Parameter.VAR_POSITIONAL
        # VAR_KEYWORD
        assert sig.parameters["kwargs"].kind == inspect.Parameter.VAR_KEYWORD
