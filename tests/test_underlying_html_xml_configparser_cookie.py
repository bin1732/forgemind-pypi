# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 html (escape / unescape) + 真 xml (ElementTree 真 parse/序列化) + 真 configparser (真 ini 读写) + 真 http.cookies + 真 urllib.parse (quote/unquote)。
全 stdlib, 零模拟。
"""
import html
import xml.etree.ElementTree as ET
import configparser
import http.cookies
import urllib.parse
import io
import pytest


# ======================== html ========================
def test_html_escape():
    """真 html.escape 真转义"""
    s = html.escape("<script>alert('xss')</script>")
    assert "&lt;script&gt;" in s
    assert "&gt;" in s
    # quote 默认 True
    assert "&#x27;" in s or "&#39;" in s


def test_html_unescape():
    """真 html.unescape 真反转义"""
    s = "&lt;p&gt;Hello&lt;/p&gt;"
    unescaped = html.unescape(s)
    assert unescaped == "<p>Hello</p>"


def test_html_escape_quote_false():
    """真 escape quote=False 不转义引号"""
    s = html.escape("a & b", quote=False)
    assert s == "a &amp; b"


# ======================== xml.etree ========================
def test_xml_parse_simple():
    """真 ElementTree parse"""
    xml = "<root><a>1</a><b>2</b></root>"
    root = ET.fromstring(xml)
    assert root.tag == "root"
    assert root.find("a").text == "1"
    assert root.find("b").text == "2"


def test_xml_attribute():
    """真 xml 真 attribute"""
    xml = '<item id="42" name="test" />'
    elem = ET.fromstring(xml)
    assert elem.get("id") == "42"
    assert elem.get("name") == "test"


def test_xml_build_and_serialize():
    """真 xml 真 build + serialize"""
    root = ET.Element("root")
    a = ET.SubElement(root, "a")
    a.text = "1"
    b = ET.SubElement(root, "b")
    b.set("attr", "value")
    b.text = "2"
    # serialize
    s = ET.tostring(root, encoding="unicode")
    assert "<root>" in s or "<root/>" in s
    assert "<a>1</a>" in s
    assert 'attr="value"' in s


def test_xml_iterparse():
    """真 iterparse 真流式 parse"""
    xml = "<root>" + "".join(f"<item>{i}</item>" for i in range(10)) + "</root>"
    events = []
    for event, elem in ET.iterparse(io.StringIO(xml)):
        if event == "end":
            events.append(elem.tag)
    assert "item" in events
    assert events.count("item") == 10


def test_xml_xpath():
    """真 xpath findall / find"""
    xml = "<root><a>1</a><b><a>2</a></b></root>"
    root = ET.fromstring(xml)
    a_elems = root.findall(".//a")
    assert len(a_elems) == 2
    assert a_elems[0].text == "1"
    assert a_elems[1].text == "2"


# ======================== configparser ========================
def test_configparser_basic():
    """真 configparser 真 ini 读写"""
    config = configparser.ConfigParser()
    config["DEFAULT"] = {"ServerAliveInterval": "45"}
    config["bitbucket.org"] = {"User": "hg"}
    config["topsecret.server.com"] = {"Host Port": "50022", "ForwardX11": "no"}
    # 序列化
    buf = io.StringIO()
    config.write(buf)
    s = buf.getvalue()
    # 包含 section
    assert "[bitbucket.org]" in s
    # 包含 key=value
    assert "user = hg" in s.lower() or "user=hg" in s.lower()


def test_configparser_read_and_get():
    """真 configparser 真 read + get"""
    ini = """
[section1]
key1 = value1
key2 = value2

[section2]
key3 = value3
"""
    config = configparser.ConfigParser()
    config.read_string(ini)
    assert config.get("section1", "key1") == "value1"
    assert config.get("section2", "key3") == "value3"


def test_configparser_types():
    """真 configparser 真类型转换"""
    ini = """
[sec]
int_key = 42
float_key = 3.14
bool_key = true
"""
    config = configparser.ConfigParser()
    config.read_string(ini)
    assert config.getint("sec", "int_key") == 42
    assert abs(config.getfloat("sec", "float_key") - 3.14) < 0.001
    assert config.getboolean("sec", "bool_key") is True


# ======================== http.cookies ========================
def test_cookies_basic():
    """真 http.cookies 真 SimpleCookie"""
    c = http.cookies.SimpleCookie()
    c["name"] = "value"
    c["name"]["path"] = "/"
    c["name"]["secure"] = True
    # 真 serialize
    output = c.output()
    assert "name=value" in "".join(output)
    assert "Path=/" in "".join(output) or "path=/" in "".join(output).lower()


def test_cookies_parse():
    """真 cookies load 真 header"""
    c = http.cookies.SimpleCookie()
    c.load("sessionid=abc123; user=alice; theme=dark")
    assert c["sessionid"].value == "abc123"
    assert c["user"].value == "alice"
    assert c["theme"].value == "dark"


# ======================== urllib.parse ========================
def test_url_quote():
    """真 urllib.parse.quote"""
    s = urllib.parse.quote("hello world/中文")
    assert "hello%20world" in s
    # 中 = UTF-8 encode 后百分号编码
    assert "%E4" in s or "%e4" in s.lower()


def test_url_unquote():
    """真 unquote 真反转"""
    s = urllib.parse.unquote("hello%20world")
    assert s == "hello world"


def test_url_parse_query():
    """真 parse_qs 真 query 解析"""
    qs = "a=1&b=2&c=hello+world&c=foo"
    parsed = urllib.parse.parse_qs(qs)
    assert parsed["a"] == ["1"]
    assert parsed["b"] == ["2"]
    assert "hello world" in parsed["c"]


def test_urlencode():
    """真 urlencode 真编码"""
    data = {"name": "Alice", "city": "上海"}
    encoded = urllib.parse.urlencode(data)
    # 含百分号编码
    assert "%E4" in encoded or "%e4" in encoded.lower()
    # 反解
    parsed = urllib.parse.parse_qs(encoded)
    assert parsed["name"] == ["Alice"]
