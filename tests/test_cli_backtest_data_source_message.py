# Copyright (c) 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""回测降级到模拟行情时,消息必须与实际情况相符。

真出现过:用户明明写了 `--symbol 600519`,命令却打印"未指定 --symbol
且 DuckDB 无数据" —— 给了标的这件事被说没了,后面还紧跟一条"去拉这个
标的"的提示,两句话自相矛盾。用户照着读,只会以为自己没给标的。

消息说反了,比不说更糟:它把用户引向错误的下一步。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _run_backtest(tmp_path: Path, *extra: str) -> str:
    """在空库上跑一次回测,返回它的输出。"""
    env = dict(os.environ)
    env["FORGEMIND_DUCKDB_PATH"] = str(tmp_path / "empty.db")
    env["FORGEMIND_LOG_LEVEL"] = "ERROR"
    result = subprocess.run(
        [sys.executable, "-m", "forgemind.cli", "backtest",
         "--start", "2024-01-01", "--end", "2024-12-31", *extra],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    return result.stdout + result.stderr


class TestBacktestDegradationMessage:
    def test_given_symbol_is_not_reported_as_not_given(self, tmp_path):
        """给了标的,消息不能说"未指定 --symbol\""""
        out = _run_backtest(tmp_path, "--symbol", "600519")
        assert "未指定 --symbol" not in out, (
            f"给了标的却说没给:\n{out}"
        )
        assert "600519" in out, f"消息里没有点出是哪个标的:\n{out}"

    def test_without_symbol_the_message_says_so(self, tmp_path):
        """没给标的时,消息要说清是哪种情况"""
        out = _run_backtest(tmp_path)
        assert "未指定 --symbol" in out, f"没给标的却没说:\n{out}"

    def test_the_hint_matches_the_situation(self, tmp_path):
        """提示要指向用户真正缺的那一步"""
        given = _run_backtest(tmp_path, "--symbol", "600519")
        assert "forgemind etl --symbols 600519" in given, (
            f"提示没有指向这个标的:\n{given}"
        )

    def test_synthetic_data_is_always_declared(self, tmp_path):
        """不管走哪条降级路,用了模拟行情都要说出来"""
        for extra in ((), ("--symbol", "600519")):
            out = _run_backtest(tmp_path, *extra)
            assert "非真实市场" in out, f"用了模拟行情却没声明:\n{out}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
