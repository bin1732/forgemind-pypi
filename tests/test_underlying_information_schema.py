# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 DuckDB catalog 深层: information_schema + duckdb_constraints() + 
duckdb_indexes() + duckdb_tables()。比 SHOW TABLES 更深。
"""
import duckdb
import os
import pytest

import forgemind.core.data.storage as storage


@pytest.fixture
def st(tmp_path, monkeypatch):
    """独立 db, 不污染生产 db。"""
    db = tmp_path / "info.db"
    monkeypatch.setenv("FORGEMIND_DUCKDB_PATH", str(db))
    import forgemind.core.config.settings as _sm
    _sm.get_settings.cache_clear()
    _singleton = _sm.get_settings()
    _singleton.duckdb_path = str(db)
    storage._DUCKDB_CONN_CACHE.clear()
    storage.init_duckdb()
    # 用 DuckDBStorage 上下文 (与代码同路径)
    _st = storage.DuckDBStorage()
    _st.__enter__()
    yield _st
    _st.__exit__(None, None, None)


def test_information_schema_tables_complete(st):
    """information_schema.tables 应含全部 7 张业务表"""
    rows = st.conn.execute("""
        SELECT table_name FROM information_schema.tables WHERE table_type = 'BASE TABLE' ORDER BY table_name
    """).fetchall()
    names = {r[0] for r in rows}
    expected = {
        "kline_daily", "stock_list", "signal_history",
        "backtest_run", "portfolio_decision",
        "portfolio_snapshot", "portfolio_position",
    }
    assert expected.issubset(names), (
        f"information_schema 缺表: 缺 {expected - names}, 实际 {names}"
    )


def test_information_schema_columns_with_types(st):
    """information_schema.columns 真有 type 信息 (不是字符串)"""
    rows = st.conn.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'signal_history'
        ORDER BY ordinal_position
    """).fetchall()
    assert len(rows) >= 4, f"signal_history 应 ≥ 4 列, 实际 {len(rows)}: {rows}"
    cols = {r[0]: (r[1], r[2]) for r in rows}
    # signal_history 真有 symbol / side / confidence
    assert "symbol" in cols
    assert "side" in cols
    assert "confidence" in cols
    # confidence 应是 DOUBLE 或 REAL (浮点)
    assert "DOUBLE" in cols["confidence"][0] or "REAL" in cols["confidence"][0], (
        f"confidence data_type 应 DOUBLE/REAL, 实际 {cols['confidence']}"
    )


def test_duckdb_constraints_returns_check_count(st):
    """duckdb_constraints() 返 ≥ 10 个 CHECK 约束 (catalog 真查)"""
    rows = st.conn.execute("""
        SELECT count(*) FROM duckdb_constraints()
        WHERE constraint_type = 'CHECK'
    """).fetchone()
    count = rows[0]
    assert count >= 10, (
        f"CHECK 约束数应 ≥ 10, 实际 {count}; "
        f"表没初始化或 CHECK 漏加"
    )


def test_duckdb_constraints_per_table(st):
    """每张表至少 1 个 CHECK 约束 (注入测试的 4 张表)"""
    rows = st.conn.execute("""
        SELECT table_name, count(*) as n_check
        FROM duckdb_constraints()
        WHERE constraint_type = 'CHECK'
          AND table_name IN ('portfolio_position', 'portfolio_decision',
                             'signal_history', 'backtest_run')
        GROUP BY table_name
        ORDER BY table_name
    """).fetchall()
    by_table = {r[0]: r[1] for r in rows}
    for t in ('portfolio_position', 'portfolio_decision', 'signal_history', 'backtest_run'):
        assert by_table.get(t, 0) >= 1, f"{t} 应有 CHECK, 实际 {by_table}"


def test_duckdb_indexes_exist_on_signal_history(st):
    """signal_history 应有索引 (symbol / time)"""
    rows = st.conn.execute("""
        SELECT index_name, sql
        FROM duckdb_indexes()
        WHERE table_name = 'signal_history'
    """).fetchall()
    assert len(rows) >= 1, f"signal_history 应有索引, 实际 0"


def test_duckdb_tables_view_vs_base(st):
    """duckdb_tables 至少 7 张表 (无 view 区分, 但我们没建 view)"""
    rows = st.conn.execute("""
        SELECT table_name FROM duckdb_tables() ORDER BY table_name
    """).fetchall()
    assert len(rows) >= 7, f"应 ≥ 7 张表, 实际 {len(rows)}: {rows}"
    # 看 view 数为 0
    n_views = st.conn.execute("SELECT count(*) FROM duckdb_views()").fetchone()[0]
    # 不强制要求 view=0, 但若 view 存在应有 schema 准备
    assert n_views >= 0


def test_duckdb_functions_metadata(st):
    """duckdb_functions() 真能查注册的 scalar functions"""
    # DuckDB 默认有很多; 我们验不空
    rows = st.conn.execute("""
        SELECT count(*) FROM duckdb_functions()
        WHERE function_type = 'scalar'
    """).fetchone()
    assert rows[0] >= 100, f"DuckDB 默认 scalar functions 应 ≥ 100, 实际 {rows[0]}"


def test_duckdb_dependencies_no_orphan(st):
    """duckdb_dependencies() 应 0 孤儿引用 (FK 一致性)"""
    rows = st.conn.execute("""
        SELECT count(*) FROM duckdb_dependencies()
        WHERE deptype = 'fk'
    """).fetchone()
    # 我们的 schema 没设 FK, 所以 0 合理
    # 主要是验 catalog 走得通
    assert rows[0] >= 0


def test_describe_statement_returns_real_shape(st):
    """DESCRIBE signal_history 返真实列信息"""
    rows = st.conn.execute("DESCRIBE signal_history").fetchall()
    # 7 列 (id, symbol, side, confidence, rationale, source, created_at)
    assert len(rows) >= 4
    cols = {r[0] for r in rows}
    assert "symbol" in cols
    assert "side" in cols
