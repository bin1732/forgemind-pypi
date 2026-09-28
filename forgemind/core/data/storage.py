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

        # 组合快照 — query_portfolio 的唯一数据来源
        # (无此表则不会返回任何编造的持仓)
        db.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshot (
                snapshot_id VARCHAR,
                taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cash DOUBLE NOT NULL,
                currency VARCHAR DEFAULT 'CNY',
                total_equity DOUBLE,
                PRIMARY KEY (snapshot_id)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_position (
                snapshot_id VARCHAR,
                symbol VARCHAR NOT NULL,
                quantity DOUBLE NOT NULL,
                avg_price DOUBLE NOT NULL,
                unrealized_pnl DOUBLE DEFAULT 0,
                PRIMARY KEY (snapshot_id, symbol)
            )
        """)

        logger.info("duckdb_init_complete", path=settings.duckdb_path)


def save_portfolio_snapshot(portfolio) -> str:
    """把一次组合状态落盘,返回 snapshot_id

    Args:
        portfolio: PortfolioContext(或任何有 cash/positions/total_equity/currency 的对象)

    供 `forgemind agent` 在每次决策后调用,让 MCP 的 query_portfolio 读到真实数据。
    """
    import uuid

    init_duckdb()
    snap_id = f"snap_{uuid.uuid4().hex[:12]}"
    with DuckDBStorage() as db:
        db.execute(
            "INSERT INTO portfolio_snapshot (snapshot_id, cash, currency, total_equity) "
            "VALUES (?, ?, ?, ?)",
            [snap_id, float(portfolio.cash), getattr(portfolio, "currency", "CNY"),
             float(getattr(portfolio, "total_equity", 0.0))],
        )
        for p in portfolio.positions:
            db.execute(
                "INSERT INTO portfolio_position "
                "(snapshot_id, symbol, quantity, avg_price, unrealized_pnl) VALUES (?, ?, ?, ?, ?)",
                [snap_id, p.symbol, float(p.quantity), float(p.avg_price),
                 float(getattr(p, "unrealized_pnl", 0.0))],
            )
    logger.info("portfolio_snapshot_saved", snapshot_id=snap_id,
                n_positions=len(portfolio.positions))
    return snap_id


def load_latest_portfolio() -> dict | None:
    """读回最新一次组合快照;没有任何快照时返回 None(绝不编造)"""
    init_duckdb()
    with DuckDBStorage() as db:
        exists = db.query_scalar(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name='portfolio_snapshot'"
        )
        if not exists:
            return None
        latest = db.query_df(
            "SELECT snapshot_id, cash, currency, total_equity FROM portfolio_snapshot "
            "ORDER BY taken_at DESC LIMIT 1"
        )
        if latest.empty:
            return None
        row = latest.iloc[0]
        pos = db.query_df(
            "SELECT symbol, quantity, avg_price, unrealized_pnl FROM portfolio_position "
            "WHERE snapshot_id = ? ORDER BY symbol",
            [row["snapshot_id"]],
        )
    positions = [
        {
            "symbol": r["symbol"],
            "quantity": float(r["quantity"]),
            "avg_price": float(r["avg_price"]),
            "unrealized_pnl": float(r["unrealized_pnl"]),
        }
        for _, r in pos.iterrows()
    ]
    return {
        "snapshot_id": row["snapshot_id"],
        "cash": float(row["cash"]),
        "currency": row["currency"],
        "total_equity": float(row["total_equity"]),
        "positions": positions,
    }


if __name__ == "__main__":
    init_duckdb()
