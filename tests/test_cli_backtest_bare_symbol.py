# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
forgemind backtest --symbol X 归一化 symbol 命中 DuckDB 真数据
"""
import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest


@pytest.fixture
def kline_db(tmp_path, monkeypatch):
    """灌真 K 线 + 切 env"""
    db = tmp_path / "bt.db"
    monkeypatch.setenv("FORGEMIND_DUCKDB_PATH", str(db))

    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = str(db)

    # 灌 60 根 K 线(让 ma_cross 至少出 1 笔交易)
    import math, datetime
    rows = []
    base = datetime.date(2024, 1, 2)
    for i in range(120):
        d = base + datetime.timedelta(days=i)
        p = 100 + math.sin(i / 5) * 10 + i * 0.3
        rows.append((d, "600519", p - 1, p + 2, p - 2, p, 10000))
    con = duckdb.connect(str(db))
    con.execute("""
        CREATE TABLE IF NOT EXISTS kline_daily (
            date DATE, symbol VARCHAR,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
            volume BIGINT, provider VARCHAR,
            PRIMARY KEY (date, symbol)
        )
    """)
    con.executemany(
        "INSERT INTO kline_daily (date, symbol, open, high, low, close, volume, provider) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(d, s, o, h, l, c, v, "tencent") for (d, s, o, h, l, c, v) in rows]
    )
    con.close()
    yield db


def test_backtest_with_bare_symbol(kline_db):
    """--symbol 600519 (无后缀) 命中"""
    result = subprocess.run(
        [sys.executable, "-m", "forgemind.cli", "backtest",
         "--symbol", "600519", "--start", "2024-01-01", "--end", "2024-06-30"],
        env={**os.environ, "FORGEMIND_DUCKDB_PATH": str(kline_db)},
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent),
    )
    assert "真数据" in result.stdout, f"应该用真数据,stdout:\n{result.stdout}"
    # backtest_run 表应该有 1 行
    import forgemind.core.data.storage as _sm
    _sm._DUCKDB_CONN_CACHE.clear()
    con = duckdb.connect(str(kline_db))
    n = con.execute("SELECT count(*) FROM backtest_run").fetchone()[0]
    assert n >= 1
    row = con.execute("SELECT symbol, strategy, total_return, sharpe, sortino, max_drawdown, win_rate, n_trades FROM backtest_run ORDER BY ran_at DESC LIMIT 1").fetchone()
    assert row[0] == "600519"  # bare symbol 落盘
    assert row[1] == "ma_cross"
    # sharpe / max_drawdown 应该存在
    assert row[3] is not None


def test_backtest_with_dotted_symbol(kline_db):
    """--symbol 600519.SH (带后缀) 经 bare_symbol 归一化后命中"""
    result = subprocess.run(
        [sys.executable, "-m", "forgemind.cli", "backtest",
         "--symbol", "600519.SH", "--start", "2024-01-01", "--end", "2024-06-30"],
        env={**os.environ, "FORGEMIND_DUCKDB_PATH": str(kline_db)},
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent),
    )
    assert "真数据" in result.stdout, f"应该用真数据(归一化),stdout:\n{result.stdout}"


def test_backtest_with_no_data_falls_back_to_sim(kline_db):
    """DuckDB 没这个 symbol 时降级模拟行情 + 可行动提示"""
    result = subprocess.run(
        [sys.executable, "-m", "forgemind.cli", "backtest",
         "--symbol", "999999.SH", "--start", "2024-01-01", "--end", "2024-06-30"],
        env={**os.environ, "FORGEMIND_DUCKDB_PATH": str(kline_db)},
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent),
    )
    # 应有降级提示。这里断言的是意图,不是某一句文案:说了"库里没有
    # K 线",并给出下一步怎么做。
    assert "没有 K 线" in result.stdout, \
        f"应该提示库里没有 K 线,stdout:\n{result.stdout}"
    assert "forgemind etl" in result.stdout, \
        f"应该给出可行动的下一步,stdout:\n{result.stdout}"
    # 内部实现细节不能印给用户:表名与 DuckDB 的原始报错都别露出来。
    # 第一次跑的人库里还没有这张表,那是正常情况,不是故障 ——
    # 印出来像坏了,而且把内部表名与 SQL 一起交出去了。
    for leak in ("kline_daily", "CatalogException", "Catalog Error"):
        assert leak not in result.stdout, \
            f"输出里漏出了内部实现细节({leak}),stdout:\n{result.stdout}"
        assert leak not in result.stderr, \
            f"输出里漏出了内部实现细节({leak}),stderr:\n{result.stderr}"
    # 但还是落了 backtest_run,标记 DEMO 模拟
    import forgemind.core.data.storage as _sm
    _sm._DUCKDB_CONN_CACHE.clear()
    con = duckdb.connect(str(kline_db))
    row = con.execute("SELECT symbol FROM backtest_run ORDER BY ran_at DESC LIMIT 1").fetchone()
    assert row is not None
