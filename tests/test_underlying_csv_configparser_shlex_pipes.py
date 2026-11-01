# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`csv` + `configparser` + `shlex` + `pipes` 真底层测试。

覆盖文本解析与 shell 引用模块:
  - `csv.reader` 真按 dialect 拆 field,`csv.DictReader` 拿 header
  - `csv.Sniffer.has_header` 真嗅 sample 文本判有无 header
  - `configparser.ConfigParser` 真读 INI 字符串,`getint/getfloat` 类型转换
  - `configparser.RawConfigParser.optionxform` 真保留大小写
  - `shlex.split('a "b c" d')` 真去引号返 `['a', 'b c', 'd']`
  - `shlex.quote('hello world')` 真返 `'hello world'`
  - `pipes.quote` 真用兼容 `sh` 规则的引号
"""
import configparser
import csv
import io
# pipes 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        import pipes
except ImportError:
    pipes = None
import shlex

import pytest


# -- csv ----------------------------------------------------------------------

# 这些模块在 Python 3.13 起被移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(pipes is None, reason="pipes 模块在 Python 3.13 起被移除")


class TestCsv:
    def test_reader_split_quoted_field(self):
        """`csv.reader` 真按 dialect 拆引号字段,`"hello, world"` 不被切。"""
        text = 'a,"hello, world",c\n'
        rows = list(csv.reader(io.StringIO(text)))
        assert rows == [["a", "hello, world", "c"]], (
            f"应被解析为 1 行 3 列,实际 {rows!r}"
        )

    def test_dict_reader_uses_header(self):
        """`csv.DictReader` 真把首行当 header,后续行映射为 dict。"""
        text = "name,age\nalice,30\nbob,25\n"
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        assert rows[0] == {"name": "alice", "age": "30"}
        assert rows[1] == {"name": "bob", "age": "25"}

    def test_sniffer_has_header(self):
        """`csv.Sniffer.has_header` 真嗅 sample 文本。"""
        sample = "name,age\nalice,30\nbob,25\n"
        has_header = csv.Sniffer().has_header(sample)
        assert has_header is True
        no_header = csv.Sniffer().has_header("alice,30\nbob,25\n")
        assert no_header is False

    def test_writer_round_trip(self):
        """`csv.writer` 真把列表写为 CSV 格式,再 reader 拿回。"""
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["a,b", 1, "c"])
        w.writerow(["plain", 2, 3])
        text = buf.getvalue()
        rows = list(csv.reader(io.StringIO(text)))
        assert rows[0] == ["a,b", "1", "c"], f"应被 quote 的 a,b 解析回 'a,b',实际 {rows[0]!r}"
        assert rows[1] == ["plain", "2", "3"]


# -- configparser -------------------------------------------------------------

class TestConfigParser:
    def test_read_string_and_getint(self):
        """`ConfigParser` 真读 INI 字符串,`getint` 类型转换。"""
        cp = configparser.ConfigParser()
        cp.read_string("[s]\nport = 8080\nname = forge\n")
        assert cp.getint("s", "port") == 8080
        assert cp.get("s", "name") == "forge"

    def test_optionxform_preserves_case(self):
        """`RawConfigParser.optionxform = str` 真保留大小写。"""
        cp = configparser.RawConfigParser()
        cp.optionxform = str  # 不强制小写
        cp["s"] = {"MixedCase": "1", "ALLCAPS": "2"}
        assert cp.get("s", "MixedCase") == "1", (
            "optionxform=str 应保留 MixedCase 大小写"
        )
        assert cp.get("s", "ALLCAPS") == "2"

    def test_getfloat_and_getboolean(self):
        """`getfloat` 与 `getboolean` 真转换类型。"""
        cp = configparser.ConfigParser()
        cp.read_string("[s]\nratio = 1.5\nenabled = true\n")
        assert cp.getfloat("s", "ratio") == 1.5
        assert cp.getboolean("s", "enabled") is True


# -- shlex --------------------------------------------------------------------

class TestShlex:
    def test_split_unquotes_field(self):
        """`shlex.split('a "b c" d')` 真去引号,`b c` 作为单 token。"""
        tokens = shlex.split('a "b c" d')
        assert tokens == ["a", "b c", "d"], f"实际 {tokens!r}"

    def test_quote_wraps_value(self):
        """`shlex.quote('hello world')` 真用引号包空格的字符串,round-trip 还原。"""
        q = shlex.quote("hello world")
        # quote 后应被单/双引号包裹
        assert (q.startswith("'") and q.endswith("'")) or (q.startswith('"') and q.endswith('"')), (
            f"quote 后应被引号包裹,实际 {q!r}"
        )
        # round-trip: shlex.split(quote) == 原始
        assert shlex.split(q) == ["hello world"]

    def test_shlex_preserves_comments_with_posix(self):
        """`shlex(posix=True)` 真把 `#` 后的视为注释并跳过。"""
        lexer = shlex.shlex(io.StringIO("alpha beta # gamma"), posix=True)
        tokens = list(lexer)
        assert tokens == ["alpha", "beta"], f"实际 {tokens!r}"


# -- pipes --------------------------------------------------------------------

class TestPipes:
    def test_quote_wraps_unsafe_chars(self):
        """`pipes.quote` 真用兼容 sh 规则引号包裹含 shell 特殊字符的串。"""
        q = pipes.quote("hello world;rm -rf /")
        # 应至少含引号字符
        assert "'" in q or '"' in q, f"quote 应加引号,实际 {q!r}"
        # 原始 token 在 quote 内可还原
        inner = q.strip("'\"")
        assert "hello world" in inner, f"quote 内应含原 token,实际 {q!r}"
