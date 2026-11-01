# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.gather/wait/create_task` 真并发 + `concurrent.futures.ProcessPoolExecutor` 真 fork+map+submit+as_completed + `itertools.combinations_with_replacement/groupby/accumulate/starmap` 真底层测试。

覆盖 asyncio 3 真 (gather+wait+create_task) + concurrent.futures.ProcessPoolExecutor 2 真 (map+submit) + itertools 4 真 (combinations_with_replacement+groupby+accumulate+starmap) (共 9 真测试) 模块:
  - `asyncio.gather 3 coroutines 真并发 [1,2,3]`
  - `asyncio.wait 真 ≥ 1 task 必 done`
  - `asyncio.create_task 真 task + await result`
  - `ProcessPoolExecutor 真 map [3,1,4,1,5] → sq [9,1,16,1,25]`
  - `ProcessPoolExecutor.submit 必 future + result = 49`
  - `itertools.combinations_with_replacement 'AB' r=2 必 [('A','A'),('A','B'),('B','B')]`
  - `itertools.groupby 1,1,2,2,3,3 必 3 groups`
  - `itertools.accumulate [1,2,3,4] 必 [1,3,6,10]`
  - `itertools.starmap 真 _add [1,2][3,4] 必 [3,7]`
"""
import asyncio
import concurrent.futures
import itertools
import os

import pytest


def _slow_sq(x):
    return x * x


def _slow_add(x, y):
    return x + y


# -- asyncio 进阶 (gather + wait + create_task) ---------------------

class TestAsyncioAdvancedV2:
    def test_gather(self):
        """`asyncio.gather 3 coroutines 真并发 [1,2,3]。"""

        async def main():
            async def coro(i):
                return i

            results = await asyncio.gather(coro(1), coro(2), coro(3))
            return results

        results = asyncio.run(main())
        # 必 [1,2,3]
        assert results == [1, 2, 3]

    def test_wait(self):
        """`asyncio.wait 真 ≥ 1 task 必 done。"""

        async def main():
            async def coro():
                return "forge_wait"

            t = asyncio.create_task(coro())
            done, pending = await asyncio.wait([t], timeout=2)
            # 必 ≥ 1 done
            assert len(done) >= 1
            # 必 0 pending (已 done)
            assert len(pending) == 0
            return done

        done = asyncio.run(main())
        # 必能 result
        for d in done:
            assert d.result() == "forge_wait"

    def test_create_task_await(self):
        """`asyncio.create_task 真 task + await result。"""

        async def main():
            async def coro():
                return "forge_task"

            t = asyncio.create_task(coro())
            result = await t
            return result

        result = asyncio.run(main())
        # 必 'forge_task'
        assert result == "forge_task"


# -- concurrent.futures.ProcessPoolExecutor 进阶 -------------------

class TestProcessPoolExecutorAdvanced:
    def test_ProcessPoolExecutor_map(self):
        """`ProcessPoolExecutor 真 map [3,1,4,1,5] → sq [9,1,16,1,25]。"""
        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as p:
            results = list(p.map(_slow_sq, [3, 1, 4, 1, 5]))
            # 必 5 个 sq
            assert sorted(results) == [1, 1, 9, 16, 25]

    def test_ProcessPoolExecutor_submit(self):
        """`ProcessPoolExecutor.submit 必 future + result = 49。"""
        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as p:
            fut = p.submit(_slow_sq, 7)
            result = fut.result(timeout=10)
            # 必 49
            assert result == 49


# -- itertools 进阶 (combinations_with_replacement + groupby + accumulate + starmap) -

class TestItertoolsAdvancedV3:
    def test_combinations_with_replacement(self):
        """`combinations_with_replacement 'AB' r=2 必 [AA,AB,BB]。"""
        result = list(itertools.combinations_with_replacement("AB", 2))
        # 必 [(A,A), (A,B), (B,B)]
        assert result == [("A", "A"), ("A", "B"), ("B", "B")]

    def test_groupby_3groups(self):
        """`groupby 1,1,2,2,3,3 必 3 groups。"""
        data = [1, 1, 2, 2, 3, 3]
        groups = list(itertools.groupby(data, key=lambda x: x))
        # 必 3
        assert len(groups) == 3
        # 必 1, 2, 3
        keys = [k for k, _ in groups]
        assert keys == [1, 2, 3]

    def test_accumulate_sum(self):
        """`accumulate [1,2,3,4] 必 [1,3,6,10] (默认 sum)`"""
        result = list(itertools.accumulate([1, 2, 3, 4]))
        # 必 [1, 3, 6, 10]
        assert result == [1, 3, 6, 10]

    def test_starmap_add(self):
        """`starmap 真 _add [1,2][3,4] 必 [3,7]。"""
        result = list(itertools.starmap(_slow_add, [(1, 2), (3, 4)]))
        # 必 [3, 7]
        assert result == [3, 7]
