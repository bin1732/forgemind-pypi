# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio 进阶 (create_task+gather+shield+wait_for)` + `shutil 进阶 (copyfile+copytree+rmtree+move)` + `tempfile 进阶 (NamedTemporaryFile 真用 + TemporaryFile)` + `pickle 进阶 (dispatch_table 真用)` + `asyncio.subprocess.create_subprocess_exec 真用` + 真底层测试。

覆盖 asyncio 4 真 + shutil 4 真 + tempfile 2 真 + pickle 1 真 + asyncio.subprocess 1 真 (共 12 真测试) 模块:
  - `asyncio.create_task 真用 必 'forge_value'`
  - `asyncio.gather 真并发 3 task 必 [0,1,2]`
  - `asyncio.shield 真 coroutine 必 'forge_shield'`
  - `asyncio.wait_for 真 'forge' 必 'forge'`
  - `shutil.copyfile 必 file content 'forge'`
  - `shutil.copytree 必 1 file 'forge_tree.txt'`
  - `shutil.rmtree 必 not exist`
  - `shutil.move 必 file exists 'forge_moved.txt'`
  - `tempfile.NamedTemporaryFile 'w+b' 真 'forge'`
  - `tempfile.TemporaryFile 真 'forge_temp'`
  - `pickle.dispatch_table copy 必 len ≥ 1`
  - `asyncio.create_subprocess_exec 'echo forge_async' 必含 'forge_async'`
"""
import asyncio
import os
import pathlib
import pickle
import shutil
import tempfile

import pytest


# -- asyncio 进阶 (create_task+gather+shield+wait_for) ----

class TestAsyncioCreateTaskGatherShieldWaitForAdvance:
    def test_create_task(self):
        """`asyncio.create_task 真用 必 'forge_value'。"""

        async def main():
            async def coro():
                return "forge_value"

            task = asyncio.create_task(coro())
            result = await task
            return result

        result = asyncio.run(main())
        # 必 'forge_value'
        assert result == "forge_value"

    def test_gather_3(self):
        """`asyncio.gather 真并发 3 task 必 [0,1,2]。"""

        async def main():
            async def coro(i):
                return i

            results = await asyncio.gather(*[coro(i) for i in range(3)])
            return results

        results = asyncio.run(main())
        # 必 [0, 1, 2]
        assert results == [0, 1, 2]

    def test_shield(self):
        """`asyncio.shield 真 coroutine 必 'forge_shield'。"""

        async def main():
            async def coro():
                return "forge_shield"

            result = await asyncio.shield(coro())
            return result

        result = asyncio.run(main())
        # 必 'forge_shield'
        assert result == "forge_shield"

    def test_wait_for(self):
        """`asyncio.wait_for 真 'forge' 必 'forge'。"""

        async def main():
            async def coro():
                return "forge"

            result = await asyncio.wait_for(coro(), timeout=1)
            return result

        result = asyncio.run(main())
        # 必 'forge'
        assert result == "forge"


# -- shutil 进阶 (copyfile+copytree+rmtree+move) ---------

class TestShutilCopyCopytreeRmtreeMoveAdvance:
    def test_copyfile(self, tmp_path):
        """`shutil.copyfile 必 file content 'forge'。"""
        src = tmp_path / "forge_src.txt"
        src.write_text("forge")
        dst = tmp_path / "forge_dst.txt"
        # copyfile
        shutil.copyfile(src, dst)
        # 必 'forge' content
        assert dst.read_text() == "forge"

    def test_copytree(self, tmp_path):
        """`shutil.copytree 必 1 file 'forge_tree.txt'。"""
        src = tmp_path / "forge_src_dir"
        src.mkdir()
        (src / "forge_tree.txt").write_text("forge")
        dst = tmp_path / "forge_dst_dir"
        # copytree
        shutil.copytree(src, dst)
        # 必 1 file
        assert (dst / "forge_tree.txt").exists()

    def test_rmtree(self, tmp_path):
        """`shutil.rmtree 必 not exist。"""
        d = tmp_path / "forge_rmtree"
        d.mkdir()
        (d / "forge.txt").write_text("forge")
        # rmtree
        shutil.rmtree(d)
        # 必 not exist
        assert not d.exists()

    def test_move(self, tmp_path):
        """`shutil.move 必 file exists 'forge_moved.txt'。"""
        src = tmp_path / "forge_move_src"
        src.mkdir()
        (src / "forge_moved.txt").write_text("forge")
        dst = tmp_path / "forge_move_dst"
        # move
        shutil.move(str(src), str(dst))
        # 必 file exists
        assert (dst / "forge_moved.txt").exists()


# -- tempfile 进阶 (NamedTemporaryFile 真用) ------------

class TestTempfileNamedTemporaryFileModeSuffixPrefixAdvance:
    def test_NamedTemporaryFile_wb(self):
        """`tempfile.NamedTemporaryFile 'w+b' 真 'forge'。"""
        with tempfile.NamedTemporaryFile(mode="w+b", delete=False) as f:
            f.write(b"forge")
            f.flush()
            path = f.name
        # read back
        with open(path, "rb") as fp:
            content = fp.read()
        # 必 'forge'
        assert content == b"forge"
        os.unlink(path)

    def test_TemporaryFile(self):
        """`tempfile.TemporaryFile 真 'forge_temp'。"""
        f = tempfile.TemporaryFile(mode="w+")
        try:
            f.write("forge_temp")
            f.seek(0)
            content = f.read()
            # 必 'forge_temp'
            assert content == "forge_temp"
        finally:
            f.close()


# -- pickle 进阶 (dispatch_table 真用) -----------------

class TestPickleDispatchTableAdvance:
    def test_dispatch_table(self):
        """`pickle.dispatch_table copy 必 len ≥ 1。"""
        dt = pickle.dispatch_table.copy()
        # 必 dict ≥ 1
        assert isinstance(dt, dict)
        assert len(dt) >= 1


# -- asyncio.subprocess.create_subprocess_exec 真用 ----

class TestAsyncioSubprocessCreateSubprocessExecAdvance:
    def test_create_subprocess_exec(self):
        """`asyncio.create_subprocess_exec 'echo forge_async' 必含 'forge_async'。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "echo", "forge_async",
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout

        stdout = asyncio.run(main())
        # 必含 'forge_async'
        assert b"forge_async" in stdout
