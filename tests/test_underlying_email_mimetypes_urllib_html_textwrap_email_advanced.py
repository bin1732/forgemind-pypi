# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`email` + `mimetypes` + `urllib.parse` 进阶 + `html` 进阶 + `textwrap` 进阶 真底层测试。

覆盖邮件解析 / MIME 类型 / URL 解析 / HTML 工具 / 文本包装模块:
  - `email.message.EmailMessage` 真建
  - `email.message_from_string` 真解 RFC2822
  - `email.message_from_bytes` 真解 bytes RFC2822
  - `mimetypes.guess_type('a.html')` 真返 'text/html'
  - `mimetypes.guess_extension('image/jpeg')` 真返 '.jpg' 类
  - `mimetypes.add_type` 真注册
  - `urllib.parse.urlparse('https://a/b?x=1')` 真解 6 部分
  - `urllib.parse.urlencode({'a': 1, 'b': '中'})` 真 URL encode
  - `urllib.parse.parse_qs('a=1&b=2')` 真解
  - `urllib.parse.quote('中')` 真 percent-encode
  - `urllib.parse.urljoin('https://a/b/c', 'd')` 真='https://a/b/d'
  - `html.escape('<a>')` 真 '&lt;a&gt;'
  - `html.unescape('&amp;')` 真 '&'
  - `textwrap.fill('a '*50, 10)` 真换行
  - `textwrap.indent('a\\nb', '> ')` 真加 '> '
  - `textwrap.shorten('very long', 10)` 真截断
"""
import email
import html
import mimetypes
import textwrap
import urllib.parse

import pytest


# -- email --------------------------------------------------------------------

class TestEmailAdvanced:
    def test_EmailMessage_creation(self):
        """`email.message.EmailMessage` 真建含 header。"""
        msg = email.message.EmailMessage()
        msg["Subject"] = "Forge Test"
        msg["From"] = "test@example.com"
        assert msg["Subject"] == "Forge Test"
        assert msg["From"] == "test@example.com"

    def test_message_from_string(self):
        """`email.message_from_string` 真解 RFC2822 邮件。"""
        raw = "Subject: Test\r\nFrom: a@b.com\r\n\r\nHello forge"
        m = email.message_from_string(raw)
        assert m["Subject"] == "Test"
        assert m.get_payload() == "Hello forge"

    def test_message_from_bytes(self):
        """`email.message_from_bytes` 真解 bytes 邮件。"""
        raw = b"Subject: Bytes\r\nFrom: a@b.com\r\n\r\nBody"
        m = email.message_from_bytes(raw)
        assert m["Subject"] == "Bytes"
        assert m.get_payload() == "Body"


# -- mimetypes ----------------------------------------------------------------

class TestMimetypesAdvanced:
    def test_guess_type_html(self):
        """`mimetypes.guess_type('a.html')` 真返 'text/html'。"""
        ctype, _ = mimetypes.guess_type("a.html")
        assert ctype == "text/html", f"a.html 应=text/html,实际 {ctype}"

    def test_guess_extension_jpeg(self):
        """`mimetypes.guess_extension('image/jpeg')` 真返 '.jpg' 类。"""
        ext = mimetypes.guess_extension("image/jpeg")
        assert ext in (".jpg", ".jpe", ".jpeg"), (
            f"image/jpeg 应≈.jpg,实际 {ext}"
        )

    def test_add_type(self):
        """`mimetypes.add_type` 真注册新类型。"""
        mimetypes.add_type("application/x-forge", ".forge")
        ctype, _ = mimetypes.guess_type("a.forge")
        assert ctype == "application/x-forge", (
            f"添加后 .forge 应=application/x-forge,实际 {ctype}"
        )


# -- urllib.parse -------------------------------------------------------------

class TestUrllibParseAdvanced:
    def test_urlparse_six_parts(self):
        """`urlparse('https://a/b?x=1')` 真解 6 部分。"""
        r = urllib.parse.urlparse("https://example.com/path?query=1#frag")
        assert r.scheme == "https"
        assert r.netloc == "example.com"
        assert r.path == "/path"
        assert r.query == "query=1"
        assert r.fragment == "frag"

    def test_urlencode_chinese(self):
        """`urlencode({'q': '中文'})` 真 percent-encode。"""
        out = urllib.parse.urlencode({"q": "中文"})
        # '中' = %E4%B8%AD, '文' = %E6%96%87
        assert "%E4%B8%AD" in out, f"urlencode 应含 %E4%B8%AD,实际 {out}"
        assert "%E6%96%87" in out, f"urlencode 应含 %E6%96%87,实际 {out}"

    def test_parse_qs(self):
        """`parse_qs('a=1&b=2')` 真解 {'a': ['1'], 'b': ['2']}。"""
        d = urllib.parse.parse_qs("a=1&b=2&a=3")
        assert d == {"a": ["1", "3"], "b": ["2"]}, (
            f"parse_qs 应={'a':['1','3'],'b':['2']},实际 {d}"
        )

    def test_quote(self):
        """`urllib.parse.quote('中')` 真 percent-encode。"""
        out = urllib.parse.quote("中文")
        assert out == "%E4%B8%AD%E6%96%87", f"quote '中文' 应=%E4%B8%AD%E6%96%87,实际 {out}"

    def test_urljoin(self):
        """`urljoin('https://a/b/c', 'd')` 真='https://a/b/d'。"""
        out = urllib.parse.urljoin("https://a.com/b/c", "d")
        assert out == "https://a.com/b/d", f"urljoin 应=https://a.com/b/d,实际 {out}"


# -- html ---------------------------------------------------------------------

class TestHtmlAdvanced:
    def test_escape(self):
        """`html.escape('<a>')` 真 '&lt;a&gt;'。"""
        out = html.escape("<a>")
        assert out == "&lt;a&gt;", f"escape '<a>' 应=&lt;a&gt;,实际 {out!r}"

    def test_escape_with_quote(self):
        """`html.escape(quote=True)` 真转义引号。"""
        out = html.escape('"forge"', quote=True)
        assert "&quot;" in out, f"quote=True 应转义引号,实际 {out!r}"

    def test_unescape(self):
        """`html.unescape('&amp;')` 真 '&'。"""
        assert html.unescape("&amp;") == "&"
        assert html.unescape("&lt;a&gt;") == "<a>"


# -- textwrap 进阶 ------------------------------------------------------------

class TestTextwrapAdvancedV2:
    def test_fill_wraps_long(self):
        """`textwrap.fill('a '*50, 10)` 真按 10 字符换行,每行 ≤ 10。"""
        text = "a " * 50
        out = textwrap.fill(text, width=10)
        for line in out.split("\n"):
            assert len(line) <= 10, f"行应 ≤ 10,实际 {len(line)}: {line!r}"

    def test_indent_simple(self):
        """`textwrap.indent('a\\nb', '> ')` 真每行加 '> '。"""
        assert textwrap.indent("a\nb", "> ") == "> a\n> b"

    def test_shorten(self):
        """`textwrap.shorten('very long text', 10)` 真截断。"""
        out = textwrap.shorten("very long text here", width=10)
        assert "..." in out, f"shorten 应含 '...',实际 {out!r}"
