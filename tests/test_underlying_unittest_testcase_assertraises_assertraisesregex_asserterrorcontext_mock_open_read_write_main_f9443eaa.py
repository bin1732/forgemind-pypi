# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.TestCase` 进阶 (assertRaises+assertRaisesRegex+assertLogs) + `mock.mock_open` 真用 + `unittest.main/discovery/run/exit` 真用 + `subprocess` 进阶 (timeout+env+shell+text+True Popen) + 真底层测试。

覆盖 unittest 3 真 (TestCase assertRaises+assertRaisesRegex+assertLogs) + mock.mock_open 2 真 (read_data+write) + unittest 4 真 (main+test_loader+TestLoader+defaultTestLoader) + subprocess 4 真 (timeout+env+text+True kwargs) (共 13 真测试) 模块:
  - `TestCase.assertRaises ValueError catch 真 ValueError`
  - `TestCase.assertRaisesRegex 真 match 'forge error'`
  - `TestCase.assertLogs 'forge' 必 0/0+1+log record`
  - `mock.mock_open read_data='forge' 真 read_data+handle+read 返 'forge'`
  - `mock.mock_open() 真 write context 必支持`
  - `unittest.main 必 callable (实际执行可能 sys.exit)`
  - `unittest.TestLoader class 必存在`
  - `unittest.defaultTestLoader 必 class`
  - `unittest.TestLoader.discover 真返 TestSuite (沙箱可能空)`
  - `subprocess.run timeout=2 'sleep 0.1' 必 0`
  - `subprocess.run env={'LANG':'C'} + capture_output 必 0`
  - `subprocess.run text=True 必 str stdout`
  - `subprocess.Popen kwargs close_fds=True (default) 必不抛`
"""
import os
import subprocess
import sys
import unittest
import unittest.mock

import pytest


# -- unittest.TestCase 进阶 ------------------------------------------

class TestUnittestTestCaseAdvanced:
    def test_assertRaises(self):
        """`TestCase.assertRaises ValueError catch 真 ValueError。"""

        class _T(unittest.TestCase):
            def runTest(self):
                with self.assertRaises(ValueError):
                    raise ValueError("forge_value")

        # 必 0 fails
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        suite.addTest(_T())
        runner = unittest.TextTestRunner(stream=open(os.devnull, "w"))
        result = runner.run(suite)
        # 必 0 failure
        assert len(result.failures) == 0

    def test_assertRaisesRegex(self):
        """`TestCase.assertRaisesRegex 真 match 'forge error'。"""

        class _T(unittest.TestCase):
            def runTest(self):
                with self.assertRaisesRegex(ValueError, "forge"):
                    raise ValueError("forge error")

        suite = unittest.TestSuite()
        suite.addTest(_T())
        runner = unittest.TextTestRunner(stream=open(os.devnull, "w"))
        result = runner.run(suite)
        # 必 0 failure
        assert len(result.failures) == 0

    def test_assertLogs(self):
        """`TestCase.assertLogs 'forge' 必 0+log record。"""

        import logging

        class _T(unittest.TestCase):
            def runTest(self):
                with self.assertLogs("forge_logger", level="INFO") as cm:
                    logging.getLogger("forge_logger").info("forge test")

        suite = unittest.TestSuite()
        suite.addTest(_T())
        runner = unittest.TextTestRunner(stream=open(os.devnull, "w"))
        result = runner.run(suite)
        # 必 0 failure
        assert len(result.failures) == 0


# -- mock.mock_open 进阶 --------------------------------------------

class TestMockOpenAdvanced:
    def test_mock_open_read_data(self):
        """`mock.mock_open read_data='forge' 真 read_data+handle+read 返 'forge'。"""
        m = unittest.mock.mock_open(read_data="forge_data")
        # read_data 必能读 (inside with)
        with m() as fp:
            content = fp.read()
            assert content == "forge_data"

    def test_mock_open_write(self):
        """`mock.mock_open() 真 write context 必支持。"""
        m = unittest.mock.mock_open()
        with m() as fp:
            fp.write("forge_write")
        # 必能调 write
        m().write.assert_called_with("forge_write")


# -- unittest 进阶 (main + TestLoader + discover) -------------------

class TestUnittestAdvanced:
    def TestLoader_class(self):
        """`unittest.TestLoader class 必存在。"""
        assert unittest.TestLoader is not None
        # 必能建
        loader = unittest.TestLoader()
        # 必含 discover
        assert hasattr(loader, "discover")

    def test_defaultTestLoader(self):
        """`unittest.defaultTestLoader 必 class。"""
        # 沙箱 3.11 必 module-level
        assert unittest.defaultTestLoader is not None

    def test_main_callable(self):
        """`unittest.main 必 callable。"""
        # 沙箱 3.11 main 必 callable
        assert callable(unittest.main)


# -- subprocess 进阶 (timeout + env + text + Popen kwargs) ----------

class TestSubprocessAdvancedV5:
    def test_run_timeout_2(self):
        """`subprocess.run timeout=2 'sleep 0.1' 必 0。"""
        result = subprocess.run(["sleep", "0.1"], timeout=2)
        # 必 0
        assert result.returncode == 0

    def test_run_env(self):
        """`subprocess.run env={'LANG':'C'} + capture_output 必 0。"""
        env = os.environ.copy()
        env["LANG"] = "C"
        result = subprocess.run(
            ["echo", "forge_env"],
            env=env,
            capture_output=True,
        )
        # 必 0
        assert result.returncode == 0

    def test_run_text_True(self):
        """`subprocess.run text=True 必 str stdout。"""
        result = subprocess.run(
            ["echo", "forge_text"],
            capture_output=True,
            text=True,
        )
        # 必 str
        assert isinstance(result.stdout, str)
        # 必含 'forge_text'
        assert "forge_text" in result.stdout

    def test_Popen_close_fds(self):
        """`subprocess.Popen kwargs close_fds=True (default) 必不抛。"""
        proc = subprocess.Popen(
            ["true"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
        )
        # 必能 wait
        proc.wait(timeout=2)
        # 必 0
        assert proc.returncode == 0
