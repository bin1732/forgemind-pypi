# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest


class TestDuckDB:
    def test_storage_context(self):
        from forgemind.core.data.storage import DuckDBStorage
        with DuckDBStorage() as db:
            assert db.conn is not None
        
    def test_create_and_query(self):
        from forgemind.core.data.storage import DuckDBStorage
        with DuckDBStorage() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS test_temp (
                    id INTEGER,
                    name VARCHAR
                )
            """)
            db.execute("DELETE FROM test_temp")
            db.execute("INSERT INTO test_temp VALUES (1, 'alice'), (2, 'bob')")
            df = db.query_df("SELECT * FROM test_temp ORDER BY id")
            assert len(df) == 2
            assert df.iloc[0]["name"] == "alice"
    
    def test_scalar_query(self):
        from forgemind.core.data.storage import DuckDBStorage
        with DuckDBStorage() as db:
            db.execute("CREATE TABLE IF NOT EXISTS test_temp2 (n INTEGER)")
            db.execute("DELETE FROM test_temp2")
            db.execute("INSERT INTO test_temp2 VALUES (42)")
            result = db.query_scalar("SELECT n FROM test_temp2 LIMIT 1")
            assert result == 42


class TestClickHouseInit:
    def test_ddl_count(self):
        """27+ 张表的 DDL 必须有"""
        from forgemind.core.data.clickhouse_init import DDL_STATEMENTS
        assert len(DDL_STATEMENTS) >= 27
    
    def test_ttl_compliance(self):
        """关键 TTL 必须 ≥ 20y(合规)"""
        from forgemind.core.data.clickhouse_init import DDL_STATEMENTS
        # 检查 audit_logs / live_* TTL
        audit_ddl = next(d for d in DDL_STATEMENTS if "audit_logs" in d)
        assert "20 YEAR" in audit_ddl
    
    def test_init_runs_without_ch(self):
        """ClickHouse 不可用时也能跑(不崩)"""
        from forgemind.core.data.clickhouse_init import init_clickhouse
        # 没 CH 服务 → 返回 False,但不抛异常
        result = init_clickhouse()
        # False 表示没连上,但不是 crash
        assert isinstance(result, bool)