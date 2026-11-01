# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`difflib` + `string` (Template) + `secrets` 真底层测试。

覆盖文本对比与安全随机模块:
  - `difflib.SequenceMatcher` 真算两个字符串的 `get_opcodes()` 序列,
    验证 `equal/replace/delete/insert` 标签
  - `difflib.unified_diff` 真输出包含 `---` / `+++` 头与 `-` / `+` 行
  - `string.Template` 真用 `safe_substitute` 处理缺字段不抛 KeyError
  - `secrets.token_hex(16)` 返 32 hex 字符 / `secrets.compare_digest`
    对相同串返 True,不同串返 False (恒定时间)
  - `secrets.choice(seq)` 真从序列抽一个元素出来,跑 1000 次覆盖 ≥ 80% 唯一值
"""
import difflib
import secrets
import string

import pytest


# -- difflib ------------------------------------------------------------------

class TestDifflib:
    def test_sequence_matcher_get_opcodes(self):
        """`SequenceMatcher.get_opcodes` 真返回操作序列。

        比较 'abcde' vs 'abxde',应至少有一个 `replace` 标记 c→x。
        """
        sm = difflib.SequenceMatcher(a="abcde", b="abxde")
        ops = sm.get_opcodes()
        tags = [op[0] for op in ops]
        assert "equal" in tags
        assert "replace" in tags, (
            f"应至少有 1 个 replace 标签,实际 tags: {tags}"
        )

    def test_unified_diff_output(self):
        """`difflib.unified_diff` 真输出含 `---` / `+++` 与 `-` / `+` 行。"""
        a = ["one\n", "two\n", "three\n"]
        b = ["one\n", "TWO\n", "three\n"]
        diff = list(difflib.unified_diff(a, b, fromfile="a", tofile="b"))
        joined = "".join(diff)
        assert "---" in joined, f"应含 '---' 头,实际 {joined!r}"
        assert "+++" in joined, f"应含 '+++' 头,实际 {joined!r}"
        assert "-two" in joined, f"应含 '-two' 旧行,实际 {joined!r}"
        assert "+TWO" in joined, f"应含 '+TWO' 新行,实际 {joined!r}"

    def test_get_close_matches_picks_top_n(self):
        """`difflib.get_close_matches` 真按相似度返回前 N。"""
        matches = difflib.get_close_matches("apple", ["ape", "apply", "apricot", "banana"], n=2)
        assert len(matches) == 2
        # 'apply' 与 'apple' 共享 'appl' 前 4 字符,通常更近
        assert "apply" in matches, f"'apply' 应在 matches,实际 {matches}"


# -- string.Template ----------------------------------------------------------

class TestStringTemplate:
    def test_safe_substitute_keeps_missing_placeholders(self):
        """`Template.safe_substitute` 缺字段保留原 `$name` 不抛。"""
        tmpl = string.Template("$greet, $who!")
        out = tmpl.safe_substitute(greet="Hello")
        assert out == "Hello, $who!", f"应保留 $who! 原文,实际 {out!r}"

    def test_substitute_raises_on_missing_placeholder(self):
        """`Template.substitute` 缺字段抛 `KeyError`。"""
        tmpl = string.Template("$greet, $who!")
        with pytest.raises(KeyError):
            tmpl.substitute(greet="Hi")

    def test_braced_and_unescaped_dollar(self):
        """`${name}` braced 形式 + `$$` 真转义为字面 `$`。"""
        tmpl = string.Template("cost = $${price} for ${name}")
        out = tmpl.safe_substitute(name="alice", price=42)
        # $$ 应变成 $,${name} 渲染成 alice
        assert "alice" in out, f"输出应含 alice,实际 {out!r}"
        assert "$$" not in out, f"$$ 应被转义,实际 {out!r}"


# -- secrets ------------------------------------------------------------------

class TestSecrets:
    def test_token_hex_returns_even_length_hex(self):
        """`secrets.token_hex(16)` 返 32 hex 字符,charset 仅 `0-9a-f`。"""
        h = secrets.token_hex(16)
        assert len(h) == 32, f"token_hex(16) 应长 32,实际 {len(h)}"
        assert all(c in "0123456789abcdef" for c in h), (
            f"全 hex 字符,实际 {h!r}"
        )

    def test_token_bytes_length_matches_nbytes(self):
        """`secrets.token_bytes(N)` 返 N 字节。"""
        b = secrets.token_bytes(24)
        assert isinstance(b, bytes)
        assert len(b) == 24

    def test_compare_digest_returns_bool(self):
        """`secrets.compare_digest` 对相同/不同串返 True/False。"""
        assert secrets.compare_digest("forge", "forge") is True
        assert secrets.compare_digest("forge", "Forge") is False
        assert secrets.compare_digest(b"\x00\x01", b"\x00\x01") is True
        assert secrets.compare_digest(b"\x00\x01", b"\x00\x02") is False

    def test_choice_picks_from_sequence(self):
        """`secrets.choice` 真从序列抽一个,跑 1000 次覆盖 ≥ 80% 唯一值。"""
        seq = list("abcdefghij")  # 10 个字符
        seen = {secrets.choice(seq) for _ in range(1000)}
        assert len(seen) >= 8, (
            f"1000 次抽 10 元素应覆盖 ≥ 8 个唯一值,实际 {len(seen)} 个"
        )

    def test_randbelow_returns_in_range(self):
        """`secrets.randbelow(N)` 返 [0, N) 整数。"""
        for _ in range(50):
            n = secrets.randbelow(100)
            assert 0 <= n < 100, f"randbelow(100) 应在 [0,100),实际 {n}"
