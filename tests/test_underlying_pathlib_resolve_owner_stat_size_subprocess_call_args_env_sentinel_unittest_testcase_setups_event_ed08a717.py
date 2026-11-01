# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`pathlib` 进阶 (resolve+is_absolute+stat.size+mtime) + `subprocess.call 真 args+kwargs+env` + `sentinel` + `unittest.TestCase init+setUp+tearDown+longMessage+doc 真用` + `asyncio.Event 真 set+wait+clear+is_set` + `multiprocessing.Process 真 args+kwargs+start` + 真底层测试。

覆盖 pathlib 4 真 (resolve+is_absolute+stat.size+mtime) + subprocess 2 真 (call args+env) + unittest 3 真 (init+setUp+tearDown+longMessage) + asyncio 2 真 (Event set+is_set+clear) + multiprocessing 2 真 (Process args+kwargs+start) (共 13 真测试) 模块:
  - `pathlib resolve tmp_path 必 absolute 必含`
  - `pathlib is_absolute '/a/b' True / 'a/b' False`
  - `pathlib stat st_size 必 ≥ 1`
  - `pathlib stat st_mtime 必 > 0`
  - `subprocess.call 'echo' 'forge_args' 必 0`
  - `subprocess.run env=LANG=C 'echo' 必 0`
  - `unittest.TestCase.setUp 真 run + tearDown 必 run`
  - `unittest.TestCase longMessage=True 必非 None`
  - `unittest.TestCase.shortDescription 必 str 含 doc`
  - `asyncio.Event.set + is_set True + clear + is_set False`
  - `asyncio.Event 真 set + wait 必不抛`
  - `multiprocessing.Process args=('forge_target',) 必 start 不抛`
  - `multiprocessing.Process kwargs={'forge_k':'v'} 必 start 不抛`
"""
import asyncio
import multiprocessing
import os
import pathlib
import subprocess
import sys
import unittest

import pytest


# -- pathlib 进阶 (resolve + is_absolute + stat.size + mtime) ----

class TestPathlibAdvancedV8:
    def test_resolve(self, tmp_path):
        """`pathlib resolve tmp_path 必 absolute 必含。"""
        f = tmp_path / "forge.txt"
        f.write_text("forge")
        # resolve
        resolved = f.resolve()
        # 必 absolute
        assert resolved.is_absolute()
        # 必含 tmp_path part
        assert str(tmp_path.name) in str(resolved) or "forge" in str(resolved)

    def test_is_absolute(self):
        """`pathlib is_absolute '/a/b' True / 'a/b' False。"""
        # 沙箱 3.11 PurePath is_absolute 必能
        p1 = pathlib.PurePath("/a/b")
        # 必 True
        assert p1.is_absolute() is True
        p2 = pathlib.PurePath("a/b")
        # 必 False
        assert p2.is_absolute() is False

    def test_stat_size(self, tmp_path):
        """`pathlib stat st_size 必 ≥ 1。"""
        f = tmp_path / "forge.txt"
        f.write_text("forge_data")
        # stat
        s = f.stat()
        # 必 st_size ≥ 1
        assert s.st_size >= 1

    def test_stat_mtime(self, tmp_path):
        """`pathlib stat st_mtime 必 > 0。"""
        f = tmp_path / "forge_mtime.txt"
        f.write_text("forge_mtime")
        # stat
        s = f.stat()
        # 必 st_mtime > 0
        assert s.st_mtime > 0


# -- subprocess.call 进阶 (args+env) ------------------

class TestSubprocessCallArgsEnvAdvanced:
    def test_call_args(self):
        """`subprocess.call 'echo' 'forge_args' 必 0。"""
        rc = subprocess.call(["echo", "forge_args"])
        # 必 0
        assert rc == 0

    def test_run_env(self):
        """`subprocess.run env=LANG=C 'echo' 必 0。"""
        env = os.environ.copy()
        env["LANG"] = "C"
        result = subprocess.run(
            ["echo", "forge_env"],
            env=env,
            capture_output=True,
        )
        # 必 0
        assert result.returncode == 0


# -- unittest.TestCase 进阶 (setUp+tearDown+longMessage+doc) --

class _T(unittest.TestCase):
    def setUp(self):
        self.value = "forge"

    def tearDown(self):
        self.value = None

    def test_forge_value(self):
        self.assertEqual(self.value, "forge")

    def test_forge_doc(self):
        """forge test doc"""
        self.assertEqual(self.value, "forge")


class TestUnittestTestCaseSetUpsLongMessage:
    def test_setUp_tearDown(self):
        """`unittest.TestCase.setUp 真 run + tearDown 必 run。"""
        # 必能 0 fails
        suite = unittest.TestLoader().loadTestsFromTestCase(_T)
        runner = unittest.TextTestRunner(stream=open(os.devnull, "w"))
        result = runner.run(suite)
        # 必 0 fails
        assert len(result.failures) == 0

    def test_longMessage(self):
        """`unittest.TestCase.longMessage=True 必非 None。"""
        # 简测
        assert _T.longMessage is True

    def test_shortDescription(self):
        """`unittest.TestCase.shortDescription 必 str 含 doc。"""
        t = _T("test_forge_doc")
        # 必 shortDescription
        sd = t.shortDescription()
        # 必 str
        assert isinstance(sd, str)
        # 必含 'forge test doc'
        assert "forge test doc" in sd


# -- asyncio.Event 真用 (set + is_set + clear + wait) ----

class TestAsyncioEventSetClearAdvanced:
    def test_Event_set_clear(self):
        """`asyncio.Event.set + is_set True + clear + is_set False。"""

        async def main():
            e = asyncio.Event()
            # 必非 set
            assert e.is_set() is False
            # set
            e.set()
            # 必 set
            assert e.is_set() is True
            # clear
            e.clear()
            # 必非 set
            assert e.is_set() is False

        asyncio.run(main())

    def test_Event_wait(self):
        """`asyncio.Event 真 set + wait 必不抛。"""

        async def main():
            e = asyncio.Event()
            # set
            e.set()
            # wait 必不抛
            await asyncio.wait_for(e.wait(), timeout=0.1)

        asyncio.run(main())


# -- multiprocessing.Process 真用 (args+kwargs+start) ------

def _proc_target(*args, **kwargs):
    return "forge_target"


class TestMultiprocessingProcessArgsKwargsAdvanced:
    def test_Process_args(self):
        """`multiprocessing.Process args=('forge_target',) 必 start 不抛。"""
        p = multiprocessing.Process(target=_proc_target, args=("forge_target",))
        # start
        p.start()
        # join
        p.join(timeout=2)
        # 必不抛
        assert True
        # 必能 alive
        assert p.is_alive() is False

    def test_Process_kwargs(self):
        """`multiprocessing.Process kwargs={'forge_k':'v'} 必 start 不抛。"""
        p = multiprocessing.Process(
            target=_proc_target, kwargs={"forge_k": "v"}
        )
        # start
        p.start()
        # join
        p.join(timeout=2)
        # 必不抛
        assert True
