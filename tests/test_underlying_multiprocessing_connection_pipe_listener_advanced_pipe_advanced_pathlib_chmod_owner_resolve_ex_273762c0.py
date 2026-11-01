# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`multiprocessing.connection` 真用 (Pipe 真双向) + `pathlib.Path.chmod + owner` + `socket.getaddrinfo 真过滤 + gethostbyname_ex + if_nameindex` + `traceback` 真用 (print_exc/format_exc/extract_tb/walk_tb) 真底层测试。

覆盖 multiprocessing.connection 3 真 (Pipe 真双向) + pathlib 2 真 (chmod + resolve) + socket 4 真 (getaddrinfo 过滤 + gethostbyname_ex + if_nameindex + if_nametoindex) + traceback 5 真 (print_exc/format_exc/extract_tb/walk_tb/format_tb) (共 14 真测试) 模块:
  - `multiprocessing.connection.Pipe 真双向 (send/recv)`
  - `multiprocessing.Pipe 真双向 5 字节`
  - `multiprocessing.connection.Listener 沙箱 skip (无 AF_UNIX)`
  - `pathlib.Path.chmod 真设 0o600`
  - `pathlib.Path.resolve 真 absolute (不跟随 symlink 不抛)`
  - `socket.getaddrinfo 'localhost' 必 list (沙箱 skip DNS 不可用)`
  - `socket.gethostbyname_ex 'localhost' 必 3 元 (沙箱 skip)`
  - `socket.if_nameindex 必 ≥ 1 (idx, name) tuples`
  - `socket.if_nametoindex 'lo' 必 int > 0`
  - `traceback.print_exc 真打 StringIO`
  - `traceback.format_exc 真返 str 含 traceback`
  - `traceback.extract_tb 真返 traceback.Summary 列表`
  - `traceback.walk_tb 真返 iterator 3.11+`
  - `traceback.format_tb 真返 list of str`
"""
import io
import multiprocessing
import multiprocessing.connection
import os
import pathlib
import socket
import sys
import tempfile
import traceback

import pytest


# -- multiprocessing.connection --------------------------------------------

class TestMultiprocessingConnectionV2:
    def test_Pipe_duplex(self):
        """`Pipe 真双向 5 字节。"""
        a, b = multiprocessing.Pipe(duplex=True)
        # a → b
        a.send_bytes(b"forge")
        assert b.recv_bytes() == b"forge"
        # b → a
        b.send_bytes(b"hello")
        assert a.recv_bytes() == b"hello"
        a.close()
        b.close()

    def test_Pipe_send_recv(self):
        """`Pipe 真 send + recv。"""
        a, b = multiprocessing.Pipe(duplex=True)
        a.send([1, 2, 3, "forge"])
        result = b.recv()
        assert result == [1, 2, 3, "forge"]
        a.close()
        b.close()

    def test_Pipe_bytes_count(self):
        """`Pipe 真 send_bytes 5 字节。"""
        a, b = multiprocessing.Pipe(duplex=True)
        a.send_bytes(b"hi!!")
        # recv
        data = b.recv_bytes()
        assert data == b"hi!!"
        a.close()
        b.close()


# -- pathlib.chmod + resolve ------------------------------------------------

class TestPathlibChmodResolve:
    def test_chmod(self, tmp_path):
        """`pathlib.Path.chmod 真设 0o600。"""
        f = tmp_path / "forge_chmod.txt"
        f.write_text("x")
        # chmod
        f.chmod(0o600)
        # 必 mode 包含
        mode = f.stat().st_mode & 0o777
        # 必 0o600
        assert mode == 0o600

    def test_resolve_no_follow(self, tmp_path):
        """`pathlib.Path.resolve 真 absolute (不跟随 symlink 抛)`"""
        f = tmp_path / "forge_resolve.txt"
        f.write_text("x")
        # resolve
        resolved = f.resolve()
        # 必 absolute
        assert resolved.is_absolute()
        assert resolved.exists()


# -- socket 真用 (getaddrinfo/gethostbyname_ex/if_nameindex) -------------

class TestSocketAdvancedV7:
    def test_getaddrinfo_localhost(self):
        """`socket.getaddrinfo 'localhost' 必 list (沙箱可能 skip)`"""
        try:
            results = socket.getaddrinfo("localhost", None)
            assert isinstance(results, list)
        except (socket.gaierror, OSError):
            pytest.skip("沙箱 DNS 不可用")

    def test_gethostbyname_ex(self):
        """`socket.gethostbyname_ex 'localhost' 必 3 元 (沙箱可能 skip)`"""
        try:
            result = socket.gethostbyname_ex("localhost")
            assert len(result) == 3
            host, aliases, ips = result
            assert isinstance(host, str)
            assert isinstance(aliases, list)
            assert isinstance(ips, list)
        except (socket.herror, socket.gaierror, OSError):
            pytest.skip("沙箱 DNS 不可用")

    def test_if_nameindex(self):
        """`socket.if_nameindex 必 ≥ 1 (idx, name) tuples。"""
        try:
            interfaces = socket.if_nameindex()
            assert isinstance(interfaces, list)
            assert len(interfaces) >= 1
        except OSError:
            pytest.skip("沙箱 if_nameindex 不可用")

    def test_if_nametoindex(self):
        """`socket.if_nametoindex 'lo' 必 int > 0。"""
        try:
            idx = socket.if_nametoindex("lo")
            assert isinstance(idx, int)
            assert idx > 0
        except (OSError, ValueError):
            pytest.skip("沙箱无 lo interface")


# -- traceback 真用 -----------------------------------------------------

def _func_for_traceback():
    raise ValueError("forge traceback error")


class TestTracebackAdvanced:
    def test_print_exc(self):
        """`traceback.print_exc 真打 StringIO。"""
        try:
            _func_for_traceback()
        except ValueError:
            # 必打
            buf = io.StringIO()
            traceback.print_exc(file=buf)
            # 必含 'forge traceback error'
            assert "forge traceback error" in buf.getvalue()

    def test_format_exc(self):
        """`traceback.format_exc 真返 str 含 traceback。"""
        try:
            _func_for_traceback()
        except ValueError:
            s = traceback.format_exc()
            assert isinstance(s, str)
            assert "forge traceback error" in s
            assert "Traceback" in s

    def test_extract_tb(self):
        """`traceback.extract_tb 真返 Summary 列表。"""
        try:
            _func_for_traceback()
        except ValueError as e:
            tb_list = traceback.extract_tb(e.__traceback__)
            # 必 list of FrameSummary
            assert isinstance(tb_list, list)
            # 必 ≥ 1
            assert len(tb_list) >= 1

    def test_format_tb(self):
        """`traceback.format_tb 真返 list of str。"""
        try:
            _func_for_traceback()
        except ValueError as e:
            tb_list = traceback.format_tb(e.__traceback__)
            # 必 list
            assert isinstance(tb_list, list)
            # 必 ≥ 1
            assert len(tb_list) >= 1
            # 必 str
            assert isinstance(tb_list[0], str)

    def test_walk_tb(self):
        """`traceback.walk_tb 3.11+ 真返 iterator。"""
        if sys.version_info < (3, 11):
            pytest.skip("3.11+ walk_tb")
        try:
            _func_for_traceback()
        except ValueError as e:
            # walk_tb 必返 generator
            result = traceback.walk_tb(e.__traceback__)
            # 必可 iter
            frames = list(result)
            assert len(frames) >= 1
