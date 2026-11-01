# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""MCP get_kline 必须只读真实数据,没数据就如实说没有

桌面端 K 线图画的是 Math.random() 生成的随机游走。之所以能用假数据
"撑"这么久,是因为根本没有读真实 K 线的通路 —— 8 个工具里没有一个能读。
这个工具补上通路,并且明确:库里没有就是没有,不用随机数补。
"""

import asyncio

import pytest


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _call(**kw):
    from forgemind.mcp.server import ForgeMindMCPServer

    return asyncio.run(ForgeMindMCPServer()._tool_get_kline(**kw))


class TestNoFabrication:
    def test_missing_database_reports_no_data_not_an_exception(self, workdir):
        r = _call(symbol="600519")
        assert r["status"] == "no_data"
        assert r["bars"] == []
        # 必须是能指导下一步的话,而不是 DuckDB 的原始 CatalogException
        assert "etl" in r["message"].lower()
        assert "CatalogException" not in r["message"]

    def test_empty_symbol_rejected(self, workdir):
        r = _call(symbol="")
        assert r["status"] == "failed"
        assert "symbol" in r["error"]

    def test_symbol_not_in_db_explains_the_six_digit_convention(self, workdir):
        """库里确实没有这个代码时,才该报 empty

        这条断言原先用 '600519.SH' —— 而库里种的就是 600519,归一化后
        查得到是**正确**行为,测试却把它当成了"应当查不到"。
        也就是把 bug 固化成了契约。换成一个真正不存在的代码。
        """

        from forgemind.core.data.storage import DuckDBStorage

        with DuckDBStorage() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS kline_daily (
                date DATE, symbol VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE,
                close DOUBLE, volume BIGINT, provider VARCHAR,
                PRIMARY KEY (date, symbol))""")
            db.execute("INSERT OR REPLACE INTO kline_daily VALUES "
                       "('2024-06-03','600519',10.0,10.5,9.8,10.3,1000,'sina')")
        r = _call(symbol="999999.SH")
        assert r["status"] == "empty"
        assert "6 位" in r["message"], r["message"]


class TestRealDataPath:
    @pytest.fixture
    def seeded(self, workdir):
        from forgemind.core.data.storage import DuckDBStorage

        with DuckDBStorage() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS kline_daily (
                date DATE, symbol VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE,
                close DOUBLE, volume BIGINT, provider VARCHAR,
                PRIMARY KEY (date, symbol))""")
            for i, (o, h, l, c) in enumerate(
                    [(10.0, 10.5, 9.8, 10.3), (10.3, 11.0, 10.2, 10.9),
                     (10.9, 11.2, 10.5, 10.6)]):
                db.execute(
                    "INSERT OR REPLACE INTO kline_daily VALUES "
                    f"('2024-06-0{i+3}','600519',{o},{h},{l},{c},1000,'sina')")
        return None

    def test_returns_real_bars_in_ascending_time_order(self, seeded):
        r = _call(symbol="600519")
        assert r["status"] == "ok"
        assert r["n_bars"] == 3
        times = [b["time"] for b in r["bars"]]
        assert times == sorted(times), "图表要时间正序,倒序会画成左跌右涨"
        assert r["bars"][0]["close"] == 10.3
        assert r["provider"] == "sina"

    def test_bars_carry_ohlcv(self, seeded):
        b = _call(symbol="600519")["bars"][0]
        for f in ("time", "open", "high", "low", "close", "volume"):
            assert f in b and b[f] is not None

    def test_limit_is_respected(self, seeded):
        assert _call(symbol="600519", limit=2)["n_bars"] == 2

    def test_suffixed_symbol_now_resolves_to_the_stored_row(self, workdir):
        """带后缀必须能查到 —— 带后缀查询必须命中,这是该用例的核心断言

        ETL 存 600519,用户按文档敲 600519.SH。查不到时提示是"没有行情
        数据",用户只会以为没拉成功,然后反复重跑 etl。
        """
        import datetime as dt

        from forgemind.core.data.storage import DuckDBStorage

        with DuckDBStorage() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS kline_daily (
                date DATE, symbol VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE,
                close DOUBLE, volume BIGINT, provider VARCHAR,
                PRIMARY KEY (date, symbol))""")
            for i in range(90):
                day = (dt.date(2024, 1, 1) + dt.timedelta(days=i)).isoformat()
                db.execute("INSERT OR REPLACE INTO kline_daily VALUES "
                           f"('{day}','600519',10.0,10.5,9.8,10.3,1000,'sina')")
        for sym in ("600519", "600519.SH", "sh600519"):
            r = _call(symbol=sym)
            assert r["status"] == "ok", f"{sym}: {r.get('status')} — {r.get('message','')}"
            assert r["n_bars"] == 90, (sym, r["n_bars"])
