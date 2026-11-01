# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""glob 模块的真实行为验证

覆盖模块:glob(标准库)

真实测试项(共 18 个):
   1. 通配符 * 收集当前层的全部 .txt 文件
   2. 通配符 * 不跨越目录分隔符
   3. 通配符 ? 精确对应一个字符
   4. 字符数不足时 ? 模式匹配为空
   5. 字符组 [ab] 只接受列出的字符
   6. 字符组区间 [b-c] 按范围取舍
   7. 无命中时 glob 返回空列表
   8. recursive=True 时 ** 递归收集子目录文件
   9. recursive=False 时 ** 只展开一层
  10. root_dir 让相对模式以指定目录为基准
  11. iglob 与 glob 命中同一批文件
  12. iglob 返回迭代器而不是列表
  13. escape 让模式只命中字面量文件名
  14. escape 不改动不含通配符的名字
  15. has_magic 识别出模式里的通配符
  16. has_magic 对普通路径返回 False
  17. include_hidden=True 把隐藏文件收进结果
  18. glob.translate(3.13+)把模式译成可匹配的正则

所有匹配都建立在 tmp_path 下真实写入的目录树上,断言的是真实文件名集合。
"""

import glob
import re
from pathlib import Path

import pytest


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """在 tmp_path 下建出真实的目录树,返回树根路径。

    树结构:
        alpha.txt beta.txt gamma.log q.txt .hidden.txt br1.txt br[1].txt
        data/x1.csv data/x2.csv data/notes.md
        sub/delta.txt sub/epsilon.log sub/nested/zeta.txt
    """
    (tmp_path / "alpha.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "beta.txt").write_text("beta", encoding="utf-8")
    (tmp_path / "gamma.log").write_text("gamma", encoding="utf-8")
    (tmp_path / "q.txt").write_text("q", encoding="utf-8")
    (tmp_path / ".hidden.txt").write_text("hidden", encoding="utf-8")
    (tmp_path / "br1.txt").write_text("br1", encoding="utf-8")
    (tmp_path / "br[1].txt").write_text("br-bracket", encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()
    (data / "x1.csv").write_text("1", encoding="utf-8")
    (data / "x2.csv").write_text("2", encoding="utf-8")
    (data / "notes.md").write_text("notes", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "delta.txt").write_text("delta", encoding="utf-8")
    (sub / "epsilon.log").write_text("epsilon", encoding="utf-8")
    nested = sub / "nested"
    nested.mkdir()
    (nested / "zeta.txt").write_text("zeta", encoding="utf-8")
    return tmp_path


def _rel(paths: list[str], root: Path) -> list[str]:
    """把绝对路径集合转成相对树根、按字典序排好的字符串列表。"""
    return sorted(str(Path(p).relative_to(root)) for p in paths)


def test_glob_star_collects_expected_file_names(tree: Path) -> None:
    """顶层 *.txt 命中 5 个真实文件,隐藏文件与子目录文件都不在其中。"""
    matched = _rel(glob.glob(str(tree / "*.txt")), tree)
    assert matched == ["alpha.txt", "beta.txt", "br1.txt", "br[1].txt", "q.txt"]
    assert ".hidden.txt" not in matched
    assert "gamma.log" not in matched


def test_glob_star_does_not_cross_directory_boundary(tree: Path) -> None:
    """单层 * 不跨越目录分隔符,结果里没有任何带子目录的路径。"""
    matched = _rel(glob.glob(str(tree / "*.txt")), tree)
    assert "sub/delta.txt" not in matched
    assert "data/x1.csv" not in matched
    assert all("/" not in name for name in matched)
    assert len(matched) == 5


def test_glob_question_mark_matches_exactly_one_character(tree: Path) -> None:
    """? 精确对应一个字符,只有单字符名 q.txt 命中 ?.txt。"""
    assert _rel(glob.glob(str(tree / "?.txt")), tree) == ["q.txt"]


def test_glob_question_mark_pattern_with_wrong_length_matches_nothing(tree: Path) -> None:
    """??.txt 要求前缀恰好两个字符,树里没有这种文件,匹配结果为空列表。"""
    assert glob.glob(str(tree / "??.txt")) == []


def test_glob_character_class_matches_only_listed_prefixes(tree: Path) -> None:
    """字符组 [ab] 只接受列出的字符,命中 alpha/beta/br1/br[1] 四个文件。"""
    matched = _rel(glob.glob(str(tree / "[ab]*.txt")), tree)
    assert matched == ["alpha.txt", "beta.txt", "br1.txt", "br[1].txt"]
    assert "q.txt" not in matched
    assert "gamma.log" not in matched


def test_glob_character_class_range_matches_names_in_range(tree: Path) -> None:
    """区间 [b-c] 以 b 起头,alpha.txt 被排除,剩下三个文件。"""
    matched = _rel(glob.glob(str(tree / "[b-c]*.txt")), tree)
    assert matched == ["beta.txt", "br1.txt", "br[1].txt"]
    assert "alpha.txt" not in matched


def test_glob_returns_empty_list_when_pattern_matches_nothing(tree: Path) -> None:
    """顶层没有 .csv 文件(它们都在 data/ 下),*.csv 的结果是空列表。"""
    assert glob.glob(str(tree / "*.csv")) == []


def test_glob_recursive_double_star_collects_nested_files(tree: Path) -> None:
    """recursive=True 时 ** 递归展开,结果含 sub/delta.txt 与 sub/nested/zeta.txt。"""
    matched = _rel(glob.glob(str(tree / "**/*.txt"), recursive=True), tree)
    assert matched == [
        "alpha.txt",
        "beta.txt",
        "br1.txt",
        "br[1].txt",
        "q.txt",
        "sub/delta.txt",
        "sub/nested/zeta.txt",
    ]


def test_glob_double_star_without_recursive_expands_single_level(tree: Path) -> None:
    """recursive=False 时 ** 只展开一层,仅命中 sub/delta.txt。"""
    matched = _rel(glob.glob(str(tree / "**/*.txt")), tree)
    assert matched == ["sub/delta.txt"]


def test_glob_root_dir_resolves_relative_pattern(tree: Path) -> None:
    """root_dir 指定基准目录,相对模式 *.txt 返回相对路径,*.csv 返回空列表。"""
    assert sorted(glob.glob("*.txt", root_dir=str(tree))) == [
        "alpha.txt",
        "beta.txt",
        "br1.txt",
        "br[1].txt",
        "q.txt",
    ]
    assert glob.glob("*.csv", root_dir=str(tree)) == []


def test_glob_iglob_matches_glob_result_set(tree: Path) -> None:
    """iglob 与 glob 命中同一批真实文件,排序后集合完全一致。"""
    from_glob = sorted(glob.glob(str(tree / "*.txt")))
    from_iglob = sorted(glob.iglob(str(tree / "*.txt")))
    assert from_iglob == from_glob
    assert len(from_iglob) == 5


def test_glob_iglob_returns_iterator_instead_of_list(tree: Path) -> None:
    """iglob 返回的是生成器,取出首个元素后剩余 4 个元素仍可继续迭代。"""
    from_glob = sorted(glob.glob(str(tree / "*.txt")))
    iterator = glob.iglob(str(tree / "*.txt"))
    assert not isinstance(iterator, list)
    assert hasattr(iterator, "__next__")
    first = next(iterator)
    remaining = list(iterator)
    assert first in from_glob
    assert len(remaining) == 4


def test_glob_escape_matches_literal_file_name_only(tree: Path) -> None:
    """escape 后的模式只命中字面量文件 br[1].txt,未转义模式只命中 br1.txt。"""
    literal = glob.glob(glob.escape(str(tree / "br[1].txt")))
    assert _rel(literal, tree) == ["br[1].txt"]
    assert _rel(glob.glob(str(tree / "br[1].txt")), tree) == ["br1.txt"]


def test_glob_escape_keeps_name_without_wildcards_unchanged(tree: Path) -> None:
    """不含通配符的名字经 escape 后逐字符不变,glob 仍能命中该文件。"""
    assert glob.escape("plainname") == "plainname"
    assert glob.glob(glob.escape(str(tree / "q.txt"))) == [str(tree / "q.txt")]


def test_glob_has_magic_detects_wildcard_characters() -> None:
    """has_magic 对含 *、?、[ 的模式一律返回 True。"""
    assert glob.has_magic("*.txt") is True
    assert glob.has_magic("data?.csv") is True
    assert glob.has_magic("[ab]*.txt") is True


def test_glob_has_magic_returns_false_for_plain_path() -> None:
    """has_magic 对不含通配符的普通路径返回 False。"""
    assert glob.has_magic("data/report.txt") is False
    assert glob.has_magic("plainname") is False


def test_glob_include_hidden_adds_dot_files_to_result(tree: Path) -> None:
    """include_hidden=True 时 .hidden.txt 进入结果,默认参数下不出现。"""
    with_hidden = _rel(glob.glob(str(tree / "*.txt"), include_hidden=True), tree)
    without_hidden = _rel(glob.glob(str(tree / "*.txt")), tree)
    assert ".hidden.txt" in with_hidden
    assert ".hidden.txt" not in without_hidden
    assert len(with_hidden) == len(without_hidden) + 1


@pytest.mark.skipif(not hasattr(glob, "translate"), reason="glob.translate 需要 Python 3.13+")
def test_glob_translate_builds_matching_regular_expression() -> None:
    """glob.translate 把通配模式译成正则,命中的名字集合与 .txt 文件一致。"""
    pattern = glob.translate("*.txt")
    names = ("alpha.txt", "beta.txt", "gamma.log", "q.txt")
    matched = {name for name in names if re.match(pattern, name)}
    assert matched == {"alpha.txt", "beta.txt", "q.txt"}
