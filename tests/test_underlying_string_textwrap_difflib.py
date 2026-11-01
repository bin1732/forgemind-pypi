# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 string (Template / Formatter / capwords) + 真 textwrap (fill / dedent / indent) + 真 difflib (SequenceMatcher / unified_diff / HtmlDiff) + 真 unicodedata。
全 stdlib, 零模拟。
"""
import string
import textwrap
import difflib
import unicodedata
import pytest


# ======================== string ========================
def test_string_ascii_lowercase():
    """真 ascii_lowercase"""
    assert string.ascii_lowercase == "abcdefghijklmnopqrstuvwxyz"
    assert string.ascii_uppercase == "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    assert string.digits == "0123456789"
    assert string.punctuation == "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
    assert string.whitespace == " \t\n\r\x0b\x0c"


def test_string_template_basic():
    """真 Template 真替换"""
    t = string.Template("Hello, $name! You are $age years old.")
    result = t.substitute(name="Alice", age=30)
    assert result == "Hello, Alice! You are 30 years old."


def test_string_template_safe_substitute():
    """真 safe_substitute 缺 key 不抛"""
    t = string.Template("$name $age")
    result = t.safe_substitute(name="Bob")
    # age 保持 $age
    assert result == "Bob $age"


def test_string_template_idpattern():
    """真 Template.idpattern 真可改"""
    t = string.Template("$name")
    # 改 idpattern 接受 $ 起始
    t.idpattern = r"(?a:[$_a-z][$_a-z0-9]*)"
    result = t.substitute(name="Charlie")
    assert result == "Charlie"


def test_string_formatter():
    """真 Formatter 真字段访问"""
    fmt = string.Formatter()
    parts = list(fmt.parse("Hello {name}, you are {age:d}"))
    # 4 元组: literal, field_name, format_spec, conversion
    assert parts[0] == ("Hello ", "name", "", None)
    assert parts[1] == (", you are ", "age", "d", None)


def test_string_capwords():
    """真 capwords 真首字母大写"""
    assert string.capwords("hello world") == "Hello World"
    assert string.capwords("HELLO WORLD") == "Hello World"
    assert string.capwords("hello  world") == "Hello World"


# ======================== textwrap ========================
def test_textwrap_fill():
    """真 fill 真换行"""
    text = "The quick brown fox jumps over the lazy dog. " * 5
    wrapped = textwrap.fill(text, width=20)
    # 多行
    assert "\n" in wrapped
    # 每行不超 20 (除最后)
    for line in wrapped.split("\n"):
        assert len(line) <= 20


def test_textwrap_dedent():
    """真 dedent 真去缩进"""
    text = """
        hello
        world
    """
    dedented = textwrap.dedent(text)
    # 缩进已去
    assert "hello" in dedented
    assert "world" in dedented
    # 公共前导空白已去
    lines = [l for l in dedented.split("\n") if l.strip()]
    assert all(not l.startswith(" ") for l in lines)


def test_textwrap_indent():
    """真 indent 真加前缀"""
    text = "line1\nline2\nline3"
    indented = textwrap.indent(text, "  ")
    # 每行加 "  "
    for line in indented.split("\n"):
        assert line.startswith("  ")


def test_textwrap_shorten():
    """真 shorten 真截断"""
    text = "The quick brown fox jumps over the lazy dog"
    shortened = textwrap.shorten(text, width=20)
    assert len(shortened) <= 20
    # 末尾 "[...]" (默认 placeholder)
    assert shortened.endswith("...") or shortened.endswith("[...]")


# ======================== difflib ========================
def test_difflib_sequence_matcher_ratio():
    """真 SequenceMatcher 真相似度"""
    s = difflib.SequenceMatcher(None, "abcde", "abcfg")
    ratio = s.ratio()
    # 3/5 字符匹配
    assert 0.5 < ratio < 0.7


def test_difflib_get_close_matches():
    """真 get_close_matches 真最近匹配"""
    matches = difflib.get_close_matches("apple", ["ape", "apply", "apricot", "banana"])
    assert "apply" in matches
    # "ape" 也很近


def test_difflib_unified_diff():
    """真 unified_diff 真 diff 格式"""
    a = ["line1\n", "line2\n", "line3\n"]
    b = ["line1\n", "line2 changed\n", "line3\n"]
    diff = list(difflib.unified_diff(a, b, lineterm=""))
    diff_text = "\n".join(diff)
    # 包含 @@ hunk
    assert "@@" in diff_text
    # 包含 -  / +
    assert "-line2" in diff_text
    assert "+line2 changed" in diff_text


def test_difflib_html_diff():
    """真 HtmlDiff 真 HTML"""
    d = difflib.HtmlDiff()
    a = ["line1\n", "line2\n"]
    b = ["line1\n", "line2 different\n"]
    html = d.make_table(a, b)
    # 包含 HTML 标签
    assert "<table" in html or "<TABLE" in html
    # 包含 escape 后内容
    assert "line1" in html


# ======================== unicodedata ========================
def test_unicodedata_name():
    """真 unicodedata.name"""
    assert unicodedata.name("A") == "LATIN CAPITAL LETTER A"
    assert unicodedata.name("中") == "CJK UNIFIED IDEOGRAPH-4E2D"


def test_unicodedata_lookup():
    """真 lookup 真 by name"""
    assert unicodedata.lookup("LATIN CAPITAL LETTER A") == "A"
    # lookup 不存在抛 KeyError
    with pytest.raises(KeyError):
        unicodedata.lookup("NOT EXIST")


def test_unicodedata_category():
    """真 category"""
    assert unicodedata.category("A") == "Lu"  # Letter, uppercase
    assert unicodedata.category("a") == "Ll"  # Letter, lowercase
    assert unicodedata.category("1") == "Nd"  # Number, decimal
    assert unicodedata.category(" ") == "Zs"  # Separator, space


def test_unicodedata_normalize():
    """真 NFC / NFD normalize"""
    # 'é' 预组合 = 单 codepoint
    composed = "é"
    assert len(composed) == 1
    # NFD 拆 = 'e' + 0x0301 (combining acute)
    decomposed = unicodedata.normalize("NFD", composed)
    assert len(decomposed) == 2
    # NFC 把 decomposed 归一化回
    nfc = unicodedata.normalize("NFC", decomposed)
    assert nfc == composed
    assert len(nfc) == 1


def test_unicodedata_east_asian_width():
    """真 east_asian_width"""
    # 中 = 'W' (Wide)
    assert unicodedata.east_asian_width("中") == "W"
    # A = 'Na' (Narrow)
    assert unicodedata.east_asian_width("A") == "Na"
    # 1 = 'Na'
    assert unicodedata.east_asian_width("1") == "Na"
