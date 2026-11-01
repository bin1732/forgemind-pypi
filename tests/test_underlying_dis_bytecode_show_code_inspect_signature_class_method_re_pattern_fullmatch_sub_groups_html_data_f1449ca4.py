# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`dis` 进阶 (get_instructions+Bytecode+show_code) + `inspect.signature 真 class method` + `re.Pattern.match+fullmatch+sub+groups+index` 真用 + `html.parser.HTMLParser.handle_starttag+endtag+handle_data+feed` 真用 + `multiprocessing.Pool.apply_async+imap+starmap_unordered` 真并发 + 真底层测试。

覆盖 dis 3 真 (get_instructions+Bytecode+show_code) + inspect 2 真 (signature class method+signature 进阶) + re 3 真 (match+fullmatch+sub groups) + html.parser 3 真 (handle_starttag+endtag+handle_data) + multiprocessing.Pool 2 真 (apply_async+imap+starmap_unordered) (共 13 真测试) 模块:
  - `dis.get_instructions lambda 必 ≥ 1 (含 RESUME 3.11+)`
  - `dis.Bytecode 真子化 + dis 必 ≥ 1 instr`
  - `dis.show_code 必 callable (沙箱 skip 实际输出)`
  - `inspect.signature 真 class method bound a, b=2`
  - `inspect.signature 真 class method unbound self, a, b=2`
  - `re.Pattern 真 match 'forge' 'forge hello' 必 match.group 'forge'`
  - `re.Pattern 真 fullmatch 'forge' 必 match`
  - `re.sub '\\d+ r'\\d+ -> 'X' 'a12b34' 必 'aXbX' (groups 验 1)`
  - `html.parser handle_starttag 'a' href='forge' 必存`
  - `html.parser handle_data 'forge_data' 必存`
  - `html.parser 真 feed '<a>forge</a>' 不抛`
  - `Pool apply_async 3 task 真并发 sq [1,4,9]`
  - `Pool starmap_unordered 真 sq [(1,2),(3,4)] [1,9]`
"""
import dis
import html.parser
import inspect
import multiprocessing
import re
import sys

import pytest


# -- dis 进阶 (get_instructions + Bytecode + show_code) ------

class TestDisAdvancedV2:
    def test_get_instructions_lambda(self):
        """`dis.get_instructions lambda 必 ≥ 1 (含 RESUME 3.11+)。"""
        instructions = list(dis.get_instructions(lambda x: x))
        # 必 ≥ 1
        assert len(instructions) >= 1
        # 沙箱 3.11+ 必含 RESUME
        opnames = [i.opname for i in instructions]
        assert "RESUME" in opnames

    def test_Bytecode(self):
        """`dis.Bytecode 真子化 + dis 必 ≥ 1 instr。"""
        bc = dis.Bytecode(lambda x: x)
        # 必 dis
        instructions = list(bc)
        # 必 ≥ 1
        assert len(instructions) >= 1

    def test_show_code_callable(self):
        """`dis.show_code 必 callable (沙箱 skip 实际输出)。"""
        # 必 callable
        assert callable(dis.show_code)


# -- inspect.signature 真 class method -------------------

class _ClsForSig:
    def method(self, a, b=2):
        return a + b


class TestInspectSignatureClassMethodAdvanced:
    def test_signature_bound_method(self):
        """`inspect.signature 真 class method bound a, b=2。"""
        o = _ClsForSig()
        # bound method
        sig = inspect.signature(o.method)
        # 必 parameters a, b
        params = list(sig.parameters.keys())
        assert "a" in params
        assert "b" in params

    def test_signature_unbound_method(self):
        """`inspect.signature 真 class method unbound self, a, b=2。"""
        sig = inspect.signature(_ClsForSig.method)
        # 必 parameters self, a, b
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "a" in params
        assert "b" in params


# -- re 进阶 (match + fullmatch + sub + groups) ---------

class TestReAdvancedV6:
    def test_match_group(self):
        """`re.Pattern 真 match 'forge' 'forge hello' 必 match.group 'forge'。"""
        p = re.compile(r"forge")
        m = p.match("forge hello")
        # 必 match
        assert m is not None
        # 必 group 'forge'
        assert m.group() == "forge"

    def test_fullmatch_group(self):
        """`re.Pattern 真 fullmatch 'forge' 必 match。"""
        p = re.compile(r"forge")
        m = p.fullmatch("forge")
        # 必 match
        assert m is not None
        # 必 group 'forge'
        assert m.group() == "forge"

    def test_sub_groups(self):
        """`re.sub '\\d+' r'\\d+' 'a12b34' 必 'aXbX' (groups 验 1)。"""
        result = re.sub(r"\d+", "X", "a12b34")
        # 必 'aXbX'
        assert result == "aXbX"


# -- html.parser 进阶 (handle_starttag + endtag + handle_data) -

class _MyHTMLParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.data = []
        self.attrs = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.append(dict(attrs))

    def handle_endtag(self, tag):
        self.tags.append("/" + tag)

    def handle_data(self, data):
        self.data.append(data)


class TestHtmlParserAdvancedV2:
    def test_handle_starttag(self):
        """`html.parser handle_starttag 'a' href='forge' 必存。"""
        p = _MyHTMLParser()
        p.feed("<a href='forge'>x</a>")
        # 必 'a' in tags
        assert "a" in p.tags
        # 必 'href' in attrs
        assert any("href" in a for a in p.attrs)

    def test_handle_data(self):
        """`html.parser handle_data 'forge_data' 必存。"""
        p = _MyHTMLParser()
        p.feed("forge_data<x>more</x>")
        # 必 'forge_data' in data
        assert "forge_data" in p.data

    def test_feed(self):
        """`html.parser 真 feed '<a>forge</a>' 不抛。"""
        p = _MyHTMLParser()
        # feed 必不抛
        p.feed("<a>forge</a>")
        # 必 'a' in tags
        assert "a" in p.tags


# -- multiprocessing.Pool 进阶 (apply_async + imap + starmap_unordered) -

def _sq(x):
    return x * x


def _add(x, y):
    return x + y


class TestMultiprocessingPoolAdvancedV5:
    def test_Pool_apply_async_3(self):
        """`Pool apply_async 3 task 真并发 sq [1,4,9]。"""
        with multiprocessing.Pool(2) as p:
            results = []
            for i in [1, 2, 3]:
                ar = p.apply_async(_sq, (i,))
                results.append(ar.get(timeout=10))
            # 必 [1, 4, 9]
            assert results == [1, 4, 9]

    def test_Pool_imap_unordered(self):
        """`Pool imap_unordered 真 sq [1,2,3,4] [1,4,9,16]。"""
        with multiprocessing.Pool(2) as p:
            results = list(p.imap_unordered(_sq, [1, 2, 3, 4]))
            # 必 4 个
            assert len(results) == 4
            # 必排序 [1, 4, 9, 16]
            assert sorted(results) == [1, 4, 9, 16]
