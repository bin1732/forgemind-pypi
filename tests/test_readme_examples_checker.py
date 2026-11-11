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


class TestReferencedFilesExist:
    """README 点名的仓内文件必须真的存在 —— 读者点开不该是 404"""

    def test_missing_file_is_reported(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        text = "结果记在 `scripts/not_there.md`,那里有详细说明。\n"
        problems = examples.check_referenced_files_exist(text, tmp_path)
        assert len(problems) == 1, problems
        assert "not_there.md" in problems[0]

    def test_existing_file_is_not_reported(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "there.md").write_text("x", encoding="utf-8")
        text = "结果记在 `scripts/there.md`。\n"
        assert examples.check_referenced_files_exist(text, tmp_path) == []

    def test_glob_is_not_treated_as_a_file(self, tmp_path):
        """通配写法不是一个具体文件,不该报"""
        text = "全部脚本在 `scripts/check_*.py` 里。\n"
        assert examples.check_referenced_files_exist(text, tmp_path) == []

    def test_dead_markdown_link_is_reported(self, tmp_path):
        problems = examples.check_referenced_files_exist("见 [说明](docs/gone.md)。\n", tmp_path)
        assert len(problems) == 1, problems
        assert "gone.md" in problems[0]

    def test_real_readme_has_no_dead_references(self):
        """真的 README 里点名的仓内文件都在"""
        text = (REPO / "README.md").read_text(encoding="utf-8")
        assert examples.check_referenced_files_exist(text, REPO) == []


class TestEverySubcommandIsDocumented:
    """命令存在却没写进文档,读者就找不到它"""

    def test_undocumented_command_is_reported(self, monkeypatch):
        monkeypatch.setattr(examples, "_real_subcommands", lambda: {"info", "brand_new_command"})
        problems = examples.check_every_subcommand_is_documented("`forgemind info`\n")
        assert len(problems) == 1, problems
        assert "brand_new_command" in problems[0]

    def test_documented_command_is_not_reported(self, monkeypatch):
        monkeypatch.setattr(examples, "_real_subcommands", lambda: {"info"})
        assert examples.check_every_subcommand_is_documented("`forgemind info`\n") == []

    def test_real_readme_documents_every_command(self):
        text = (REPO / "README.md").read_text(encoding="utf-8")
        assert examples.check_every_subcommand_is_documented(text) == []


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


class TestQuotedMessages:
    """FAQ 里引用的报错原文必须还真的会被打印出来"""

    @staticmethod
    def _repo(tmp_path: pathlib.Path, source: str) -> pathlib.Path:
        pkg = tmp_path / "forgemind"
        pkg.mkdir(parents=True)
        (pkg / "cli.py").write_text(source, encoding="utf-8")
        return tmp_path

    def test_stale_quote_is_reported(self, tmp_path):
        """引用的原文在源码里没了 → 报出来(读者照着引号里的字找不到)"""
        repo = self._repo(tmp_path, 'print("库里没有 K 线")')
        text = '<summary><b>Q: 报 "在库里没有行情数据" 怎么办?</b></summary>'
        problems = examples.check_quoted_messages(text, repo)
        assert len(problems) == 1, problems
        assert "第 1 行" in problems[0]

    def test_live_quote_is_not_reported(self, tmp_path):
        """原文还在 → 不许报"""
        repo = self._repo(tmp_path, 'print("在库里没有行情数据")')
        text = '<summary><b>Q: 报 "在库里没有行情数据" 怎么办?</b></summary>'
        assert examples.check_quoted_messages(text, repo) == []

    def test_platform_message_is_not_reported(self, tmp_path):
        """平台自己的报错原文不在本仓源码里 —— 不该按本仓文案核"""
        repo = self._repo(tmp_path, "")
        text = '<summary><b>Q: 报 "No matching distribution found" 怎么办?</b></summary>'
        assert examples.check_quoted_messages(text, repo) == []

    def test_ellipsis_quote_checks_every_part(self, tmp_path):
        """省略写法:每段都得在源码里找得到"""
        repo = self._repo(tmp_path, 'print("本地库里没有这个标的的行情数据")')
        text = ('<summary><b>Q: 报 "本地库里没有这个标的的行情数据 ... '
                '先跑一次 etl" 怎么办?</b></summary>')
        problems = examples.check_quoted_messages(text, repo)
        assert len(problems) == 1, problems
        assert "先跑一次 etl" in problems[0]

    def test_real_readme_quotes_are_live(self):
        """真的 README 里引用的每句话都还会在源码里出现"""
        text = (REPO / "README.md").read_text(encoding="utf-8")
        assert examples.check_quoted_messages(text, REPO) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))


class TestCommandOptions:
    """README 里写的选项,这个命令真的认

    之前只核对子命令在不在 —— 用户照着抄一条带选项的命令,选项写错了
    一样报错,而那时没人拦。
    """

    def test_unknown_option_is_reported(self):
        text = "forgemind backtest --strategys ma_cross --symbol 600519\n"
        problems = examples.check_command_options(text)
        assert len(problems) == 1, problems
        assert "--strategys" in problems[0]

    def test_known_option_is_not_reported(self):
        text = "forgemind backtest --strategy ma_cross --symbol 600519\n"
        assert examples.check_command_options(text) == []

    def test_unique_prefix_is_accepted(self):
        """argparse 允许唯一前缀缩写,--symbol 就是 --symbols 的前缀"""
        text = "forgemind pick --symbol 600519.SH --top-n 5\n"
        assert examples.check_command_options(text) == []

    def test_ambiguous_prefix_is_reported(self):
        """前缀不唯一时 argparse 会报歧义,这里也要报"""
        text = "forgemind backtest --s ma_cross\n"
        problems = examples.check_command_options(text)
        assert problems, "歧义的前缀没人拦"

    def test_option_of_another_command_is_reported(self):
        """选项得是这个命令认的,不是别的命令的"""
        text = "forgemind info --strategy ma_cross\n"
        problems = examples.check_command_options(text)
        assert len(problems) == 1, problems

    def test_real_readme_options_are_all_real(self):
        text = (REPO / "README.md").read_text(encoding="utf-8")
        assert examples.check_command_options(text) == []
