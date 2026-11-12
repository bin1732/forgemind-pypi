# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""选股失败要说清是"读不到"还是"没有数据"。

活证据(2026-11-12):桌面端开着的时候,它占着同一个 DuckDB 文件,终端里
的选股命令直接查询失败。可命令告诉用户的是"库里没有该标的",并让他去
跑 `forgemind etl` —— 而 etl 同样读不到那个库。用户照着提示走,一路撞墙。

所以这两种情况必须分开报:
- 读不到(query failed):告诉用户本地库读不了,以及大概是什么原因。
- 没有数据(no data):告诉用户去拉数据。

这里真的让查询失败一次,看它报的是哪一种。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from forgemind.core.agents.stock_picker import StockPickerAgent  # noqa: E402


class _Boom:
    """一读就炸的库 —— 模拟"桌面端占着同一个 DuckDB 文件"的情形。"""

    def table_exists(self, _name: str) -> bool:
        return True

    def query_df(self, *_args, **_kwargs):
        raise OSError("Could not set lock on file")

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class _Empty:
    """表在,但没有这个标的的行情。"""

    def table_exists(self, _name: str) -> bool:
        return True

    def query_df(self, *_args, **_kwargs):
        import pandas as pd

        return pd.DataFrame()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _picker(db) -> StockPickerAgent:
    return StockPickerAgent(db=db)


class TestQueryFailureIsNotMissingData:
    def test_query_failure_is_recorded_separately(self):
        picker = _picker(_Boom())
        asyncio.run(picker.pick(universe=["600519"], top_n=3))
        assert picker.last_query_errors, "查询失败没有单独记下来"
        assert "600519" in picker.last_query_errors
        # 关键:不能同时被算成"数据不足" —— 那会让上层说"库里没有该标的"
        assert "600519" not in picker.last_insufficient, (
            "查询失败的标的被算成了'数据不足',用户会被引去跑 etl —— "
            "而 etl 同样读不到那个库"
        )

    def test_missing_data_is_still_insufficient(self):
        """真的没有数据时,仍然走"数据不足"那条路"""
        picker = _picker(_Empty())
        asyncio.run(picker.pick(universe=["600519"], top_n=3))
        assert picker.last_insufficient.get("600519") == 0
        assert not picker.last_query_errors

    def test_query_error_state_does_not_leak_across_picks(self):
        """上一轮读不到的状态不能留在下一轮"""
        picker = _picker(_Boom())
        asyncio.run(picker.pick(universe=["600519"], top_n=3))
        assert picker.last_query_errors
        picker = _picker(_Empty())
        asyncio.run(picker.pick(universe=["600519"], top_n=3))
        assert not picker.last_query_errors, (
            "上一轮的读不到状态留在了下一轮 —— 一次偶发的库占用会一直显示"
        )


class TestCliSaysWhichOne:
    """命令行要说清是哪一种"""

    def test_cli_reports_unreadable_separately(self, tmp_path, capsys):
        from forgemind.cli import build_parser, cmd_pick
        import argparse

        args = build_parser().parse_args(["pick", "--symbol", "600519"])
        args.top_n = 3
        args.symbol = "600519"

        picker = _picker(_Boom())
        asyncio.run(picker.pick(universe=["600519"], top_n=3))

        # 走命令行的真实分支:把 picker 换成会失败的库。
        # 命令行是在函数里 import 的 ⇒ 得打在真正定义它的地方。
        import forgemind.core.agents.stock_picker as sp

        class _P:
            def __init__(self):
                self.last_insufficient = {}
                self.last_query_errors = {"600519": "读不到本地行情"}
                self.last_data_date = None

            async def pick(self, universe, top_n=10):
                return []

        original = sp.StockPickerAgent
        sp.StockPickerAgent = _P
        try:
            cmd_pick(args)
        finally:
            sp.StockPickerAgent = original
        out = capsys.readouterr().out
        assert "读不到本地行情" in out, out
        assert "库里没有该标的" not in out, (
            "读不到的时候还写'库里没有该标的',用户会去跑一条同样失败的命令"
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
