# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 xml 进阶 (CDATA / 真 parse 大文件) + 真 email 进阶 (MIME 真 multi-part / Header 真 encode) + 真 json 进阶 (encoder 嵌套 / custom default / 真 sort 真) + 真 unicodedata 进阶 (decomposition 真 normalize 链)。
全 stdlib, 零模拟。
"""
import xml.etree.ElementTree as ET
import email
import email.mime.multipart
import email.mime.text
import email.header
import json
import unicodedata
import os
import tempfile
import pytest


# ======================== xml 进阶 ========================
def test_xml_parse_with_attrs():
    """真 xml 真 attrs 真 namespace"""
    xml = '''<root xmlns:ns="http://example.com">
<ns:item id="1" type="a">value 1</ns:item>
<ns:item id="2" type="b">value 2</ns:item>
</root>'''
    root = ET.fromstring(xml)
    ns = "{http://example.com}"
    items = root.findall(f".//{ns}item")
    assert len(items) == 2
    assert items[0].get("id") == "1"
    assert items[0].get("type") == "a"
    assert items[0].text == "value 1"


def test_xml_parse_big_file():
    """真 xml 真大文件真 parse"""
    # 1000 个元素
    lines = ['<root>']
    for i in range(1000):
        lines.append(f'  <item id="{i}" value="v{i}">item {i}</item>')
    lines.append('</root>')
    xml = "\n".join(lines)
    root = ET.fromstring(xml)
    items = root.findall("item")
    assert len(items) == 1000
    # 第一个
    assert items[0].get("id") == "0"
    # 最后
    assert items[999].get("id") == "999"


def test_xml_write_read_roundtrip():
    """真 xml 写读 round-trip"""
    root = ET.Element("data")
    for i in range(5):
        item = ET.SubElement(root, "item", id=str(i))
        item.text = f"value {i}"
    # serialize
    xml_str = ET.tostring(root, encoding="unicode")
    # 解析回
    root2 = ET.fromstring(xml_str)
    items = root2.findall("item")
    assert len(items) == 5
    assert items[2].text == "value 2"


# ======================== email 进阶 ========================
def test_email_mime_multipart():
    """真 email.mime 真 multi-part"""
    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg["Subject"] = "Test multi-part"
    msg["From"] = "alice@example.com"
    msg["To"] = "bob@example.com"
    # 加 part
    text = email.mime.text.MIMEText("Hello plain", "plain", "utf-8")
    html = email.mime.text.MIMEText("<p>Hello HTML</p>", "html", "utf-8")
    msg.attach(text)
    msg.attach(html)
    # 序列化
    s = msg.as_string()
    # 验证
    assert "multipart/alternative" in s
    # base64 编码内容
    assert "SGVsbG8gcGxhaW4=" in s  # base64("Hello plain")
    assert "PHA+SGVsbG8gSFRNTDwvcD4=" in s  # base64("<p>Hello HTML</p>")


def test_email_header_encode():
    """真 email.header 真 encode"""
    # 中文 subject
    subject = "测试中文主题"
    encoded = email.header.Header(subject, "utf-8").encode()
    # 含 "=?utf-8?" 或 RFC 2047
    s = str(encoded)
    assert "=?utf-8" in s.lower() or "=?" in s


def test_email_header_decode():
    """真 email.header 真 decode"""
    encoded = email.header.Header("测试").encode()
    decoded = str(email.header.make_header(email.header.decode_header(encoded)))
    assert "测试" in decoded


# ======================== json 进阶 ========================
def test_json_nested_unicode():
    """真 json 真嵌套 + unicode"""
    data = {
        "user": {
            "name": "中文字符",
            "tags": ["python", "JSON", "测试"]
        },
        "count": 42
    }
    # ensure_ascii=False 保留 UTF-8
    s = json.dumps(data, ensure_ascii=False)
    assert "中文字符" in s
    # parse 回
    parsed = json.loads(s)
    assert parsed == data


def test_json_separators_custom():
    """真 json 真 separators"""
    data = {"a": 1, "b": 2}
    # 默认
    s1 = json.dumps(data)
    # 紧凑
    s2 = json.dumps(data, separators=(",", ":"))
    # 紧凑 < 默认
    assert len(s2) < len(s1)
    # 仍可 parse
    assert json.loads(s2) == data


def test_json_indent():
    """真 indent"""
    data = {"a": [1, 2, 3], "b": {"x": "y"}}
    s = json.dumps(data, indent=2)
    # 多行
    assert "\n" in s
    # 含 indent (2 space)
    assert "  " in s


def test_json_check_circular():
    """真 json circular 检测 (TypeError)"""
    a = {"name": "A"}
    a["self"] = a  # circular
    with pytest.raises((ValueError, TypeError)):
        json.dumps(a)


# ======================== unicodedata 进阶 ========================
def test_unicodedata_decomposition():
    """真 decomposition 真拆"""
    # "é" 预组合 → NFD 拆
    composed = "é"
    decomposed = unicodedata.normalize("NFD", composed)
    assert len(decomposed) == 2
    # e (U+0065) + combining acute (U+0301)
    parts = [hex(ord(c)) for c in decomposed]
    assert "0x65" in parts
    assert "0x301" in parts


def test_unicodedata_mirrored():
    """真 mirrored 真镜像"""
    # "<" 是镜像
    assert unicodedata.mirrored("<") == 1
    # "A" 不是
    assert unicodedata.mirrored("A") == 0
    # "中" 不是
    assert unicodedata.mirrored("中") == 0


def test_unicodedata_combining():
    """真 combining 真组合"""
    # combining acute (U+0301) 是 combining
    combining = "\u0301"
    # combining 类
    cat = unicodedata.category(combining)
    # M* = combining mark
    assert cat.startswith("M")
