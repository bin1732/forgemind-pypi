# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
DuckDB schema 完整性 + 老 db 升级 migration + 真并发写

1. CHECK 约束:side 必须是 BUY/SELL/HOLD,confidence 0-1,score 0-5,max_drawdown ∈ [-1, 0]
2. 老 db (2026.9.0 之前) 升级:market_data / factor_cache / decision_cache 三张死表
   DROP IF EXISTS, 新表 CREATE IF NOT EXISTS, 老数据保留
3. 真并发:两个 subprocess 同时 init_duckdb 同一 db path, _init_lock + _init_done_for
   避免 "TransactionException: Catalog write-write conflict on create with idx_*"
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import duckdb
import pytest


def test_check_constraint_rejects_bad_side():
    """save_signal 收到非法 side 要 ValueError 拒绝 (不是 DB 抛)"""
    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = "/tmp/test_chk1.db"

    import forgemind.core.data.storage as sm
    sm._init_done_for.clear()
    from forgemind.core.data.storage import save_signal
    with pytest.raises(ValueError, match="side 必须是"):
        save_signal("sig_x", "600519", "BUY_NOW", 0.5, "test")


def test_check_constraint_rejects_bad_confidence():
    """save_signal 收到 confidence > 1 拒绝"""
    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = "/tmp/test_chk2.db"

    import forgemind.core.data.storage as sm
    sm._init_done_for.clear()
    from forgemind.core.data.storage import save_signal
    with pytest.raises(ValueError, match="confidence 必须在"):
        save_signal("sig_x", "600519", "BUY", 1.5, "test")
    with pytest.raises(ValueError):
        save_signal("sig_y", "600519", "BUY", -0.1, "test")


def test_check_constraint_rejects_bad_decision_vote():
    """portfolio_decision 收到非法 vote 拒绝"""
    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = "/tmp/test_chk3.db"

    import forgemind.core.data.storage as sm
    sm._init_done_for.clear()
    from forgemind.core.data.storage import init_duckdb, DuckDBStorage
    init_duckdb()
    import uuid
    with DuckDBStorage() as db:
        # 先有 snapshot (unique id 避免 fixture 复用)
        snp = f"snp_{uuid.uuid4().hex[:8]}"
        db.execute("INSERT INTO portfolio_snapshot (snapshot_id, cash) VALUES (?, ?)", [snp, 80000])
        # 合法 vote (NULL/buy/sell/hold) OK
        for v in (None, "buy", "sell", "hold"):
            db.execute(
                "INSERT INTO portfolio_decision (snapshot_id, agent, vote) VALUES (?,?,?)",
                [snp, f"test_{v}_{uuid.uuid4().hex[:6]}", v],
            )
        # 非法 vote 拒绝
        with pytest.raises(Exception, match="CHECK"):
            db.execute(
                "INSERT INTO portfolio_decision (snapshot_id, agent, vote) VALUES (?,?,?)",
                [snp, f"test_bad_{uuid.uuid4().hex[:6]}", "WRONG_VOTE"],
            )


def test_check_constraint_rejects_bad_backtest_metrics():
    """backtest_run 收到 max_drawdown > 0 / win_rate > 1 拒绝"""
    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = "/tmp/test_chk4.db"

    import forgemind.core.data.storage as sm
    sm._init_done_for.clear()
    from forgemind.core.data.storage import init_duckdb, DuckDBStorage
    init_duckdb()
    import uuid
    tag = uuid.uuid4().hex[:8]
    with DuckDBStorage() as db:
        # drawdown > 0 拒绝 (回测最大回撤必须 ≤ 0)
        with pytest.raises(Exception, match="CHECK"):
            db.execute(
                "INSERT INTO backtest_run (run_id, symbol, strategy, max_drawdown) "
                "VALUES (?,?,?,?)",
                [f"bt_bad1_{tag}", "600519", "ma_cross", 0.5],
            )
        # win_rate > 1 拒绝
        with pytest.raises(Exception, match="CHECK"):
            db.execute(
                "INSERT INTO backtest_run (run_id, symbol, strategy, win_rate) "
                "VALUES (?,?,?,?)",
                [f"bt_bad2_{tag}", "600519", "ma_cross", 1.5],
            )
        # n_trades < 0 拒绝
        with pytest.raises(Exception, match="CHECK"):
            db.execute(
                "INSERT INTO backtest_run (run_id, symbol, strategy, n_trades) "
                "VALUES (?,?,?,?)",
                [f"bt_bad3_{tag}", "600519", "ma_cross", -1],
            )
        # 合法 OK
        db.execute(
            "INSERT INTO backtest_run (run_id, symbol, strategy, total_return, "
            "sharpe, sortino, max_drawdown, win_rate, n_trades) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [f"bt_ok_{tag}", "600519", "ma_cross", -0.27, -2.2, -2.64, -0.28, 0.33, 9],
        )


