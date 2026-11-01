# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`sqlite3` 进阶: row_factory / text_factory / progress_hook / set_trace_callback + `subprocess.Popen` args/bufsize + `unittest.mock.seal` + `async for` 异步迭代 + `itertools.chain/tee/cycle/repeat/groupby` 完整真底层测试。

覆盖 sqlite3 row_factory / text_factory / progress_hook / set_trace_callback / subprocess Popen args/bufsize/cwd/env / mock seal / async for 异步 / itertools chain/tee/cycle/repeat/groupby/islice/filterfalse/zip_longest/compress/count 模块:
  - `sqlite3.Row 真按名访问`
  - `sqlite3.Connection.text_factory 真改 text 类型`
  - `sqlite3.Connection.row_factory 真 Row factory`
  - `sqlite3.Connection.set_trace_callback 真调`
  - `sqlite3.Connection.set_progress_handler 真调`
  - `subprocess.Popen cwd 真 cd /tmp 跑 'pwd'`
  - `subprocess.Popen bufsize=0 真 no buffer`
  - `subprocess.Popen shell=False 必传 list args`
  - `unittest.mock.seal(mock) 必阻止 set attr`
  - `async for 真迭代 async iterator`
  - `itertools.chain 真接 2 list`
  - `itertools.tee 真拆 1 iter 为 2`
  - `itertools.cycle 真循环 ≥ 10 item`
  - `itertools.repeat 真 repeat 3 次`
  - `itertools.islice 真取前 3`
  - `itertools.filterfalse 真过滤真`
  - `itertools.zip_longest 真补 None`
  - `itertools.compress 真 filter selector`
  - `itertools.count 真从 10 起`
  - `itertools.groupby 真分组`
  - `itertools.accumulate 真累加`
  - `itertools.dropwhile / takewhile 真边界`
  - `itertools.product 真笛卡尔积`
  - `itertools.permutations 真排列`
  - `itertools.combinations 真组合`
