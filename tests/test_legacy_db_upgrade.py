# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""老库升级:老版本建的库,新代码接手时不能出问题。

真实用户是从旧版本一路升上来的,库里留着旧版本建的东西。这里把旧版
的库原样造出来,再用新代码的初始化流程接手,确认数据还在、重复的索引
被清掉、缺的那一列被补上。
"""

from __future__ import annotations

import duckdb
import pytest

from forgemind.core.data.storage import DuckDBStorage, create_market_tables


def _legacy_db(path) -> set[str]:
    """造一个旧版本留下的库:同样的表,旧名字的索引,没有 provider 列。"""
    con = duckdb.connect(str(path))
    con.execute("""
        CREATE TABLE IF NOT EXISTS stock_list (
            symbol VARCHAR PRIMARY KEY,
            name VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS kline_daily (
            date DATE,
            symbol VARCHAR,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume BIGINT,
            PRIMARY KEY (date, symbol)
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_kline_symbol ON kline_daily(symbol, date)")
    con.execute(
        "INSERT INTO kline_daily VALUES (DATE '2024-01-02', '600519', "
        "10.0, 11.0, 9.0, 10.5, 100)"
    )
    con.execute("INSERT INTO stock_list VALUES ('600519', '贵州茅台')")
    names = {
        r[0] for r in con.execute(
            "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'kline_daily'"
        ).fetchall()
    }
    con.close()
    return names


def _index_names(db) -> set[str]:
    """用存储层自己的连接查索引 —— 同一个库文件不能另开一个配置不同的连接。"""
    rows = db.query_df(
        "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'kline_daily'"
    )
    return set(rows["index_name"].tolist())


class TestUpgradeFromLegacyDatabase:
    def test_legacy_index_is_dropped(self, tmp_path):
        """同列的旧索引要清掉,否则写入放大一倍。"""
        db_path = tmp_path / "legacy.db"
        assert "idx_kline_symbol" in _legacy_db(db_path)

        with DuckDBStorage(db_path) as db:
            create_market_tables(db)
            names = _index_names(db)
        assert "idx_kline_symbol" not in names, "旧索引还在,写入会放大"
        assert "idx_kline_symbol_date" in names, "新索引没建上"

    def test_missing_provider_column_is_added(self, tmp_path):
        """老库缺的那一列要补上。"""
        db_path = tmp_path / "legacy.db"
        _legacy_db(db_path)
        with DuckDBStorage(db_path) as db:
            create_market_tables(db)
            cols = set(db.query_df("SELECT * FROM kline_daily LIMIT 0").columns)
        assert "provider" in cols

    def test_existing_rows_survive(self, tmp_path):
        """升级不能动用户已有的数据。"""
        db_path = tmp_path / "legacy.db"
        _legacy_db(db_path)
        with DuckDBStorage(db_path) as db:
            create_market_tables(db)
            rows = db.query_scalar("SELECT COUNT(*) FROM kline_daily")
            names = db.query_scalar("SELECT COUNT(*) FROM stock_list")
        assert rows == 1, "老数据被弄没了"
        assert names == 1, "代码表被弄没了"

    def test_running_twice_is_idempotent(self, tmp_path):
        """初始化会跑很多次,重复跑不能出错。"""
        db_path = tmp_path / "legacy.db"
        _legacy_db(db_path)
        with DuckDBStorage(db_path) as db:
            create_market_tables(db)
            create_market_tables(db)
            names = _index_names(db)
        assert names == {"idx_kline_symbol_date"}, f"索引不对: {names}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
