# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
forgemind signal CLI 真落 DuckDB signal_history
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest


@pytest.fixture
def cli_db(tmp_path, monkeypatch):
    db = tmp_path / "signal.db"
    monkeypatch.setenv("FORGEMIND_DUCKDB_PATH", str(db))

    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = str(db)
    yield db


def test_forgemind_signal_落盘_dedicated_source(cli_db):
    """forgemind signal --symbol X 落 signal_history,source=forgemind_signal_cli"""
    result = subprocess.run(
        [sys.executable, "-m", "forgemind.cli", "signal",
         "--symbol", "600519.SH", "--side", "BUY", "--confidence", "0.85",
         "--rationale", "测试落盘"],
        env={"FORGEMIND_DUCKDB_PATH": str(cli_db), "PATH": os.environ["PATH"]},
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent),
    )
    assert "signal_id" in result.stdout or "信号已落" in result.stdout, \
        f"CLI 跑失败:\n{result.stdout}\n{result.stderr}"
    # 落盘验证
    import forgemind.core.data.storage as _sm
    _sm._DUCKDB_CONN_CACHE.clear()
    con = duckdb.connect(str(cli_db))
    rows = con.execute("SELECT symbol, side, confidence, rationale, source FROM signal_history").fetchall()
    assert len(rows) == 1
    r = rows[0]
    # bare_symbol 归一化 600519.SH → 600519
    assert r[0] == "600519"
    assert r[1] == "BUY"
    assert abs(r[2] - 0.85) < 1e-6
    assert "测试落盘" in r[3]
    assert r[4] == "forgemind_signal_cli"


def test_forgemind_signal_invalid_side_rejected(cli_db):
    """--side 非法值要拒绝"""
    # 先让 db 文件存在(argparse 早退不会建表)
    import forgemind.core.data.storage as storage_mod
    storage_mod._init_done_for.clear()
    from forgemind.core.data.storage import init_duckdb
    init_duckdb()
    result = subprocess.run(
        [sys.executable, "-m", "forgemind.cli", "signal",
         "--symbol", "600519", "--side", "INVALID"],
        env={"FORGEMIND_DUCKDB_PATH": str(cli_db), "PATH": os.environ["PATH"]},
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent),
    )
    # argparse 应该 exit 2
    assert result.returncode != 0 or "invalid choice" in result.stderr.lower(), \
        f"非法 side 应该拒绝:\n{result.stdout}\n{result.stderr}"
    # 没落盘
    import forgemind.core.data.storage as _sm
    _sm._DUCKDB_CONN_CACHE.clear()
    con = duckdb.connect(str(cli_db))
    assert con.execute("SELECT count(*) FROM signal_history").fetchone()[0] == 0


def test_forgemind_signal_dotted_and_bare_symbol_both_落盘(cli_db):
    """600519.SH 和 600519 都该归一化命中同一行(去重 primary key)"""
    for sym in ("600519.SH", "600519"):
        subprocess.run(
            [sys.executable, "-m", "forgemind.cli", "signal",
             "--symbol", sym, "--side", "HOLD", "--confidence", "0.3",
             "--rationale", f"symbol={sym} 归一化测试"],
            env={"FORGEMIND_DUCKDB_PATH": str(cli_db), "PATH": os.environ["PATH"]},
            capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent),
        )
    import forgemind.core.data.storage as _sm
    _sm._DUCKDB_CONN_CACHE.clear()
    con = duckdb.connect(str(cli_db))
    rows = con.execute("SELECT DISTINCT symbol FROM signal_history").fetchall()
    # 归一化后应该都落 '600519'(可能 1 或 2 条,signal_id 不同)
    assert all(r[0] == "600519" for r in rows)
    assert len(rows) >= 1
