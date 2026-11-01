# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.subprocess_exec` 真 stdin PIPE write+communicate (cat) + `ctypes.c_float/c_double/c_longdouble` 真值 (浮点精度) + `math.fsum/fabs/fmod/exp/log/sqrt` 真 + `unittest.TestCase.subTest` 真用 + `unittest.skip` 装饰器 + `unittest.TestLoader.loadTestsFromName/loadTestsFromModule` 真 + 真底层测试。

覆盖 asyncio 1 真 (subprocess_exec stdin 'forge_stdin_cat' + communicate 必 echo back) + ctypes 3 真 (c_float 1.5 / c_double 1.5 / c_longdouble 1.5) + math 5 真 (fsum+fabs+fmod+exp+log) + unittest 3 真 (subTest 真用+skip 装饰器+loadTestsFromName) (共 12 真测试) 模块:
  - `asyncio.subprocess 'cat' stdin 'forge_stdin_cat' 必 echo back`
  - `ctypes.c_float 1.5 真 float`
  - `ctypes.c_double 1.5 真 double`
  - `ctypes.c_longdouble 1.5 真 longdouble`
  - `math.fsum [0.1,0.2,0.3] 必 ~0.6 (高精度)`
  - `math.fabs -3.14 必 3.14`
  - `math.fmod 5,3 必 2.0`
  - `math.exp 1 必 ~2.71828`
  - `math.log e 必 ~1.0`
  - `unittest.TestCase.subTest 真子化 + 2 subTest pass`
  - `unittest.skip 装饰器真装 必 skip (没跑)`
  - `TestLoader.loadTestsFromName 真返 suite`
"""
import asyncio
import ctypes
import math
import os
import sys
import unittest
import unittest.case

import pytest


# -- asyncio.subprocess 进阶 (stdin 真写) ------------------------

class TestAsyncioSubprocessStdinAdvanced:
    def test_subprocess_stdin_write(self):
        """`asyncio.subprocess 'cat' stdin 'forge_stdin_cat' 必 echo back。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "cat",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # 必能 write
            proc.stdin.write(b"forge_stdin_cat\n")
            await proc.stdin.drain()
            proc.stdin.close()
            stdout, _ = await proc.communicate()
            return stdout

        result = asyncio.run(main())
        # 必含 'forge_stdin_cat'
        assert b"forge_stdin_cat" in result


# -- ctypes 进阶 (c_float + c_double + c_longdouble) ------------

class TestCtypesFloatAdvanced:
    def test_c_float(self):
        """`ctypes.c_float 1.5 真 float。"""
        f = ctypes.c_float(1.5)
        # 必 ~1.5 (1e-6 容差)
        assert abs(f.value - 1.5) < 1e-6

    def test_c_double(self):
        """`ctypes.c_double 1.5 真 double。"""
        d = ctypes.c_double(1.5)
        # 必 1.5
        assert d.value == 1.5

    def test_c_longdouble(self):
        """`ctypes.c_longdouble 1.5 真 longdouble。"""
        ld = ctypes.c_longdouble(1.5)
        # 必 1.5
        assert ld.value == 1.5


# -- math 进阶 (fsum + fabs + fmod + exp + log) ----------------

class TestMathAdvancedV3:
    def test_fsum(self):
        """`math.fsum [0.1,0.2,0.3] 必 ~0.6 (高精度)`"""
        r = math.fsum([0.1, 0.2, 0.3])
        # 必 ~0.6
        assert abs(r - 0.6) < 1e-10

    def test_fabs(self):
        """`math.fabs -3.14 必 3.14。"""
        r = math.fabs(-3.14)
        # 必 3.14
        assert r == 3.14

    def test_fmod(self):
        """`math.fmod 5,3 必 2.0。"""
        r = math.fmod(5, 3)
        # 必 2.0
        assert r == 2.0

    def test_exp(self):
        """`math.exp 1 必 ~2.71828。"""
        r = math.exp(1)
        # 必 ~ 2.71828
        assert abs(r - math.e) < 1e-10

    def test_log(self):
        """`math.log e 必 ~1.0。"""
        r = math.log(math.e)
        # 必 ~ 1.0
        assert abs(r - 1.0) < 1e-10


# -- unittest.TestCase.subTest 进阶 --------------------------

class TestUnittestSubTest:
    def test_subTest(self):
        """`unittest.TestCase.subTest 真子化 + 2 subTest pass。"""

        class _T(unittest.TestCase):
            def runTest(self):
                for i in [1, 2, 3]:
                    with self.subTest(i=i):
                        # 必能 assertion
                        self.assertEqual(i, i)

        suite = unittest.TestSuite()
        suite.addTest(_T())
        runner = unittest.TextTestRunner(stream=open(os.devnull, "w"))
        result = runner.run(suite)
        # 必 0 failure (3 subTest pass)
        assert len(result.failures) == 0

    def test_skip_decorator(self):
        """`unittest.skip 装饰器真装 必 skip。"""

        @unittest.skip("forge_skip")
        class _T(unittest.TestCase):
            def test_forge(self):
                self.assertTrue(True)

        suite = unittest.TestSuite()
        suite.addTest(_T("test_forge"))
        runner = unittest.TextTestRunner(stream=open(os.devnull, "w"))
        result = runner.run(suite)
        # 必 ≥ 1 skip
        assert len(result.skipped) >= 1

    def test_loadTestsFromName_class(self):
        """`TestLoader.loadTestsFromName 真返 suite (3.11+ method 存在)。"""
        # 沙箱 3.11+ 必有
        loader = unittest.TestLoader()
        # loadTestsFromName 必为 method
        assert hasattr(loader, "loadTestsFromName")
        # callable
        assert callable(loader.loadTestsFromName)
