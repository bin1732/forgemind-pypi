# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真底层:多进程并发写 DuckDB — 真 fork, 真跑 init + save_signal

DuckDB 嵌入式 OLAP 是单写多读 — 同一时刻只允许 1 个写连接
多进程并发 init:必须串行化, 否则 "TransactionException: Catalog write-write conflict"

我们的 _init_lock + _init_done_for 是同进程串行化, 跨进程靠
DuckDB 自身的 file lock + retry

3 个进程同时 init 同 db path:
  1. 每个进程都调 init_duckdb
  2. 第一个进来拿 conn 写 DDL
  3. 后面的 catch TransactionException → 等 → 重试
  4. 全部 3 个最终都成功 (init_duckdb 幂等)

**为什么显式传 wait_for_lock=True**:DuckDB 的进程间锁是排他的,抢着
建表的后来者只能等前一个建完、放开锁。等多久由调用方决定:
init_duckdb 默认不等待(库被桌面端这类长驻进程占着时,等下去锁也不会
自己放开,让用户干等是白等);明确知道"有人正在建表"的地方才传
wait_for_lock=True。这几个用例正是那种地方。
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


def test_three_processes_init_same_db_concurrently(tmp_path):
    """3 个进程同时 init 同一 db, 全部成功"""
    db = tmp_path / "concurrent.db"

    # 3 个子进程同时跑 init_duckdb
    procs = []
    for i in range(3):
        p = subprocess.Popen(
            [sys.executable, "-c", f"""
import os
os.environ['FORGEMIND_DUCKDB_PATH'] = '{db}'
os.environ['FORGEMIND_LOG_LEVEL'] = 'WARNING'
from forgemind.core.config.settings import get_settings
get_settings.cache_clear()
from forgemind.core.data import storage
storage.init_duckdb(wait_for_lock=True)
print('PROC {i} OK', flush=True)
"""],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        procs.append((i, p))

    # 等全部
    results = []
    for i, p in procs:
        out, err = p.communicate(timeout=180)
        rc = p.returncode
        results.append((i, rc, out, err))

    # 全部应成功 (rc=0)
    for i, rc, out, err in results:
        assert rc == 0, f"proc {i} 失败 (rc={rc}): stdout={out!r} stderr={err[:500]!r}"
        assert f"PROC {i} OK" in out, f"proc {i} 应输出 PROC {i} OK, 实际: {out!r}"

    # db 应有完整 schema
    import duckdb
    con = duckdb.connect(str(db))
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    con.close()
    expected = {"stock_list", "kline_daily", "portfolio_snapshot",
                "portfolio_position", "portfolio_decision",
                "signal_history", "backtest_run"}
    assert expected.issubset(tables), f"7 张表应全在, 实际: {tables}"


def test_concurrent_save_signals_same_db(tmp_path):
    """3 个进程同时 save_signal, 都应成功 (CHECK 通过的合法值)"""
    db = tmp_path / "signal.db"

    procs = []
    for i in range(3):
        # 用 template + format, 避免嵌套 f-string
        code = (
            "import os, time\n"
            "os.environ['FORGEMIND_DUCKDB_PATH'] = '%(db)s'\n"
            "os.environ['FORGEMIND_LOG_LEVEL'] = 'WARNING'\n"
            "from forgemind.core.config.settings import get_settings\n"
            "get_settings.cache_clear()\n"
            "from forgemind.core.data import storage\n"
            "storage._DUCKDB_CONN_CACHE.clear()\n"
            "storage._init_done_for.clear()\n"
            "storage.init_duckdb(wait_for_lock=True)\n"
            "time.sleep(%(delay)s)\n"
            "storage.save_signal('sig_p%(i)d', '600519', 'BUY', %(conf)s, 'reason %(i)d', 'concurrent_test')\n"
            "print('PROC %(i)d OK', flush=True)\n"
        ) % {"db": str(db), "delay": i * 0.1, "i": i, "conf": 0.7 + i * 0.05}
        p = subprocess.Popen(
            [sys.executable, "-c", code],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        procs.append((i, p))

    for i, p in procs:
        out, err = p.communicate(timeout=180)
        assert p.returncode == 0, f"proc {i} 失败: stderr={err[:500]!r}"

    # 3 个 signal 应都在
    import duckdb
    sm_path = str(db)
    from forgemind.core.data.storage import _DUCKDB_CONN_CACHE
    _DUCKDB_CONN_CACHE.clear()
    con = duckdb.connect(sm_path)
    rows = con.execute(
        "SELECT signal_id, source FROM signal_history WHERE source = 'concurrent_test'"
    ).fetchall()
    con.close()
    assert len(rows) == 3, f"应 3 条 signal 落盘, 实际 {len(rows)}: {rows}"
    sig_ids = {r[0] for r in rows}
    expected_ids = {f"sig_p{i}" for i in range(3)}
    assert sig_ids == expected_ids, f"signal_id 集应匹配, 实际: {sig_ids}"


def test_concurrent_init_doesnt_corrupt_schema(tmp_path):
    """10 个进程同时 init, schema 完整且 CHECK 约束都在"""
    db = tmp_path / "stress.db"

    procs = []
    for i in range(10):
        p = subprocess.Popen(
            [sys.executable, "-c", f"""
import os
os.environ['FORGEMIND_DUCKDB_PATH'] = '{db}'
os.environ['FORGEMIND_LOG_LEVEL'] = 'ERROR'
from forgemind.core.config.settings import get_settings
get_settings.cache_clear()
from forgemind.core.data import storage
storage.init_duckdb(wait_for_lock=True)
print('OK', flush=True)
"""],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        procs.append(p)

    for p in procs:
        out, err = p.communicate(timeout=180)
        assert p.returncode == 0, f"subprocess 失败: {err[:300]!r}"
        assert "OK" in out

    # schema 完整
    import duckdb
    con = duckdb.connect(str(db))
    # 全部 CHECK 约束都在
    rows = con.execute("""
        SELECT table_name, COUNT(*) AS n
        FROM duckdb_constraints()
        WHERE constraint_type = 'CHECK'
        GROUP BY table_name
        ORDER BY table_name
    """).fetchall()
    con.close()
    by_table = {r[0]: r[1] for r in rows}
    for required in ("portfolio_position", "portfolio_decision",
                     "signal_history", "backtest_run"):
        assert required in by_table, (
            f"{required} 应有 CHECK, 实际分布: {by_table}"
        )
        assert by_table[required] >= 2, (
            f"{required} 应 ≥ 2 个 CHECK, 实际: {by_table[required]}"
        )
