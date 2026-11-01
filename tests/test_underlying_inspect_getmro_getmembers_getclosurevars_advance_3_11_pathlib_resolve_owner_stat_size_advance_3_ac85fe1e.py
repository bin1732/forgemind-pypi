# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`inspect 进阶 (getmro+getmembers+getclosurevars 3.11+ 真用)` + `pathlib 进阶 (resolve+owner+stat 进阶)` + `csv 进阶 (DictReader+DictWriter+field_size_limit)` + `functools 进阶 (lru_cache+partial+cmp_to_key+total_ordering)` + 真底层测试。

覆盖 inspect 3 真 (getmro+getmembers+getclosurevars 3.11+) + pathlib 3 真 (resolve+stat 进阶+stat 3 真) + csv 3 真 (DictReader+DictWriter+field_size_limit) + functools 4 真 (lru_cache+partial+cmp_to_key+total_ordering) (共 13 真测试) 模块:
  - `inspect.getmro int 必 [int, object]`
  - `inspect.getmembers int 必 ≥ 5`
  - `inspect.getclosurevars 3.11+ ClosureVars nonlocals`
  - `pathlib.resolve tmp_path absolute`
  - `pathlib.stat tmp_path st_size ≥ 1`
  - `pathlib.stat st_mtime > 0`
  - `csv DictReader 'forge,42'`
  - `csv DictWriter 'forge,42'`
  - `csv field_size_limit ≥ 0`
  - `functools.lru_cache fib(5)=5`
  - `functools.partial(inc,10)(5) 必 15`
  - `functools.cmp_to_key reverse [3,2,1]`
  - `functools.total_ordering [3,1,2] [1,2,3]`
"""
import csv
import functools
import inspect
import io
import pathlib

import pytest


def _make_closure_forge():
    forge_outer = "forge_outer"
    forge_inner = "forge_inner"

    def inner():
        return forge_inner

    return inner


def _inc(x, y):
    return x + y


@functools.lru_cache(maxsize=128)
def _fib_forge(n):
    if n < 2:
        return n
    return _fib_forge(n - 1) + _fib_forge(n - 2)


@functools.total_ordering
class _ForgeTotal4:
    def __init__(self, val):
        self.val = val

    def __eq__(self, other):
        return self.val == other.val

    def __lt__(self, other):
        return self.val < other.val


# -- inspect 进阶 (getmro+getmembers+getclosurevars 3.11+) -

class TestInspectAdvanceV2:
    def test_getmro(self):
        """`inspect.getmro int 必 [int, object]。"""
        mro = inspect.getmro(int)
        # 必 int first
        assert mro[0] is int
        # 必 object last
        assert mro[-1] is object

    def test_getmembers(self):
        """`inspect.getmembers int 必 ≥ 5。"""
        members = inspect.getmembers(int)
        # 必 list ≥ 5
        assert isinstance(members, list)
        assert len(members) >= 5

    def test_getclosurevars(self):
        """`inspect.getclosurevars 3.11+ ClosureVars nonlocals。"""
        fn = _make_closure_forge()
        # 沙箱 3.11+ 必能
        cvars = inspect.getclosurevars(fn)
        # 必 ClosureVars 类
        # 必 nonlocals ≥ 0
        assert hasattr(cvars, "nonlocals")
        # 必 globals
        assert hasattr(cvars, "globals")


# -- pathlib 进阶 (resolve+stat) -----

class TestPathlibResolveStatAdvance:
    def test_resolve(self, tmp_path):
        """`pathlib.resolve tmp_path absolute。"""
        f = tmp_path / "forge_resolve.txt"
        f.write_text("forge")
        # resolve
        resolved = f.resolve()
        # 必 absolute
        assert resolved.is_absolute()

    def test_stat_size(self, tmp_path):
        """`pathlib.stat tmp_path st_size ≥ 1。"""
        f = tmp_path / "forge_size.txt"
        f.write_text("forge_data")
        # stat
        s = f.stat()
        # 必 st_size ≥ 1
        assert s.st_size >= 1

    def test_stat_mtime(self, tmp_path):
        """`pathlib.stat st_mtime > 0。"""
        f = tmp_path / "forge_mtime.txt"
        f.write_text("forge_mtime")
        # stat
        s = f.stat()
        # 必 st_mtime > 0
        assert s.st_mtime > 0


# -- csv 进阶 (DictReader+DictWriter+field_size_limit) ---

class TestCsvDictReaderWriterFieldSizeLimitAdvanceV3:
    def test_DictReader(self):
        """`csv DictReader 'forge,42'。"""
        data = "name,value\nforge,42\n"
        reader = csv.DictReader(io.StringIO(data))
        rows = list(reader)
        # 必 1
        assert len(rows) == 1
        # 必 'forge'
        assert rows[0]["name"] == "forge"

    def test_DictWriter(self):
        """`csv DictWriter 'forge,42'。"""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["name", "value"])
        # writeheader
        writer.writeheader()
        # writerow
        writer.writerow({"name": "forge", "value": "42"})
        # 必含 'name' 'value' 'forge'
        output = buf.getvalue()
        assert "name" in output
        assert "value" in output
        assert "forge" in output

    def test_field_size_limit(self):
        """`csv field_size_limit ≥ 0。"""
        old = csv.field_size_limit()
        # 必 int
        assert isinstance(old, int)
        # 必 ≥ 0
        assert old >= 0
        # restore
        csv.field_size_limit(old)


# -- functools 进阶 (lru_cache+partial+cmp_to_key+total_ordering) --

class TestFunctoolsLruCachePartialCmpToKeyTotalOrderingAdvance:
    def test_lru_cache_fib(self):
        """`functools.lru_cache fib(5)=5。"""
        # 必 5
        assert _fib_forge(5) == 5

    def test_partial(self):
        """`functools.partial(inc,10)(5) 必 15。"""
        inc_10 = functools.partial(_inc, 10)
        # 必 15
        assert inc_10(5) == 15

    def test_cmp_to_key(self):
        """`functools.cmp_to_key reverse [3,2,1]。"""

        def cmp(a, b):
            return b - a

        result = sorted([3, 1, 2], key=functools.cmp_to_key(cmp))
        # 必 [3, 2, 1]
        assert result == [3, 2, 1]

    def test_total_ordering(self):
        """`functools.total_ordering [3,1,2] [1,2,3]。"""
        a, b, c = _ForgeTotal4(1), _ForgeTotal4(2), _ForgeTotal4(3)
        result = sorted([c, a, b])
        # 必 [1, 2, 3]
        assert [x.val for x in result] == [1, 2, 3]
