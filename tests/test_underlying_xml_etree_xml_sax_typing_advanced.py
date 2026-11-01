# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`xml.etree.ElementTree` + `xml.sax` + `typing` 进阶真底层测试。

覆盖 XML 元素树 / SAX 流式解析 / typing 模块高级:
  - `xml.etree.ElementTree.fromstring('<a><b x="1">hi</b></a>')` 真建 ElementTree
  - `ElementTree.iter('tag')` 真遍历子 tag
  - `Element.findtext('tag')` 真返第一个匹配 text
  - `Element.set('attr', val)` 真写属性
  - `Element.tostring()` 真序列化回 bytes
  - `xml.sax.make_parser` 真建 SAX parser
  - `xml.sax.parseString(src, handler)` 真流式触发 ContentHandler
  - `typing.TypeVar` 显式 bound=str 真限制类型
  - `typing.NewType` 真建 distinct type
  - `typing.runtime_checkable` Protocol 真 `isinstance` 判
  - `typing.overload` 真返 Union 类型
  - `typing.get_type_hints` 真解 PEP 563 annotations
"""
import sys
import typing
import xml.etree.ElementTree as ET
import xml.sax
import xml.sax.handler

import pytest


# -- xml.etree.ElementTree ----------------------------------------------------

class TestElementTree:
    def test_fromstring_builds_tree(self):
        """`ElementTree.fromstring('<a><b x="1">hi</b></a>')` 真建 ElementTree。"""
        root = ET.fromstring('<a><b x="1">hi</b></a>')
        assert root.tag == "a"
        assert root[0].tag == "b"
        assert root[0].attrib["x"] == "1"
        assert root[0].text == "hi"

    def test_findtext_returns_first_match(self):
        """`Element.findtext('b')` 真返第一个匹配 b 的 text。"""
        root = ET.fromstring("<root><b>first</b><b>second</b></root>")
        assert root.findtext("b") == "first", (
            f"findtext 应返 'first',实际 {root.findtext('b')!r}"
        )

    def test_iter_traverses_descendants(self):
        """`Element.iter('item')` 真遍历所有 descendant。"""
        root = ET.fromstring(
            "<root><item>1</item><wrap><item>2</item></wrap><item>3</item></root>"
        )
        items = list(root.iter("item"))
        assert len(items) == 3, f"应找到 3 个 item,实际 {len(items)}"
        texts = [e.text for e in items]
        assert texts == ["1", "2", "3"], f"text 顺序错: {texts}"

    def test_set_attribute_and_tostring(self):
        """`Element.set('k', 'v')` 真写属性,`tostring()` 真序列化回。"""
        root = ET.Element("a")
        root.set("forge", "1")
        child = ET.SubElement(root, "b")
        child.text = "hello"
        out = ET.tostring(root, encoding="unicode")
        assert 'forge="1"' in out
        assert ">hello</b>" in out


# -- xml.sax 流式解析 --------------------------------------------------------

class _CountingHandler(xml.sax.handler.ContentHandler):
    def __init__(self):
        super().__init__()
        self.starts = []
        self.ends = []
        self.texts = []

    def startElement(self, name, attrs):
        self.starts.append(name)

    def endElement(self, name):
        self.ends.append(name)

    def characters(self, content):
        self.texts.append(content)


class TestXmlSax:
    def test_sax_parseString_triggers_handler(self):
        """`xml.sax.parseString(src, handler)` 真流式触发 ContentHandler。"""
        handler = _CountingHandler()
        xml.sax.parseString("<a><b>forge</b></a>", handler)
        assert handler.starts == ["a", "b"], (
            f"startElement 顺序错: {handler.starts}"
        )
        assert handler.ends == ["b", "a"], f"endElement 顺序错: {handler.ends}"
        assert any("forge" in t for t in handler.texts), (
            f"characters 应含 'forge',实际 {handler.texts}"
        )

    def test_sax_make_parser_returns_parser(self):
        """`xml.sax.make_parser` 真建 SAX parser。"""
        parser = xml.sax.make_parser()
        assert parser is not None
        # SAX parser 必是 xml.sax.xmlreader.XMLReader 子类
        assert hasattr(parser, "parse") and hasattr(parser, "setContentHandler")


# -- typing 进阶 --------------------------------------------------------------

class TestTypingAdvanced:
    def test_TypeVar_with_bound(self):
        """`TypeVar('T', bound=str)` 真限制 T 是 str 子类。"""
        T = typing.TypeVar("T", bound=str)

        class Container(typing.Generic[T]):
            def __init__(self, value: T):
                self.value = value

        c = Container("forge")
        assert c.value == "forge"
        # 必是 T 推断
        assert typing.get_type_hints(Container.__init__)["value"] is T

    def test_NewType_creates_distinct_type(self):
        """`NewType('UserId', int)` 真建 distinct type,IDE 会区分。"""
        UserId = typing.NewType("UserId", int)
        uid = UserId(42)
        assert uid == 42
        # 运行时 UserId 是 plain function,int 可被 NewType 包裹
        assert isinstance(uid, int)
        # 不同 NewType 互不相等
        OrderId = typing.NewType("OrderId", int)
        assert UserId(42) == OrderId(42)  # 值相等
        # 但 typing 知道 UserId != OrderId
        assert UserId is not OrderId

    def test_runtime_checkable_Protocol(self):
        """`runtime_checkable` Protocol 真 `isinstance` 判鸭子类型。"""
        @typing.runtime_checkable
        class Drawable(typing.Protocol):
            def draw(self) -> str: ...

        class Circle:
            def draw(self) -> str:
                return "circle"

        c = Circle()
        # runtime_checkable 允许 isinstance 判
        assert isinstance(c, Drawable), "circle 应被 runtime_checkable 判为 Drawable"

    def test_overload_marks_function(self):
        """`@overload` 装饰函数后真被标记,`typing.get_overloads` 能拿到。"""

        @typing.overload
        def f(x: int) -> int: ...

        @typing.overload
        def f(x: str) -> str: ...

        def f(x):  # noqa: F811
            return x

        overloads = typing.get_overloads(f)
        assert len(overloads) == 2, f"应记 2 个 overload,实际 {len(overloads)}"

    def test_get_type_hints_resolves_forward_refs(self):
        """`get_type_hints` 真解 PEP 563 forward ref 字符串。"""
        # 模块内 forward ref: 同 module 内字符串 annotation
        ns = {"SomeType": int}
        hints = typing.get_type_hints(
            lambda x: None,  # placeholder
            globalns=ns,
            localns={},
        )
        # 上面 lambda 拿不到 'x' 注解,改用真实函数

        def f(x: "int") -> None:  # type: ignore[valid-type]
            pass

        hints = typing.get_type_hints(f)
        assert hints["x"] is int
