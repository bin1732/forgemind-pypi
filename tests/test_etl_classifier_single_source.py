# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""ETL 异常分类器在类内路径与模块级路径上必须给出同一结论。

`forgemind.core.data.akshare_etl` 同时提供模块级 `_classify_fetch_error`
与 `AKShareDataSource._classify_fetch_error`。两处曾各留一份实现:类内那份只按
异常消息文本匹配,把 DuckDB 的并发锁、权限、磁盘满一并报成网络问题,用户
看不到"另一个进程正占用数据库文件"这类可行动指引。模块级那份按异常类型
分类,结论正确。

本测试固定住"类内与模块级必须同源"这一约束:类内入口与模块级入口对
同一异常必须给出完全相同的结论,且都不得把 DuckDB 的三类并发写错误
归到网络或未分类。
"""
import duckdb
import pytest

from forgemind.core.data.akshare_etl import (
    AKShareDataSource,
    _classify_fetch_error,
)


class TestClassifyFetchErrorSingleSource:
    """类内与模块级分类器必须共用同一份实现"""

    def test_class_attribute_is_module_level_implementation(self):
        """`AKShareDataSource._classify_fetch_error 就是模块级那个函数。"""
        assert AKShareDataSource._classify_fetch_error is _classify_fetch_error

    def test_class_attribute_is_staticmethod(self):
        """`通过类访问时不需要传入实例。"""
        assert isinstance(
            AKShareDataSource.__dict__["_classify_fetch_error"],
            staticmethod,
        )


class TestClassifyFetchErrorSameConclusion:
    """同一异常经两个入口必须得到同一结论"""

    @pytest.mark.parametrize("exc", [
        duckdb.ConstraintException("Duplicate key (date, symbol)"),
        duckdb.TransactionException("Conflict on tuple update"),
        duckdb.IOException("Could not set lock on file"),
        ConnectionError("connection reset by peer"),
        PermissionError("permission denied"),
        ModuleNotFoundError("No module named 'akshare'"),
        ValueError("invalid symbol format"),
    ])
    def test_same_conclusion_via_both_entry_points(self, exc):
        """`类内入口与模块级入口对同一异常给出相同结论。"""
        assert AKShareDataSource._classify_fetch_error(exc) == _classify_fetch_error(exc)

    @pytest.mark.parametrize("exc", [
        duckdb.ConstraintException("Duplicate key (date, symbol)"),
        duckdb.TransactionException("Conflict on tuple update"),
        duckdb.IOException("Could not set lock on file"),
    ])
    def test_duckdb_errors_are_storage_locked_via_class_entry(self, exc):
        """`经类内入口,DuckDB 三类并发写错误仍归 storage_locked。"""
        msg = AKShareDataSource._classify_fetch_error(exc)
        assert msg.startswith("storage_locked"), msg
        assert "network_unreachable" not in msg, msg
        assert not msg.startswith("unclassified"), msg

    def test_network_error_still_reported_as_network(self):
        """`经类内入口,网络异常仍归 network_unreachable。"""
        exc = ConnectionError("connection reset by peer")
        assert AKShareDataSource._classify_fetch_error(exc) == "network_unreachable"
