# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`xml.etree.Element` 进阶 (iter+remove+append+findall 进阶) + `csv.Dialect.register 真 delimiter+quotechar` + `inspect.signature.bind+get_annotations+formatannotation 进阶` + `pickle` 进阶 2-3-4-5 protocol + `logging.Filter 真用 进阶` + `functools.reduce+cmp_to_key+total_ordering+cache_clear 进阶` + 真底层测试。

覆盖 xml.etree 4 真 + csv 2 真 + inspect 3 真 + pickle 2 真 (protocol 2+5) + logging 1 真 (Filter 真用) + functools 4 真 (reduce+cmp_to_key+total_ordering+cache_clear) (共 16 真测试) 模块:
  - `xml.etree iter+remove 'a' 必 len 减 1`
  - `xml.etree append Element 必 len 加 1`
  - `xml.etree findall './/b' 必 3`
  - `xml.etree clear+set 'forge'`
  - `csv.register_dialect 'forge_d' delimiter=';' quotechar="'"'`
  - `csv 必能用 'forge_d' dialect reader 真读`
  - `inspect.signature.bind 真 a=1 b='forge' 必不抛`
  - `inspect.get_annotations 函数 必 dict 'a':int`
  - `inspect.formatannotation 必 str 'str'`
  - `pickle.protocol 2 dumps+loads round-trip 必等`
  - `pickle.protocol 5 dumps+loads round-trip 必等`
  - `logging.Filter 真用 filter 'forge' 必 True`
  - `functools.reduce 真 [1,2,3] sum 6`
  - `functools.cmp_to_key reverse [3,2,1]`
  - `functools.total_ordering 必排序 [3,1,2] 必 [1,2,3]`
  - `functools.cache_clear 必 hits=0 after clear`
