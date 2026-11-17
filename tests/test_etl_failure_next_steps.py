# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""每一种失败原因都要说清下一步

分类名只回答"是什么",没回答"该做什么"。对命令行的读者来说,后者才是
他真正要的东西 —— 看到"未分类的异常"或"数据源没装"却不知道下一步,
等于把活原样推回给他。

所以每种分类都得配一句可执行的建议,而且建议只能给**它自己那类**原因 ——
库被占着的时候去查网络、去看代码格式,都是白忙。

这里逐类核对:造出那种失败,看命令行有没有说出该做什么。
"""

import argparse
import asyncio
import contextlib
import io

import pytest

from forgemind.cli import cmd_etl

#: 失败分类 → 输出里必须出现的提示关键字
EXPECTED_NEXT_STEPS = {
    "store_locked(库被另一个进程占着)": ("FORGEMIND_DATA_DIR",),
    "store_write_failed(存储写不进去)": ("清出空间",),
    "data_inconsistent(高低收不自洽)": ("上游",),
    "akshare_not_installed": ("pip install",),
    "empty_result(可能是代码无数据或日期区间为空)": ("6 位",),
}


def _run_etl_with_failure(monkeypatch, reason: str) -> str:
    """造出一次失败,返回命令行的输出。"""
    import forgemind.core.data.akshare_etl as mod

    class FakeETL:
        def __init__(self, *a, **k):
            pass

        async def run(self, **kwargs):
            return {
                "klines": 0,
                "stocks": 0,
                "ok_symbols": 0,
                "failures": {reason: 1},
            }

    monkeypatch.setattr(mod, "AKShareETL", FakeETL)
    args = argparse.Namespace(
        symbols="600519",
        start="2024-01-01",
        end="2024-01-31",
    )
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        with pytest.raises(SystemExit):
            cmd_etl(args)
    return buf.getvalue()


class TestEveryFailureReasonHasANextStep:
    @pytest.mark.parametrize("reason", sorted(EXPECTED_NEXT_STEPS))
    def test_reason_carries_an_actionable_advice(self, monkeypatch, reason):
        out = _run_etl_with_failure(monkeypatch, reason)
        assert reason in out, out
        for keyword in EXPECTED_NEXT_STEPS[reason]:
            assert keyword in out, (
                f"失败原因 {reason} 没有给出下一步(缺 {keyword!r}):\n{out}"
            )

    def test_lock_conflict_does_not_advise_changing_the_symbol(self, monkeypatch):
        """库被占着的时候,去查代码格式或日期区间都是白忙"""
        out = _run_etl_with_failure(monkeypatch, "store_locked(库被另一个进程占着)")
        assert "代码格式" not in out, out
        assert "网络" not in out, out

    def test_inconsistent_rows_do_not_advise_checking_the_symbol(self, monkeypatch):
        """数据自相矛盾不是标的代码的问题"""
        out = _run_etl_with_failure(monkeypatch, "data_inconsistent(高低收不自洽)")
        assert "代码格式" not in out, out
