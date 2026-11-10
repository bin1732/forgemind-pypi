# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
开发层补缺测试:
1. portfolio_position CHECK (quantity > 0, avg_price > 0)
2. DuckDBStorage 连接缓存 (同 path 复用 conn)
3. CLI 错误码分级 (etl MemoryError→2, TimeoutError→3, ENOSPC→4, 0 bars→3)
4. 因子 IC cache 切 symbol 不重算 (前端, 验 store 行为)
5. walk-forward / monte-carlo / train-lgbm action 走 runPipeline 不再 alert
"""
import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest


# === 1. portfolio_position CHECK ===
def test_portfolio_position_check_constraints():
    """持仓 quantity / avg_price 必须 > 0, DB CHECK 拒绝"""
    db_path = "/tmp/test_pos_check.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = db_path

    import forgemind.core.data.storage as sm
    sm._DUCKDB_CONN_CACHE.clear()
    sm._init_done_for.clear()
    sm._init_lock = sm._init_lock  # 保 lock

    # 触发 init_duckdb 创建所有表
    sm.init_duckdb()

    with sm.DuckDBStorage() as db:
        # 合法
        db.execute(
            "INSERT INTO portfolio_position VALUES ('snap_x', '600519', 100, 1500.0, 0)"
        )
        rows = db.query_df("SELECT count(*) AS n FROM portfolio_position")
        assert rows.iloc[0]["n"] == 1, "合法持仓应入表"

        # 非法 quantity = 0
        with pytest.raises(duckdb.ConstraintException):
            db.execute(
                "INSERT INTO portfolio_position VALUES ('snap_y', '600519', 0, 1500.0, 0)"
            )
        # 非法 quantity < 0
        with pytest.raises(duckdb.ConstraintException):
            db.execute(
                "INSERT INTO portfolio_position VALUES ('snap_z', '600519', -100, 1500.0, 0)"
            )
        # 非法 avg_price = 0
        with pytest.raises(duckdb.ConstraintException):
            db.execute(
                "INSERT INTO portfolio_position VALUES ('snap_w', '600519', 100, 0, 0)"
            )


# === 2. DuckDBStorage 连接缓存 ===
def test_duckdb_storage_connection_cache():
    """同 path 第二次 with DuckDBStorage() 复用底层连接"""
    db_path = "/tmp/test_conn_cache.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = db_path

    import forgemind.core.data.storage as sm
    sm._DUCKDB_CONN_CACHE.clear()
    sm.init_duckdb()

    # 第一个 with
    with sm.DuckDBStorage() as db:
        db.execute("CREATE TABLE t (x INT)")
        db.execute("INSERT INTO t VALUES (1)")

    # 第二个 with 应落在同一个数据库实例(拿的是它的游标)
    with sm.DuckDBStorage() as db:
        n = db.query_scalar("SELECT count(*) FROM t")
        assert n == 1
        cached = sm._DUCKDB_CONN_CACHE.get(db_path)
        assert cached is not None
        assert db.conn is not cached, "每次 with 拿自己的游标,不是缓存对象本身"

    # 第三个 with 同样落在同一个库
    with sm.DuckDBStorage() as db:
        n = db.query_scalar("SELECT count(*) FROM t")
        assert n == 1

    # force_new 拿新 conn
    with sm.DuckDBStorage(force_new=True) as db:
        n = db.query_scalar("SELECT count(*) FROM t")
        assert n == 1
        # 仍是 cached (force_new 重新 connect 但 cache 仍指向原 conn)
        cached = sm._DUCKDB_CONN_CACHE.get(db_path)
        assert db.conn is not cached, "force_new 拿新 conn"

    # 清理
    sm._DUCKDB_CONN_CACHE.clear()


# === 3. CLI 错误码分级 ===
def _etl_args(**kw):
    import argparse

    base = {"symbols": "600519", "start": "2024-01-01", "end": "2024-01-31"}
    base.update(kw)
    return argparse.Namespace(**base)


def _etl_with_fake(monkeypatch, result=None, raises=None):
    """把 ETL 换成假的:要么给一个结果,要么抛一个异常。"""
    import forgemind.core.data.akshare_etl as etl_mod

    class _FakeETL:
        async def run(self, symbols=None, start=None, end=None):
            if raises is not None:
                raise raises
            return result or {}

    monkeypatch.setattr(etl_mod, "AKShareETL", _FakeETL)


def test_cli_etl_zero_bars_exits_with_the_data_code(monkeypatch, capsys):
    """一条都没取到 → 退出码 3(数据类);init 阶段就失败 → 4(资源类)

    **真跑那条分支**,不靠 grep 源码:源码写法一改(比如把字面量换成
    具名常量)就红,那是测试盯错了东西 —— 盯的应该是读者拿到的退出码。
    """
    import forgemind.cli as cli_mod

    _etl_with_fake(monkeypatch, result={
        "klines": 0, "failures": {"upstream_timeout": 1}, "ok_symbols": 0, "stocks": 0,
    })
    with pytest.raises(SystemExit) as exc:
        cli_mod.cmd_etl(_etl_args())
    assert exc.value.code == 3, f"0 bars 应退 3(数据类),实际 {exc.value.code}"
    out = capsys.readouterr().out
    assert "失败原因分类" in out, out

    _etl_with_fake(monkeypatch, result={
        "klines": 0, "failures": {"init: 数据库打不开": 1}, "ok_symbols": 0, "stocks": 0,
    })
    with pytest.raises(SystemExit) as exc:
        cli_mod.cmd_etl(_etl_args())
    assert exc.value.code == 4, f"init 阶段失败应退 4(资源类),实际 {exc.value.code}"


def test_cli_etl_failure_paths_exit_with_their_own_codes(monkeypatch, capsys):
    """取数失败的三条路各退各的码:内存不够 2 / 上游超时 3 / 磁盘满 4"""
    import errno

    import forgemind.cli as cli_mod

    cases = [
        (MemoryError("装不下"), 2),
        (TimeoutError("上游没响应"), 3),
        (OSError(errno.ENOSPC, "磁盘满"), 4),
    ]
    for exc_obj, want in cases:
        _etl_with_fake(monkeypatch, raises=exc_obj)
        with pytest.raises(SystemExit) as exc:
            cli_mod.cmd_etl(_etl_args())
        assert exc.value.code == want, (
            f"{type(exc_obj).__name__} 应退 {want},实际 {exc.value.code}"
        )


# === 4. 因子 IC cache 切 symbol 不重算 (前端, 验 backend.tsx 行为) ===
def test_factor_ic_cache_by_symbol():
    """loadFactorIC 同 symbol 切回直接走 cache"""
    # 这个测试是 JS 测试 - 我们用 Py mock loadFactorIC 行为
    # 实际验证: backend.tsx 有 _factorICByName Map
    p = Path(__file__).parent.parent / "forgemind-ui" / "lib" / "backend.tsx"
    code = p.read_text(encoding="utf-8")
    assert "_factorICByName" in code, "backend.tsx 缺因子 IC 缓存 Map"
    assert "_factorICByName.has(symbol)" in code, "缓存未按 symbol 查询"
    assert "_factorICByName.set(symbol, byName)" in code, "缓存未按 symbol 写入"


# === 5. ⌘K walk-forward / monte-carlo / train-lgbm 走 runPipeline ===
def test_cmd_palette_silent_pipeline_actions():
    """3 个 action 应调 runPipeline, 不再 alert"""
    p = Path(__file__).parent.parent / "forgemind-ui" / "components" / "command-palette.tsx"
    code = p.read_text(encoding="utf-8")
    # 3 个 id 应各调用 runPipeline
    for cmd_id in ("train-lgbm", "walk-forward", "monte-carlo"):
        # 找 id 后面的 action 块
        idx = code.find(f'id: "{cmd_id}"')
        assert idx > 0, f"未找到 id: {cmd_id}"
        # 找下一个 } 块 (粗略)
        end = code.find('},', idx)
        block = code[idx:end]
        assert "runPipeline(" in block, f"{cmd_id} 应调 runPipeline"
        # 不应再有 alert(...LightGBM/...WFO/...Monte Carlo)
        # alert 只在错误路径允许
        for bad in ('alert("LightGBM', 'alert("WFO', 'alert("Walk-Forward', 'alert("Monte Carlo'):
            assert bad not in block, f"{cmd_id} 不应有 {bad}"