"""
import csv
import functools
import inspect
import io
import logging
import pickle
import xml.etree.ElementTree as ET

import pytest


# -- xml.etree.Element 进阶 (iter+remove+append+findall) ----

class TestXmlEtreeElementIterRemoveAppendFindallAdvance:
    def test_iter_remove(self):
        """`xml.etree iter+remove 'a' 必 len 减 1。"""
        root = ET.fromstring("<r><a>1</a><a>2</a><a>3</a></r>")
        # 必 3 'a' elements
        children = list(root.iter("a"))
        assert len(children) == 3
        # remove first
        root.remove(children[0])
        # 必 2
        assert len(list(root.iter("a"))) == 2

    def test_append(self):
        """`xml.etree append Element 必 len 加 1。"""
        root = ET.fromstring("<r><a/></r>")
        # 必 1
        assert len(list(root.iter("a"))) == 1
        # append
        root.append(ET.Element("a"))
        # 必 2
        assert len(list(root.iter("a"))) == 2

    def test_findall(self):
        """`xml.etree findall './/b' 必 3。"""
        root = ET.fromstring("<r><b>1</b><b>2</b><a><b>3</b></a></r>")
        # findall './/b' 必 3
        elements = root.findall(".//b")
        # 必 3
        assert len(elements) == 3

    def test_clear_set(self):
        """`xml.etree clear+set 'forge'。"""
        a = ET.fromstring("<a>old</a>")
        # clear
        a.clear()
        # set text
        a.text = "forge"
        # 必 'forge'
        assert a.text == "forge"


# -- csv.Dialect.register 进阶 ----------------------------

class TestCsvDialectRegisterAdvance:
    def test_register_dialect(self):
        """`csv.register_dialect 'forge_d' delimiter=';' quotechar="'"'。"""
        try:
            csv.register_dialect(
                "forge_d",
                delimiter=";",
                quotechar="'",
            )
            # 必能 list dialects
            assert "forge_d" in csv.list_dialects()
        finally:
            csv.unregister_dialect("forge_d")

    def test_registered_dialect_read(self):
        """`csv 必能用 'forge_d' dialect reader 真读。"""
        try:
            csv.register_dialect(
                "forge_d",
                delimiter=";",
                quotechar="'",
            )
            data = "a;b;c\n1;2;3\n"
            reader = csv.reader(io.StringIO(data), dialect="forge_d")
            rows = list(reader)
            # 必 2
            assert len(rows) == 2
            # 必 1st row ['a', 'b', 'c']
            assert rows[0] == ["a", "b", "c"]
        finally:
            csv.unregister_dialect("forge_d")


# -- inspect.signature.bind+get_annotations+formatannotation 进阶 --

def _forge_sig(a: int, b: str = "forge") -> str:
    return f"{a}{b}"


class TestInspectSignatureBindGetAnnotationsFormatannotationAdvance:
    def test_signature_bind(self):
        """`inspect.signature.bind 真 a=1 b='forge' 必不抛。"""
        sig = inspect.signature(_forge_sig)
        # bind
        bound = sig.bind(a=1, b="forge_value")
        # 必 BoundArguments
        assert "a" in bound.arguments
        # 必 1
        assert bound.arguments["a"] == 1

    def test_get_annotations(self):
        """`inspect.get_annotations 函数 必 dict 'a':int。"""
        ann = inspect.get_annotations(_forge_sig)
        # 必 dict
        assert isinstance(ann, dict)
        # 必含 'a':int + 'b':str
        assert ann["a"] is int
        assert ann["b"] is str

    def test_formatannotation(self):
        """`inspect.formatannotation 必 str 'str'。"""
        s = inspect.formatannotation(str)
        # 必 str
        assert isinstance(s, str)
        # 必 'str'
        assert s == "str"


# -- pickle 进阶 2-3-4-5 protocol round-trip --------------

class TestPickleProtocol2To5Advance:
    def test_protocol_2(self):
        """`pickle protocol 2 dumps+loads round-trip。"""
        original = {"forge": 42, "value": [1, 2, 3]}
        encoded = pickle.dumps(original, protocol=2)
        decoded = pickle.loads(encoded)
        # 必等
        assert decoded == original

    def test_protocol_5(self):
        """`pickle protocol 5 dumps+loads round-trip。"""
        original = {"forge": 42, "value": [1, 2, 3]}
        encoded = pickle.dumps(original, protocol=5)
        decoded = pickle.loads(encoded)
        # 必等
        assert decoded == original


# -- logging.Filter 真用 进阶 ------------------------------

class _ForgeFilter(logging.Filter):
    def filter(self, record):
        return "forge" in record.getMessage()


class TestLoggingFilterAdvance:
    def test_Filter_True(self):
        """`logging.Filter 真用 filter 'forge' 必 True。"""
        f = _ForgeFilter()
        record = logging.LogRecord("forge_n", logging.INFO, "/p", 1, "msg forge", None, None)
        # 必 True
        assert f.filter(record) is True


# -- functools.reduce+cmp_to_key+total_ordering+cache_clear 进阶 --

@functools.total_ordering
class _ForgeTotal2:
    def __init__(self, val):
        self.val = val

    def __eq__(self, other):
        return self.val == other.val

    def __lt__(self, other):
        return self.val < other.val


@functools.lru_cache(maxsize=10)
def _forge_cached(x):
    return x * 2


class TestFunctoolsReduceCmpToKeyTotalOrderingCacheClearAdvance:
    def test_reduce(self):
        """`functools.reduce 真 [1,2,3] sum 6。"""
        result = functools.reduce(lambda x, y: x + y, [1, 2, 3])
        # 必 6
        assert result == 6

    def test_cmp_to_key_reverse(self):
        """`functools.cmp_to_key reverse [3,2,1]。"""

        def cmp(a, b):
            return b - a

        result = sorted([3, 1, 2], key=functools.cmp_to_key(cmp))
        # 必 [3, 2, 1]
        assert result == [3, 2, 1]

    def test_total_ordering(self):
        """`functools.total_ordering 必排序 [3,1,2] 必 [1,2,3]。"""
        a, b, c = _ForgeTotal2(1), _ForgeTotal2(2), _ForgeTotal2(3)
        result = sorted([c, a, b])
        # 必 [a, b, c]
        assert [x.val for x in result] == [1, 2, 3]

    def test_cache_clear(self):
        """`functools.cache_clear 必 hits=0 after clear。"""
        # 真算 1 次
        _forge_cached(99)
        # clear
        _forge_cached.cache_clear()
        # 必 hit 0
        info = _forge_cached.cache_info()
        # 必 hit 0
        assert info.hits == 0
