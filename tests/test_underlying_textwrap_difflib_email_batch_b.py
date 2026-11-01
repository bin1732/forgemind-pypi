# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`difflib` 模块的真实行为验证。

覆盖模块:difflib(标准库)

真实测试项(共 18 个):
   1. `SequenceMatcher.ratio` 给出两段文本的相似比例
   2. `ratio` 对完全相同的两段文本返回 1.0
   3. `real_quick_ratio` / `quick_ratio` / `ratio` 构成逐级收紧的上下界
   4. `get_matching_blocks` 给出公共片段并以空块收尾
   5. `get_opcodes` 描述 replace 区段
   6. `get_opcodes` 描述 insert 与 delete 区段
   7. `get_grouped_opcodes` 把相邻改动并入同一组
   8. `set_seq2` 之后匹配块按新序列重算
   9. `unified_diff` 输出真实的头部与 @@ 区段
  10. `unified_diff(lineterm="")` 去掉每行末尾的换行
  11. `context_diff` 用 ! 标出被改动的行
  12. `ndiff` 标出新增行与被删行
  13. `ndiff` 对行内改动给出 ? 提示行
  14. `restore` 能从 ndiff 结果还原出目标文本
  15. `get_close_matches` 按相似度排出候选
  16. `IS_LINE_JUNK` / `IS_CHARACTER_JUNK` 判定空白行与空白字符
  17. `HtmlDiff.make_table` 生成同时含两侧内容的 HTML 表格
  18. `itertools.batched`(3.13+ 的 strict 参数)对真实 opcode 分组并拒绝残缺批

