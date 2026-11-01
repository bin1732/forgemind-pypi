# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`inspect 进阶 (signature+Parameter+Signature+bind+replace)` + `ctypes 进阶 (c_int+c_long+c_float+c_double+c_char+c_wchar_p)` + `collections 进阶 (Counter+OrderedDict+defaultdict+deque+namedtuple+ChainMap)` + `re 进阶 (compile+match+search+fullmatch)` + `csv 进阶 (DictReader+DictWriter+field_size_limit)` + 真底层测试。

覆盖 inspect 4 真 + ctypes 6 真 + collections 6 真 + re 4 真 + csv 3 真 (共 23 真测试) 模块:
  - `inspect.signature Signature parameters`
  - `inspect.Parameter.empty sentinel`
  - `inspect.Signature.bind a=1 b='forge_value'`
  - `inspect.Signature.replace 'forge_replaced'`
  - `ctypes.c_int 42`
  - `ctypes.c_long 100`
  - `ctypes.c_float 1.5`
  - `ctypes.c_double 1.5`
  - `ctypes.c_char b'F'`
  - `ctypes.c_wchar_p 'forge'`
  - `collections.Counter 'forge_forge' 频 2`
  - `collections.OrderedDict 保序 [z, a, m]`
  - `collections.defaultdict 'forge_default'`
  - `collections.deque append+appendleft`
  - `collections.namedtuple _ForgePt`
  - `collections.ChainMap 'forge_child'`
  - `re.compile 'forge' Pattern search`
  - `re.match 'forge'`
  - `re.search 'forge'`
  - `re.fullmatch 'forge'`
  - `csv.DictReader 'forge'`
  - `csv.DictWriter 'forge'`
  - `csv.field_size_limit ≥ 0`
"""
import collections
import ctypes
import csv
import inspect
import io
import re

import pytest


def _forge_inspect_sig3(a: int, b: str = "forge") -> str:
    return f"{a}{b}"


# -- inspect 进阶 (signature+Parameter+Signature+bind+replace) --

class TestInspectAdvanceV6:
    def test_signature(self):
        """`inspect.signature Signature parameters。"""
        sig = inspect.signature(_forge_inspect_sig3)
        assert isinstance(sig, inspect.Signature)
        assert "a" in sig.parameters

    def test_Parameter_empty(self):
        """`inspect.Parameter.empty sentinel。"""
        empty = inspect.Parameter.empty
        assert empty is not None

    def test_Signature_bind(self):
        """`inspect.Signature.bind a=1 b='forge_value'。"""
        sig = inspect.signature(_forge_inspect_sig3)
        bound = sig.bind(a=1, b="forge_value")
        assert bound.arguments["a"] == 1

    def test_Signature_replace(self):
        """`inspect.Signature.replace 'forge_replaced'。"""
        sig = inspect.signature(_forge_inspect_sig3)
        new_sig = sig.replace(
            parameters=[
                sig.parameters["a"],
                sig.parameters["b"].replace(default="forge_replaced"),
            ]
        )
        assert new_sig.parameters["b"].default == "forge_replaced"


# -- ctypes 进阶 (c_int+c_long+c_float+c_double+c_char+c_wchar_p) --

class TestCtypesAdvanceV7:
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


# -- collections 进阶 (Counter+OrderedDict+defaultdict+deque+namedtuple+ChainMap) ---

class TestCollectionsAdvanceV4:
    def test_Counter(self):
        c = collections.Counter("forge_forge")
        assert c["f"] == 2
        assert c["o"] == 2

    def test_OrderedDict(self):
        od = collections.OrderedDict()
        od["z"] = 1
        od["a"] = 2
        od["m"] = 3
        assert list(od.keys()) == ["z", "a", "m"]

    def test_defaultdict(self):
        dd = collections.defaultdict(lambda: "forge_default")
        assert dd["nonexistent"] == "forge_default"

    def test_deque(self):
        dq = collections.deque()
        dq.append("forge_right")
        dq.appendleft("forge_left")
        assert dq[0] == "forge_left"

    def test_namedtuple(self):
        _ForgePt = collections.namedtuple("_ForgePt", ["x", "y"])
        pt = _ForgePt(42, "forge")
        assert pt.x == 42
        assert pt.y == "forge"

    def test_ChainMap(self):
        parent = {"a": "parent_value"}
        child = {"b": "forge_child"}
        cm = collections.ChainMap(child, parent)
        assert cm["b"] == "forge_child"


# -- re 进阶 (compile+match+search+fullmatch) --------

class TestReAdvanceV6:
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


# -- csv 进阶 (DictReader+DictWriter+field_size_limit) ---

class TestCsvAdvanceV5:
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