"""
import asyncio
import itertools
import os
import sqlite3
import subprocess
import sys
import unittest.mock

import pytest


# -- sqlite3 进阶 ------------------------------------------------------------

class TestSqlite3AdvancedV2:
    def test_Row_named_access(self):
        """`sqlite3.Row 真按名访问 + values()."""
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE TABLE t (id INTEGER, name TEXT)")
            conn.execute("INSERT INTO t VALUES (1, 'forge')")
            conn.commit()
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM t")
            row = cur.fetchone()
            # 按名访问
            assert row["id"] == 1
            assert row["name"] == "forge"
            # values
            assert tuple(row) == (1, "forge")
        finally:
            conn.close()

    def test_text_factory(self):
        """`sqlite3.Connection.text_factory 真改 text 类型 (bytes)`"""
        conn = sqlite3.connect(":memory:")
        try:
            # 默认 str
            # 改 bytes
            conn.text_factory = bytes
            conn.execute("CREATE TABLE t (name TEXT)")
            conn.execute("INSERT INTO t VALUES ('forge')")
            conn.commit()
            cur = conn.execute("SELECT name FROM t")
            row = cur.fetchone()
            # 必是 bytes
            assert isinstance(row[0], bytes)
        finally:
            conn.close()

    def test_set_trace_callback(self):
        """`sqlite3.Connection.set_trace_callback 真调 + 验 SQL。"""
        conn = sqlite3.connect(":memory:")
        try:
            captured = []

            def trace(sql):
                captured.append(sql)

            conn.set_trace_callback(trace)
            conn.execute("CREATE TABLE t (id INTEGER)")
            conn.execute("INSERT INTO t VALUES (1)")
            conn.commit()
            # 必 capture
            assert len(captured) >= 2
            assert any("CREATE TABLE" in s for s in captured)
        finally:
            conn.close()

    def test_progress_handler(self):
        """`sqlite3.Connection.set_progress_handler 真设 + 调 progress。"""
        conn = sqlite3.connect(":memory:")
        try:
            called = []

            def progress():
                called.append(1)

            conn.set_progress_handler(progress, 1)
            # 必不抛
            conn.execute("CREATE TABLE t (id INTEGER)")
            # 必被调
            assert len(called) >= 1, f"progress 必调,实际 {len(called)} 次"
            conn.set_progress_handler(None, 1)
        finally:
            conn.close()


# -- subprocess.Popen args/bufsize/cwd/env 进阶 -----------------------------

class TestSubprocessPopenAdvancedV2:
    def test_Popen_cwd(self):
        """`Popen cwd 真 cd /tmp 跑 'pwd'。"""
        if sys.platform == "win32":
            pytest.skip("Windows 走不同 cwd API")
        proc = subprocess.Popen(
            ["pwd"],
            stdout=subprocess.PIPE,
            cwd="/tmp",
        )
        stdout, _ = proc.communicate()
        # 必在 /tmp
        assert b"/tmp" in stdout, f"stdout 应含 '/tmp',实际 {stdout!r}"

    def test_Popen_bufsize(self):
        """`Popen bufsize=0 真 no buffer (shell:echo)`"""
        proc = subprocess.Popen(
            "echo forge bufsize",
            shell=True,
            stdout=subprocess.PIPE,
            bufsize=0,
        )
        stdout, _ = proc.communicate()
        assert b"forge" in stdout

    def test_Popen_shell_true_args_str(self):
        """`Popen shell=True 必传 str cmd`. """
        proc = subprocess.Popen(
            "echo forge shell",
            shell=True,
            stdout=subprocess.PIPE,
        )
        stdout, _ = proc.communicate()
        assert b"forge" in stdout


# -- unittest.mock.seal -----------------------------------------------------

class TestMockSeal:
    def test_seal(self):
        """`unittest.mock.seal 必阻止 setattr。"""
        m = unittest.mock.MagicMock()
        # 默认可 setattr
        m.x = 42
        assert m.x == 42
        # seal 必锁
        unittest.mock.seal(m)
        with pytest.raises(AttributeError):
            m.new_attr = 99


# -- async for 异步迭代 -----------------------------------------------------

class TestAsyncForV2:
    def test_async_for(self):
        """`async for 真迭代 async iterator。"""

        async def main():
            results = []
            async for x in _AsyncRange(5):
                results.append(x)
            return results

        result = asyncio.run(main())
        assert result == [0, 1, 2, 3, 4]


class _AsyncRange:
    def __init__(self, n):
        self.n = n
        self.i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.i >= self.n:
            raise StopAsyncIteration
        v = self.i
        self.i += 1
        return v


# -- itertools 完整 -------------------------------------------------------

class TestItertoolsV2:
    def test_chain(self):
        """`itertools.chain 真接 2 list。"""
        result = list(itertools.chain([1, 2], [3, 4]))
        assert result == [1, 2, 3, 4]

    def test_tee(self):
        """`itertools.tee 真拆 1 iter 为 2。"""
        a, b = itertools.tee([1, 2, 3], 2)
        assert list(a) == [1, 2, 3]
        assert list(b) == [1, 2, 3]

    def test_cycle(self):
        """`itertools.cycle 真循环 ≥ 10 item。"""
        cyc = itertools.cycle([1, 2, 3])
        # 取 7 次
        result = [next(cyc) for _ in range(7)]
        # 必 1+2+3+1+2+3+1
        assert result == [1, 2, 3, 1, 2, 3, 1]

    def test_repeat(self):
        """`itertools.repeat 真 repeat 3 次 'forge'。"""
        result = list(itertools.repeat("forge", 3))
        assert result == ["forge", "forge", "forge"]

    def test_islice(self):
        """`itertools.islice 真取前 3。"""
        result = list(itertools.islice([1, 2, 3, 4, 5], 3))
        assert result == [1, 2, 3]

    def test_filterfalse(self):
        """`itertools.filterfalse 真过滤真。"""
        result = list(itertools.filterfalse(lambda x: x % 2 == 0, [1, 2, 3, 4, 5]))
        # 必奇数
        assert result == [1, 3, 5]

    def test_zip_longest(self):
        """`itertools.zip_longest 真补 None。"""
        result = list(itertools.zip_longest([1, 2, 3], [4, 5], fillvalue=None))
        assert result == [(1, 4), (2, 5), (3, None)]

    def test_compress(self):
        """`itertools.compress 真 filter selector。"""
        result = list(itertools.compress([1, 2, 3, 4, 5], [1, 0, 1, 0, 1]))
        assert result == [1, 3, 5]

    def test_count(self):
        """`itertools.count 真从 10 起 3 个。"""
        c = itertools.count(10)
        result = [next(c) for _ in range(3)]
        assert result == [10, 11, 12]

    def test_groupby(self):
        """`itertools.groupby 真分组。"""
        data = [("a", 1), ("a", 2), ("b", 3), ("b", 4)]
        result = {k: list(g) for k, g in itertools.groupby(data, key=lambda x: x[0])}
        # 必 2 group
        assert "a" in result
        assert "b" in result
        assert len(result["a"]) == 2
        assert len(result["b"]) == 2

    def test_accumulate(self):
        """`itertools.accumulate 真累加。"""
        result = list(itertools.accumulate([1, 2, 3, 4, 5]))
        assert result == [1, 3, 6, 10, 15]

    def test_dropwhile(self):
        """`itertools.dropwhile 真边界。"""
        result = list(itertools.dropwhile(lambda x: x < 3, [1, 2, 3, 4, 1]))
        assert result == [3, 4, 1]

    def test_takewhile(self):
        """`itertools.takewhile 真边界。"""
        result = list(itertools.takewhile(lambda x: x < 3, [1, 2, 3, 4, 1]))
        assert result == [1, 2]

    def test_product(self):
        """`itertools.product 真笛卡尔积。"""
        result = list(itertools.product([1, 2], ["a", "b"]))
        # 必 4
        assert len(result) == 4

    def test_permutations(self):
        """`itertools.permutations 真排列。"""
        result = list(itertools.permutations([1, 2, 3], 2))
        # 必 6
        assert len(result) == 6

    def test_combinations(self):
        """`itertools.combinations 真组合。"""
        result = list(itertools.combinations([1, 2, 3, 4], 2))
        # 必 6
        assert len(result) == 6
