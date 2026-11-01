# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真底层:17 个 CHECK 约束 + 路径注入测 — 不只是 surface 验"行为对"

不是看"我代码写了 CHECK",是注入非法值,看 DB 真拒绝
DuckDB ConstraintException 真抛, raise 路径真生效

10 个 CHECK 覆盖:
  portfolio_position:  chk_pos_qty (quantity > 0) + chk_pos_avg (avg_price > 0)
  portfolio_decision:  chk_dec_vote + chk_dec_score + chk_dec_conf
  signal_history:      chk_signal_side + chk_signal_conf
  backtest_run:        chk_bt_drawdown + chk_bt_winrate + chk_bt_ntrades
"""
import os

import duckdb
import pytest

# 各 CHECK 注入非法值 — 每条约束至少 1 个真违规
INJECTION = {
    "portfolio_position": [
        # (sql_suffix, why_invalid, must_contain)
        ("'snap_x', '600519', 0,    1500.0, 0",  "quantity=0",     "quantity"),
        ("'snap_x', '600519', -100, 1500.0, 0",  "quantity<0",     "quantity"),
        ("'snap_x', '600519', 100,  0,      0",  "avg_price=0",    "avg_price"),
        ("'snap_x', '600519', 100,  -1,     0",  "avg_price<0",    "avg_price"),
    ],
    "portfolio_decision": [
        # PK 是 (snapshot_id, agent), 每个 case 不同的 agent
        ("'snap_d1', 'Bull',  'INVALID_VOTE', 3.0, 0.8", "vote 不在 enum",  "vote"),
        ("'snap_d2', 'Bear',  'buy',          6.0, 0.8", "score > 5",        "score"),
        ("'snap_d3', 'PM',    'buy',         -1.0, 0.8", "score < 0",        "score"),
        ("'snap_d4', 'Tech',  'buy',          3.0, 1.5", "confidence > 1",   "confidence"),
        ("'snap_d5', 'Fund',  'buy',          3.0,-0.1", "confidence < 0",   "confidence"),
        # 合法 (NULL vote / NULL score / NULL conf 都不触发 CHECK)
        ("'snap_d6', 'Sent',  NULL,  3.0, 0.8", "NULL vote 合法",   None),
        ("'snap_d7', 'Risk',  'buy', NULL, 0.8", "NULL score 合法",  None),
    ],
    "signal_history": [
        ("'sig_x', '600519', 'WRONG_SIDE', 0.5, 'r', 'forgemind_test', '2026-01-01 00:00:00'",
         "side 不在 enum", "side"),
        ("'sig_x', '600519', 'BUY',        1.5, 'r', 'forgemind_test', '2026-01-01 00:00:00'",
         "confidence > 1", "confidence"),
        ("'sig_x', '600519', 'SELL',      -0.1, 'r', 'forgemind_test', '2026-01-01 00:00:00'",
         "confidence < 0", "confidence"),
        # side 大小写敏感: 'buy' 应拒绝
        ("'sig_x', '600519', 'buy',        0.5, 'r', 'forgemind_test', '2026-01-01 00:00:00'",
         "side 大小写敏感", "side"),
    ],
    "backtest_run": [
        # max_drawdown 必须在 [-1, 0]; 0 合法 (无亏损)
        ("'bt_x1', '2026-01-01 00:00:00', '600519.SH', 'ma_cross', 0.5,  0.0001, 0.5, 5, 0.5",
         "max_drawdown > 0",   "max_drawdown"),
        ("'bt_x2', '2026-01-01 00:00:00', '600519.SH', 'ma_cross', 0.5, -2.0,   0.5, 5, 0.5",
         "max_drawdown < -1",  "max_drawdown"),
        # win_rate 必须在 [0, 1]
        ("'bt_x3', '2026-01-01 00:00:00', '600519.SH', 'ma_cross', 0.5, -0.1,  1.5, 5, 0.5",
         "win_rate > 1",       "win_rate"),
        ("'bt_x4', '2026-01-01 00:00:00', '600519.SH', 'ma_cross', 0.5, -0.1, -0.1, 5, 0.5",
         "win_rate < 0",       "win_rate"),
        # n_trades >= 0
        ("'bt_x5', '2026-01-01 00:00:00', '600519.SH', 'ma_cross', 0.5, -0.1, 0.5, -1, 0.5",
         "n_trades < 0",       "n_trades"),
    ],
}

# 各表 INSERT 列模板
INSERT_TMPL = {
    "portfolio_position": (
        "INSERT INTO portfolio_position VALUES ({suffix})"
    ),
    "portfolio_decision": (
        "INSERT INTO portfolio_decision "
        "(snapshot_id, agent, vote, score, confidence) "
        "VALUES ({suffix})"
    ),
    "signal_history": (
        "INSERT INTO signal_history "
        "(signal_id, symbol, side, confidence, rationale, source, emitted_at) "
        "VALUES ({suffix})"
    ),
    "backtest_run": (
        "INSERT INTO backtest_run "
        "(run_id, ran_at, symbol, strategy, total_return, "
        " max_drawdown, win_rate, n_trades, sharpe) "
        "VALUES ({suffix})"
    ),
}


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """每个 test 拿干净 db + 隔离 path (三件套)"""
    db = tmp_path / "test.db"
    monkeypatch.setenv("FORGEMIND_DUCKDB_PATH", str(db))
    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = str(db)
    import forgemind.core.data.storage as sm
    sm._DUCKDB_CONN_CACHE.clear()
    sm._init_done_for.clear()
    sm.init_duckdb()
    return db


@pytest.mark.parametrize("table", list(INJECTION.keys()))
def test_all_checks_fire_at_db_level(fresh_db, table):
    """每条 CHECK 注入非法值, DB 真拒"""
    import forgemind.core.data.storage as sm
    sm._DUCKDB_CONN_CACHE.clear()
    con = duckdb.connect(str(fresh_db))

    insert_sql_tmpl = INSERT_TMPL[table]
    cases = INJECTION[table]

    fired = 0
    for sql_suffix, why, must_contain in cases:
        sql = insert_sql_tmpl.format(suffix=sql_suffix)
        if must_contain is None:
            # 合法路径 — 应当 ACCEPT
            con.execute(sql)
            continue
        try:
            con.execute(sql)
            raise AssertionError(
                f"[{table}] 非法值应被 CHECK 拒, 实际通过了: {why}\nSQL: {sql}"
            )
        except duckdb.ConstraintException as e:
            fired += 1
            # 真拒 — 错误信息要提到列名
            err = str(e)
            assert must_contain in err, (
                f"[{table}] 拒绝信息应含 '{must_contain}', 实际: {err[:200]}"
            )
        except Exception as e:
            raise AssertionError(
                f"[{table}] 应抛 ConstraintException, 实际 {type(e).__name__}: {e}\n"
                f"SQL: {sql}"
            )

    expected_fires = sum(1 for c in cases if c[2] is not None)
    assert fired == expected_fires, (
        f"[{table}] 应触发 {expected_fires} 次 CHECK 拒绝, 实际 {fired}"
    )
    con.close()


def test_checks_total_count():
    """DB 真有 10 个 CHECK 约束 (不靠源码 grep, 查 catalog)"""
    import subprocess
    db = "/tmp/test_check_count.db"
    if os.path.exists(db):
        os.remove(db)
    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = db

    import forgemind.core.data.storage as sm
    sm._DUCKDB_CONN_CACHE.clear()
    sm._init_done_for.clear()
    sm.init_duckdb()

    sm._DUCKDB_CONN_CACHE.clear()
    con = duckdb.connect(db)
    rows = con.execute("""
        SELECT table_name, constraint_name
        FROM duckdb_constraints()
        WHERE constraint_type = 'CHECK'
    """).fetchall()
    con.close()

    by_table = {}
    for table, name in rows:
        by_table.setdefault(table, []).append(name)

    # 必须每张表都有 CHECK
    for required in ("portfolio_position", "portfolio_decision",
                     "signal_history", "backtest_run"):
        assert required in by_table, (
            f"{required} 应有 CHECK, 实际表 CHECK 分布: {by_table}"
        )
    # 总数 ≥ 10
    total = sum(len(v) for v in by_table.values())
    assert total >= 10, f"CHECK 总数应 ≥ 10, 实际 {total}: {by_table}"
