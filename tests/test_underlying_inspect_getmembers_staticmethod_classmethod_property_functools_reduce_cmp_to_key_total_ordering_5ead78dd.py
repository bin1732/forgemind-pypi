# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`inspect 进阶 (getmembers+staticmethod+classmethod+property+signature+annotations)` + `functools 进阶 (reduce+cmp_to_key+total_ordering+partialmethod+wraps)` + `pathlib 进阶 (resolve+absolute+is_absolute+glob+rglob)` + `csv 进阶 (DictReader+DictWriter+field_size_limit)` + `threading 进阶 (Thread daemon=True)` + 真底层测试。

覆盖 inspect 5 真 + functools 5 真 + pathlib 5 真 + csv 3 真 + threading 1 真 (共 19 真测试) 模块:
  - `inspect.getmembers int ≥ 5`
  - `staticmethod descriptor`
  - `classmethod descriptor`
  - `property fget`
  - `inspect.signature.bind+get_annotations`
  - `functools.reduce sum 6`
  - `functools.cmp_to_key reverse`
  - `functools.total_ordering [1,2,3]`
  - `functools.partialmethod 'partialmethod'`
  - `functools.wraps __name__`
  - `pathlib.resolve absolute`
  - `pathlib.absolute absolute`
  - `pathlib.is_absolute True`
  - `pathlib.glob ≥ 1 file`
  - `pathlib.rglob ≥ 1 file`
  - `csv DictReader 'forge'`
  - `csv DictWriter 'forge'`
  - `csv field_size_limit ≥ 0`
  - `threading.Thread daemon=True`
"""
import csv
import functools
import inspect
import io
import pathlib
import threading

import pytest


# -- inspect 进阶 (getmembers+staticmethod+classmethod+property+signature+annotations) ---

def _forge_inspect_method(a: int, b: str = "forge") -> str:
    return f"{a}{b}"


class TestInspectAdvanceV3:
    def test_getmembers(self):
        """`inspect.getmembers int ≥ 5。"""
        members = inspect.getmembers(int)
        assert isinstance(members, list)
        assert len(members) >= 5

    def test_staticmethod(self):
        """`staticmethod descriptor。"""
        sm = staticmethod(lambda x: x)
        assert callable(sm)

    def test_classmethod(self):
        """`classmethod descriptor。"""

        class _ForgeCls:
            @classmethod
            def cm(cls):
                return "forge_classmethod"

        assert _ForgeCls.cm() == "forge_classmethod"

    def test_property(self):
        """`property fget。"""

        class _ForgeP:
            def __init__(self):
                self._x = "forge_prop"

            @property
            def x(self):
                return self._x

        p = _ForgeP()
        assert p.x == "forge_prop"

    def test_signature_bind_annotations(self):
        """`inspect.signature.bind+get_annotations。"""
        sig = inspect.signature(_forge_inspect_method)
        bound = sig.bind(a=42, b="forge_v")
        assert bound.arguments["a"] == 42
        ann = inspect.get_annotations(_forge_inspect_method)
        assert isinstance(ann, dict)
        assert ann["a"] is int


# -- functools 进阶 (reduce+cmp_to_key+total_ordering+partialmethod+wraps) ---

@functools.total_ordering
class _ForgeTotal5:
    def __init__(self, val):
        self.val = val

    def __eq__(self, other):
        return self.val == other.val

    def __lt__(self, other):
        return self.val < other.val


def _add_simple2(x, y):
    return x + y


def _forge_wrapped3():
    """forge docstring"""
    return "forge"


@functools.wraps(_forge_wrapped3)
def _forge_wrapper3(*args, **kwargs):
    return _forge_wrapped3(*args, **kwargs)


class TestFunctoolsAdvanceV3:
    def test_reduce(self):
        """`functools.reduce sum 6。"""
        result = functools.reduce(lambda x, y: x + y, [1, 2, 3])
        assert result == 6

    def test_cmp_to_key(self):
        """`functools.cmp_to_key reverse。"""

        def cmp(a, b):
            return b - a

        result = sorted([3, 1, 2], key=functools.cmp_to_key(cmp))
        assert result == [3, 2, 1]

    def test_total_ordering(self):
        """`functools.total_ordering [1,2,3]。"""
        a, b, c = _ForgeTotal5(1), _ForgeTotal5(2), _ForgeTotal5(3)
        result = sorted([c, a, b])
        assert [x.val for x in result] == [1, 2, 3]

    def test_partialmethod(self):
        """`functools.partialmethod 'partialmethod'。"""
        pm = functools.partialmethod(_add_simple2, 10)
        assert pm is not None
        assert type(pm).__name__ == "partialmethod"

    def test_wraps(self):
        """`functools.wraps __name__。"""
        assert _forge_wrapper3.__name__ == "_forge_wrapped3"


# -- pathlib 进阶 (resolve+absolute+is_absolute+glob+rglob) --

class TestPathlibAdvanceV4:
    def test_resolve(self, tmp_path):
        """`pathlib.resolve absolute。"""
        f = tmp_path / "forge_resolve.txt"
        f.write_text("forge")
        resolved = f.resolve()
        assert resolved.is_absolute()

    def test_absolute(self, tmp_path):
        """`pathlib.absolute absolute。"""
        f = tmp_path / "forge_abs.txt"
        f.write_text("forge")
        abs_path = f.absolute()
        assert abs_path.is_absolute()

    def test_is_absolute(self):
        """`pathlib.is_absolute True。"""
        p = pathlib.PurePath("/a/b")
        assert p.is_absolute() is True

    def test_glob(self, tmp_path):
        """`pathlib.glob ≥ 1 file。"""
        (tmp_path / "forge_glob.txt").write_text("forge")
        result = list(tmp_path.glob("*.txt"))
        assert len(result) >= 1

    def test_rglob(self, tmp_path):
        """`pathlib.rglob ≥ 1 file。"""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "forge_rglob.txt").write_text("forge")
        result = list(tmp_path.rglob("*.txt"))
        assert len(result) >= 1


# -- csv 进阶 (DictReader+DictWriter+field_size_limit) ---

class TestCsvAdvanceV4:
    def test_DictReader(self):
        """`csv DictReader 'forge'。"""
        data = "name,value\nforge,42\n"
        reader = csv.DictReader(io.StringIO(data))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["name"] == "forge"

    def test_DictWriter(self):
        """`csv DictWriter 'forge'。"""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["name", "value"])
        writer.writeheader()
        writer.writerow({"name": "forge", "value": "42"})
        output = buf.getvalue()
        assert "name" in output
        assert "value" in output
        assert "forge" in output

    def test_field_size_limit(self):
        """`csv field_size_limit ≥ 0。"""
        old = csv.field_size_limit()
        assert isinstance(old, int)
        assert old >= 0
        csv.field_size_limit(old)


# -- threading 进阶 (Thread daemon=True) ----

def _thread_daemon():
    return "forge_daemon"


class TestThreadingThreadDaemonAdvance:
    def test_Thread_daemon(self):
        """`threading.Thread daemon=True start+join。"""
        t = threading.Thread(target=_thread_daemon, daemon=True)
        assert t.daemon is True
        t.start()
        t.join(timeout=5)
        assert True
