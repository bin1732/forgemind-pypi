# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`textwrap` 模块的真实行为验证。

覆盖模块:textwrap(标准库)

真实测试项(共 18 个):
   1. `wrap` 按 width 切分段落,每行内容与行数都符合预期
   2. `fill` 把切分后的行用换行拼回一整段文本
   3. `fill` 的 initial_indent / subsequent_indent 落到首行与续行
   4. `shorten` 用占位符替换被截掉的尾部
   5. `shorten` 的结果总长不超 width,占位符长度计入预算
   6. `shorten` 遇到本来就短的文本时原样返回
   7. `dedent` 去掉所有行共有的行首空白
   8. `dedent` 在各行缩进不一致时保持原样
   9. `indent` 给每一行加统一前缀
  10. `indent` 的 predicate 只给命中的行加前缀
  11. `TextWrapper(break_long_words=True)` 把超长单词硬切到 width 内
  12. `TextWrapper(break_long_words=False)` 保留超长单词不切
  13. `TextWrapper(break_on_hyphens=True)` 允许在连字符处断行
  14. `TextWrapper(break_on_hyphens=False)` 不在连字符处断行
  15. `TextWrapper(drop_whitespace=False)` 保留行尾多余空格
  16. `TextWrapper(max_lines=...)` 截断行数并用 placeholder 收尾
  17. `TextWrapper` 的 initial_indent / subsequent_indent 落到首行与续行
  18. `itertools.batched`(3.12+)把换行结果按批重组,内容与原列表一致

