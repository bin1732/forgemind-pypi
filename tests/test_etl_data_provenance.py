# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""落到 DuckDB 的每一行 K 线必须能说清自己来自哪个源

多源回退解决了可用性(东财对境外 IP 直接重置连接),但引入了新的
数据一致性问题:**三个源的"前复权"基准并不一致**。

已验证茅台 600519、2024-06-03 至 2024-09-30、adjust=qfq:
  腾讯  首日 1505.05  末日 1644.54
  新浪  首日 1489.77  末日 1621.37
  收盘价最大相对差 1.41%

而 kline_daily 表里没有 provider 列,来源只进了日志。于是同一张表里
可能混着两套价格约定,而且完全看不出来 —— 因子值与回测结果会随
"今天哪个源可用"而漂移。

这个测试的作用是把"混用"变成可检出的,而不是继续隐形。
"""

import asyncio
import os
import tempfile

import pandas as pd
import pytest

from forgemind.core.data.storage import DuckDBStorage


class TestProviderIsPersisted:
    @pytest.fixture
    def etl_env(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        import forgemind.core.data.akshare_etl as mod

        class FakeDS:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get_stock_list(self):
                return pd.DataFrame()

            async def get_history(self, symbol, *a, **k):
                d = pd.DataFrame({
                    "date": [pd.Timestamp("2024-06-03"), pd.Timestamp("2024-06-04")],
                    "symbol": [symbol, symbol],
                    "open": [10.0, 10.2], "high": [10.5, 10.6],
                    "low": [9.8, 9.9], "close": [10.3, 10.4],
                    "volume": [1000, 1100],
                })
                d.attrs["provider"] = "sina"
                return d

        monkeypatch.setattr(mod, "AKShareDataSource", FakeDS)
        return mod

    def test_rows_record_which_source_they_came_from(self, etl_env):
        from forgemind.core.data.akshare_etl import AKShareETL

        asyncio.run(AKShareETL().run(symbols=["600519"]))
        with DuckDBStorage() as db:
            rows = db.query_df("SELECT DISTINCT provider FROM kline_daily")
            assert "provider" in db.query_df("SELECT * FROM kline_daily LIMIT 0").columns
            assert rows["provider"].tolist() == ["sina"]

    def test_mixed_sources_become_visible(self, etl_env, monkeypatch):
        """回退链中途换了源,历史数据里必须查得出来

        同一 (date, symbol) 只会保留一份价格 —— 主键会 REPLACE,这是对的,
        一个日期只能有一个价格。混用发生在**不同日期来自不同源**的情况:
        某次拉 6 月走的是新浪,下次补 7 月时东财挂了回退到腾讯。
        """
        from forgemind.core.data.akshare_etl import AKShareETL

        class SourcedDS:
            calls = 0  # 类级:AKShareETL.run 每次都会新建实例

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get_stock_list(self):
                return pd.DataFrame()

            async def get_history(self, symbol, *a, **k):
                SourcedDS.calls += 1
                prov, day = ("sina", 3) if SourcedDS.calls == 1 else ("tencent", 4)
                d = pd.DataFrame({
                    "date": [pd.Timestamp(f"2024-06-{day:02d}")], "symbol": [symbol],
                    "open": [10.0], "high": [10.5], "low": [9.8],
                    "close": [10.3], "volume": [1000],
                })
                d.attrs["provider"] = prov
                return d

        monkeypatch.setattr(etl_env, "AKShareDataSource", SourcedDS)
        asyncio.run(AKShareETL().run(symbols=["600519"]))
        asyncio.run(AKShareETL().run(symbols=["600519"]))

        with DuckDBStorage() as db:
            rows = db.query_df(
                "SELECT date, provider FROM kline_daily ORDER BY date")
        got = dict(zip(rows["date"].astype(str), rows["provider"]))
        assert got.get("2024-06-03") == "sina", got
        assert got.get("2024-06-04") == "tencent", got

    def test_same_date_is_replaced_not_duplicated(self, etl_env):
        """一个日期只能有一个价格:后写的源覆盖先写的,不留重复"""
        from forgemind.core.data.akshare_etl import AKShareETL

        asyncio.run(AKShareETL().run(symbols=["600519"]))
        asyncio.run(AKShareETL().run(symbols=["600519"]))
        with DuckDBStorage() as db:
            n = db.query_df("SELECT COUNT(*) AS n FROM kline_daily")["n"][0]
        assert n == 2, f"重复写入导致 {n} 行,主键失效"


class TestSchemaMigration:
    def test_existing_database_gains_the_column(self):
        """老库必须能补列,且重复执行不报错"""
        d = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(d)
        try:
            from forgemind.core.data.akshare_etl import AKShareETL

            with DuckDBStorage() as db:
                db.execute("""CREATE TABLE kline_daily (date DATE, symbol VARCHAR,
                    open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
                    volume BIGINT, PRIMARY KEY (date, symbol))""")
                assert "provider" not in set(
                    db.query_df("SELECT * FROM kline_daily LIMIT 0").columns)

            asyncio.run(AKShareETL().init_tables())
            with DuckDBStorage() as db:
                assert "provider" in set(
                    db.query_df("SELECT * FROM kline_daily LIMIT 0").columns)
            asyncio.run(AKShareETL().init_tables())  # 幂等
        finally:
            os.chdir(cwd)