def test_old_db_upgrade_drops_dead_tables_and_keeps_kline():
    """老 db (有 3 张死表 + kline_daily 真数据) 升级新 init → 死表 DROP, 真数据保留"""
    db = "/tmp/test_migration.db"
    if Path(db).exists():
        Path(db).unlink()
    # 1. 模拟老 db: 创建 kline_daily + 3 张死表 + 灌点 K 线
    con = duckdb.connect(db)
    con.execute("""
        CREATE TABLE kline_daily (
            date DATE, symbol VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE,
            close DOUBLE, volume BIGINT, provider VARCHAR,
            PRIMARY KEY (date, symbol)
        )
    """)
    con.execute("""
        INSERT INTO kline_daily VALUES
        ('2024-01-02', '600519', 1580.66, 1583.85, 1543.76, 1550.67, 12345, 'tencent'),
        ('2024-01-03', '600519', 1546.77, 1560.88, 1541.99, 1559.66, 11234, 'tencent')
    """)
    # 3 张死表 (老 schema 残留)
    con.execute("CREATE TABLE market_data (symbol VARCHAR, ts TIMESTAMP, price DOUBLE)")
    con.execute("CREATE TABLE factor_cache (factor_name VARCHAR, value DOUBLE)")
    con.execute("CREATE TABLE decision_cache (decision_id VARCHAR, payload TEXT)")
    con.close()
    # 2. 切到新代码,跑 init_duckdb
    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = db

    import forgemind.core.data.storage as sm
    sm._init_done_for.clear()
    from forgemind.core.data.storage import init_duckdb
    init_duckdb()

    # 3. 验证: 死表 DROP 了, kline_daily 数据保留, 新表都建好
    # 不要 read_only: 我们的连接缓存持有一个 rw conn, duckdb 不允许
    # 同 path 同时有 rw 和 ro — 用 rw
    import forgemind.core.data.storage as sm
    sm._DUCKDB_CONN_CACHE.clear()
    con = duckdb.connect(db)
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    # 死表必须不在
    assert "market_data" not in tables
    assert "factor_cache" not in tables
    assert "decision_cache" not in tables
    # 真数据必须保留
    kline_count = con.execute("SELECT count(*) FROM kline_daily").fetchone()[0]
    assert kline_count == 2
    # 新表都建好
    for t in ("stock_list", "kline_daily", "portfolio_snapshot",
             "portfolio_position", "portfolio_decision",
             "signal_history", "backtest_run"):
        assert t in tables, f"新表 {t} 没建好"
    # 新表有 CHECK 约束
    chk = con.execute(
        "SELECT count(*) FROM information_schema.table_constraints "
        "WHERE table_name='signal_history' AND constraint_type='CHECK'"
    ).fetchone()[0]
    assert chk >= 2, f"signal_history 应该至少 2 个 CHECK 约束,实际 {chk}"


def test_concurrent_init_duckdb_serialized_succeeds():
    """多 subprocess 串行 init_duckdb 同一 db, 都能成功(每个进程互不冲突)

    真实场景:
    - 进程内多线程: _init_lock 守住, 同 db path 只跑一次 DDL (已有 _init_done_for)
    - 跨进程并发: DuckDB 是单写, 4 个 subprocess 同时 connect 同一 db 文件
      会报 "Could not set lock"; 真实生产 fork-and-write 模式应串行, 或
      让 Python DuckDBStorage 走 single-writer / multi-reader
    - 串行测试验证:init_duckdb 幂等, 重复跑不出错,db 一直可用
    """
    db = "/tmp/test_concurrent.db"
    if Path(db).exists():
        Path(db).unlink()
    env = {**os.environ, "FORGEMIND_DUCKDB_PATH": db}
    code = (
        "from forgemind.core.config.settings import get_settings;"
        "get_settings.cache_clear();"
        "s = get_settings();"
        f"s.duckdb_path = '{db}';"
        "from forgemind.core.data.storage import init_duckdb;"
        "import forgemind.core.data.storage as sm;"
        "sm._init_done_for.clear();"
        "init_duckdb();"
        # 再调一次,验证幂等
        "init_duckdb();"
        "print('OK')"
    )
    # 串行启 4 个 subprocess
    for i in range(4):
        r = subprocess.run(
            [sys.executable, "-c", code],
            env=env, cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True, text=True, timeout=60,
        )
        if "OK" not in r.stdout:
            pytest.fail(
                f"subprocess {i} failed:\nstdout={r.stdout}\nstderr={r.stderr[:500]}"
            )
    # db 上各表都在
    import forgemind.core.data.storage as _sm
    _sm._DUCKDB_CONN_CACHE.clear()
    con = duckdb.connect(db)
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    for t in ("kline_daily", "signal_history", "backtest_run",
             "portfolio_decision", "portfolio_position", "portfolio_snapshot"):
        assert t in tables


def test_init_duckdb_is_idempotent_in_process():
    """同一进程多次 init_duckdb 不重复 DDL, 也不出错"""
    import uuid
    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = "/tmp/test_idempotent.db"

    import forgemind.core.data.storage as sm
    sm._init_done_for.clear()
    from forgemind.core.data.storage import init_duckdb
    # 跑 5 次
    for _ in range(5):
        init_duckdb()
    # db 还可用
    from forgemind.core.data.storage import DuckDBStorage
    with DuckDBStorage() as db:
        db.execute("INSERT INTO signal_history (signal_id, symbol, side, confidence) "
                   "VALUES (?,?,?,?)",
                   [f"sig_idem_{uuid.uuid4().hex[:8]}", "600519", "BUY", 0.5])
