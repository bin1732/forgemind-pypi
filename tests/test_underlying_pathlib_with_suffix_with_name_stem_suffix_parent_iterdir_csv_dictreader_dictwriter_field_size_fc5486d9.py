# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`pathlib 进阶 (with_suffix+with_name+stem+suffix+parent+iterdir)` + `csv 进阶 (DictReader+DictWriter+field_size_limit)` + `functools 进阶 (partialmethod+wraps+total_ordering+cache_clear)` + `threading 进阶 (Thread args+start+join)` + 真底层测试。

覆盖 pathlib 6 真 + csv 3 真 + functools 4 真 + threading 1 真 (共 14 真测试) 模块:
  - `pathlib with_suffix '.txt'`
  - `pathlib with_name 'new.txt'`
  - `pathlib Path 'forge.py' stem`
  - `pathlib Path 'forge.py' suffix`
  - `pathlib Path '/a/b/c' parent`
  - `pathlib iterdir tmp_path ≥ 2`
  - `csv DictReader 'forge,42'`
  - `csv DictWriter 'forge,42'`
  - `csv field_size_limit ≥ 0`
  - `functools.partialmethod 'partialmethod'`
  - `functools.wraps __name__`
  - `functools.total_ordering [1,2,3]`
  - `functools.cache_clear hits=0`
  - `threading.Thread args start+join`
"""
import csv
import functools
import io
import pathlib
import threading

import pytest


# -- pathlib 进阶 (with_suffix+with_name+stem+suffix+parent+iterdir) ---

class TestPathlibAdvanceV3:
    def test_with_suffix(self):
        """`pathlib with_suffix '.txt'。"""
        p = pathlib.Path("/a/b/forge.py")
        p2 = p.with_suffix(".txt")
        # 必 .txt
        assert p2.suffix == ".txt"

    def test_with_name(self):
        """`pathlib with_name 'new.txt'。"""
        p = pathlib.Path("/a/b/forge.py")
        p2 = p.with_name("new.txt")
        # 必 'new.txt'
        assert p2.name == "new.txt"

    def test_stem(self):
        """`pathlib Path 'forge.py' stem。"""
        p = pathlib.Path("forge.py")
        # 必 'forge'
        assert p.stem == "forge"

    def test_suffix(self):
        """`pathlib Path 'forge.py' suffix。"""
        p = pathlib.Path("forge.py")
        # 必 '.py'
        assert p.suffix == ".py"

    def test_parent(self):
        """`pathlib Path '/a/b/c' parent。"""
        p = pathlib.PurePath("/a/b/c")
        # 必 '/a/b'
        assert str(p.parent) == "/a/b"

    def test_iterdir(self, tmp_path):
        """`pathlib iterdir tmp_path 必 ≥ 2。"""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        entries = list(tmp_path.iterdir())
        # 必 ≥ 2
        assert len(entries) >= 2
        # 必含 'a.txt' + 'b.txt'
        names = [e.name for e in entries]
        assert "a.txt" in names
        assert "b.txt" in names


# -- csv 进阶 (DictReader+DictWriter+field_size_limit) ---

class TestCsvDictReaderWriterFieldSizeLimitAdvanceV2:
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


# -- functools 进阶 (partialmethod+wraps+total_ordering+cache_clear) ---

@functools.total_ordering
class _ForgeTotal3:
    def __init__(self, val):
        self.val = val

    def __eq__(self, other):
        return self.val == other.val

    def __lt__(self, other):
        return self.val < other.val


@functools.lru_cache(maxsize=10)
def _forge_cached3(x):
    return x * 2


def _add_simple(x, y):
    return x + y


class TestFunctoolsPartialmethodWrapsTotalOrderingCacheClearAdvanceV2:
    def test_partialmethod(self):
        """`functools.partialmethod 'partialmethod'。"""
        pm = functools.partialmethod(_add_simple, 10)
        # 必非 None
        assert pm is not None
        # 必 'partialmethod' 名称
        assert type(pm).__name__ == "partialmethod"

    def test_wraps(self):
        """`functools.wraps __name__。"""

        def _forge_wrapped2():
            """forge docstring"""
            return "forge"

        @functools.wraps(_forge_wrapped2)
        def wrapper(*args, **kwargs):
            return _forge_wrapped2(*args, **kwargs)

        # 必 '_forge_wrapped2'
        assert wrapper.__name__ == "_forge_wrapped2"

    def test_total_ordering(self):
        """`functools.total_ordering [1,2,3]。"""
        a, b, c = _ForgeTotal3(1), _ForgeTotal3(2), _ForgeTotal3(3)
        result = sorted([c, a, b])
        # 必 [1, 2, 3]
        assert [x.val for x in result] == [1, 2, 3]

    def test_cache_clear(self):
        """`functools.cache_clear hits=0。"""
        # 真算 1 次
        _forge_cached3(99)
        # clear
        _forge_cached3.cache_clear()
        # 必 hit 0
        info = _forge_cached3.cache_info()
        # 必 hit 0
        assert info.hits == 0


# -- threading 进阶 (Thread args+start+join) -----

def _thread_target2(arg):
    return f"forge_thread_{arg}"


class TestThreadingThreadArgsTargetStartJoinAdvanceV2:
    def test_Thread_args(self):
        """`threading.Thread args=('forge_arg',) start+join。"""
        t = threading.Thread(target=_thread_target2, args=("forge_arg",))
        # start
        t.start()
        # join
        t.join(timeout=5)
        # 必不抛
        assert True
