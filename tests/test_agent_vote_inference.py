# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
agent 命令落 portfolio_decision 时 vote 字段必填合理值,不让 vote=None (除非缺数据)

bug 历史:
- Bull/Bear 之前 confidence <= 0.5 时落 vote=None, 桌面 6 Agent 面板少一票
- Fundamentals/News status=unavailable 时落 vote=None 是对的 (缺数据不算投票)
- 修: Bull/Bear 有 thesis 时落 hold (有观点但弱信号);没 thesis 才 None
"""
import json
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest


@pytest.fixture
def agent_db(tmp_path, monkeypatch):
    db = tmp_path / "agent.db"
    monkeypatch.setenv("FORGEMIND_DUCKDB_PATH", str(db))

    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = str(db)
    yield db


def test_agent_decisions_have_valid_votes_when_technical_runs(agent_db):
    """DuckDB 有 K 线 → Technical / Bull / Bear / PM 都有真分析,vote 必填

    反向验证:Bull/Bear 有 thesis 时必为 buy/sell/hold (不为 None,即使
    confidence 低也给 hold —— 因为"有观点但弱信号"不是"无观点")
    """
    # 先灌 K 线让 Technical 能跑
    import datetime, math
    con = duckdb.connect(str(agent_db))
    con.execute("""
        CREATE TABLE IF NOT EXISTS kline_daily (
            date DATE, symbol VARCHAR,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
            volume BIGINT, provider VARCHAR,
            PRIMARY KEY (date, symbol)
        )
    """)
    rows = []
    base = datetime.date(2024, 1, 2)
    for i in range(120):
        d = base + datetime.timedelta(days=i)
        p = 100 + math.sin(i / 5) * 10 + i * 0.3
        rows.append((d, "600519", p - 1, p + 2, p - 2, p, 10000, "tencent"))
    con.executemany(
        "INSERT INTO kline_daily (date, symbol, open, high, low, close, volume, provider) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.close()

    result = subprocess.run(
        [sys.executable, "-m", "forgemind.cli", "agent",
         "--symbol", "600519.SH", "--cash", "80000", "--yes"],
        env={"FORGEMIND_DUCKDB_PATH": str(agent_db), "PATH": os.environ["PATH"]},
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent),
        timeout=120,
    )
    assert "Portfolio snapshot saved" in result.stdout, f"agent 跑失败:\n{result.stdout}\n{result.stderr[:500]}"
    assert "Agent decisions saved: 6/6" in result.stdout

    import forgemind.core.data.storage as _sm
    _sm._DUCKDB_CONN_CACHE.clear()
    con = duckdb.connect(str(agent_db))
    rows_by_agent = {r[0]: r for r in
                     con.execute("SELECT agent, vote, confidence FROM portfolio_decision ORDER BY agent").fetchall()}

    # 有真 K 线 → 6 Agent 全部应该有 vote (Fundamentals/News 是数据源缺, 仍然 None)
    for agent in ("Bull", "Bear", "Technical", "PM"):
        assert rows_by_agent[agent][1] in ("buy", "sell", "hold"), \
            f"{agent} vote 必须是 buy/sell/hold,实际 {rows_by_agent[agent]}"

    # Bull/Bear 有 thesis → 不该 None (即使 conf 弱也给 hold)
    assert rows_by_agent["Bull"][1] != None
    assert rows_by_agent["Bear"][1] != None


import os
