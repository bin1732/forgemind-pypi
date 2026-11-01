# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`gzip` / `bz2` / `lzma` / `fractions` / `html.entities` / `shlex` 真底层测试。

- gzip / bz2 / lzma:真的压缩与解压,往返后内容一致
- fractions:真的做分数运算
- html.entities:真的查 HTML 实体
- shlex:真的按 shell 规则切分命令行

覆盖 gzip 5 + bz2 5 + lzma 5 + fractions 5 + html.entities 5 + shlex 5 + 真底层测试。
"""

import bz2
import fractions
import gzip
import html.entities
import lzma
import shlex
from pathlib import Path

import pytest

PAYLOAD = b"forge payload line\n" * 50


# ======================== gzip ========================


class TestGzip:
    """gzip 压缩"""

    def test_compress_decompress(self, tmp_path):
        """往返后内容一致"""
        path = tmp_path / "forge.gz"
        with gzip.open(path, "wb") as fh:
            fh.write(PAYLOAD)
        with gzip.open(path, "rb") as fh:
            assert fh.read() == PAYLOAD

    def test_compressed_smaller(self, tmp_path):
        """压缩后比原文小"""
        path = tmp_path / "forge.gz"
        with gzip.open(path, "wb") as fh:
            fh.write(PAYLOAD)
        assert path.stat().st_size < len(PAYLOAD)

    def test_gzip_magic_number(self, tmp_path):
        """文件头是 gzip 的魔数"""
        path = tmp_path / "forge.gz"
        with gzip.open(path, "wb") as fh:
            fh.write(PAYLOAD)
        assert path.read_bytes()[:2] == b"\x1f\x8b"

    def test_write_text_mode(self, tmp_path):
        """文本模式写入与读出"""
        path = tmp_path / "forge.gz"
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            fh.write("forge 中文")
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            assert fh.read() == "forge 中文"

    def test_read_all(self, tmp_path):
        """一次读完全部内容"""
        path = tmp_path / "forge.gz"
        with gzip.open(path, "wb") as fh:
            fh.write(PAYLOAD)
        with gzip.open(path, "rb") as fh:
            assert fh.read() == PAYLOAD


# ======================== bz2 ========================


class TestBz2:
    """bz2 压缩"""

    def test_compress_decompress(self, tmp_path):
        """往返后内容一致"""
        path = tmp_path / "forge.bz2"
        with bz2.open(path, "wb") as fh:
            fh.write(PAYLOAD)
        with bz2.open(path, "rb") as fh:
            assert fh.read() == PAYLOAD

    def test_magic_number(self, tmp_path):
        """文件头是 bz2 的魔数"""
        path = tmp_path / "forge.bz2"
        with bz2.open(path, "wb") as fh:
            fh.write(PAYLOAD)
        assert path.read_bytes()[:3] == b"BZh"

    def test_compress_function(self):
        """直接压缩得到字节串"""
        data = bz2.compress(PAYLOAD)
        assert bz2.decompress(data) == PAYLOAD

    def test_decompress_invalid(self):
        """非法数据报错"""
        with pytest.raises(Exception):
            bz2.decompress(b"not bz2 data")

    def test_compresslevel(self):
        """压缩级别可调"""
        low = bz2.compress(PAYLOAD, compresslevel=1)
        high = bz2.compress(PAYLOAD, compresslevel=9)
        assert bz2.decompress(low) == bz2.decompress(high) == PAYLOAD


# ======================== lzma ========================


class TestLzma:
    """lzma 压缩"""

    def test_compress_decompress(self, tmp_path):
        """往返后内容一致"""
        path = tmp_path / "forge.xz"
        with lzma.open(path, "wb") as fh:
            fh.write(PAYLOAD)
        with lzma.open(path, "rb") as fh:
            assert fh.read() == PAYLOAD

    def test_magic_number(self, tmp_path):
        """文件头是 xz 的魔数"""
        path = tmp_path / "forge.xz"
        with lzma.open(path, "wb") as fh:
            fh.write(PAYLOAD)
        assert path.read_bytes()[:6] == b"\xfd7zXZ\x00"

    def test_compress_function(self):
        """直接压缩得到字节串"""
        data = lzma.compress(PAYLOAD)
        assert lzma.decompress(data) == PAYLOAD

    def test_format_alone(self):
        """别的容器格式也能用"""
        data = lzma.compress(PAYLOAD, format=lzma.FORMAT_ALONE)
        assert lzma.decompress(data) == PAYLOAD

    def test_decompress_invalid(self):
        """非法数据报错"""
        with pytest.raises(Exception):
            lzma.decompress(b"not lzma data")


# ======================== fractions ========================


class TestFractions:
    """分数运算"""

    def test_add(self):
        """分数相加"""
        assert fractions.Fraction(1, 2) + fractions.Fraction(1, 3) == fractions.Fraction(5, 6)

    def test_subtract(self):
        """分数相减"""
        assert fractions.Fraction(1, 2) - fractions.Fraction(1, 3) == fractions.Fraction(1, 6)

    def test_multiply(self):
        """分数相乘"""
        assert fractions.Fraction(2, 3) * fractions.Fraction(3, 4) == fractions.Fraction(1, 2)

    def test_divide(self):
        """分数相除"""
        assert fractions.Fraction(1, 2) / fractions.Fraction(1, 4) == fractions.Fraction(2, 1)

    def test_from_decimal_and_float(self):
        """能从小数与浮点构造"""
        assert fractions.Fraction("0.5") == fractions.Fraction(1, 2)
        assert fractions.Fraction(0.25) == fractions.Fraction(1, 4)

    def test_normalize(self):
        """约分后规范表示"""
        assert fractions.Fraction(2, 4) == fractions.Fraction(1, 2)
        assert fractions.Fraction(2, 4).numerator == 1
        assert fractions.Fraction(2, 4).denominator == 2

    def test_limit_denominator(self):
        """能逼近到指定分母"""
        value = fractions.Fraction(0.3333).limit_denominator(6)
        assert value.denominator <= 6

    def test_to_float(self):
        """能转成浮点"""
        assert float(fractions.Fraction(1, 4)) == 0.25

    def test_equality_with_int(self):
        """与整数比较"""
        assert fractions.Fraction(4, 2) == 2

    def test_zero_division(self):
        """除以零报错"""
        with pytest.raises(ZeroDivisionError):
            fractions.Fraction(1, 2) / fractions.Fraction(0, 1)


# ======================== html.entities ========================


class TestHtmlEntities:
    """HTML 实体"""

    def test_name2codepoint(self):
        """实体名转码位"""
        assert html.entities.name2codepoint["amp"] == 38
        assert html.entities.name2codepoint["lt"] == 60

    def test_codepoint2name(self):
        """码位转实体名"""
        assert html.entities.codepoint2name[38] == "amp"

    def test_html5_contains_amp(self):
        """HTML5 实体表里有常见实体"""
        assert "amp" in html.entities.html5
        assert "lt" in html.entities.html5
        assert "gt" in html.entities.html5

    def test_html5_mapping_structure(self):
        """HTML5 实体表是名字到字符的映射"""
        assert html.entities.html5["amp"] == "&"

    def test_unknown_name(self):
        """查不到的名字会报错"""
        with pytest.raises(KeyError):
            html.entities.name2codepoint["no_such_entity_forge"]

    def test_codepoint2name_unknown(self):
        """查不到的码位会报错"""
        with pytest.raises(KeyError):
            html.entities.codepoint2name[0x10FFFD]


# ======================== shlex ========================


class TestShlex:
    """命令行切分"""

    def test_split_simple(self):
        """按空白切分"""
        assert shlex.split("forge one two") == ["forge", "one", "two"]

    def test_split_quotes(self):
        """引号里的内容不被切开"""
        assert shlex.split('forge "one two"') == ["forge", "one two"]

    def test_split_single_quotes(self):
        """单引号同样有效"""
        assert shlex.split("forge 'one two'") == ["forge", "one two"]

    def test_split_escaped(self):
        """转义字符被处理"""
        assert shlex.split(r"forge one\ two") == ["forge", "one two"]

    def test_split_with_comments(self):
        """注释能被去掉"""
        assert shlex.split("forge one # comment", comments=True) == ["forge", "one"]

    def test_split_posix(self):
        """位置参数模式可用"""
        lexer = shlex.shlex("forge one two", posix=True)
        assert list(lexer) == ["forge", "one", "two"]

    def test_shlex_punctuation_chars(self):
        """标点字符会被单独分出来"""
        lexer = shlex.shlex("forge:one", punctuation_chars=":")
        lexer.whitespace_split = True
        assert list(lexer) == ["forge", ":", "one"]

    def test_quote(self):
        """能按 shell 规则加引号"""
        assert shlex.quote("forge one") == "'forge one'"
        assert shlex.quote("forge") == "forge"
