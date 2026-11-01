# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`pathlib 进阶 (resolve+with_name+with_suffix+iterdir+glob+rglob+absolute)` + `csv 进阶 (DictReader+DictWriter+field_size_limit+register_dialect)` + `re 进阶 (compile+match+search+fullmatch)` + `ctypes 进阶 (c_int+c_long+c_float+c_double+c_char+c_wchar_p)` + 真底层测试。

覆盖 pathlib 6 真 + csv 4 真 + re 4 真 + ctypes 6 真 (共 20 真测试) 模块:
  - `pathlib.resolve absolute`
  - `pathlib.with_name 'new.txt'`
  - `pathlib.with_suffix '.txt'`
  - `pathlib.iterdir tmp_path ≥ 2`
  - `pathlib.glob '*.txt' ≥ 1`
  - `pathlib.rglob '*.txt' ≥ 1`
  - `csv.DictReader 'forge'`
  - `csv.DictWriter 'forge'`
  - `csv.field_size_limit ≥ 0`
  - `csv.register_dialect 'forge_d3' 真用`
  - `re.compile 'forge' Pattern search`
  - `re.match 'forge'`
  - `re.search 'forge'`
  - `re.fullmatch 'forge'`
  - `ctypes.c_int 42`
  - `ctypes.c_long 100`
  - `ctypes.c_float 1.5`
  - `ctypes.c_double 1.5`
  - `ctypes.c_char b'F'`
  - `ctypes.c_wchar_p 'forge'`
"""
import csv
import ctypes
import io
import pathlib
import re

import pytest


# -- pathlib 进阶 (resolve+with_name+with_suffix+iterdir+glob+rglob) ---

class TestPathlibAdvanceV10:
    def test_resolve(self, tmp_path):
        """`pathlib.resolve absolute。"""
        f = tmp_path / "forge_resolve.txt"
        f.write_text("forge")
        assert f.resolve().is_absolute()

    def test_with_name(self, tmp_path):
        """`pathlib.with_name 'new.txt'。"""
        f = tmp_path / "forge_old.txt"
        f.write_text("forge")
        f2 = f.with_name("new.txt")
        assert f2.name == "new.txt"

    def test_with_suffix(self, tmp_path):
        """`pathlib.with_suffix '.txt'。"""
        f = tmp_path / "forge_old.py"
        f.write_text("forge")
        f2 = f.with_suffix(".txt")
        assert f2.suffix == ".txt"

    def test_iterdir(self, tmp_path):
        """`pathlib.iterdir tmp_path ≥ 2。"""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        entries = list(tmp_path.iterdir())
        assert len(entries) >= 2

    def test_glob(self, tmp_path):
        """`pathlib.glob '*.txt' ≥ 1。"""
        (tmp_path / "forge_glob.txt").write_text("forge")
        result = list(tmp_path.glob("*.txt"))
        assert len(result) >= 1

    def test_rglob(self, tmp_path):
        """`pathlib.rglob '*.txt' ≥ 1。"""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "forge_rglob.txt").write_text("forge")
        result = list(tmp_path.rglob("*.txt"))
        assert len(result) >= 1


# -- csv 进阶 (DictReader+DictWriter+field_size_limit+register_dialect) --

class TestCsvAdvanceV6:
    def test_DictReader(self):
        data = "name,value\nforge,42\n"
        reader = csv.DictReader(io.StringIO(data))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["name"] == "forge"

    def test_DictWriter(self):
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["name", "value"])
        writer.writeheader()
        writer.writerow({"name": "forge", "value": "42"})
        output = buf.getvalue()
        assert "name" in output
        assert "value" in output
        assert "forge" in output

    def test_field_size_limit(self):
        old = csv.field_size_limit()
        assert isinstance(old, int)
        assert old >= 0
        csv.field_size_limit(old)

    def test_register_dialect(self):
        try:
            csv.register_dialect(
                "forge_d3",
                delimiter="|",
                quotechar="*",
            )
            assert "forge_d3" in csv.list_dialects()
        finally:
            csv.unregister_dialect("forge_d3")


# -- re 进阶 (compile+match+search+fullmatch) --------

class TestReAdvanceV7:
    def test_compile_search(self):
        p = re.compile("forge")
        assert isinstance(p, re.Pattern)
        m = p.search("forge_value")
        assert m is not None
        assert m.group() == "forge"

    def test_match(self):
        m = re.match("forge", "forge_value")
        assert m is not None
        assert m.group() == "forge"

    def test_search(self):
        m = re.search("forge", "value_forge_value")
        assert m is not None
        assert m.group() == "forge"

    def test_fullmatch(self):
        m = re.fullmatch("forge", "forge")
        assert m is not None
        assert m.group() == "forge"


# -- ctypes 进阶 (c_int+c_long+c_float+c_double+c_char+c_wchar_p) --

class TestCtypesAdvanceV8:
    def test_c_int(self):
        v = ctypes.c_int(42)
        assert v.value == 42

    def test_c_long(self):
        v = ctypes.c_long(100)
        assert v.value == 100

    def test_c_float(self):
        v = ctypes.c_float(1.5)
        assert v.value == 1.5

    def test_c_double(self):
        v = ctypes.c_double(1.5)
        assert v.value == 1.5

    def test_c_char(self):
        c = ctypes.c_char(b"F")
        assert c.value == b"F"

    def test_c_wchar_p(self):
        c = ctypes.c_wchar_p("forge")
        assert c.value == "forge"
