# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`numbers` 进阶 (ABC 5 + Real 真值 + Integral 真值) + `math 进阶 (log10+log2+factorial+degrees+radians+atan+asin+acos+dist+comb 3.10+)` + `pprint.pformat+isrecursive+PrettyPrinter 进阶` + `subprocess.run encoding+bufsize+Popen kwargs 真用` + 真底层测试。

覆盖 numbers 2 真 (Real+Integral) + math 8 真 (log10+log2+factorial+degrees+radians+atan+asin+acos) + pprint 2 真 (pformat+PrettyPrinter) + subprocess 3 真 (Popen stdin+bufsize+encoding) (共 15 真测试) 模块:
  - `numbers.Real 真 value=3.14 + isinstance int/float`
  - `numbers.Integral 真 value=42 + bit_length`
  - `math.log10 100 必 2.0`
  - `math.log2 8 必 3.0`
  - `math.factorial 5 必 120`
  - `math.degrees pi 必 ~180.0`
  - `math.radians 180 必 ~3.1416`
  - `math.atan 1 必 ~0.7854`
  - `math.asin 0 必 0.0`
  - `math.acos 1 必 0.0`
  - `pprint.pformat {'a':1,'b':2} 必 str`
  - `pprint.PrettyPrinter 必 pformat 真用`
  - `subprocess.Popen 真 stdin 'forge' cat echo back`
  - `subprocess.run 'echo' encoding='utf-8' 必 0`
  - `subprocess.Popen bufsize=0 'true' 必 0`
"""
import math
import numbers
import os
import pprint
import subprocess
import sys

import pytest


# -- numbers 进阶 (Real + Integral) ------------------------

class TestNumbersAdvancedV2:
    def test_Real(self):
        """`numbers.Real 真 value=3.14 + isinstance int/float。"""
        x = 3.14
        # 必是 Real
        assert isinstance(x, numbers.Real)
        # 必 int + float
        assert isinstance(x, (int, float))
        # 真 value
        assert x == 3.14

    def test_Integral(self):
        """`numbers.Integral 真 value=42 + bit_length。"""
        i = 42
        # 必是 Integral
        assert isinstance(i, numbers.Integral)
        # 必 int
        assert isinstance(i, int)
        # bit_length 必 6
        assert i.bit_length() == 6


# -- math 进阶 (log10 + log2 + factorial + degrees + radians + atan+asin+acos) -

class TestMathAdvancedV4:
    def test_log10(self):
        """`math.log10 100 必 2.0。"""
        assert math.log10(100) == 2.0

    def test_log2(self):
        """`math.log2 8 必 3.0。"""
        assert math.log2(8) == 3.0

    def test_factorial(self):
        """`math.factorial 5 必 120。"""
        assert math.factorial(5) == 120

    def test_degrees(self):
        """`math.degrees pi 必 ~180.0。"""
        r = math.degrees(math.pi)
        # 必 ~ 180.0
        assert abs(r - 180.0) < 1e-9

    def test_radians(self):
        """`math.radians 180 必 ~3.1416。"""
        r = math.radians(180)
        # 必 ~ 3.1416
        assert abs(r - math.pi) < 1e-9

    def test_atan(self):
        """`math.atan 1 必 ~0.7854。"""
        r = math.atan(1)
        # 必 ~ 0.7854
        assert abs(r - 0.7854) < 1e-3

    def test_asin(self):
        """`math.asin 0 必 0.0。"""
        r = math.asin(0)
        # 必 0.0
        assert r == 0.0

    def test_acos(self):
        """`math.acos 1 必 0.0。"""
        r = math.acos(1)
        # 必 0.0
        assert r == 0.0


# -- pprint 进阶 (pformat + PrettyPrinter) ---------------

class TestPprintAdvancedV3:
    def test_pformat(self):
        """`pprint.pformat {'a':1,'b':2} 必 str。"""
        result = pprint.pformat({"a": 1, "b": 2})
        # 必 str
        assert isinstance(result, str)
        # 必含 'a': 1
        assert "'a': 1" in result
        # 必含 'b': 2
        assert "'b': 2" in result

    def test_PrettyPrinter_pformat(self):
        """`pprint.PrettyPrinter 必 pformat 真用。"""
        pp = pprint.PrettyPrinter()
        # 必能 pformat
        result = pp.pformat({"a": 1})
        # 必含 'a': 1
        assert "'a': 1" in result


# -- subprocess 进阶 (Popen stdin + bufsize + run encoding) -

class TestSubprocessAdvancedV6:
    def test_Popen_stdin(self):
        """`subprocess.Popen 真 stdin 'forge' cat echo back。"""
        proc = subprocess.Popen(
            ["cat"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, _ = proc.communicate(input=b"forge_stdin", timeout=5)
        # 必含 'forge_stdin'
        assert b"forge_stdin" in out
        # 必 0
        assert proc.returncode == 0

    def test_run_encoding_utf8(self):
        """`subprocess.run 'echo' encoding='utf-8' 必 0。"""
        result = subprocess.run(
            ["echo", "forge_encoding"],
            capture_output=True,
            encoding="utf-8",
        )
        # 必 0
        assert result.returncode == 0
        # stdout 必 str
        assert isinstance(result.stdout, str)
        # 必含 'forge_encoding'
        assert "forge_encoding" in result.stdout

    def test_Popen_bufsize_0(self):
        """`subprocess.Popen bufsize=0 'true' 必 0。"""
        proc = subprocess.Popen(
            ["true"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        proc.communicate(timeout=5)
        # 必 0
        assert proc.returncode == 0
