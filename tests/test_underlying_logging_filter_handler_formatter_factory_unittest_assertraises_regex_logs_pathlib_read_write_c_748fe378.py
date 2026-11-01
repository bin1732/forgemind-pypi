# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`logging 进阶 (Filter+Handler+Formatter+LogRecord+factory)` + `unittest 进阶 (assertRaises+assertRaisesRegex+assertLogs+assertEqual+assertTrue)` + `pathlib 进阶 (read_text+write_text+chmod+read_bytes)` + `ctypes 进阶 (c_int+c_long+c_double+c_float)` + `asyncio.subprocess.shell=True (create_subprocess_shell)` + 真底层测试。

覆盖 logging 4 真 + unittest 5 真 + pathlib 4 真 + ctypes 4 真 + asyncio 1 真 (共 18 真测试) 模块:
  - `logging.Filter 子化 'forge' True`
  - `logging.Handler 子化 emit 'forge_handler_msg'`
  - `logging.Formatter format 'INFO'`
  - `logging getLogRecordFactory callable`
  - `unittest assertRaises ValueError`
  - `unittest assertRaisesRegex 'forge'`
  - `unittest assertLogs 'forge_assertlogs'`
  - `unittest assertEqual`
  - `unittest assertTrue`
  - `pathlib read_text 'forge_text'`
  - `pathlib write_text 'forge_write'`
  - `pathlib chmod 0o644`
  - `pathlib read_bytes b'forge_bytes'`
  - `ctypes.c_int 42`
  - `ctypes.c_long 100`
  - `ctypes.c_double 1.5`
  - `ctypes.c_float 1.5`
  - `asyncio.create_subprocess_shell 'echo forge_shell'`
