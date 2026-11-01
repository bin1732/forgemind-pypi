# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`xml.dom.minidom` / `xml.sax` / `html.parser` / `json.tool` 真底层测试。

- minidom:真的解析 XML 文档并遍历节点
- xml.sax:真的用 SAX 解析器读文档,逐个回调
- html.parser:真的解析 HTML,取出标签与文本
- json.tool:真的美化与压缩 JSON 文本

覆盖 minidom 5 + xml.sax 5 + html.parser 5 + json.tool 5 + 真底层测试。
"""

import json
import xml.dom.minidom
import xml.sax
from html.parser import HTMLParser
from json import JSONDecoder, JSONEncoder

import pytest

XML_TEXT = """<?xml version="1.0" encoding="utf-8"?>
<catalog count="2">
  <book id="b1" lang="zh">
    <title>第一个</title>
    <price>10.5</price>
  </book>
  <book id="b2" lang="en">
    <title>Second</title>
    <price>20</price>
  </book>
</catalog>
"""


# ======================== minidom ========================


class TestMinidom:
    """XML 文档对象模型"""

    def _doc(self):
        return xml.dom.minidom.parseString(XML_TEXT)

    def test_root_element(self):
        """根元素是 catalog"""
        doc = self._doc()
        assert doc.documentElement.tagName == "catalog"

    def test_root_attribute(self):
        """根元素的属性可读"""
        doc = self._doc()
        assert doc.documentElement.getAttribute("count") == "2"

    def test_child_elements(self):
        """子元素能列出来"""
        doc = self._doc()
        books = doc.documentElement.getElementsByTagName("book")
        assert len(books) == 2

    def test_text_content(self):
        """能取到节点的文本"""
        doc = self._doc()
        titles = doc.getElementsByTagName("title")
        assert titles[0].firstChild.data == "第一个"
        assert titles[1].firstChild.data == "Second"

    def test_child_nodes_count(self):
        """子节点数量可数"""
        doc = self._doc()
        book = doc.getElementsByTagName("book")[0]
        # book 下有 title 与 price 两个元素
        elements = [n for n in book.childNodes if n.nodeType == n.ELEMENT_NODE]
        assert len(elements) == 2

    def test_iterate_attributes(self):
        """能遍历元素的所有属性"""
        doc = self._doc()
        book = doc.getElementsByTagName("book")[0]
        attrs = dict(book.attributes.items())
        assert attrs["id"] == "b1"
        assert attrs["lang"] == "zh"

    def test_write_to_string(self):
        """能序列化回字符串"""
        doc = self._doc()
        text = doc.toxml()
        assert "catalog" in text
        assert "b1" in text

    def test_invalid_xml_raises(self):
        """非法 XML 报错"""
        with pytest.raises(Exception):
            xml.dom.minidom.parseString("<a><b></a>")

    def test_get_elements_by_tag_name_empty(self):
        """查不存在的标签返回空列表"""
        doc = self._doc()
        assert doc.getElementsByTagName("absent") == []


# ======================== xml.sax ========================


class _RecordingHandler(xml.sax.ContentHandler):
    """记录 SAX 回调。"""

    def __init__(self):
        super().__init__()
        self.started = []
        self.ended = []
        self.texts = []
        self.attributes = {}

    def startElement(self, name, attrs):
        self.started.append(name)
        # 同名元素会被多次回调,这里按名字累积
        self.attributes.setdefault(name, []).append(dict(attrs.items()))

    def endElement(self, name):
        self.ended.append(name)

    def characters(self, content):
        if content.strip():
            self.texts.append(content.strip())


class TestXmlSax:
    """SAX 解析"""

    def _parse(self):
        handler = _RecordingHandler()
        xml.sax.parseString(XML_TEXT.encode("utf-8"), handler)
        return handler

    def test_start_elements(self):
        """开始元素被回调"""
        handler = self._parse()
        assert handler.started[0] == "catalog"
        assert "book" in handler.started

    def test_end_elements(self):
        """结束元素被回调"""
        handler = self._parse()
        assert handler.ended[-1] == "catalog"
        assert handler.ended.count("book") == 2

    def test_characters(self):
        """文本内容被回调"""
        handler = self._parse()
        assert "第一个" in handler.texts
        assert "Second" in handler.texts

    def test_attributes(self):
        """属性被传进来"""
        handler = self._parse()
        assert handler.attributes["book"][0]["id"] == "b1"
        assert handler.attributes["book"][1]["id"] == "b2"

    def test_root_attributes(self):
        """根元素的属性也传进来"""
        handler = self._parse()
        assert handler.attributes["catalog"][0]["count"] == "2"

    def test_invalid_xml_raises(self):
        """非法 XML 报错"""
        with pytest.raises(xml.sax.SAXParseException):
            xml.sax.parseString(b"<a><b></a>", _RecordingHandler())


# ======================== html.parser ========================


class _CollectingParser(HTMLParser):
    """收集标签与文本。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.texts = []
        self.attrs = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.append((tag, dict(attrs)))

    def handle_data(self, data):
        if data.strip():
            self.texts.append(data.strip())


