# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`collections 进阶 (Counter+OrderedDict+defaultdict+deque+namedtuple+ChainMap)` + `re 进阶 (compile+match+search+fullmatch+findall)` + `csv 进阶 (DictReader+DictWriter+field_size_limit)` + 真底层测试。

覆盖 collections 6 + re 5 + csv 3 (共 14 真测试) 模块:
  - `collections.Counter 'forge_forge' 频 2`
  - `collections.OrderedDict 保序 [z, a, m]`
  - `collections.defaultdict 'forge_default'`
  - `collections.deque append+appendleft`
  - `collections.namedtuple _ForgePt (42, 'forge')`
  - `collections.ChainMap 'forge_child'`
  - `re.compile 'forge' Pattern search`
  - `re.match 'forge'`
  - `re.search 'forge'`
  - `re.fullmatch 'forge'`
  - `re.findall 'forge' ≥ 1`
  - `csv.DictReader 'forge'`
  - `csv.DictWriter 'forge'`
  - `csv.field_size_limit ≥ 0`
"""
import collections
import csv
import io
import re

import pytest


# -- collections 进阶 (Counter+OrderedDict+defaultdict+deque+namedtuple+ChainMap) ---

class TestCollectionsAdvanceV5:
    def test_Counter(self):
        """`collections.Counter 'forge_forge' 频 2。"""
        c = collections.Counter("forge_forge")
        assert c["f"] == 2
        assert c["o"] == 2

    def test_OrderedDict(self):
        """`collections.OrderedDict 保序 [z, a, m]。"""
        od = collections.OrderedDict()
        od["z"] = 1
        od["a"] = 2
        od["m"] = 3
        assert list(od.keys()) == ["z", "a", "m"]

    def test_defaultdict(self):
        """`collections.defaultdict 'forge_default'。"""
        dd = collections.defaultdict(lambda: "forge_default")
        assert dd["nonexistent"] == "forge_default"

    def test_deque(self):
        """`collections.deque append+appendleft。"""
        dq = collections.deque()
        dq.append("forge_right")
        dq.appendleft("forge_left")
        assert dq[0] == "forge_left"

    def test_namedtuple(self):
        """`collections.namedtuple _ForgePt (42, 'forge')。"""
        _ForgePt = collections.namedtuple("_ForgePt", ["x", "y"])
        pt = _ForgePt(42, "forge")
        assert pt.x == 42
        assert pt.y == "forge"

    def test_ChainMap(self):
        """`collections.ChainMap 'forge_child'。"""
        parent = {"a": "parent_value"}
        child = {"b": "forge_child"}
        cm = collections.ChainMap(child, parent)
        assert cm["b"] == "forge_child"


# -- re 进阶 (compile+match+search+fullmatch+findall) -

class TestReAdvanceV8:
    def test_compile_search(self):
        """`re.compile 'forge' Pattern search。"""
        p = re.compile("forge")
        assert isinstance(p, re.Pattern)
        m = p.search("forge_value")
        assert m is not None
        assert m.group() == "forge"

    def test_match(self):
        """`re.match 'forge'。"""
        m = re.match("forge", "forge_value")
        assert m is not None
        assert m.group() == "forge"

    def test_search(self):
        """`re.search 'forge'。"""
        m = re.search("forge", "value_forge_value")
        assert m is not None
        assert m.group() == "forge"

    def test_fullmatch(self):
        """`re.fullmatch 'forge'。"""
        m = re.fullmatch("forge", "forge")
        assert m is not None
        assert m.group() == "forge"

    def test_findall(self):
        """`re.findall 'forge' ≥ 1。"""
        result = re.findall("forge", "forge_value_forge_test")
        assert len(result) >= 1
        assert result == ["forge", "forge"]


# -- csv 进阶 (DictReader+DictWriter+field_size_limit) ---

class TestCsvAdvanceV7:
    def test_DictReader(self):
        """`csv.DictReader 'forge'。"""
        data = "name,value\nforge,42\n"
        reader = csv.DictReader(io.StringIO(data))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["name"] == "forge"

    def test_DictWriter(self):
        """`csv.DictWriter 'forge'。"""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["name", "value"])
        writer.writeheader()
        writer.writerow({"name": "forge", "value": "42"})
        output = buf.getvalue()
        assert "name" in output
        assert "value" in output
        assert "forge" in output

    def test_field_size_limit(self):
        """`csv.field_size_limit ≥ 0。"""
        old = csv.field_size_limit()
        assert isinstance(old, int)
        assert old >= 0
        csv.field_size_limit(old)
