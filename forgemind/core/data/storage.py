# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import duckdb

from forgemind.core.config.settings import get_settings
from forgemind.core.observability.logging import get_logger

logger = get_logger("forgemind.storage")


class DuckDBStorage:
    """
    DuckDB 单节点 OLAP — 给 Agent / Notebook 用

    用法:
        with DuckDBStorage() as db:
            df = db.query_df("SELECT * FROM market_data WHERE symbol = '600519.SH'")
    """

    def __init__(self, path: str | None = None):
        settings = get_settings()
        self.path = path or settings.duckdb_path
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn: duckdb.DuckDBPyConnection | None = None
        logger.info("duckdb_storage_init", path=self.path)

    def __enter__(self):
        self.conn = duckdb.connect(self.path)
        return self

    def __exit__(self, exc_type, exc_val, _exc_tb):
        if self.conn:
            if exc_type is not None:
                logger.warning(
                    "duckdb_context_exit_with_error",
                    exc_type=exc_type.__name__,
                    exc_msg=str(exc_val) if exc_val else None,
                )
            self.conn.close()
            self.conn = None

    def execute(self, sql: str, params: list | None = None):
        """执行 SQL(insert/update/ddl)"""
        if not self.conn:
            raise RuntimeError("Use within 'with' block")
        if params:
            self.conn.execute(sql, params)
        else:
            self.conn.execute(sql)

    def query_df(self, sql: str, params: list | None = None):
        """查询 → DataFrame"""
        if not self.conn:
            raise RuntimeError("Use within 'with' block")
        if params:
            return self.conn.execute(sql, params).df()
        return self.conn.execute(sql).df()

    def query_scalar(self, sql: str, params: list | None = None):
        """查询 → 单值"""
        df = self.query_df(sql, params)
        if df.empty:
            return None
        return df.iloc[0, 0]


def init_duckdb():
    """初始化 DuckDB — 创建本地表"""
    settings = get_settings()

    with DuckDBStorage() as db:
        # 本地行情(小数据量,给 Agent 用)
        db.execute("""
            CREATE TABLE IF NOT EXISTS market_data (
                date DATE,
                symbol VARCHAR,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_market_symbol_date ON market_data(symbol, date)")

        # 因子缓存
        db.execute("""
            CREATE TABLE IF NOT EXISTS factor_cache (
                feature_name VARCHAR,
                symbol VARCHAR,
                as_of DATE,
                value DOUBLE,
                computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (feature_name, symbol, as_of)
            )
        """)

        # 决策日志缓存(本地副本,主在 ClickHouse)
        db.execute("""
            CREATE TABLE IF NOT EXISTS decision_cache (
                run_id VARCHAR,
                symbol VARCHAR,
                timestamp TIMESTAMP,
                direction VARCHAR,
                quantity INTEGER,
                confidence DOUBLE,
                rationale TEXT,
                PRIMARY KEY (run_id)
            )
        """)

        logger.info("duckdb_init_complete", path=settings.duckdb_path)


if __name__ == "__main__":
    init_duckdb()
