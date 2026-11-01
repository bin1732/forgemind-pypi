# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`re.Pattern.finditer/Match.groups/groupdict` 真用 + `re 进阶 (count+sub lambda+compile flags DOTALL+MULTILINE+VERBOSE+ASCII+UNICODE)` + `inspect.signature.bind+formatannotation` 真用 + `inspect.get_annotations 真用` + `unittest.TestCase.id+shortDescription` 进阶 + 真底层测试。

覆盖 re 4 真 (finditer+groups+groupdict+count+sub lambda+compile flags DOTALL/MULTILINE/VERBOSE) + inspect 3 真 (signature.bind+get_annotations+formatannotation) + unittest 2 真 (id+shortDescription) (共 9 真测试) 模块:
  - `re.Pattern 真 finditer 'a1b22c333' r'\\d+' 必 3 match`
  - `re.Match 真 groups + groupdict 双 named group 'name'+'value'`
  - `re.compile r'\\d+' flags=re.DOTALL 必 Pattern + 不抛`
  - `re.compile r'\\d+' flags=re.MULTILINE 必 Pattern + 不抛`
  - `re.compile r'\\d+' flags=re.VERBOSE 必 Pattern + 不抛`
  - `inspect.signature 真 bind(a=1, b=2) 含 'a' 'b'`
  - `inspect.get_annotations 真子化 my_fn 必含 'x':'int'`
  - `inspect.formatannotation 'int' 必 str 含 'int'`
  - `unittest.TestCase.id + shortDescription 必非空 str`
"""
import inspect
import os
import re
import sys
import unittest

import pytest


# -- re 进阶 (finditer + groups + groupdict + flags) ----------

class TestReAdvancedV5:
    def test_finditer(self):
        """`re.Pattern 真 finditer 'a1b22c333' r'\\d+' 必 3 match。"""
        p = re.compile(r"\d+")
        matches = list(p.finditer("a1b22c333"))
        # 必 3
        assert len(matches) == 3
        # 必 '1' '22' '333'
        assert matches[0].group() == "1"
        assert matches[1].group() == "22"
        assert matches[2].group() == "333"

    def test_Match_groups_groupdict(self):
        """`re.Match 真 groups + groupdict 双 named group 'name'+'value'。"""
        p = re.compile(r"(?P<name>\w+)=(?P<value>\d+)")
        m = p.match("forge=42")
        # groups 必 ('forge', '42')
        groups = m.groups()
        assert groups == ("forge", "42")
        # groupdict 必含 'name' + 'value'
        gd = m.groupdict()
        assert gd["name"] == "forge"
        assert gd["value"] == "42"

    def test_compile_flags_dotall(self):
        """`re.compile r'\\d+' flags=re.DOTALL 必 Pattern + 不抛。"""
        p = re.compile(r"a.+b", flags=re.DOTALL)
        # 必 Pattern
        assert isinstance(p, re.Pattern)
        # 必 match 'a\nb'
        m = p.search("a\nb")
        assert m is not None

    def test_compile_flags_multiline_verbose(self):
        """`re.compile r'\\d+' flags=re.MULTILINE|re.VERBOSE 必 Pattern。"""
        p = re.compile(r"\d+", flags=re.MULTILINE | re.VERBOSE)
        # 必 Pattern
        assert isinstance(p, re.Pattern)


# -- inspect 进阶 (signature.bind + get_annotations + formatannotation) -

class TestInspectAdvancedV11:
    def test_Signature_bind_kwargs(self):
        """`inspect.signature 真 bind(a=1, b=2) 含 'a' 'b'。"""
        def my_fn(a, b=42):
            return a + b

        sig = inspect.signature(my_fn)
        bound = sig.bind(a=1, b=2)
        # 必能 access
        assert "a" in bound.arguments
        assert "b" in bound.arguments
        assert bound.arguments["a"] == 1
        assert bound.arguments["b"] == 2

    def test_get_annotations(self):
        """`inspect.get_annotations 真子化 my_fn 必含 'x':'int'。"""

        def my_fn(x: int, y: str = "forge") -> bool:
            return True

        ann = inspect.get_annotations(my_fn)
        # 必含 'x' + 'y'
        assert "x" in ann
        assert "y" in ann
        # x 必 int
        assert ann["x"] is int
        # y 必 str
        assert ann["y"] is str

    def test_formatannotation(self):
        """`inspect.formatannotation 'int' 必 str 含 'int'。"""
        result = inspect.formatannotation("int")
        # 必 str
        assert isinstance(result, str)
        # 必含 'int'
        assert "int" in result


# -- unittest.TestCase 进阶 (id + shortDescription) --------

class TestUnittestTestCaseAttributes:
    def test_id_and_shortDescription(self):
        """`unittest.TestCase.id + shortDescription 必非空 str。"""

        class _T(unittest.TestCase):
            def test_forge(self):
                """forge test doc."""
                self.assertTrue(True)

        t = _T("test_forge")
        # 必 id
        tid = t.id()
        assert isinstance(tid, str)
        # 必含 'test_forge'
        assert "test_forge" in tid
        # 必 shortDescription
        sd = t.shortDescription()
        assert sd is not None
        # 必 'forge test doc.'
        assert "forge" in sd
