# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""fnmatch 模块的真实行为验证

覆盖模块:fnmatch(标准库)

真实测试项(共 17 个):
   1. 通配符 * 匹配任意后缀
   2. 通配符 * 匹配空串而 ? 不匹配
   3. fnmatch 的 * 不把路径分隔符当特殊字符
   4. 通配符 ? 精确对应一个字符
   5. fnmatchcase 严格区分大小写
   6. fnmatch 先按 os.path.normcase 归一名字与模式
   7. 字符组 [ab] 只接受列出的字符
   8. 字符组只占一个字符位置
   9. 取反写法是 [!ab]
  10. 字符组里的 ^ 是普通字符而非取反
  11. 字面量方括号要写成 [[] 的形式
  12. filter 只返回命中的名字
  13. filter 保持输入顺序
  14. 无命中时 filter 返回空列表
  15. translate 生成的正则命中 .txt 不命中 .log
  16. translate 把正则元字符转义
  17. translate 的星号能匹配含换行的字符串

断言全部落在具体的 True/False 与具体字符串上,不依赖任何替身。
"""

import fnmatch
import glob
import os
import re
from pathlib import Path


def test_fnmatch_star_matches_any_suffix() -> None:
    """* 匹配任意后缀,*.txt 命中 readme.txt,不命中 readme.log。"""
    assert fnmatch.fnmatch("readme.txt", "*.txt") is True
    assert fnmatch.fnmatch("readme.log", "*.txt") is False


def test_fnmatch_star_matches_empty_remainder() -> None:
    """模式 * 匹配空串,模式 ? 不匹配空串。"""
    assert fnmatch.fnmatchcase("", "*") is True
    assert fnmatch.fnmatchcase("", "?") is False


def test_fnmatch_star_matches_across_path_separator(tmp_path: Path) -> None:
    """fnmatch 不把 / 当特殊字符,*.txt 命中 a/b.txt,而 glob 的 * 不下钻进子目录。"""
    nested = tmp_path / "a"
    nested.mkdir()
    (nested / "b.txt").write_text("b", encoding="utf-8")
    assert fnmatch.fnmatchcase("a/b.txt", "*.txt") is True
    assert glob.glob(str(tmp_path / "*.txt")) == []
    assert glob.glob(str(nested / "*.txt")) == [str(nested / "b.txt")]


def test_fnmatch_question_mark_matches_exactly_one_character() -> None:
    """? 精确对应一个字符,a.txt 命中 ?.txt 与 a?txt,abc.txt 不命中 a?txt。"""
    assert fnmatch.fnmatchcase("a.txt", "?.txt") is True
    assert fnmatch.fnmatchcase("a.txt", "a?txt") is True
    assert fnmatch.fnmatchcase("abc.txt", "a?txt") is False


def test_fnmatchcase_is_case_sensitive() -> None:
    """fnmatchcase 不做大小写归一,README.TXT 不匹配 *.txt。"""
    assert fnmatch.fnmatchcase("README.TXT", "*.txt") is False
    assert fnmatch.fnmatchcase("readme.txt", "*.txt") is True


def test_fnmatch_applies_normcase_to_name_and_pattern() -> None:
    """fnmatch 先按 os.path.normcase 归一名字与模式,结果与 normcase 规则一致。"""
    name, pattern = "README.TXT", "*.txt"
    expected = fnmatch.fnmatchcase(os.path.normcase(name), os.path.normcase(pattern))
    assert fnmatch.fnmatch(name, pattern) is expected
    if os.path.normcase("A") == os.path.normcase("a"):
        assert fnmatch.fnmatch("README.TXT", "*.txt") is True
    else:
        assert fnmatch.fnmatch("README.TXT", "*.txt") is False


def test_fnmatch_character_class_matches_listed_characters() -> None:
    """字符组 [ab] 命中 a.txt 与 b.txt,不命中 c.txt。"""
    assert fnmatch.fnmatchcase("a.txt", "[ab].txt") is True
    assert fnmatch.fnmatchcase("b.txt", "[ab].txt") is True
    assert fnmatch.fnmatchcase("c.txt", "[ab].txt") is False


def test_fnmatch_character_class_matches_exactly_one_character() -> None:
    """字符组只占一个字符位置,aab 命中 a[ab]b,少一个字符的 ab 不命中。"""
    assert fnmatch.fnmatchcase("aab", "a[ab]b") is True
    assert fnmatch.fnmatchcase("abb", "a[ab]b") is True
    assert fnmatch.fnmatchcase("ab", "a[ab]b") is False


def test_fnmatch_character_class_negation_uses_exclamation_mark() -> None:
    """取反写法是 [!ab],c.txt 命中,a.txt 不命中。"""
    assert fnmatch.fnmatchcase("c.txt", "[!ab].txt") is True
    assert fnmatch.fnmatchcase("a.txt", "[!ab].txt") is False


def test_fnmatch_caret_inside_class_is_not_negation() -> None:
    """[^ab] 里的 ^ 是普通字符,集合是 {^, a, b},c.txt 不命中而 a.txt 命中。"""
    assert fnmatch.fnmatchcase("c.txt", "[^ab].txt") is False
    assert fnmatch.fnmatchcase("a.txt", "[^ab].txt") is True


def test_fnmatch_literal_bracket_needs_bracket_escape_syntax() -> None:
    """fnmatch 不认反斜杠转义,字面量方括号要写成 a[[]1].txt。"""
    assert fnmatch.fnmatchcase("a[1].txt", "a[[]1].txt") is True
    assert fnmatch.fnmatchcase("a[1].txt", "a\\[1\\].txt") is False


def test_fnmatch_filter_returns_matching_names() -> None:
    """filter 只返回命中的名字,*.txt 在混合列表里选出四个 .txt 文件。"""
    names = ["a.txt", "b.txt", "c.log", "d.txt", "A.TXT", "e.txt"]
    assert fnmatch.filter(names, "*.txt") == ["a.txt", "b.txt", "d.txt", "e.txt"]


def test_fnmatch_filter_preserves_input_order() -> None:
    """filter 保持输入顺序,不做排序。"""
    names = ["z.txt", "a.txt", "m.txt"]
    assert fnmatch.filter(names, "*.txt") == ["z.txt", "a.txt", "m.txt"]


def test_fnmatch_filter_returns_empty_list_when_nothing_matches() -> None:
    """没有命中时 filter 返回空列表,不是 None。"""
    result = fnmatch.filter(["a.txt", "b.log"], "*.csv")
    assert result == []
    assert isinstance(result, list)


def test_fnmatch_translate_matches_expected_names() -> None:
    """translate 生成的正则命中 .txt 名字,不命中 .log 名字。"""
    pattern = fnmatch.translate("*.txt")
    names = ("readme.txt", "readme.log", "notes.md")
    matched = {name for name in names if re.match(pattern, name)}
    assert matched == {"readme.txt"}


def test_fnmatch_translate_escapes_regex_metacharacters() -> None:
    """translate 把 . 转义,模式 a.txt 只命中 a.txt,不命中 axtxt。"""
    pattern = fnmatch.translate("a.txt")
    names = ("a.txt", "axtxt", "atxt")
    matched = {name for name in names if re.match(pattern, name)}
    assert matched == {"a.txt"}


def test_fnmatch_translate_star_matches_across_newline() -> None:
    """translate 输出带 (?s:) 修饰,星号把含换行的整串都吃掉。"""
    matched = re.match(fnmatch.translate("*"), "a\nb")
    assert matched is not None
    assert matched.group(0) == "a\nb"