HTML_TEXT = """<html>
<head><title>标题</title></head>
<body>
<p class="first">段落一</p>
<p class="second">段落二</p>
<a href="http://forge.invalid">链接</a>
<img src="a.png" alt="图">
</body>
</html>
"""


class TestHtmlParser:
    """HTML 解析"""

    def _parse(self):
        parser = _CollectingParser()
        parser.feed(HTML_TEXT)
        parser.close()
        return parser

    def test_tags(self):
        """标签被收集"""
        parser = self._parse()
        assert "html" in parser.tags
        assert parser.tags.count("p") == 2

    def test_texts(self):
        """文本被收集"""
        parser = self._parse()
        assert "段落一" in parser.texts
        assert "链接" in parser.texts

    def test_attributes(self):
        """属性被收集"""
        parser = self._parse()
        attrs = dict(parser.attrs)
        assert attrs["a"]["href"] == "http://forge.invalid"
        assert attrs["img"]["alt"] == "图"

    def test_class_attribute(self):
        """class 属性可读"""
        parser = self._parse()
        classes = [a.get("class") for tag, a in parser.attrs if tag == "p"]
        assert classes == ["first", "second"]

    def test_charrefs_converted(self):
        """字符引用被转换"""
        parser = _CollectingParser()
        parser.feed("<p>&amp;&lt;&gt;</p>")
        parser.close()
        assert "&" in "".join(parser.texts)

    def test_self_closing_tag(self):
        """自闭合标签也被记录"""
        parser = _CollectingParser()
        parser.feed("<br/><hr/>")
        parser.close()
        assert "br" in parser.tags
        assert "hr" in parser.tags


# ======================== json.tool ========================


class TestJsonTool:
    """JSON 文本处理"""

    def test_decode_basic(self):
        """能解出基本结构"""
        data, index = JSONDecoder().raw_decode('{"a": 1}')
        assert data == {"a": 1}
        assert index == 8

    def test_decode_nested(self):
        """能解出嵌套结构"""
        data, _ = JSONDecoder().raw_decode('{"a": {"b": [1, 2]}}')
        assert data["a"]["b"] == [1, 2]

    def test_decode_with_whitespace(self):
        """前导空白由标准解码接口处理"""
        assert json.loads('   {"a": 1}') == {"a": 1}

    def test_decode_error(self):
        """非法 JSON 报错"""
        with pytest.raises(ValueError):
            JSONDecoder().raw_decode("{not json}")

    def test_encode_basic(self):
        """能编码成字符串"""
        text = JSONEncoder().encode({"a": 1})
        assert json.loads(text) == {"a": 1}

    def test_encode_sort_keys(self):
        """能按键排序"""
        text = JSONEncoder(sort_keys=True).encode({"b": 1, "a": 2})
        assert text.index('"a"') < text.index('"b"')

    def test_encode_indent(self):
        """能缩进输出"""
        text = JSONEncoder(indent=2).encode({"a": 1})
        assert "\n" in text
        assert "  " in text
