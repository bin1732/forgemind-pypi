# Copyright (c) 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""README 示例核对器自己得可靠。

它盯的是文档里的承诺:README 提到的命令得真的存在,提到的策略数得与
命令真能跑的数一致。这些检查一旦失效,文档就会慢慢变成过期说法 ——
而没人会去发现,因为检查还在跑,只是不再报。

所以这里逐条验:坏样本它得报出来,好样本它不许误报。
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_readme_examples as examples  # noqa: E402


class TestCommandMentions:
    """README 里点名的命令必须真的存在 —— 整篇都查,不只是代码块"""

    def test_fake_command_in_prose_is_reported(self):
        """正文里(不在代码块里)写了不存在的命令,要报出来"""
        text = "`forgemind totally_not_a_command` 跑的是事件驱动回测。\n"
        problems = examples.check_all_mentions(text, [])
        assert len(problems) == 1, problems
        assert "totally_not_a_command" in problems[0]

    def test_real_command_in_prose_is_not_reported(self):
        """真命令不该被报"""
        text = "`forgemind backtest` 跑的是事件驱动回测。\n"
        assert examples.check_all_mentions(text, []) == []

    def test_module_path_is_not_a_command(self):
        """`forgemind.core.pipeline.X` 是模块路径,不是子命令"""
        text = "完整流水线在 `forgemind.core.pipeline.EndToEndPipeline` 里。\n"
        assert examples.check_all_mentions(text, []) == []

    def test_real_readme_has_no_fake_commands(self):
        """真的 README 里没有不存在的命令"""
        text = (REPO / "README.md").read_text(encoding="utf-8")
        blocks = examples._bash_blocks(text)  # noqa: SLF001
        assert examples.check_all_mentions(text, blocks) == []


class TestStrategyCount:
    """README 说的策略数要等于命令真能跑的那批"""

    def test_wrong_count_is_reported(self):
        """数字对不上要报出来,并给出行号"""
        problems = examples.check_strategy_count("这一档有 17 个策略。\n")
        assert len(problems) == 1, problems
        assert "第 1 行" in problems[0]

    def test_right_count_is_not_reported(self):
        """数字对得上不该报"""
        from forgemind.core.strategies.library import cli_runnable_strategies

        n = len(cli_runnable_strategies())
        assert examples.check_strategy_count(f"这一档有 {n} 个策略。\n") == []

    def test_real_readme_count_matches(self):
        """真的 README 里的数字与代码一致"""
        text = (REPO / "README.md").read_text(encoding="utf-8")
        assert examples.check_strategy_count(text) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
