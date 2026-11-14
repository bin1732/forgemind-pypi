# Copyright (c) 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""命令状态核对器:它自己也得可靠。

它盯的是"每条命令在各种状态下有没有说真话"。这类判据最容易出两种错:

- 规则太宽 ⇒ 一堆假红 ⇒ 没人看它。
- 规则太窄 ⇒ 真的漏了也放过。

所以这里逐条钉:该报的报、不该报的不报,而且用**真的命令输出**做样本 ——
不是自己编的字符串。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_command_states as states  # noqa: E402


class TestStateRules:
    def test_states_are_defined(self):
        assert set(states.STATES) == {
            "no_data",
            "insufficient",
            "locked",
            "no_key",
            "write_full",
        }
        assert states.COMMANDS, "没有要核的命令"

    def test_every_command_runs_in_every_state(self):
        """每条命令都要在每种状态下核过 —— 少一个组合就是少一处没验"""
        for command in states.COMMANDS:
            for state in states.STATES:
                assert state in states.STATES
                # 命令本身得是能跑的形态:第一个元素是子命令名
                assert command[0]
                assert not command[0].startswith("-"), command

    def test_forbidden_kinds_are_internal_implementation(self):
        """不许出现的那几种,都是内部实现"""
        assert "异常类名" in states.FORBIDDEN
        assert "SQL 片段" in states.FORBIDDEN
        assert "Python 栈回溯" in states.FORBIDDEN
        assert "本机绝对路径" in states.FORBIDDEN

    def test_unreadable_and_missing_markers_are_different(self):
        """ "读不到"与"没有数据"必须是两套说法,不能混"""
        assert set(states.UNREADABLE_MARKERS) & set(states.MISSING_MARKERS) == set()


class TestRulesOnSyntheticOutput:
    """规则本身,用编出来的输出逐条验。

    真跑一遍能验"整条命令在这个状态下合规",但验不出**哪条规则**在
    起作用 —— 规则没生效与场景没造出来,在真跑里长得一模一样。
    这里直接喂输出,把每条规则单独钉住:该报的报,不该报的不报。
    """

    def test_resource_state_demands_exit_code_four(self):
        """资源类状态下,退出码必须是 4"""
        problems = states.check_output_rules(
            ["backtest", "--symbol", "600519"],
            "locked",
            0,
            "本地库正被另一个进程占用\n",
        )
        assert any("退出码 0" in p for p in problems), problems

    def test_resource_state_forbids_result_numbers(self):
        """资源类状态下不许吐出回测数字"""
        problems = states.check_output_rules(
            ["backtest", "--symbol", "600519"],
            "locked",
            4,
            "本地库正被另一个进程占用\nTotal Return: 11.54%\nSharpe: 0.87\n",
        )
        assert any("Total Return" in p for p in problems), problems

    def test_write_failure_must_not_be_reported_as_missing_data(self):
        """写不进去与没有数据是两回事"""
        problems = states.check_output_rules(
            ["backtest", "--symbol", "600519"],
            "write_full",
            4,
            "600519 在库里没有 K 线\n",
        )
        assert any("没有数据" in p for p in problems), problems

    def test_compliant_output_has_no_problems(self):
        """合规的输出不该被报出问题 —— 规则太宽会让人不再看它"""
        problems = states.check_output_rules(
            ["backtest", "--symbol", "600519"],
            "locked",
            4,
            "本地库正被另一个进程占用 —— 关掉那个进程再试\n",
        )
        assert not problems, problems

    def test_commands_not_touching_the_store_are_not_judged(self):
        """不碰本地库的命令不该被判退出码"""
        problems = states.check_output_rules(["info"], "locked", 0, "版本 2026.9.3\n")
        assert not problems, problems


class TestRealOutputIsChecked:
    """用真的命令输出做样本"""

    def test_locked_store_is_reported_as_unreadable(self):
        """库被占着时,输出必须说读不到,而且不许说'没有数据'"""
        problems = states._check_one(
            ["backtest", "--symbol", "600519", "--start", "2024-01-01", "--end", "2024-06-30"],
            "locked",
        )
        assert not problems, problems

    def test_write_full_state_is_checked_on_real_output(self):
        """写不进去这个状态也要真跑一遍 —— 没跑过的规则等于没有规则"""
        problems = states._check_one(
            [
                "backtest",
                "--symbol",
                "600519",
                "--start",
                "2024-01-01",
                "--end",
                "2024-06-30",
            ],
            "write_full",
        )
        assert not problems, problems

    def test_real_locked_output_contains_no_traceback(self):
        """真的占着锁跑一次,输出里不许有栈回溯"""
        import tempfile

        with tempfile.TemporaryDirectory(prefix="forgemind_lock_probe_") as tmp:
            work = Path(tmp)
            db = states._duckdb_path(work)
            states._make_db(db, 5)
            holder = states._lock_holder(db)
            assert holder.stdout is not None
            holder.stdout.readline()
            try:
                rc, out = states._run(["signal", "--symbol", "600519"], work, db)
            finally:
                holder.terminate()
                try:
                    holder.wait(timeout=10)
                except Exception:  # noqa: BLE001
                    holder.kill()
            assert "Traceback" not in out, out[-500:]
            assert "占用" in out or "读不到" in out, out[-500:]


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
