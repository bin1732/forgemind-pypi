# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""ETL 失败必须给出可行动分类,而不是裸堆栈

两个真实 bug:
  1. 初始化路径(AKShareETL.run 的 init_tables)不在任何 try 内,上游抖动时
     用户直接看到 traceback。
  2. 加上保护后立刻暴露第二个:_classify_fetch_error 挂在
     AKShareDataSource 上,而 AKShareETL 要调用它 —— AttributeError,
     **保护代码自己比不保护更糟**。
  3. 分类器只看异常消息文本,不看类型:ConnectionError("reset") 的消息里
     没有 "connection" 字样,被误判成 unclassified。
"""

import argparse
import asyncio
import json

import pytest

from forgemind.core.data.akshare_etl import AKShareETL, _classify_fetch_error


class TestClassificationCoversTypesNotJustMessages:
    @pytest.mark.parametrize(("exc", "expected"), [
        (ConnectionError("reset"), "network_unreachable"),
        (ConnectionError(), "network_unreachable"),
        (TimeoutError(), "network_unreachable"),
        (json.JSONDecodeError("Expecting value", "", 0), "upstream_returned_non_json"),
        (ModuleNotFoundError("No module named 'akshare'"), "akshare_not_installed"),
        (PermissionError("[Errno 13] Permission denied"), "storage_permission_denied"),
        (OSError("[Errno 28] No space left on device"), "storage_full"),
        (ValueError("invalid symbol"), "invalid_symbol_format"),
    ])
    def test_maps_to_actionable_reason(self, exc, expected):
        assert expected in _classify_fetch_error(exc)

    def test_unknown_still_reports_type(self):
        out = _classify_fetch_error(ValueError("某个没见过的错"))
        assert out.startswith("unclassified:")
        assert "ValueError" in out


class TestInitFailureIsContained:
    def test_init_tables_failure_returns_breakdown_not_raises(self, tmp_path, monkeypatch):
        """初始化失败也要走分类返回,而不是抛异常"""
        monkeypatch.chdir(tmp_path)
        etl = AKShareETL()

        async def boom():
            raise PermissionError("[Errno 13] Permission denied: 'data/duckdb/main.db'")

        etl.init_tables = boom
        stats = asyncio.run(etl.run(symbols=["600519"]))
        assert stats["klines"] == 0
        assert stats["failures"], "失败时必须给出分类"
        assert any(k.startswith("init:") for k in stats["failures"]), stats

    def test_stock_list_failure_does_not_abort_etl(self, tmp_path, monkeypatch):
        """拿不到代码表不该中断:历史 K 线仍可拉"""
        import pandas as pd

        import forgemind.core.data.akshare_etl as mod

        monkeypatch.chdir(tmp_path)

        class FakeDS:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get_stock_list(self):
                raise ConnectionError("reset by peer")

            async def get_history(self, *a, **k):
                return pd.DataFrame(
                    {"date": [pd.Timestamp("2024-01-02")], "symbol": ["600519"],
                     "open": [10.0], "high": [11.0], "low": [9.0],
                     "close": [10.5], "volume": [100]})

        monkeypatch.setattr(mod, "AKShareDataSource", FakeDS)
        etl = AKShareETL()
        stats = asyncio.run(etl.run(symbols=["600519"]))
        assert stats["klines"] > 0, "stock_list 失败不该阻断 K 线拉取"
        assert stats["ok_symbols"] == 1


class TestDataSourceSurfaceIntact:
    """AKShareDataSource 的方法面必须完整

    这层是为一个真实事故加的:把 _classify_fetch_error 提为模块级函数时,
    用范围删除把 get_history / _history_providers / _exchange_prefixed /
    _normalize_history 一起删掉了。ruff 不检查"方法是否存在",单测因为
    mock 掉了数据源也没发现 —— 直到全量跑 CLI 真实取数才炸出
    AttributeError: 'AKShareDataSource' object has no attribute 'get_history'。
    """

    REQUIRED = {
        "__init__", "__aenter__", "__aexit__", "get_stock_list", "get_history",
        "_classify_fetch_error", "_history_providers", "_exchange_prefixed",
        "_normalize_history",
    }

    def test_all_methods_present(self):
        from forgemind.core.data.akshare_etl import AKShareDataSource

        missing = self.REQUIRED - set(dir(AKShareDataSource))
        assert not missing, f"数据源方法缺失: {missing}"

    def test_history_has_multi_source_fallback(self):
        """多源回退是多可用性保障,不能被优化掉"""
        import inspect

        from forgemind.core.data.akshare_etl import AKShareDataSource

        src = inspect.getsource(AKShareDataSource.get_history)
        assert "providers" in src, "get_history 不再走多源回退"
        names = [n for n in ("eastmoney", "tencent", "sina")
                 if n in inspect.getsource(AKShareDataSource._history_providers)]
        assert len(names) >= 2, f"可用数据源只剩 {names}"

    def test_module_level_classifier_is_reachable(self):
        """AKShareETL 要能直接调用,不能只挂在数据源类上"""
        from forgemind.core.data.akshare_etl import _classify_fetch_error

        assert callable(_classify_fetch_error)
        assert "network_unreachable" in _classify_fetch_error(ConnectionError("reset"))


class TestStorageLockConflict:
    """DuckDB 是单进程写锁:开着 API 服务再跑 etl 就会撞上

    这是真实用户路径才暴露的组合。之前的输出是:

        ⚠️  ETL 拉到 0 条数据,没有写入任何 K 线。
           失败原因分类: 1× init:unclassified:IOException
           代码格式应为 6 位(如 600519),而非 600519.SH

    三处都错:取数压根没开始("0 条"是假的)、分类无信息、
    提示的代码格式与锁冲突毫无关系。
    """

    def test_lock_conflict_is_classified_actionably(self):
        import _duckdb

        reason = _classify_fetch_error(_duckdb.IOException(
            'IO Error: Could not set lock on file "data/duckdb/main.db": '
            "Conflicting lock is held"))
        assert reason.startswith("storage_locked")
        assert "另一个进程" in reason or "FORGEMIND_DATA_DIR" in reason, (
            f"提示必须能指导下一步,实际: {reason}")

    def test_non_lock_ioerror_is_not_mislabelled(self):
        import _duckdb

        reason = _classify_fetch_error(
            _duckdb.IOException('IO Error: Cannot read from file "x"'))
        assert "storage_locked" not in reason

    def test_cli_says_nothing_was_fetched_on_init_failure(self, monkeypatch, tmp_path):
        """init 失败不是"拉到 0 条" —— 那会让用户查错方向"""
        import contextlib
        import io

        import forgemind.core.data.akshare_etl as mod
        from forgemind.cli import cmd_etl

        monkeypatch.chdir(tmp_path)

        class FakeETL:
            async def run(self, **k):
                return {"stocks": 0, "klines": 0, "ok_symbols": 0,
                        "failures": {"init:storage_locked(被占用)": 1}}

        monkeypatch.setattr(mod, "AKShareETL", FakeETL)
        monkeypatch.setattr("forgemind.core.data.akshare_etl.AKShareETL", FakeETL)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with pytest.raises(SystemExit):
                cmd_etl(argparse.Namespace(symbols="600519", start="2024-01-01",
                                           end="2024-02-01"))
        out = buf.getvalue()
        assert "未能开始取数" in out, out
        assert "拉到 0 条" not in out, out
        assert "代码格式" not in out, "锁冲突与代码格式无关,不该提示"
        assert "forgemind[cn]" not in out, "锁冲突与缺依赖无关,不该提示"

    def test_missing_dependency_still_suggests_the_extra(self, monkeypatch, tmp_path):
        import contextlib
        import io

        import forgemind.core.data.akshare_etl as mod
        from forgemind.cli import cmd_etl

        monkeypatch.chdir(tmp_path)

        class FakeETL:
            async def run(self, **k):
                return {"stocks": 0, "klines": 0, "ok_symbols": 0,
                        "failures": {"init:akshare_not_installed": 1}}

        monkeypatch.setattr(mod, "AKShareETL", FakeETL)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with pytest.raises(SystemExit):
                cmd_etl(argparse.Namespace(symbols="600519", start="2024-01-01",
                                           end="2024-02-01"))
        out = buf.getvalue()
        assert "forgemind[cn]" in out, out
        assert "代码格式" not in out, out
