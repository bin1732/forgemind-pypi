# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""命令行列出来的策略,要么真能跑,要么被明确拒绝。

策略清单是给用户看的承诺:清单里有的,命令就应该能跑;跑不了的,清单上
就要说清楚为什么跑不了,并且命令要明确拒绝,而不是照样吐一个数。

这个问题真出现过:横截面动量与风险平价在只喂一支标的时会退化成同一个
结果(逐位相同的收益、回撤与夏普),看着像结论,其实什么都不说明。
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from forgemind.core.strategies.library import (  # noqa: E402
    available_strategies,
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

    def test_single_symbol_strategy_still_runs(self):
        """单标的策略照常能跑 —— 拒绝不能误伤"""
        result = _run_cli("backtest", "--strategy", "ma_cross")
        output = result.stdout + result.stderr
        assert "多标的" not in output, f"单标的策略不该被当成多标的拒绝:\n{output}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