所有断言都针对 difflib 的真实输出,不替换任何标准库对象。
"""

import difflib
import inspect
import itertools

import pytest

_BATCHED_HAS_STRICT = hasattr(itertools, "batched") and "strict" in inspect.signature(
    itertools.batched,
).parameters


class TestSequenceMatcherRatios:
    """`SequenceMatcher` 的三个相似度指标。"""

    def test_ratio_of_strings_with_shared_prefix(self):
        """`ratio` 对 "abcdef" 与 "abcdxy" 给出 2/3 的相似度。"""
        matcher = difflib.SequenceMatcher(None, "abcdef", "abcdxy")
        assert matcher.ratio() == 2 / 3
        assert matcher.ratio() == 0.6666666666666666

    def test_ratio_of_identical_strings_is_one(self):
        """`ratio` 对两段完全相同的文本返回 1.0。"""
        assert difflib.SequenceMatcher(None, "same text", "same text").ratio() == 1.0

    def test_quick_ratio_and_real_quick_ratio_bracket_ratio(self):
        """`real_quick_ratio` 不小于 `quick_ratio`,`quick_ratio` 不小于 `ratio`。"""
        left = "x" * 40 + "abcdefgh"
        right = "x" * 40 + "abcdxxxx"
        matcher = difflib.SequenceMatcher(None, left, right)
        assert matcher.real_quick_ratio() == 1.0
        assert matcher.quick_ratio() == 0.9166666666666666
        assert matcher.real_quick_ratio() >= matcher.quick_ratio() >= matcher.ratio()


class TestSequenceMatcherBlocks:
    """`SequenceMatcher` 的匹配块与操作码。"""

    def test_get_matching_blocks_reports_common_runs_and_sentinel(self):
        """`get_matching_blocks` 给出公共片段,并以 size 为 0 的空块收尾。"""
        matcher = difflib.SequenceMatcher(None, [1, 2, 3, 4], [1, 2, 9, 4])
        blocks = matcher.get_matching_blocks()
        assert [(block.a, block.b, block.size) for block in blocks] == [
            (0, 0, 2),
            (3, 3, 1),
            (4, 4, 0),
        ]

    def test_get_opcodes_describes_replace_run(self):
        """`get_opcodes` 把不一致的区间报成 replace。"""
        matcher = difflib.SequenceMatcher(None, "abcdef", "abcdxy")
        assert matcher.get_opcodes() == [
            ("equal", 0, 4, 0, 4),
            ("replace", 4, 6, 4, 6),
        ]

    def test_get_opcodes_describes_insert_and_delete(self):
        """`get_opcodes` 分别报出 insert 与 delete 区段。"""
        insert = difflib.SequenceMatcher(None, "abcd", "abXcd").get_opcodes()
        assert insert == [
            ("equal", 0, 2, 0, 2),
            ("insert", 2, 2, 2, 3),
            ("equal", 2, 4, 3, 5),
        ]
        delete = difflib.SequenceMatcher(None, "abXcd", "abcd").get_opcodes()
        assert delete == [
            ("equal", 0, 2, 0, 2),
            ("delete", 2, 3, 2, 2),
            ("equal", 3, 5, 2, 4),
        ]

    def test_get_grouped_opcodes_merges_nearby_changes(self):
        """`get_grouped_opcodes` 把两处相距不远的改动并进同一组。"""
        left = [f"l{index}\n" for index in range(1, 11)]
        right = [f"l{index}\n" for index in range(1, 11)]
        right[2] = "X\n"
        right[6] = "Y\n"
        matcher = difflib.SequenceMatcher(None, left, right)
        groups = [list(group) for group in matcher.get_grouped_opcodes(3)]
        assert len(groups) == 1
        assert groups[0] == [
            ("equal", 0, 2, 0, 2),
            ("replace", 2, 3, 2, 3),
            ("equal", 3, 6, 3, 6),
            ("replace", 6, 7, 6, 7),
            ("equal", 7, 10, 7, 10),
        ]

    def test_set_seq2_recomputes_matching_blocks(self):
        """`set_seq2` 换掉比较对象后,匹配块按新序列重新计算。"""
        matcher = difflib.SequenceMatcher(None, [1, 2, 3, 4], [1, 2, 9, 4])
        assert matcher.get_matching_blocks()[-1].size == 0
        matcher.set_seq2([1, 2, 3, 4, 5])
        assert [(block.a, block.b, block.size) for block in matcher.get_matching_blocks()] == [
            (0, 0, 4),
            (4, 5, 0),
        ]


class TestDiffGenerators:
    """`unified_diff` / `context_diff` / `ndiff` 的真实输出。"""

    def test_unified_diff_emits_header_and_hunk(self):
        """`unified_diff` 输出 --- / +++ 头部与 @@ 区段,改动行带 - 与 + 前缀。"""
        left = [f"line {index}\n" for index in range(1, 6)]
        right = [f"line {index}\n" for index in range(1, 6)]
        right[2] = "changed\n"
        diff = list(difflib.unified_diff(left, right, fromfile="old", tofile="new"))
        assert diff[0] == "--- old\n"
        assert diff[1] == "+++ new\n"
        assert diff[2] == "@@ -1,5 +1,5 @@\n"
        assert "-line 3\n" in diff
        assert "+changed\n" in diff

    def test_unified_diff_lineterm_empty_drops_trailing_newline(self):
        """`unified_diff(lineterm="")` 时头部与区段行不带换行,内容行仍带自身换行。"""
        diff = list(
            difflib.unified_diff(["a\n", "b\n"], ["a\n", "c\n"], lineterm=""),
        )
        assert diff == [
            "--- ",
            "+++ ",
            "@@ -1,2 +1,2 @@",
            " a\n",
            "-b\n",
            "+c\n",
        ]

    def test_context_diff_marks_changed_lines(self):
        """`context_diff` 用 ! 前缀标出被改动的行,上下文行用空格前缀。"""
        diff = list(
            difflib.context_diff(
                ["a\n", "b\n", "c\n", "d\n"],
                ["a\n", "b\n", "X\n", "d\n"],
                n=1,
            ),
        )
        assert "*** 2,4 ****\n" in diff
        assert "! c\n" in diff
        assert "--- 2,4 ----\n" in diff
        assert "! X\n" in diff
        assert "  b\n" in diff

    def test_ndiff_marks_added_and_removed_lines(self):
        """`ndiff` 用 - 标出被删行、用 + 标出新增行、未变行用两个空格。"""
        result = list(difflib.ndiff(["one\n", "two\n", "three\n"], ["one\n", "TWO\n", "three\n"]))
        assert result == [
            "  one\n",
            "- two\n",
            "+ TWO\n",
            "  three\n",
        ]

    def test_ndiff_marks_intraline_change(self):
        """`ndiff` 对行内改动额外给出 ? 提示行,指出差异所在列。"""
        result = list(difflib.ndiff(["abcde"], ["abXde"]))
        assert result == ["- abcde", "?   ^\n", "+ abXde", "?   ^\n"]

    def test_restore_rebuilds_original_from_ndiff(self):
        """`restore(ndiff 结果, 2)` 还原出第二份文本。"""
        source = ["one\n", "two\n", "three\n"]
        target = ["one\n", "TWO\n", "three\n"]
        ndiff_result = list(difflib.ndiff(source, target))
        assert list(difflib.restore(ndiff_result, 2)) == target


class TestDiffHelpers:
    """`difflib` 的辅助函数与判定谓词。"""

    def test_get_close_matches_ranks_similar_words(self):
        """`get_close_matches` 按相似度从高到低返回候选,低于 cutoff 的被排除。"""
        matches = difflib.get_close_matches("appel", ["ape", "apple", "peach", "puppy"])
        assert matches == ["apple", "ape"]
        assert difflib.get_close_matches("appel", ["peach", "puppy"], n=3, cutoff=0.6) == []

    def test_junk_predicates_identify_blank_and_space(self):
        """`IS_LINE_JUNK` 把纯空白行判为垃圾行,`IS_CHARACTER_JUNK` 把空格判为垃圾字符。"""
        assert difflib.IS_LINE_JUNK("  \n") is True
        assert difflib.IS_LINE_JUNK("x\n") is False
        assert difflib.IS_CHARACTER_JUNK(" ") is True
        assert difflib.IS_CHARACTER_JUNK("x") is False

    def test_html_diff_table_contains_both_columns(self):
        """`HtmlDiff.make_table` 生成一张同时含两侧内容的 HTML 表格。"""
        table = difflib.HtmlDiff().make_table(["a\n", "b\n"], ["a\n", "c\n"])
        assert "<table" in table
        # 差异块的编号随版本变化,断言表格结构与两侧内容即可
        assert 'id="difflib_chg_to' in table
        assert table.count("<tr") == 2
        assert "b" in table
        assert "c" in table


@pytest.mark.skipif(
    not _BATCHED_HAS_STRICT,
    reason="itertools.batched 的 strict 参数需要 Python 3.13+",
)
def test_batched_groups_opcodes_with_strict():
    """`itertools.batched`(3.13+ 的 strict)对真实 opcode 分组,残缺批会抛 ValueError。"""
    matcher = difflib.SequenceMatcher(None, "abcdef", "abcdxy")
    opcodes = matcher.get_opcodes()
    batches = [list(batch) for batch in itertools.batched(opcodes, 1)]
    assert batches == [[("equal", 0, 4, 0, 4)], [("replace", 4, 6, 4, 6)]]
    with pytest.raises(ValueError, match="incomplete batch"):
        list(itertools.batched(opcodes, 3, strict=True))
