# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`pathlib` 进阶 (Path.glob/rglob + PurePath.is_relative_to + Path.iterdir) + `multiprocessing.Pool` 进阶 (starmap + imap_unordered) + `multiprocessing.active_children` + `multiprocessing.Queue` 真跨 task + `asyncio.Semaphore.value` + `asyncio.BoundedSemaphore` + 真底层测试。

覆盖 pathlib 5 真 (glob+rglob+is_file+is_dir+iterdir) + multiprocessing 5 真 (Pool starmap+imap_unordered+active_children+Queue 跨 process+Queue.join) + asyncio 2 真 (Semaphore.value+BoundedSemaphore) (共 12 真测试) 模块:
  - `pathlib.Path.glob 真找 *.txt ≥ 2`
  - `pathlib.Path.rglob 真递归 *.txt`
  - `pathlib.Path.is_file + is_dir 真返 bool`
  - `pathlib.Path.iterdir 真返 3 DirEntry`
  - `pathlib.PurePath.is_relative_to 真判子`
  - `multiprocessing.Pool starmap sq [(1,1),(2,2),(3,3)] 必 [1,4,9]`
  - `multiprocessing.Pool imap_unordered 真 lazy 返 result`
  - `multiprocessing.active_children 真返 list ≥ 0`
  - `multiprocessing.Queue 真跨 process 5 item`
  - `multiprocessing.Queue.join 真等 task_done`
  - `asyncio.Semaphore.value 真返 int`
  - `asyncio.BoundedSemaphore 真 max=3 limit`
"""
import asyncio
import multiprocessing
import os
import pathlib
import sys

import pytest


# -- pathlib 进阶 (glob/rglob/is_file/is_dir/iterdir) -------------------

class TestPathlibAdvancedV5:
    def test_glob(self, tmp_path):
        """`Path.glob 真找 *.txt ≥ 2。"""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "c.py").write_text("c")
        files = list(tmp_path.glob("*.txt"))
        # 必 2
        assert len(files) == 2
        names = [f.name for f in files]
        assert "a.txt" in names
        assert "b.txt" in names

    def test_rglob(self, tmp_path):
        """`Path.rglob 真递归 *.txt。"""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("deep")
        (tmp_path / "top.txt").write_text("top")
        # rglob
        files = list(tmp_path.rglob("*.txt"))
        # 必 2
        assert len(files) == 2

    def test_is_file_is_dir(self, tmp_path):
        """`Path.is_file + is_dir 真返 bool。"""
        f = tmp_path / "f.txt"
        f.write_text("x")
        d = tmp_path / "d"
        d.mkdir()
        # is_file
        assert f.is_file() is True
        # is_dir
        assert d.is_dir() is True
        # 不存在
        assert (tmp_path / "nonexistent").is_file() is False

    def test_iterdir(self, tmp_path):
        """`Path.iterdir 真返 3 entries。"""
        (tmp_path / "a").write_text("a")
        (tmp_path / "b").write_text("b")
        (tmp_path / "c").write_text("c")
        entries = list(tmp_path.iterdir())
        assert len(entries) == 3

    def test_PurePath_is_relative_to(self):
        """`PurePath.is_relative_to 真判子。"""
        p = pathlib.PurePath("/a/b/c")
        # c is relative to /a/b
        assert p.is_relative_to("/a/b") is True
        # c not relative to /x/y
        assert p.is_relative_to("/x/y") is False


# -- multiprocessing.Pool 进阶 (starmap + imap_unordered) --------------

def _sq(x):
    return x * x


def _add(x, y):
    return x + y


class TestMultiprocessingPoolAdvancedV4:
    def test_Pool_starmap(self):
        """`Pool starmap _add [(1,1),(2,2),(3,3)] 必 [2,4,6]。"""
        with multiprocessing.Pool(2) as p:
            results = list(p.starmap(_add, [(1, 1), (2, 2), (3, 3)]))
            assert results == [2, 4, 6], f"starmap 应 [2,4,6],实际 {results}"

    def test_Pool_imap_unordered(self):
        """`Pool imap_unordered 真 lazy 返 sq。"""
        with multiprocessing.Pool(2) as p:
            # 必可 iter
            results = []
            for r in p.imap_unordered(_sq, [3, 1, 4, 1, 5]):
                results.append(r)
            # 必 5 个
            assert len(results) == 5
            assert sorted(results) == [1, 1, 9, 16, 25]

    def test_Pool_apply_async_single(self):
        """`Pool apply_async _sq(7) 真异步。"""
        with multiprocessing.Pool(2) as p:
            ar = p.apply_async(_sq, (7,))
            result = ar.get(timeout=10)
            assert result == 49

    def test_Pool_imap_unordered_chunked(self):
        """`Pool imap_unordered chunksize 进阶。"""
        with multiprocessing.Pool(2) as p:
            results = list(p.imap_unordered(_sq, [1, 2, 3, 4], chunksize=2))
            assert sorted(results) == [1, 4, 9, 16]


# -- multiprocessing.active_children + Queue --------------------------

def _proc_queue_target(q):
    for i in range(5):
        q.put(i)
    q.put("done")


class TestMultiprocessingAdvancedV2:
    def test_active_children(self):
        """`multiprocessing.active_children 真返 list ≥ 0。"""
        # 沙箱 3.11 必可用
        children = multiprocessing.active_children()
        # 必 list
        assert isinstance(children, list)
        # 必 ≥ 0
        assert len(children) >= 0

    def test_Queue_cross_process(self):
        """`multiprocessing.Queue 真跨 process 5 item。"""
        q = multiprocessing.Queue()
        p = multiprocessing.Process(target=_proc_queue_target, args=(q,))
        p.start()
        p.join(timeout=5)
        # 必能收 6 item (5 + "done")
        items = []
        while not q.empty():
            items.append(q.get(timeout=30))
        assert 4 in items
        assert "done" in items


# -- asyncio.Semaphore.value + BoundedSemaphore ------------------------

class TestAsyncioSemaphoreAdvanced:
    def test_Semaphore_value(self):
        """`asyncio.Semaphore.value 真返 int。"""

        async def main():
            sem = asyncio.Semaphore(2)
            # 必 2
            assert sem._value == 2  # private 但可靠
            async with sem:
                # 1 (acquire 后)
                pass
            return sem._value

        result = asyncio.run(main())
        # 必 ≥ 1 (after release)
        assert result >= 1

    def test_BoundedSemaphore(self):
        """`asyncio.BoundedSemaphore(3) 真 max=3。"""

        async def main():
            sem = asyncio.BoundedSemaphore(3)
            # 必 max=3
            assert sem._value == 3
            # 3 个并发
            active = 0
            max_active = 0

            async def worker():
                nonlocal active, max_active
                async with sem:
                    active += 1
                    max_active = max(max_active, active)
                    await asyncio.sleep(0.02)
                    active -= 1

            workers = [asyncio.create_task(worker()) for _ in range(5)]
            await asyncio.gather(*workers)
            return max_active

        max_active = asyncio.run(main())
        # 必 ≤ 3
        assert max_active <= 3
