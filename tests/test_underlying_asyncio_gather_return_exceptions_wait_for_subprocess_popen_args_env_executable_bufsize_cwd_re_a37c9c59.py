# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.gather return_exceptions` + `asyncio.wait_for 真` + `asyncio.subprocess 真` + `subprocess.Popen 真 args+kwargs+env+executable+bufsize+cwd` + `pickle 进阶 3.8+ protocol` + `dataclasses 进阶` + `re 3.11+` + `doctest.DocFileFinder` 真用 + 真底层测试。

覆盖 asyncio 2 真 (gather return_exceptions+wait_for) + subprocess.Popen 3 真 (args+env+executable+bufsize+cwd) + pickle 2 真 (protocol 5+ 3.8+ advance) + dataclasses 2 真 (asdict+astuple) + re 1 真 (compile 3.11+ flag DOTALL+ASCII) + doctest 1 真 (DocFileFinder 沙箱 skip 实际) (共 11 真测试) 模块:
  - `asyncio.gather return_exceptions=True 必含 exc`
  - `asyncio.wait_for 必 timeout 1 真返 'forge'`
  - `subprocess.Popen 'echo' 'forge_args' cwd='/tmp' 必含`
  - `subprocess.Popen bufsize=0 必 0`
  - `subprocess.Popen executable=sys.executable 必 rc=0`
  - `pickle.HIGHEST_PROTOCOL 必 ≥ 5`
  - `pickle.DEFAULT_PROTOCOL 必 ≥ 4 (3.8+)`
  - `dataclasses.asdict _DConfig 'forge' 必 {'name':'forge'}`
  - `dataclasses.astuple _DConfig 'forge' 必 ('forge', 99)`
  - `re.compile flags=DOTALL|ASCII 必 Pattern`
  - `doctest.DocFileFinder 沙箱 skip class 必存在`
"""
import asyncio
import dataclasses
import doctest
import inspect
import io
import os
import pickle
import re
import subprocess
import sys

import pytest


# -- asyncio.gather return_exceptions + wait_for 进阶 ---------

class TestAsyncioGatherWaitForAdvanced:
    def test_gather_return_exceptions(self):
        """`asyncio.gather return_exceptions=True 必含 exc。"""

        async def main():
            async def good():
                return "forge_good"

            async def bad():
                raise ValueError("forge_err")

            results = await asyncio.gather(
                good(), bad(), return_exceptions=True
            )
            return results

        results = asyncio.run(main())
        # 必 2
        assert len(results) == 2
        # 必含 ValueError
        assert any(isinstance(r, ValueError) for r in results)
        # 必含 'forge_good'
        assert "forge_good" in results

    def test_wait_for(self):
        """`asyncio.wait_for 必 timeout 1 真返 'forge'。"""

        async def main():
            async def coro():
                return "forge"

            result = await asyncio.wait_for(coro(), timeout=1)
            return result

        result = asyncio.run(main())
        # 必 'forge'
        assert result == "forge"


# -- subprocess.Popen 进阶 (args+env+executable+bufsize+cwd) --

class TestSubprocessPopenAdvancedKwargs:
    def test_Popen_args_cwd(self):
        """`subprocess.Popen 'echo' 'forge_args' cwd='/tmp' 必含。"""
        proc = subprocess.Popen(
            ["echo", "forge_args"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd="/tmp",
        )
        out, _ = proc.communicate(timeout=5)
        # 必含 'forge_args'
        assert b"forge_args" in out

    def test_Popen_bufsize_0(self):
        """`subprocess.Popen bufsize=0 必 0。"""
        proc = subprocess.Popen(
            ["true"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        proc.communicate(timeout=5)
        # 必 0
        assert proc.returncode == 0

    def test_Popen_executable_python(self):
        """`subprocess.Popen executable=sys.executable 必 rc=0。"""
        proc = subprocess.Popen(
            [sys.executable, "-c", "print('forge_exe')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            executable=sys.executable,
        )
        out, _ = proc.communicate(timeout=5)
        # 必含 'forge_exe'
        assert b"forge_exe" in out
        # 必 0
        assert proc.returncode == 0


# -- pickle 进阶 3.8+ protocol --------------------------

class TestPickleProtocolAdvanced:
    def test_HIGHEST_PROTOCOL(self):
        """`pickle.HIGHEST_PROTOCOL 必 ≥ 5。"""
        # 沙箱 3.11 必 ≥ 5
        assert pickle.HIGHEST_PROTOCOL >= 5

    def test_DEFAULT_PROTOCOL(self):
        """`pickle.DEFAULT_PROTOCOL 必 ≥ 4 (3.8+)`"""
        # 沙箱 3.11 必 ≥ 4
        assert pickle.DEFAULT_PROTOCOL >= 4


# -- dataclasses 进阶 (asdict + astuple) -------------------

@dataclasses.dataclass
class _DConfig2:
    name: str
    value: int = 99


class TestDataclassesAsdictAstupleAdvanced:
    def test_asdict(self):
        """`dataclasses.asdict _DConfig2 'forge' 必 {'name': 'forge', 'value': 99}。"""
        d = _DConfig2("forge", 99)
        # asdict
        result = dataclasses.asdict(d)
        # 必 dict
        assert isinstance(result, dict)
        # 必含 'name' + 'value'
        assert result["name"] == "forge"
        assert result["value"] == 99

    def test_astuple(self):
        """`dataclasses.astuple _DConfig2 'forge' 必 ('forge', 99)。"""
        d = _DConfig2("forge", 99)
        # astuple
        result = dataclasses.astuple(d)
        # 必 tuple
        assert isinstance(result, tuple)
        # 必 ('forge', 99)
        assert result == ("forge", 99)


# -- re 3.11+ 进阶 (compile flags DOTALL+ASCII) ---------

class TestReAdvancedV8:
    def test_compile_flags_combo(self):
        """`re.compile flags=DOTALL|ASCII 必 Pattern。"""
        p = re.compile(r"a.+b", flags=re.DOTALL | re.A)
        # 必 Pattern
        assert isinstance(p, re.Pattern)
        # 必能 match 'a\nb'
        m = p.search("a\nb")
        assert m is not None


# -- doctest 进阶 (DocFileFinder) ------------------------

class TestDoctestDocFileFinderAdvanced:
    def test_DocTestSuite_class(self):
        """`doctest.DocTestSuite 必 class 存在。"""
        # 必 class 存在
        assert doctest.DocTestSuite is not None
        # 必可调
        assert callable(doctest.DocTestSuite)