所有断言都针对标准库的真实输出,不替换任何标准库对象。
"""

import itertools
import textwrap

import pytest

_HAS_BATCHED = hasattr(itertools, "batched")


class TestTextwrapWrap:
    """`textwrap.wrap` / `textwrap.fill` 的真实输出。"""

    def test_wrap_splits_paragraph_at_width(self):
        """`wrap` 在 width=20 处切分,得到两行且每行长度不超过 20。"""
        text = "alpha beta gamma delta epsilon zeta"
        lines = textwrap.wrap(text, width=20)
        assert lines == ["alpha beta gamma", "delta epsilon zeta"]
        assert all(len(line) <= 20 for line in lines)

    def test_fill_joins_wrapped_lines_with_newline(self):
        """`fill` 把 `wrap` 的结果用换行拼成一个字符串。"""
        text = "alpha beta gamma delta epsilon zeta"
        filled = textwrap.fill(text, width=20)
        assert filled == "alpha beta gamma\ndelta epsilon zeta"
        assert filled.split("\n") == textwrap.wrap(text, width=20)

    def test_fill_applies_initial_and_subsequent_indent(self):
        """`fill` 的 initial_indent 只加在首行,subsequent_indent 加在其余行。"""
        filled = textwrap.fill(
            "one two three four five",
            width=12,
            initial_indent="> ",
            subsequent_indent="| ",
        )
        assert filled == "> one two\n| three four\n| five"
        assert filled.split("\n")[0].startswith("> ")
        assert all(line.startswith("| ") for line in filled.split("\n")[1:])


class TestTextwrapShorten:
    """`textwrap.shorten` 的真实截断行为。"""

    def test_shorten_replaces_tail_with_placeholder(self):
        """`shorten` 把放不下的尾部换成占位符,前面的词保持原样。"""
        text = "alpha beta gamma delta epsilon zeta"
        assert textwrap.shorten(text, width=25) == "alpha beta gamma [...]"

    def test_shorten_respects_placeholder_budget(self):
        """`shorten` 的结果总长不超 width,占位符自身长度计入预算。"""
        text = "alpha beta gamma delta epsilon zeta"
        result = textwrap.shorten(text, width=20, placeholder=" ...")
        assert len(result) == 20
        assert result.endswith(" ...")
        assert result == "alpha beta gamma ..."

    def test_shorten_keeps_text_when_it_fits(self):
        """`shorten` 在文本本身不超 width 时原样返回,不加占位符。"""
        text = "ab cd ef"
        assert textwrap.shorten(text, width=8, placeholder=" ...") == text


class TestTextwrapDedentIndent:
    """`textwrap.dedent` / `textwrap.indent` 的真实缩进行为。"""

    def test_dedent_removes_common_indent(self):
        """`dedent` 去掉所有行共有的四个空格,行内其他空白保留。"""
        assert textwrap.dedent("    a\n    b\n") == "a\nb\n"

    def test_dedent_keeps_text_when_indent_inconsistent(self):
        """`dedent` 在各行缩进不一致时找不到公共前缀,原样返回。"""
        source = "foo\n    bar\n"
        assert textwrap.dedent(source) == source

    def test_indent_prefixes_all_lines(self):
        """`indent` 给每一行都加上前缀,行数不变。"""
        assert textwrap.indent("a\nb", "  ") == "  a\n  b"

    def test_indent_predicate_selects_lines(self):
        """`indent` 的 predicate 返回 False 的行不加前缀。"""
        result = textwrap.indent("a\nb\n", "> ", lambda line: "b" in line)
        assert result == "a\n> b\n"


class TestTextWrapperOptions:
    """`textwrap.TextWrapper` 的各个开关的真实效果。"""

    def test_textwrapper_break_long_words_true_splits_token(self):
        """`break_long_words=True` 把 26 个字符的单词硬切成 15 + 11。"""
        wrapper = textwrap.TextWrapper(width=15, break_long_words=True)
        assert wrapper.wrap("a" * 26) == ["a" * 15, "a" * 11]

    def test_textwrapper_break_long_words_false_keeps_token(self):
        """`break_long_words=False` 时 15 个字符的单词整行保留,不被切碎。"""
        wrapper = textwrap.TextWrapper(width=10, break_long_words=False)
        assert wrapper.wrap("abcdefghijklmno") == ["abcdefghijklmno"]

    def test_textwrapper_break_on_hyphens_true_splits_at_hyphen(self):
        """`break_on_hyphens=True` 时 "aaaa-bbbb" 在连字符处断成 "aaaa-" 与 "bbbb"。"""
        wrapper = textwrap.TextWrapper(width=8, break_on_hyphens=True)
        assert wrapper.wrap("aaaa-bbbb ccc") == ["aaaa-", "bbbb ccc"]

    def test_textwrapper_break_on_hyphens_false_keeps_hyphenated_word(self):
        """`break_on_hyphens=False` 时连字符不作为断点,单词整体超宽仍按 width 切。"""
        wrapper = textwrap.TextWrapper(width=8, break_on_hyphens=False)
        assert wrapper.wrap("aaaa-bbbb ccc") == ["aaaa-bbb", "b ccc"]

    def test_textwrapper_drop_whitespace_false_keeps_padding(self):
        """`drop_whitespace=False` 时行尾多余空格被保留。"""
        wrapper = textwrap.TextWrapper(width=10, drop_whitespace=False)
        assert wrapper.wrap("aa   bb   cc") == ["aa   bb   ", "cc"]

    def test_textwrapper_max_lines_truncates_with_placeholder(self):
        """`max_lines=2` 只保留两行,末行用 placeholder 收尾。"""
        wrapper = textwrap.TextWrapper(width=10, max_lines=2, placeholder=" ...")
        assert wrapper.wrap("aa bb cc dd ee ff gg hh") == ["aa bb cc", "dd ee ..."]

    def test_textwrapper_initial_and_subsequent_indent(self):
        """`TextWrapper` 的 initial_indent 只加在首行,subsequent_indent 加在其余行。"""
        wrapper = textwrap.TextWrapper(width=12, initial_indent="* ", subsequent_indent="  ")
        assert wrapper.wrap("one two three four") == ["* one two", "  three four"]


@pytest.mark.skipif(not _HAS_BATCHED, reason="itertools.batched 需要 Python 3.12+")
def test_batched_regroups_wrapped_lines():
    """`itertools.batched`(3.12+)把 6 行换行结果按 4 个一批重组,拼回后与原列表一致。"""
    text = " ".join(f"w{index}" for index in range(18))
    lines = textwrap.wrap(text, width=12)
    assert lines == [
        "w0 w1 w2 w3",
        "w4 w5 w6 w7",
        "w8 w9 w10",
        "w11 w12 w13",
        "w14 w15 w16",
        "w17",
    ]
    batches = [list(batch) for batch in itertools.batched(lines, 4)]
    assert [len(batch) for batch in batches] == [4, 2]
    assert [line for batch in batches for line in batch] == lines
