# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`forgemind demo`:新手的第一条命令,必须真的跑得通,而且不骗人。

这道测试锁两件事:

1. **跑得通** —— 零配置、零密钥、零网络,装完就能看到结果。
2. **不骗人** —— 输出里报的收益、夏普、进出次数,必须与直接调引擎算出来
   的完全一致;数据来源必须写清楚是真实行情。

第 2 条是重点:命令可以自己编排流程,但只要它报的数与真实算出来的不
一样,那就是欺骗 —— 哪怕它报的数"好看"。
"""
import argparse
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

from _path_setup import prefer_source_tree  # noqa: E402

prefer_source_tree()

from forgemind.cli import cmd_demo  # noqa: E402


def _args(**kw):
    base = dict(symbol="600519", start="2024-01-01", end="2024-12-31", strategy="ma_cross")
    base.update(kw)
    return argparse.Namespace(**base)


class TestDemoRuns:
    def test_demo_completes_without_network_or_keys(self, capsys):
        """没有任何准备,直接跑 —— 必须成功退出"""
        rc = cmd_demo(_args())
        out = capsys.readouterr().out
        assert rc == 0, f"demo 没跑通:\n{out}"

    def test_demo_reports_the_data_source(self, capsys):
        """数据来源必须写清楚"""
        cmd_demo(_args())
        out = capsys.readouterr().out
        assert "数据来源" in out, f"输出里没有说明数据来源:\n{out}"
        assert "真实价格" in out, f"输出没有说清用的是真实价格:\n{out}"

    def test_demo_never_claims_synthetic_data_is_real(self, capsys):
        """不许出现"模拟数据"却被当成真结果的表述"""
        cmd_demo(_args())
        out = capsys.readouterr().out
        for line in out.splitlines():
            if "模拟" in line or "随机" in line:
                assert "不是模拟数据" in line or "非真实" in line, (
                    f"这一行把编造的数据说成了真的:\n{line}"
                )

    def test_demo_numbers_match_a_direct_engine_run(self, capsys):
        """demo 报的数必须与直接调引擎算出来的一致

        这是最要紧的一条:命令可以自己编排流程,但报出来的数必须是真算
        出来的 —— 差一分都是欺骗。
        """
        import pandas as pd

        from forgemind.core.backtest.engine import SimpleBacktestEngine
        from forgemind.core.data import bundled_sample_path
        from forgemind.core.strategies.library import STRATEGY_REGISTRY

        cmd_demo(_args())
        out = capsys.readouterr().out

        frame = pd.read_csv(bundled_sample_path(), parse_dates=["date"]).set_index("date")
        strategy = STRATEGY_REGISTRY["ma_cross"]()
        strategy.validate_parameters()
        result = SimpleBacktestEngine(initial_capital=100_000).run(strategy, frame)

        assert f"{result.total_return:+.2%}" in out, (
            f"demo 报的收益与引擎算的对不上(引擎:{result.total_return:+.2%}):\n{out}"
        )
        assert f"{result.sharpe:.2f}" in out, "demo 报的夏普与引擎算的对不上"
        assert f"进出 {result.n_trades} 次" in out, "demo 报的进出次数与引擎算的对不上"

    def test_demo_refuses_an_unknown_strategy(self, capsys):
        """策略名写错要明确说,不能悄悄换成一个别的策略"""
        with pytest.raises(SystemExit) as exc:
            cmd_demo(_args(strategy="不存在的策略"))
        assert exc.value.code == 2
        out = capsys.readouterr().out
        assert "未知策略" in out
        assert "ma_cross" in out, "报错时应该列出可用的策略名"


class TestDemoFirstRunIsClean:
    """第一次跑的那台机器:库里还没有 K 线表 —— 那是正常情况,不是故障。

    用异常去问"这张表在不在",会在存储层留下一条带内部表名与 SQL 的
    告警,新手第一次上手看到的是一串 JSON,像坏了。demo 是门面,门面
    上不能出现这种东西。
    """

    def test_first_run_leaks_no_internal_details(self, monkeypatch, capsys, tmp_path):
        import forgemind.core.data.storage as _sm

        fresh = tmp_path / "fresh" / "main.db"
        monkeypatch.setenv("FORGEMIND_DUCKDB_PATH", str(fresh))
        from forgemind.core.config.settings import get_settings

        get_settings.cache_clear()
        _sm._DUCKDB_CONN_CACHE.clear()
        try:
            rc = cmd_demo(_args())
            captured = capsys.readouterr()
        finally:
            _sm._DUCKDB_CONN_CACHE.clear()
            get_settings.cache_clear()

        assert rc == 0, f"demo 没跑通:\n{captured.out}"
        # 输出仍然要说清用的是包内置的真实行情
        assert "真实价格" in captured.out, captured.out
        # 内部实现细节一律不许出现 —— stdout 与 stderr 都一样
        for stream, text in (("stdout", captured.out), ("stderr", captured.err)):
            for leak in ("kline_daily", "CatalogException", "Catalog Error",
                         "information_schema"):
                assert leak not in text, (
                    f"{stream} 里漏出了内部实现细节({leak}):\n{text}")


class TestDemoDataIntegrity:
    def test_demo_refuses_unusable_data(self, monkeypatch, capsys):
        """内置行情文件坏了就不许拿它去跑 —— 更不能拿编造的数据顶上"""
        import pandas as pd

        import forgemind.cli as cli

        broken = pd.DataFrame(
            {
                "open": [10.0, 11.0],
                "high": [1.0, 2.0],  # high 比 open 还小 —— 列序写错了
                "low": [9.0, 10.0],
                "close": [10.5, 11.5],
                "volume": [100.0, 200.0],
            },
            index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
        )
        monkeypatch.setattr(cli, "_bundled_real_prices", lambda s, e: broken)
        with pytest.raises(ValueError, match="不自洽"):
            cmd_demo(_args())
