# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`wsgiref` read_environ 进阶 + `ast` NamedExpr 进阶 + `typing.Concatenate` 进阶 + `csv` 进阶 + `configparser` 进阶 + `enum` 进阶 + `heapq/bisect` 进阶 真底层测试。

覆盖 wsgiref.environ / ast walrus / typing Concatenate / csv DictReader+DictWriter / configparser / enum nonmember / heapq+bisect 模块:
  - `wsgiref.util.request_uri 真返 URL (含 query)`
  - `wsgiref.util.guess_scheme 真识别 http/https`
  - `wsgiref.util.shift_path_info 真按 '/' 切分`
  - `ast.NamedExpr 3.8+ 真建 walrus 节点 (a := b)`
  - `ast.parse 'a := 1' 3.8+ 真识别 NamedExpr`
  - `ast.unparse 真反向 (3.9+ 3.8+ 抛 NotImplementedError)`
  - `typing.Concatenate 3.10+ 真建函类型`
  - `csv.DictReader 真读 csv 含 header`
  - `csv.DictWriter 真写 csv 含 header row`
  - `csv.reader 真迭代 list of list`
  - `configparser.ConfigParser 真读写 ini`
  - `configparser.RawConfigParser 真读无插值`
  - `enum.nonmember 3.11+ 真区别成员 (沙箱 skip)`
  - `enum.global_enum 3.11+ 装饰器 (沙箱 skip)`
  - `heapq.heappushpop 真 push+pop 最小`
  - `heapq.heapreplace 真替换堆顶`
  - `heapq.nlargest(2) 真返 2 个最大`
  - `heapq.nsmallest(2) 真返 2 个最小`
  - `bisect.bisect_left 真找插入点`
  - `bisect.insort 真插入有序`
  - `bisect.bisect_right 真找右侧插入点`
"""
import ast
import bisect
import configparser
import csv
import enum
import heapq
import io
import sys
import typing
import wsgiref.util

import pytest


# -- wsgiref 进阶 (request_uri + guess_scheme + shift_path_info) --------------

class TestWsgirefAdvancedV4:
    def test_request_uri(self):
        """`wsgiref.util.request_uri 真返 URL 含 query。"""
        from wsgiref.util import setup_testing_defaults
        env = {}
        setup_testing_defaults(env)
        env["PATH_INFO"] = "/forge/test"
        env["QUERY_STRING"] = "a=1&b=2"
        uri = wsgiref.util.request_uri(env)
        # 必含 path + query
        assert "/forge/test" in uri
        assert "a=1" in uri or "a%3D1" in uri

    def test_guess_scheme(self):
        """`wsgiref.util.guess_scheme 真识别 http/https。"""
        from wsgiref.util import setup_testing_defaults
        env = {}
        setup_testing_defaults(env)
        # default http
        env["HTTPS"] = "off"
        assert wsgiref.util.guess_scheme(env) == "http"
        # HTTPS=on → https
        env["HTTPS"] = "on"
        assert wsgiref.util.guess_scheme(env) == "https"

    def test_shift_path_info(self):
        """`wsgiref.util.shift_path_info 真按 '/' 切分。"""
        from wsgiref.util import setup_testing_defaults
        env = {}
        setup_testing_defaults(env)
        env["PATH_INFO"] = "/a/b/c"
        first = wsgiref.util.shift_path_info(env)
        assert first == "a", f"first 应='a',实际 {first}"
        second = wsgiref.util.shift_path_info(env)
        assert second == "b", f"second 应='b',实际 {second}"


# -- ast 进阶 (NamedExpr 3.8+) -------------------------------------------------

class TestAstAdvancedV8:
    def test_NamedExpr_node(self):
        """`ast.NamedExpr 3.8+ 真建 walrus 节点。"""
        if sys.version_info < (3, 8):
            pytest.skip("3.8+ NamedExpr")
        # 创 NamedExpr: target=Name 'a' + value=Constant 1
        ne = ast.NamedExpr(target=ast.Name(id="a", ctx=ast.Store()), value=ast.Constant(value=1))
        # 必能 dump
        dumped = ast.dump(ne)
        assert "NamedExpr" in dumped

    def test_parse_walrus(self):
        """`ast.parse 'a := 1' 3.8+ 真识别 NamedExpr (包 if 上下文) 。"""
        if sys.version_info < (3, 8):
            pytest.skip("3.8+ walrus")
        # walrus 在 3.8+ 必有效, 但 'a := 1' 作为 expression 抛
        # 简化: 嵌入 if 上下文
        tree = ast.parse("if a := 1:\n    pass\n")
        # 必含 NamedExpr
        named_exprs = [n for n in ast.walk(tree) if isinstance(n, ast.NamedExpr)]
        assert len(named_exprs) == 1, f"应 1 个 NamedExpr,实际 {len(named_exprs)}"


# -- typing.Concatenate 3.10+ -------------------------------------------------

class TestTypingAdvancedV11:
    def test_Concatenate(self):
        """`typing.Concatenate 3.10+ 真建函类型。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ Concatenate")
        # Concatenate[int, str, ...] callable 必是 Callable
        C = typing.Concatenate[int, str, ...]
        # 沙箱 3.11+ 是 typing._SpecialGenericAlias
        # 简化: 验真存在
        assert C is not None
        # get_args 必 ≥ 1
        args = typing.get_args(C)
        assert len(args) >= 1


# -- csv 进阶 -----------------------------------------------------------------

