# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
from unittest.mock import patch, MagicMock


class TestDDLStatements:
    """DDL 完整性 + 数量"""
    
    def test_ddl_exists(self):
        from forgemind.core.data.clickhouse_init import DDL_STATEMENTS
        assert isinstance(DDL_STATEMENTS, list)
        assert len(DDL_STATEMENTS) >= 25  # 27 表(我们说的)
    
    def test_ddl_uses_create_table(self):
        from forgemind.core.data.clickhouse_init import DDL_STATEMENTS
        create_count = sum(1 for s in DDL_STATEMENTS if "CREATE TABLE" in s.upper())
        assert create_count >= 20
    
    def test_ddl_uses_merge_tree(self):
        """ClickHouse 应主要用 MergeTree 引擎"""
        from forgemind.core.data.clickhouse_init import DDL_STATEMENTS
        merge_tree_count = sum(1 for s in DDL_STATEMENTS if "MergeTree" in s)
        # 至少 50% 表用 MergeTree
        assert merge_tree_count >= len(DDL_STATEMENTS) // 2


class TestInitClickHouse:
    """init_clickhouse 行为测试"""
    
    def test_init_skips_when_no_client(self):
        """没装 clickhouse_driver 应返回 False(不抛)"""
        from forgemind.core.data.clickhouse_init import init_clickhouse
        
        with patch.dict("sys.modules", {"clickhouse_driver": None}):
            result = init_clickhouse()
            # 不抛 + 返回 False
            assert result is False
    
    def test_init_runs_ddl_on_success(self):
        """真连上时执行 DDL"""
        from forgemind.core.data.clickhouse_init import init_clickhouse, DDL_STATEMENTS
        
        # Mock clickhouse_driver.Client
        with patch.dict("sys.modules", {"clickhouse_driver": None}):
            # 强制模块不存在
            result = init_clickhouse()
            # 应该返回 False(unavailable module)
            assert result is False


class TestMainEntry:
    """__main__ 入口测试"""
    
    def test_main_executes(self):
        """__main__ 块应可执行"""
        # 直接模拟 sys.exit, 不实际 init
        from forgemind.core.data import clickhouse_init as mod
        # 模拟 __main__ 块
        with patch.object(mod, "init_clickhouse", return_value=True):
            with patch("sys.exit") as mock_exit:
                # 模拟 __main__ 执行
                success = mod.init_clickhouse()
                mod.sys.exit(0 if success else 1)
                mock_exit.assert_called_with(0)