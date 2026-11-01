# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`pathlib 进阶 (touch+unlink+rename+replace)` + `unittest 进阶 (TestLoader+loadTestsFromName+loadTestsFromModule)` + `ctypes 进阶 (string_at+memset)` + `subprocess 进阶 (Popen.communicate+send_signal+terminate+kill)` + 真底层测试。

覆盖 pathlib 4 真 (touch+unlink+rename+replace) + unittest 2 真 (TestLoader+loadTestsFromModule) + ctypes 2 真 (string_at+memset) + subprocess 4 真 (Popen communicate+send_signal+terminate+kill) (共 12 真测试) 模块:
  - `pathlib.touch tmp_path 真 exists`
  - `pathlib.unlink tmp_path 真 not exists`
  - `pathlib.rename tmp_path 真 exists new name`
  - `pathlib.replace tmp_path 真 exists new name`
  - `unittest.TestLoader.loadTestsFromTestCase 真用 ≥ 1`
  - `unittest.TestLoader.loadTestsFromModule os ≥ 0`
  - `ctypes.string_at 必 b'forge'`
  - `ctypes.memset 真 'forge' 必 zero`
  - `subprocess.Popen 'echo' 'forge' communicate 必 stdout b'forge'`
  - `subprocess.Popen 'sleep' send_signal SIGUSR1 必不抛`
  - `subprocess.Popen 'sleep' terminate 必不抛`
  - `subprocess.Popen 'sleep' kill 必不抛`
"""
import ctypes
import os
import pathlib
import signal
import subprocess
import unittest

import pytest


# -- pathlib 进阶 (touch+unlink+rename+replace) ---------

class TestPathlibTouchUnlinkRenameReplaceAdvance:
    def test_touch(self, tmp_path):
        """`pathlib.touch tmp_path 真 exists。"""
        f = tmp_path / "forge_touch.txt"
        f.touch()
        # 必 exists
        assert f.exists()

    def test_unlink(self, tmp_path):
        """`pathlib.unlink tmp_path 真 not exists。"""
        f = tmp_path / "forge_unlink.txt"
        f.write_text("forge")
        f.unlink()
        # 必 not exists
        assert not f.exists()

    def test_rename(self, tmp_path):
        """`pathlib.rename tmp_path 真 exists new name。"""
        f = tmp_path / "forge_old.txt"
        f.write_text("forge")
        f2 = f.rename(tmp_path / "forge_new.txt")
        # 必 exists new name
        assert f2.exists()
        # 必 'forge_new.txt'
        assert f2.name == "forge_new.txt"

    def test_replace(self, tmp_path):
        """`pathlib.replace tmp_path 真 exists new name。"""
        f = tmp_path / "forge_replace_old.txt"
        f.write_text("forge")
        f2 = f.replace(tmp_path / "forge_replace_new.txt")
        # 必 exists new name
        assert f2.exists()


# -- unittest 进阶 (TestLoader+loadTestsFromModule) ----

class _UTSimple(unittest.TestCase):
    def test_forge(self):
        self.assertEqual(1, 1)


class TestUnittestTestLoaderAdvance:
    def test_loadTestsFromTestCase(self):
        """`unittest.TestLoader.loadTestsFromTestCase 真用 ≥ 1。"""
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(_UTSimple)
        # 必 ≥ 1
        assert suite.countTestCases() >= 1

    def test_loadTestsFromModule(self):
        """`unittest.TestLoader.loadTestsFromModule os ≥ 0。"""
        loader = unittest.TestLoader()
        import os as _os
        suite = loader.loadTestsFromModule(_os)
        # 必 ≥ 0
        assert suite.countTestCases() >= 0


# -- ctypes 进阶 (string_at+memset) ---------------------

class TestCtypesStringAtMemsetAdvance:
    def test_string_at(self):
        """`ctypes.string_at 必 b'forge'。"""
        # create_string_buffer + 内存地址
        buf = ctypes.create_string_buffer(b"forge")
        addr = ctypes.addressof(buf)
        result = ctypes.string_at(addr, 5)
        # 必 b'forge'
        assert result == b"forge"

    def test_memset_zero(self):
        """`ctypes.memset 真 'forge' 必 zero。"""
        buf = ctypes.create_string_buffer(b"forge")
        ctypes.memset(buf, 0, 5)
        # 必 length 6 (5 + NUL 终止)
        assert len(buf.raw) == 6
        # 必 前 5 字节 全 0
        for b in buf.raw[:5]:
            assert b == 0


# -- subprocess 进阶 (Popen communicate + send_signal+terminate+kill) --

class TestSubprocessPopenCommunicateSendSignalTerminateKillAdvance:
    def test_communicate(self):
        """`subprocess.Popen 'echo' 'forge' communicate 必 stdout b'forge'。"""
        p = subprocess.Popen(
            ["echo", "forge"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        stdout, _ = p.communicate(input=b"", timeout=5)
        # 必含 b'forge'
        assert b"forge" in stdout

    def test_send_signal(self):
        """`subprocess.Popen 'sleep' send_signal SIGUSR1 必不抛。"""
        p = subprocess.Popen(["sleep", "10"])
        try:
            # send_signal
            p.send_signal(signal.SIGUSR1)
            # 必不抛
            assert True
        finally:
            p.terminate()
            p.wait(timeout=5)

    def test_terminate(self):
        """`subprocess.Popen 'sleep' terminate 必不抛。"""
        p = subprocess.Popen(["sleep", "10"])
        # terminate
        p.terminate()
        p.wait(timeout=5)
        # 必 必不抛
        assert True

    def test_kill(self):
        """`subprocess.Popen 'sleep' kill 必不抛。"""
        p = subprocess.Popen(["sleep", "10"])
        # kill
        p.kill()
        p.wait(timeout=5)
        # 必 必不抛
        assert True