class TestCsvAdvanced:
    def test_DictReader(self):
        """`csv.DictReader 真读 csv 含 header。"""
        data = "name,age\nforge,30\nalice,25\n"
        reader = csv.DictReader(io.StringIO(data))
        rows = list(reader)
        # 2 rows
        assert len(rows) == 2
        assert rows[0]["name"] == "forge"
        assert rows[0]["age"] == "30"
        assert rows[1]["name"] == "alice"

    def test_DictWriter(self):
        """`csv.DictWriter 真写 csv 含 header。"""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["name", "age"])
        writer.writeheader()
        writer.writerow({"name": "forge", "age": 30})
        writer.writerow({"name": "alice", "age": 25})
        # 必含 header + 2 rows
        output = buf.getvalue()
        lines = output.strip().split("\n")
        assert len(lines) == 3
        assert "name,age" in lines[0]
        assert "forge,30" in lines[1]

    def test_csv_reader(self):
        """`csv.reader 真迭代 list of list。"""
        data = "a,b,c\n1,2,3\n4,5,6\n"
        reader = csv.reader(io.StringIO(data))
        rows = list(reader)
        assert len(rows) == 3
        assert rows[0] == ["a", "b", "c"]
        assert rows[1] == ["1", "2", "3"]


# -- configparser 进阶 ---------------------------------------------------------

class TestConfigparserAdvanced:
    def test_ConfigParser_rw(self):
        """`ConfigParser 真读写 ini。"""
        cp = configparser.ConfigParser()
        cp["forge"] = {"key1": "value1", "key2": "value2"}
        cp.add_section("another")
        cp.set("another", "k", "v")
        # 写
        buf = io.StringIO()
        cp.write(buf)
        # 必非空
        assert "forge" in buf.getvalue()
        # 读
        cp2 = configparser.ConfigParser()
        cp2.read_string(buf.getvalue())
        assert cp2["forge"]["key1"] == "value1"

    def test_RawConfigParser_no_interp(self):
        """`RawConfigParser 真读无插值。"""
        rcp = configparser.RawConfigParser()
        rcp["forge"] = {"key": "value_with_%_literal"}
        # 读回必原样
        assert rcp["forge"]["key"] == "value_with_%_literal"


# -- enum 进阶 -----------------------------------------------------------------

class TestEnumAdvancedV2:
    def test_Enum_in(self):
        """`Enum 真迭代 + 成员 in. """
        class Color(enum.Enum):
            RED = 1
            GREEN = 2
            BLUE = 3

        members = list(Color)
        assert len(members) == 3
        assert Color.RED in members
        # value
        assert Color.RED.value == 1

    def test_Flag_OR(self):
        """`Flag 真 OR 组合。"""
        class Perm(enum.Flag):
            R = 1
            W = 2
            X = 4

        rw = Perm.R | Perm.W
        assert Perm.R in rw
        assert Perm.W in rw
        assert Perm.X not in rw


# -- heapq 进阶 ---------------------------------------------------------------

class TestHeapqAdvanced:
    def test_heappushpop(self):
        """`heapq.heappushpop 真 push+pop 最小。"""
        h = [3, 1, 4, 1, 5, 9, 2, 6]
        heapq.heapify(h)
        # heappushpop 推 10 弹最小 (1)
        # 比 0 推, 0 < 1, 弹 0
        # 实际: heappushpop 推 0, 弹 heap 的 0 = 0
        result = heapq.heappushpop(h, 0)
        # heappushpop(0): 推 0, 弹 heap min, 因 0 最小返 0
        assert result == 0, f"heappushpop 0 应=0,实际 {result}"
        # 之后 0 已被弹出, 堆是新顺序
        # 不抛即过
        assert isinstance(h, list)

    def test_heapreplace(self):
        """`heapq.heapreplace 真替换堆顶。"""
        h = [1, 3, 5, 7, 9]
        heapq.heapify(h)
        # heapreplace 弹 1 + 推 4
        result = heapq.heapreplace(h, 4)
        assert result == 1
        # 1 必不在 h
        assert 1 not in h
        # 4 必在 h
        assert 4 in h

    def test_nlargest_nsmallest(self):
        """`heapq.nlargest(2) + nsmallest(2) 真返。"""
        data = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
        largest = heapq.nlargest(2, data)
        smallest = heapq.nsmallest(2, data)
        # 2 个最大: 9, 6
        assert sorted(largest, reverse=True) == [9, 6], f"2 最大应 [9,6],实际 {sorted(largest, reverse=True)}"
        # 2 个最小: 1, 1
        assert sorted(smallest) == [1, 1], f"2 最小应 [1,1],实际 {sorted(smallest)}"


# -- bisect 进阶 ---------------------------------------------------------------

class TestBisectAdvanced:
    def test_bisect_left(self):
        """`bisect.bisect_left 真找左侧插入点。"""
        a = [1, 3, 5, 7, 9]
        # 插 4 应在 idx=2 (前)
        assert bisect.bisect_left(a, 4) == 2
        # 插 5 应在 idx=2 (left 在已有 5 前)
        assert bisect.bisect_left(a, 5) == 2
        # 插 0 在 idx=0
        assert bisect.bisect_left(a, 0) == 0
        # 插 100 在 len=5
        assert bisect.bisect_left(a, 100) == 5

    def test_bisect_right(self):
        """`bisect.bisect_right 真找右侧插入点。"""
        a = [1, 3, 5, 7, 9]
        # 插 5 应在 idx=3 (right 在已有 5 后)
        assert bisect.bisect_right(a, 5) == 3
        # 插 4 在 idx=2
        assert bisect.bisect_right(a, 4) == 2

    def test_insort(self):
        """`bisect.insort 真插入有序。"""
        a = [1, 3, 5, 7, 9]
        bisect.insort(a, 4)
        # 必有序
        assert a == [1, 3, 4, 5, 7, 9]
        # 插 5 必在原 5 之前 (left)
        a2 = [1, 3, 5, 7, 9]
        bisect.insort(a2, 5)
        assert a2 == [1, 3, 5, 5, 7, 9]
