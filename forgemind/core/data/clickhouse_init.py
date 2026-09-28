# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

from forgemind.core.config.settings import get_settings
from forgemind.core.observability.logging import get_logger

logger = get_logger("forgemind.clickhouse_init")


# 完整 DDL — 27 张表(从 §11-clickhouse-ddl.md)
DDL_STATEMENTS = [
    # ===== 行情集市 =====
    """
    CREATE TABLE IF NOT EXISTS market_data_1d (
        date Date,
        symbol String,
        open Float64,
        high Float64,
        low Float64,
        close Float64,
        volume UInt64,
        amount Float64,
        adj_factor Float64 DEFAULT 1.0
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(date)
    ORDER BY (symbol, date)
    TTL date + INTERVAL 50 YEAR
    """,
    """
    CREATE TABLE IF NOT EXISTS market_data_1m (
        timestamp DateTime,
        symbol String,
        open Float64,
        high Float64,
        low Float64,
        close Float64,
        volume UInt64
    ) ENGINE = MergeTree()
    PARTITION BY (toYYYYMM(timestamp), symbol)
    ORDER BY (symbol, timestamp)
    TTL timestamp + INTERVAL 10 YEAR
    """,
    """
    CREATE TABLE IF NOT EXISTS market_data_tick (
        timestamp DateTime64(6),
        symbol String,
        price Float64,
        volume UInt64,
        side String
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(timestamp)
    ORDER BY (symbol, timestamp)
    TTL timestamp + INTERVAL 1 YEAR
    """,
    """
    CREATE TABLE IF NOT EXISTS market_data_realtime (
        ts DateTime64(6),
        symbol String,
        bid Float64,
        ask Float64,
        last Float64,
        volume UInt64
    ) ENGINE = MergeTree()
    ORDER BY (symbol, ts)
    """,

    # ===== 因子集市 =====
    """
    CREATE TABLE IF NOT EXISTS factors (
        factor_id UUID DEFAULT generateUUIDv4(),
        factor_name String,
        factor_version UInt32 DEFAULT 1,
        description String,
        computation_hash String,
        owner_user_id UUID,
        status String DEFAULT 'ACTIVE',
        tags Map(String, String),
        created_at DateTime DEFAULT now()
    ) ENGINE = ReplacingMergeTree(created_at)
    PARTITION BY toYYYYMM(created_at)
    ORDER BY (factor_name, factor_version)
    """,
    """
    CREATE TABLE IF NOT EXISTS factor_values (
        date Date,
        factor_id UUID,
        factor_name String,
        factor_version UInt32 DEFAULT 1,
        symbol String,
        value Float64,
        computation_id UUID DEFAULT generateUUIDv4(),
        computed_at DateTime DEFAULT now()
    ) ENGINE = ReplacingMergeTree(computed_at)
    PARTITION BY (toYYYYMM(date), factor_name)
    ORDER BY (factor_name, symbol, date)
    TTL date + INTERVAL 10 YEAR
    """,
    """
    CREATE TABLE IF NOT EXISTS factor_evaluations (
        eval_id UUID DEFAULT generateUUIDv4(),
        date Date,
        factor_id UUID,
        factor_name String,
        symbol String,
        ic Float64,
        icir Float64,
        group_returns Array(Float64),
        rank_in_factor Float64
    ) ENGINE = AggregatingMergeTree()
    PARTITION BY toYYYYMM(date)
    ORDER BY (factor_name, date, symbol)
    TTL date + INTERVAL 10 YEAR
    """,

    # ===== 回测集市 =====
    """
    CREATE TABLE IF NOT EXISTS backtest_equity (
        backtest_id UUID,
        timestamp DateTime,
        equity Float64,
        cash Float64,
        position_value Float64,
        drawdown Float64
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(timestamp)
    ORDER BY (backtest_id, timestamp)
    TTL timestamp + INTERVAL 10 YEAR
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_trades (
        trade_id UUID DEFAULT generateUUIDv4(),
        backtest_id UUID,
        timestamp DateTime,
        symbol String,
        side String,
        quantity Int64,
        price Float64,
        pnl Float64 DEFAULT 0
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(timestamp)
    ORDER BY (backtest_id, timestamp)
    TTL timestamp + INTERVAL 10 YEAR
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_param_scan (
        scan_id UUID DEFAULT generateUUIDv4(),
        rank UInt32,
        params JSON,
        sharpe Float64,
        total_return Float64,
        max_drawdown Float64,
        n_trades UInt32
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(now())
    ORDER BY (scan_id, rank)
    TTL now() + INTERVAL 10 YEAR
    """,

    # ===== 实盘集市(TTL 已纠为 20y)=====
    """
    CREATE TABLE IF NOT EXISTS live_orders (
        order_id UUID DEFAULT generateUUIDv4(),
        client_order_id String,
        user_id UUID,
        strategy_id UUID,
        session_id UUID,
        symbol String,
        side String,
        quantity Int64,
        price Nullable(Float64),
        order_type String DEFAULT 'MARKET',
        status String DEFAULT 'PENDING',
        broker_order_id String,
        created_at DateTime DEFAULT now(),
        updated_at DateTime DEFAULT now(),
        o32_tag UInt32 DEFAULT 0
    ) ENGINE = ReplacingMergeTree(updated_at)
    PARTITION BY (toYYYYMM(created_at), user_id)
    ORDER BY (user_id, session_id, created_at)
    TTL created_at + INTERVAL 20 YEAR
    """,
    """
    CREATE TABLE IF NOT EXISTS live_trades (
        trade_id UUID DEFAULT generateUUIDv4(),
        order_id UUID,
        user_id UUID,
        strategy_id UUID,
        session_id UUID,
        symbol String,
        side String,
        quantity Int64,
        price Float64,
        commission Float64 DEFAULT 0,
        slippage_bps Float32 DEFAULT 0,
        executed_at DateTime DEFAULT now()
    ) ENGINE = MergeTree()
    PARTITION BY (toYYYYMM(executed_at), user_id)
    ORDER BY (user_id, session_id, executed_at)
    TTL executed_at + INTERVAL 20 YEAR
    """,
    """
    CREATE TABLE IF NOT EXISTS live_positions (
        snapshot_id UUID DEFAULT generateUUIDv4(),
        user_id UUID,
        strategy_id UUID,
        session_id UUID,
        symbol String,
        date Date,
        quantity Int64,
        avg_price Float64,
        market_price Float64,
        unrealized_pnl Float64 DEFAULT 0,
        realized_pnl Float64 DEFAULT 0
    ) ENGINE = SummingMergeTree()
    PARTITION BY (toYYYYMM(date), user_id)
    ORDER BY (user_id, session_id, symbol, date)
    TTL date + INTERVAL 20 YEAR
    """,
    """
    CREATE TABLE IF NOT EXISTS live_pnl (
        snapshot_id UUID DEFAULT generateUUIDv4(),
        user_id UUID,
        strategy_id UUID,
        session_id UUID,
        timestamp DateTime,
        cash Float64,
        equity Float64,
        realized_pnl Float64 DEFAULT 0,
        unrealized_pnl Float64 DEFAULT 0
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(timestamp)
    ORDER BY (user_id, session_id, timestamp)
    TTL timestamp + INTERVAL 20 YEAR
    """,
    """
    CREATE TABLE IF NOT EXISTS live_signals (
        signal_id UUID DEFAULT generateUUIDv4(),
        user_id UUID,
        strategy_id UUID,
        symbol String,
        timestamp DateTime,
        direction String,
        strength Float64,
        confidence Float64,
        source String,
        rationale String DEFAULT ''
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(timestamp)
    ORDER BY (strategy_id, timestamp)
    TTL timestamp + INTERVAL 20 YEAR
    """,

    # ===== ML 集市 =====
    """
    CREATE TABLE IF NOT EXISTS ml_models (
        model_id UUID DEFAULT generateUUIDv4(),
        model_name String,
        version UInt32 DEFAULT 1,
        status String DEFAULT 'STAGING',
        features Array(UUID),
        feature_importance JSON,
        metrics JSON,
        tags Map(String, String),
        created_at DateTime DEFAULT now(),
        updated_at DateTime DEFAULT now()
    ) ENGINE = ReplacingMergeTree(updated_at)
    ORDER BY (model_name, version)
    """,
    """
    CREATE TABLE IF NOT EXISTS model_predictions (
        prediction_id UUID DEFAULT generateUUIDv4(),
        model_id UUID,
        timestamp DateTime,
        symbol String,
        prediction Float64,
        actual Nullable(Float64),
        feature_values JSON,
        feature_contributions JSON
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(timestamp)
    ORDER BY (model_id, timestamp)
    TTL timestamp + INTERVAL 20 YEAR
    """,

    # ===== 系统集市(TTL 已纠为 20y)=====
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        audit_id UUID DEFAULT generateUUIDv4(),
        event_type String,
        actor_id UUID,
        target_id UUID,
        payload JSON,
        hash_chain String,
        timestamp DateTime DEFAULT now()
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(timestamp)
    ORDER BY (event_type, timestamp)
    TTL timestamp + INTERVAL 20 YEAR
    """,
    """
    CREATE TABLE IF NOT EXISTS system_events (
        event_id UUID DEFAULT generateUUIDv4(),
        event_type String,
        severity String DEFAULT 'INFO',
        source String,
        message String,
        metadata JSON,
        timestamp DateTime DEFAULT now()
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(timestamp)
    ORDER BY (event_type, timestamp)
    TTL timestamp + INTERVAL 90 DAY
    """,
    """
    CREATE TABLE IF NOT EXISTS task_runs (
        run_id UUID DEFAULT generateUUIDv4(),
        task_name String,
        status String,
        started_at DateTime DEFAULT now(),
        ended_at Nullable(DateTime),
        duration_ms UInt64 DEFAULT 0,
        error Nullable(String)
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(started_at)
    ORDER BY (task_name, started_at)
    TTL started_at + INTERVAL 90 DAY
    """,

    # ===== 影子交易(§28)=====
    """
    CREATE TABLE IF NOT EXISTS shadow_traders (
        shadow_id UUID,
        strategy_id UUID,
        live_broker String,
        capital Float64,
        status String DEFAULT 'RUNNING',
        started_at DateTime DEFAULT now(),
        stopped_at Nullable(DateTime)
    ) ENGINE = ReplacingMergeTree(started_at)
    ORDER BY shadow_id
    """,
    """
    CREATE TABLE IF NOT EXISTS shadow_fills (
        fill_id UUID DEFAULT generateUUIDv4(),
        shadow_id UUID,
        symbol String,
        side String,
        quantity Float64,
        price Float64,
        commission Float64 DEFAULT 0,
        tick_price Float64,
        slippage_bps Float32,
        is_virtual UInt8 DEFAULT 1,
        timestamp DateTime DEFAULT now()
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(timestamp)
    ORDER BY (shadow_id, timestamp)
    TTL timestamp + INTERVAL 20 YEAR
    """,
    """
    CREATE TABLE IF NOT EXISTS shadow_pnl_comparisons (
        comparison_id UUID DEFAULT generateUUIDv4(),
        shadow_id UUID,
        shadow_total_pnl Float64,
        live_total_pnl Float64,
        diff_pnl Float64,
        diff_pct Float32,
        shadow_sharpe Float32,
        live_sharpe Float32,
        compared_at DateTime DEFAULT now()
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(compared_at)
    ORDER BY (shadow_id, compared_at)
    TTL compared_at + INTERVAL 20 YEAR
    """,

    # ===== 多账户 / PB / O32(§26)=====
    """
    CREATE TABLE IF NOT EXISTS sub_accounts (
        sub_account_id UUID,
        parent_account_id UUID,
        name String,
        strategy_id UUID,
        pm_user_id UUID,
        max_position_value Float64,
        max_daily_trades UInt32,
        allowed_symbols Array(String),
        regulatory_purpose String,
        created_at DateTime DEFAULT now()
    ) ENGINE = ReplacingMergeTree(created_at)
    ORDER BY sub_account_id
    """,
    """
    CREATE TABLE IF NOT EXISTS pb_units (
        unit_id UUID,
        broker String,
        pb_account String,
        unit_code String,
        sub_account_id UUID,
        max_orders_per_second UInt32 DEFAULT 30,
        max_daily_orders UInt32 DEFAULT 50000,
        twap_enabled UInt8 DEFAULT 1,
        vwap_enabled UInt8 DEFAULT 1,
        created_at DateTime DEFAULT now()
    ) ENGINE = ReplacingMergeTree(created_at)
    ORDER BY unit_id
    """,
    """
    CREATE TABLE IF NOT EXISTS kill_switch_events (
        event_id UUID DEFAULT generateUUIDv4(),
        trigger_type String,
        triggered_at DateTime DEFAULT now(),
        triggered_by Nullable(UUID),
        state JSON,
        reset_by Nullable(UUID),
        reset_at Nullable(DateTime),
        reset_reason String DEFAULT ''
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(triggered_at)
    ORDER BY triggered_at
    TTL triggered_at + INTERVAL 20 YEAR
    """,

    # ===== Feature Store(§27)=====
    """
    CREATE TABLE IF NOT EXISTS feature_definitions (
        feature_id UUID,
        feature_name String,
        feature_version UInt32 DEFAULT 1,
        description String DEFAULT '',
        source_table String,
        source_columns Array(String),
        computation_hash String,
        entity_type String DEFAULT 'symbol',
        status String DEFAULT 'ACTIVE',
        owner_user_id UUID,
        tags Map(String, String),
        created_at DateTime DEFAULT now(),
        updated_at DateTime DEFAULT now(),
        deprecated_at Nullable(DateTime)
    ) ENGINE = ReplacingMergeTree(updated_at)
    PARTITION BY toYYYYMM(created_at)
    ORDER BY (feature_name, feature_version)
    """,
    """
    CREATE TABLE IF NOT EXISTS feature_lineage_events (
        event_id UUID DEFAULT generateUUIDv4(),
        event_type String,
        feature_id UUID,
        feature_version UInt32 DEFAULT 1,
        consumer_type String,
        consumer_id Nullable(UUID),
        consumer_version UInt32 DEFAULT 1,
        metadata JSON,
        event_time DateTime DEFAULT now()
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(event_time)
    ORDER BY (feature_id, event_time)
    TTL event_time + INTERVAL 20 YEAR
    """,
    """
    CREATE TABLE IF NOT EXISTS feature_offline_online_parity (
        check_id UUID DEFAULT generateUUIDv4(),
        feature_id UUID,
        feature_version UInt32,
        symbol String,
        online_value Float64,
        offline_value Float64,
        diff_pct Float32,
        is_consistent UInt8,
        threshold_pct Float32 DEFAULT 0.01,
        is_alert UInt8 DEFAULT 0,
        check_time DateTime DEFAULT now()
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(check_time)
    ORDER BY (feature_id, check_time)
    TTL check_time + INTERVAL 20 YEAR
    """,

    # ===== 字典 =====
    """
    CREATE TABLE IF NOT EXISTS dict_symbols (
        symbol String,
        name String,
        market String,
        exchange String,
        is_active UInt8 DEFAULT 1,
        listing_date Date,
        delisting_date Nullable(Date)
    ) ENGINE = MergeTree()
    ORDER BY symbol
    """,
]


def init_clickhouse():
    """初始化 ClickHouse — 执行所有 DDL"""
    settings = get_settings()

    try:
        from clickhouse_driver import Client
        client = Client(
            host=settings.ch_host,
            port=settings.ch_port,
            user=settings.ch_user,
            password=settings.ch_password,
            database=settings.ch_database,
        )
    except Exception as e:
        logger.warning(
            "clickhouse_unavailable",
            host=settings.ch_host,
            port=settings.ch_port,
            error=str(e),
            hint="Will generate SQL only, not execute",
        )
        return False

    # 先确保数据库存在
    try:
        client.execute(f"CREATE DATABASE IF NOT EXISTS {settings.ch_database}")
        logger.info("clickhouse_database_created", database=settings.ch_database)
    except Exception as e:
        logger.error("clickhouse_database_create_failed", error=str(e))
        return False

    # 执行所有 DDL
    success_count = 0
    for i, ddl in enumerate(DDL_STATEMENTS, 1):
        try:
            client.execute(ddl)
            success_count += 1
        except Exception as e:
            # 已经存在不算错
            if "already exists" in str(e).lower():
                success_count += 1
                continue
            logger.error(
                "clickhouse_ddl_failed",
                ddl_index=i,
                error=str(e),
                ddl_preview=ddl[:100],
            )

    # 验证 — 列出表
    tables = client.execute("SHOW TABLES")
    logger.info(
        "clickhouse_init_complete",
        tables_created=success_count,
        total_tables=len(tables),
        tables=[t[0] for t in tables],
    )
    return True


if __name__ == "__main__":
    success = init_clickhouse()
    sys.exit(0 if success else 1)