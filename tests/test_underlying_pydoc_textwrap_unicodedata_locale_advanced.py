# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`pydoc` + `textwrap` + `unicodedata` + `locale` 进阶真底层测试。

覆盖文档 / 文本包装 / Unicode / locale 模块:
  - `pydoc.render_doc('os')` 真返 docstring 字符串
  - `pydoc.help(os)` 真返可读 help 文本
  - `textwrap.fill('长字符串', width=20)` 真按 20 字符换行
  - `textwrap.indent('a\\nb', '> ')` 真每行前加 '> '
  - `textwrap.shorten('very long ...', width=20)` 真截断+...
  - `textwrap.dedent 多行缩进块` 真去共同前导空白
  - `unicodedata.name('A')` 'LATIN CAPITAL LETTER A'
  - `unicodedata.category('中')` 'Lo' (Letter other)
  - `unicodedata.normalize('NFC', 'é')` 'é' (precomposed) → NFC 单 codepoint
  - `unicodedata.east_asian_width('中')` 'W' (Wide)
  - `locale.getlocale()` 真返 (lang, encoding) tuple
  - `locale.format_string('%d', 42, grouping=True)` 真格式千分位
  - `locale.atof('1.5', locale_str_default='C')` 真解析
"""
import locale
import pydoc
import textwrap
import unicodedata

import pytest


# -- pydoc --------------------------------------------------------------------

class TestPydoc:
    def test_render_doc_returns_string(self):
        """`pydoc.render_doc('os')` 真返 docstring 字符串。"""
        out = pydoc.render_doc("os", renderer=pydoc.plaintext)
        assert isinstance(out, str)
        assert "os" in out.lower() or "module" in out.lower(), (
            f"render_doc 应含 'os' 或 'module',实际前 200 字符 {out[:200]!r}"
        )

    def test_help_callable_renders(self):
        """`pydoc.help(int)` 真返可读 help 文本。"""
        out = pydoc.render_doc("int", renderer=pydoc.plaintext)
        assert isinstance(out, str)
        assert len(out) > 50, f"int 的 help 应有内容,实际长度 {len(out)}"


# -- textwrap -----------------------------------------------------------------

class TestTextwrapAdvanced:
    def test_fill_wraps_at_width(self):
        """`textwrap.fill(long, width=20)` 真按 20 字符换行,每行 ≤ 20。"""
        text = "a" * 100
        out = textwrap.fill(text, width=20)
        for line in out.split("\n"):
            assert len(line) <= 20, f"行应 ≤ 20,实际 {len(line)}: {line!r}"

    def test_indent_prepends_to_each_line(self):
        """`textwrap.indent('a\\nb', '> ')` 真每行前加 '> '。"""
        out = textwrap.indent("a\nb\nc", "> ")
        assert out == "> a\n> b\n> c", f"indent 应='> a\\n> b\\n> c',实际 {out!r}"

    def test_shorten_truncates(self):
        """`textwrap.shorten('very long ...', width=15)` 真截断+...。"""
        out = textwrap.shorten("The quick brown fox jumps over", width=15)
        assert "..." in out, f"shorten 应含 '...',实际 {out!r}"
        assert len(out) <= 20  # placeholder 算宽度

    def test_dedent_removes_common_indent(self):
        """`textwrap.dedent` 真去共同前导空白。"""
        text = "    line1\n    line2\n    line3"
        out = textwrap.dedent(text)
        assert out == "line1\nline2\nline3", (
            f"dedent 应去共同 4 空格,实际 {out!r}"
        )


# -- unicodedata --------------------------------------------------------------

class TestUnicodedataAdvanced:
    def test_name_A(self):
        """`unicodedata.name('A')` 'LATIN CAPITAL LETTER A'。"""
        assert unicodedata.name("A") == "LATIN CAPITAL LETTER A"

    def test_category_中(self):
        """`unicodedata.category('中')` 'Lo' (Letter other)。"""
        assert unicodedata.category("中") == "Lo", (
            f"'中' category 应=Lo,实际 {unicodedata.category('中')}"
        )

    def test_normalize_NFC(self):
        """`unicodedata.normalize('NFC', 'é')` 'é' 真预组成。"""
        nfc = unicodedata.normalize("NFC", "é")  # 已经是 NFC
        # 单 codepoint
        assert len(nfc) == 1
        # 反向 NFD
        nfd = unicodedata.normalize("NFD", nfc)
        # NFD 应 = 2 codepoints (e + combining 0x0301)
        assert len(nfd) == 2

    def test_east_asian_width_中(self):
        """`unicodedata.east_asian_width('中')` 'W' (Wide)。"""
        w = unicodedata.east_asian_width("中")
        assert w == "W", f"'中' east_asian_width 应=W,实际 {w}"


# -- locale -------------------------------------------------------------------

class TestLocaleAdvanced:
    def test_getlocale_returns_tuple(self):
        """`locale.getlocale()` 真返 (lang, encoding) tuple。"""
        loc = locale.getlocale()
        assert isinstance(loc, tuple)
        # 长度 2 (lang, encoding)
        assert len(loc) == 2

    def test_format_string_with_grouping(self):
        """`locale.format_string('%d', 1234567, grouping=True)` 真千分位。"""
        # 沙箱 setlocale(LC_ALL, "en_US.UTF-8") 可能抛,先尝试再兜底
        try:
            saved = locale.setlocale(locale.LC_ALL)
        except locale.Error:
            saved = None
        try:
            locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
        except locale.Error:
            # 沙箱没 en_US,改用 C locale 测 grouping=False 的纯格式
            out = locale.format_string("%d", 1234567, grouping=False)
            assert out == "1234567", f"C locale 无 grouping,应原样,实际 {out!r}"
            return
        try:
            out = locale.format_string("%d", 1234567, grouping=True)
            assert isinstance(out, str)
            # en_US 千分位是 ','
            assert "," in out, f"en_US grouping 应含 ',',实际 {out!r}"
        finally:
            try:
                if saved:
                    locale.setlocale(locale.LC_ALL, saved)
            except locale.Error:
                pass

    def test_atof_parses(self):
        """`locale.atof('3.14')` 真浮点解析。"""
        try:
            v = locale.atof("3.14")
            assert isinstance(v, float)
            assert abs(v - 3.14) < 0.01
        except (locale.Error, ValueError):
            pytest.skip("locale.atof 不可用")
