# Copyright (c) 2026 灵感引擎工坊 (bin1732) | SPDX-License-Identifier: Apache-2.0
"""决策的账户状态从哪儿来。

命令行原本给现金、总权益、持仓都留了默认值(八万现金、二十万权益、
持有一百股)。于是 `forgemind agent --symbol 600519.SH` 这一条命令,
不写任何账户,就跑在一个编出来的账户上 —— 输出看着正常,依据是假的,
而审批之后它还会落进组合快照,把假状态存成了真的。

所以账户状态只能有两个来源:**命令行显式给的**,或者**库里真实落过
的组合**。两个都没有就说明还没有,不许编。
"""

from __future__ import annotations

import argparse
import subprocess
import sys

import pytest


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """一个自己的数据目录,别碰用户真实的那份库。"""
    data_dir = tmp_path / "data"
    db_path = data_dir / "duckdb" / "main.db"
    monkeypatch.setenv("FORGEMIND_DATA_DIR", str(data_dir))
    monkeypatch.setenv("FORGEMIND_DUCKDB_PATH", str(db_path))
    from forgemind.core.config.settings import get_settings

    get_settings.cache_clear()
    yield data_dir
    get_settings.cache_clear()


def _args(**over) -> argparse.Namespace:
    base = {
        "symbol": "600519.SH",
        "cash": None,
        "equity": None,
        "position_qty": None,
        "position_price": None,
    }
    base.update(over)
    return argparse.Namespace(**base)


class TestAgentAccountSource:
    def test_explicit_cash_is_used(self, isolated_store):
        from forgemind.cli import _resolve_agent_portfolio

        portfolio, problem = _resolve_agent_portfolio(_args(cash=12345.0))
        assert problem is None
        assert portfolio.cash == 12345.0
        assert portfolio.positions == []

    def test_explicit_position_is_used(self, isolated_store):
        from forgemind.cli import _resolve_agent_portfolio

        portfolio, problem = _resolve_agent_portfolio(
            _args(cash=100000.0, position_qty=30, position_price=1498.5)
        )
        assert problem is None
        assert len(portfolio.positions) == 1
        assert portfolio.positions[0].symbol == "600519.SH"
        assert portfolio.positions[0].quantity == 30

    def test_stored_snapshot_is_used(self, isolated_store):
        """库里落过组合,就该用它 —— 那才是真实账户。"""
        from forgemind.cli import _resolve_agent_portfolio
        from forgemind.core.agents.portfolio_context import (
            PortfolioContext,
            PortfolioPosition,
        )
        from forgemind.core.data.storage import save_portfolio_snapshot

        save_portfolio_snapshot(
            PortfolioContext(
                cash=55555.0,
                positions=[PortfolioPosition(symbol="000001", quantity=100, avg_price=12.5)],
            )
        )
        portfolio, problem = _resolve_agent_portfolio(_args())
        assert problem is None, problem
        assert portfolio.cash == 55555.0
        assert len(portfolio.positions) == 1
        assert portfolio.positions[0].symbol == "000001"

    def test_no_snapshot_and_no_argument_says_so(self, isolated_store):
        """两边都没有就说明还没有,顺带说清怎么办。"""
        from forgemind.cli import _resolve_agent_portfolio

        portfolio, problem = _resolve_agent_portfolio(_args())
        assert portfolio is None
        assert problem, "没有账户状态时必须给出说明"
        assert "组合" in problem, problem
        # 说明里要有下一步,不能只是"不行"
        assert "--cash" in problem, problem


class TestCommandLineRefusesToInvent:
    def test_agent_without_account_exits_with_usage_error(self, tmp_path):
        """真跑一次:空库里不带账户参数,要退出并说清楚。"""
        from _path_setup import child_env

        env = child_env(
            FORGEMIND_DATA_DIR=str(tmp_path / "data"),
            FORGEMIND_DUCKDB_PATH=str(tmp_path / "data" / "duckdb" / "main.db"),
            FORGEMIND_NONINTERACTIVE="1",
        )
        proc = subprocess.run(
            [sys.executable, "-m", "forgemind.cli", "agent", "--symbol", "600519.SH"],
            capture_output=True,
            text=True,
            env=env,
            timeout=180,
        )
        assert proc.returncode == 2, (
            f"没账户状态应当是用法错误(2),实际 {proc.returncode}: "
            f"{proc.stdout[-500:]} {proc.stderr[-500:]}"
        )
        assert "组合" in proc.stderr, proc.stderr[-500:]
        assert "--cash" in proc.stderr, proc.stderr[-500:]

    def test_parser_has_no_default_cash(self):
        """解析器里不能留默认现金 —— 留了就等于默认编一个。"""
        from forgemind.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["agent"])
        assert args.cash is None, args.cash
        assert args.equity is None, args.equity
        assert args.position_qty is None, args.position_qty
        assert args.position_price is None, args.position_price
