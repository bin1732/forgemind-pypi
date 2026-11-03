# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""命令行列出来的策略,要么真能跑,要么被明确拒绝。

策略清单是给用户看的承诺:清单里有的,命令就应该能跑;跑不了的,清单上
就要说清楚为什么跑不了,并且命令要明确拒绝,而不是照样吐一个数。

这个问题真出现过:横截面动量与风险平价在只喂一支标的时会退化成同一个
结果(逐位相同的收益、回撤与夏普),看着像结论,其实什么都不说明。
"""

import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent

from _path_setup import prefer_source_tree  # noqa: E402

prefer_source_tree()

from forgemind.core.strategies.library import (  # noqa: E402
    available_strategies,
    get_extended_strategy,
    needs_multiple_symbols,
)


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "forgemind.cli", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=180,
    )


class TestStrategyListings:
    def test_every_listed_strategy_has_a_readable_description(self):
        """清单里的每条说明都要是人话,不是内部叫法"""
        for name, desc in available_strategies().items():
            assert desc, f"{name} 没有说明"
            assert "on_bar 策略" not in desc, f"{name} 的说明还是内部叫法:{desc}"
            assert "批量策略" not in desc, f"{name} 的说明还是内部叫法:{desc}"

    def test_multi_symbol_strategies_are_marked_as_such(self):
        """需要多支标的的,说明里要写出来"""
        for name, desc in available_strategies().items():
            if needs_multiple_symbols(name):
                assert "多支标的" in desc, f"{name} 需要多支标的,说明里却没写:{desc}"


class TestTheListIsAPromise:
    """清单是一份承诺:列出来能跑的就要真跑得起来。

    之前清单列了 17 个策略,命令其实只认 5 个 —— 用户照着清单挑一个,
    得到的是"未知策略"。这一节盯的是两者一致。
    """

    def test_listed_strategies_actually_run(self):
        """清单里说能跑的,引擎真要跑得出结果"""
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        from forgemind.core.data import bundled_sample_path
        from forgemind.core.strategies.library import (
            STRATEGY_REGISTRY,
            cli_runnable_strategies,
        )

        frame = pd.read_csv(bundled_sample_path(), parse_dates=["date"]).set_index("date")
        runnable = cli_runnable_strategies()
        assert runnable, "一个都跑不了,那这个命令就没有存在的意义"
        for name in sorted(runnable):
            strategy = (
                STRATEGY_REGISTRY[name]()
                if name in STRATEGY_REGISTRY
                else get_extended_strategy(name)
            )
            strategy.validate_parameters()
            result = SimpleBacktestEngine(initial_capital=100_000).run(strategy, frame)
            assert result is not None, f"{name} 跑不出结果"
            assert isinstance(result.total_return, float), f"{name} 的收益不是数"

    def test_list_only_promises_what_can_run(self):
        """清单的第一节必须恰好是命令真能跑的那批"""
        from forgemind.core.strategies.library import cli_runnable_strategies

        out = _run_cli("backtest", "--list-strategies")
        text = out.stdout + out.stderr
        runnable = cli_runnable_strategies()
        section = text.split("=== 这个命令能跑的策略 ===")[-1]
        section = section.split("===")[0]
        for name in runnable:
            assert name in section, f"清单第一节漏了 {name}"
        for name in re.findall(r"^\s{2}(\w+)\s", section, re.M):
            assert name in runnable, f"清单第一节列了跑不了的 {name}"


class TestCliRefusesWhatItCannotRun:
    def test_multi_symbol_strategy_is_refused_with_a_reason(self):
        """多标的策略要立刻被拒,而不是跑出一个没意义的数"""
        result = _run_cli("backtest", "--strategy", "MaxSharpe")
        output = result.stdout + result.stderr
        assert result.returncode != 0, "多标的策略不该被跑出一个数来"
        assert "多标的" in output, f"拒绝时要说清原因:\n{output}"

    def test_refusal_happens_before_any_data_work(self):
        """拒绝要在动手取数之前 —— 让用户先等一轮取数再被告知跑不了,
        是在浪费他的时间"""
        result = _run_cli("backtest", "--strategy", "MaxSharpe")
        output = result.stdout + result.stderr
        assert "合成行情" not in output, f"拒绝之前不该开始准备数据:\n{output}"
        assert "DuckDB" not in output, f"拒绝之前不该去查库:\n{output}"

    def test_every_entry_point_refuses_the_same_ones(self):
        """所有接受策略的命令,拒绝的必须是同一批

        多标的守卫一度只加在 backtest 上,demo 照跑不误 —— 用户从 demo
        进去,拿到的是退化后的结果。这条断言把"几条入口"钉在一起。
        """
        from forgemind.core.strategies.library import cli_runnable_strategies

        runnable = cli_runnable_strategies()
        refused = [n for n in sorted(available_strategies()) if n not in runnable]
        assert refused, "没有需要拒绝的策略,这条断言就没有意义"
        for command in ("demo", "backtest"):
            for name in refused:
                out = _run_cli(command, "--strategy", name)
                assert out.returncode != 0, (
                    f"{command} --strategy {name} 跑通了 —— 这条命令喂不了它,结果没有意义"
                )
                text = out.stdout + out.stderr
                assert "多标的" in text or "未知策略" in text or "需要" in text, (
                    f"{command} 拒绝 {name} 时没说清原因:\n{text}"
                )

    def test_single_symbol_strategy_still_runs(self):
        """单标的策略照常能跑 —— 拒绝不能误伤"""
        result = _run_cli("backtest", "--strategy", "ma_cross")
        output = result.stdout + result.stderr
        assert "多标的" not in output, f"单标的策略不该被当成多标的拒绝:\n{output}"


class TestHelpDoesNotPromiseWhatTheCommandRefuses:
    """帮助里点名的策略,命令必须真跑得起来。

    帮助是用户读到的第一份承诺。它点名了哪个策略,用户就会照着挑一个 ——
    命令要是拒绝它,用户拿到的就是一句"未知策略",而他明明是照帮助选的。
    """

    def test_help_lists_only_runnable_strategies(self):
        from forgemind.core.strategies.library import (
            available_strategies,
            cli_runnable_strategies,
        )

        out = _run_cli("backtest", "--help")
        text = out.stdout + out.stderr
        runnable = set(cli_runnable_strategies())
        refused = set(available_strategies()) - runnable
        assert refused, "没有跑不了的策略,这条断言就没有意义"
        for name in refused:
            assert name not in text, (
                f"帮助里点名了 {name},而这条命令跑不了它 —— 照着选的用户会被拒"
            )

    def test_help_keeps_no_internal_wording(self):
        """内部叫法不进帮助 —— 读的人看不出这些策略在做什么"""
        out = _run_cli("backtest", "--help")
        text = out.stdout + out.stderr
        for phrase in ("on_bar", "批量策略"):
            assert phrase not in text, f"帮助里还有内部叫法:{phrase}"


class TestTheReasonIsOneReason:
    """跑不了的理由只有一份,清单与拒绝时说的是同一句。

    这条真出过问题:清单里明明列着 PairsTrading,命令拒绝它时却回
    "未知策略" —— 同一个命令的两处说法自相矛盾,用户照着清单挑一个,
    被告知没听说过。这种情况下用户没法判断该信哪一边。
    """

    def test_known_but_unusable_is_not_called_unknown(self):
        """存在但这个命令跑不了的,不能说成"未知策略\""""
        from forgemind.core.strategies.library import (
            available_strategies,
            cli_runnable_strategies,
        )

        runnable = cli_runnable_strategies()
        refused = [n for n in sorted(available_strategies()) if n not in runnable]
        assert refused, "没有跑不了的策略,这条断言就没有意义"
        for name in refused:
            out = _run_cli("backtest", "--strategy", name)
            text = out.stdout + out.stderr
            assert "未知策略" not in text, (
                f"{name} 存在却被称为未知策略 —— 清单与拒绝消息自相矛盾:\n{text}"
            )

    def test_truly_unknown_name_is_still_called_unknown(self):
        """真不存在的名字,还是要说未知 —— 别把拒绝消息一律改成含糊话"""
        out = _run_cli("backtest", "--strategy", "NoSuchStrategyAnywhere")
        text = out.stdout + out.stderr
        assert out.returncode != 0, "不存在的策略不该被跑出一个数来"
        assert "未知策略" in text, f"不存在的策略没说未知:\n{text}"

    def test_list_and_refusal_give_the_same_reason(self):
        """清单第二节写的理由,必须与拒绝时说的一样

        两处各写一遍就会漂 —— 漂了之后,用户按清单准备好的东西,
        拒绝时却告诉他缺的是另一回事。
        """
        from forgemind.core.strategies.library import (
            available_strategies,
            cli_runnable_strategies,
            strategy_unusable_reason,
        )

        listing = _run_cli("backtest", "--list-strategies")
        text = listing.stdout + listing.stderr
        section = text.split("=== 存在但这个命令跑不了的 ===")[-1]

        runnable = cli_runnable_strategies()
        refused = [n for n in sorted(available_strategies()) if n not in runnable]
        for name in refused:
            reason = strategy_unusable_reason(name)
            assert reason, f"{name} 被拒绝却没有理由"
            assert reason in section, f"清单里 {name} 的理由与判据不一致"
            out = _run_cli("backtest", "--strategy", name)
            assert reason in (out.stdout + out.stderr), (
                f"拒绝 {name} 时说的理由与清单不一致:\n{out.stdout}{out.stderr}"
            )

    def test_refusal_gives_a_way_forward(self):
        """拒绝不能只是"不行" —— 要给一条走得通的路"""
        from forgemind.core.strategies.library import (
            available_strategies,
            cli_runnable_strategies,
        )

        runnable = cli_runnable_strategies()
        refused = [n for n in sorted(available_strategies()) if n not in runnable]
        for name in refused:
            out = _run_cli("backtest", "--strategy", name)
            text = out.stdout + out.stderr
            assert "自己用:" in text or "用引擎直接跑" in text, (
                f"{name} 被拒绝却没说怎么自己用:\n{text}"
            )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