"""
import asyncio
import ctypes
import logging
import os
import pathlib
import unittest

import pytest


# -- logging 进阶 (Filter+Handler+Formatter+factory) ----

class _ForgeLogFilter2(logging.Filter):
    def filter(self, record):
        return "forge" in record.getMessage()


class _ForgeLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


class TestLoggingFilterHandlerFormatterLogCaptureAdvance:
    def test_Filter_subclass(self):
        """`logging.Filter 子化 'forge' True。"""
        f = _ForgeLogFilter2()
        record = logging.LogRecord("forge_n", logging.INFO, "/p", 1, "msg forge", None, None)
        assert f.filter(record) is True

    def test_Handler_subclass(self):
        """`logging.Handler 子化 emit 'forge_handler_msg'。"""
        h = _ForgeLogHandler()
        record = logging.LogRecord("forge_n", logging.INFO, "/p", 1, "forge_handler_msg", None, None)
        h.emit(record)
        assert "forge_handler_msg" in h.records

    def test_Formatter_format(self):
        """`logging.Formatter format 'INFO'。"""
        f = logging.Formatter("%(levelname)s %(message)s")
        record = logging.LogRecord("forge_n", logging.INFO, "/p", 1, "msg", None, None)
        result = f.format(record)
        assert "INFO" in result
        assert "msg" in result

    def test_getLogRecordFactory(self):
        """`logging getLogRecordFactory callable。"""
        factory = logging.getLogRecordFactory()
        assert callable(factory)


# -- unittest 进阶 (assertRaises+assertRaisesRegex+assertLogs+assertEqual+assertTrue) --

class _UTAdvanced(unittest.TestCase):
    def test_forge_value_error(self):
        with self.assertRaises(ValueError):
            raise ValueError("forge_value_error")

    def test_forge_regex(self):
        with self.assertRaisesRegex(ValueError, "forge"):
            raise ValueError("forge_msg")

    def test_forge_logs(self):
        with self.assertLogs("forge_assertlogs", level="INFO") as cm:
            logging.getLogger("forge_assertlogs").info("forge_assertlogs_msg")
        assert "forge_assertlogs_msg" in cm.output[0]

    def test_forge_equal(self):
        self.assertEqual(1, 1)

    def test_forge_true(self):
        self.assertTrue(True)


class TestUnittestAssertRaisesRegexLogsEqualTrueAdvance:
    def test_assertRaises(self):
        """`unittest assertRaises ValueError。"""
        suite = unittest.TestLoader().loadTestsFromTestCase(_UTAdvanced)
        runner = unittest.TextTestRunner(stream=open(os.devnull, "w"))
        result = runner.run(suite)
        assert len(result.failures) == 0

    def test_assertRaisesRegex(self):
        """`unittest assertRaisesRegex 'forge'。"""
        suite = unittest.TestLoader().loadTestsFromTestCase(_UTAdvanced)
        runner = unittest.TextTestRunner(stream=open(os.devnull, "w"))
        result = runner.run(suite)
        assert len(result.failures) == 0

    def test_assertLogs(self):
        """`unittest assertLogs 'forge_assertlogs'。"""
        suite = unittest.TestLoader().loadTestsFromTestCase(_UTAdvanced)
        runner = unittest.TextTestRunner(stream=open(os.devnull, "w"))
        result = runner.run(suite)
        assert len(result.failures) == 0

    def test_assertEqual(self):
        """`unittest assertEqual。"""
        suite = unittest.TestLoader().loadTestsFromTestCase(_UTAdvanced)
        runner = unittest.TextTestRunner(stream=open(os.devnull, "w"))
        result = runner.run(suite)
        assert len(result.failures) == 0

    def test_assertTrue(self):
        """`unittest assertTrue。"""
        suite = unittest.TestLoader().loadTestsFromTestCase(_UTAdvanced)
        runner = unittest.TextTestRunner(stream=open(os.devnull, "w"))
        result = runner.run(suite)
        assert len(result.failures) == 0


# -- pathlib 进阶 (read_text+write_text+chmod+read_bytes) ---

class TestPathlibAdvanceV5:
    def test_read_text(self, tmp_path):
        """`pathlib read_text 'forge_text'。"""
        f = tmp_path / "forge.txt"
        f.write_text("forge_text")
        assert f.read_text() == "forge_text"

    def test_write_text(self, tmp_path):
        """`pathlib write_text 'forge_write' 必含。"""
        f = tmp_path / "forge.txt"
        f.write_text("forge_write")
        assert "forge_write" in f.read_text()

    def test_chmod(self, tmp_path):
        """`pathlib chmod 0o644。"""
        f = tmp_path / "forge.txt"
        f.write_text("forge")
        f.chmod(0o644)
        mode = f.stat().st_mode
        assert mode & 0o644

    def test_read_bytes(self, tmp_path):
        """`pathlib read_bytes b'forge_bytes'。"""
        f = tmp_path / "forge.bin"
        f.write_bytes(b"forge_bytes")
        assert f.read_bytes() == b"forge_bytes"


# -- ctypes 进阶 (c_int+c_long+c_double+c_float) -------

class TestCtypesAdvanceV4:
    def test_c_int(self):
        """`ctypes.c_int 42。"""
        v = ctypes.c_int(42)
        assert v.value == 42

    def test_c_long(self):
        """`ctypes.c_long 100。"""
        v = ctypes.c_long(100)
        assert v.value == 100

    def test_c_double(self):
        """`ctypes.c_double 1.5。"""
        v = ctypes.c_double(1.5)
        assert v.value == 1.5

    def test_c_float(self):
        """`ctypes.c_float 1.5。"""
        v = ctypes.c_float(1.5)
        assert v.value == 1.5


# -- asyncio.subprocess.shell=True (create_subprocess_shell) -

class TestAsyncioSubprocessShellAdvanceV2:
    def test_create_subprocess_shell(self):
        """`asyncio.create_subprocess_shell 'echo forge_shell' 必含 'forge_shell'。"""

        async def main():
            proc = await asyncio.create_subprocess_shell(
                "echo forge_shell",
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout

        stdout = asyncio.run(main())
        assert b"forge_shell" in stdout
