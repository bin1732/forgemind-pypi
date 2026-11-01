# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""ETL 的两件事:取数不能挂死,统计必须说清是本次还是累计。

两个真实问题:
  1. 股票列表只走聚合接口,那个接口在受限网络下会被拒,拿不到全市场
     代码表。回退到交易所自己的名单接口后,一个交易所的名单不等于全
     市场,能取到的交易所要合并。
  2. 统计里的 stocks / klines 报的是表里累计的行数,不是本次写入的行
     数。库里已经有历史数据时,这两个数会把旧数据算成本次的成果。
"""

from __future__ import annotations

import asyncio
import socket
import threading
import time

import pandas as pd
import pytest

import forgemind.core.data.akshare_etl as mod
from forgemind.core.data.akshare_etl import AKShareDataSource, AKShareETL


class _FakeAk:
    """只提供股票列表接口的假 akshare。"""

    def __init__(self, aggregate=None, sse=None, szse=None):
        self.aggregate = aggregate
        self.sse = sse
        self.szse = szse
        self.calls: list[str] = []

    def stock_info_a_code_name(self):
        self.calls.append("eastmoney")
        if self.aggregate is None:
            raise ConnectionError("reset by peer")
        return self.aggregate

    def stock_info_sh_name_code(self):
        self.calls.append("sse")
        if self.sse is None:
            raise ConnectionError("reset by peer")
        return self.sse

    def stock_info_sz_name_code(self):
        self.calls.append("szse")
        if self.szse is None:
            raise ConnectionError("reset by peer")
        return self.szse


def _df(code_col: str, name_col: str, rows: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=[code_col, name_col])


class TestFetchTimeout:
    def test_a_hanging_socket_is_bounded(self):
        """连接建起来却不回数据时,调用要按时返回,不能一直等。"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        accepted: list[socket.socket] = []

        def accept_and_stay_silent():
            conn, _ = server.accept()
            accepted.append(conn)
            # 收下连接,但一个字节都不回
            while True:
                time.sleep(0.2)

        thread = threading.Thread(target=accept_and_stay_silent, daemon=True)
        thread.start()
        try:
            def hang():
                with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
                    return s.recv(1024)

            started = time.monotonic()
            with pytest.raises((socket.timeout, TimeoutError)):
                AKShareDataSource._call_with_timeout(hang, 1.0)
            elapsed = time.monotonic() - started
            assert elapsed < 8, f"超时没有生效,等了 {elapsed:.1f}s"
        finally:
            for conn in accepted:
                conn.close()
            server.close()

    def test_socket_default_is_restored(self):
        """调用之后 socket 的默认超时要还原,不能影响别处的取数。"""
        before = socket.getdefaulttimeout()

        def quick():
            return 42

        assert AKShareDataSource._call_with_timeout(quick, 5.0) == 42
        assert socket.getdefaulttimeout() == before

    def test_socket_default_is_restored_on_failure(self):
        """调用失败时也要还原。"""
        before = socket.getdefaulttimeout()

        def boom():
            raise ValueError("坏了")

        with pytest.raises(ValueError):
            AKShareDataSource._call_with_timeout(boom, 5.0)
        assert socket.getdefaulttimeout() == before


class TestStockListFallback:
    def test_aggregate_source_is_preferred(self):
        """聚合接口拿得到就用它,它给的是全市场。"""
        ds = AKShareDataSource()
        ds._akshare = _FakeAk(
            aggregate=_df("code", "name", [("600519", "贵州茅台")]),
        )
        result = asyncio.run(ds.get_stock_list())
        assert result.attrs["provider"] == "eastmoney"
        assert list(result["symbol"]) == ["600519"]
        assert ds._akshare.calls == ["eastmoney"], "聚合源成了就不该再问交易所"

    def test_exchange_sources_are_merged(self):
        """回退时,能取到的交易所要合并 —— 一个交易所不是全市场。"""
        ds = AKShareDataSource()
        ds._akshare = _FakeAk(
            aggregate=None,
            sse=_df("证券代码", "证券简称", [("600519", "贵州茅台")]),
            szse=_df("A股代码", "A股简称", [("000001", "平安银行")]),
        )
        result = asyncio.run(ds.get_stock_list())
        assert result.attrs["provider"] == "sse+szse"
        assert sorted(result["symbol"]) == ["000001", "600519"]

    def test_one_exchange_only_is_labelled_as_such(self):
        """只取到一个交易所时,不能自称是全市场。"""
        ds = AKShareDataSource()
        ds._akshare = _FakeAk(
            aggregate=None,
            sse=_df("证券代码", "证券简称", [("600519", "贵州茅台")]),
            szse=None,
        )
        result = asyncio.run(ds.get_stock_list())
        assert result.attrs["provider"] == "sse"
        assert list(result["symbol"]) == ["600519"]

    def test_all_sources_down_gives_empty_and_no_crash(self):
        """全都取不到时返回空表,不留半个数据。"""
        ds = AKShareDataSource()
        ds._akshare = _FakeAk(aggregate=None, sse=None, szse=None)
        result = asyncio.run(ds.get_stock_list())
        assert result.empty


class _FakeDS:
    """只返回固定 K 行的假数据源。"""

    def __init__(self, n_rows: int, stock_list: pd.DataFrame | None = None,
                 start: str = "2024-01-02"):
        self.n_rows = n_rows
        self.stock_list = stock_list
        self.start = start

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get_stock_list(self):
        if self.stock_list is None:
            return pd.DataFrame()
        return self.stock_list

    async def get_history(self, symbol, *a, **k):
        dates = pd.date_range(self.start, periods=self.n_rows, freq="D")
        return pd.DataFrame({
            "date": dates,
            "symbol": [symbol] * self.n_rows,
            "open": [10.0] * self.n_rows,
            "high": [11.0] * self.n_rows,
            "low": [9.0] * self.n_rows,
            "close": [10.5] * self.n_rows,
            "volume": [100] * self.n_rows,
        })


class TestFetchHasAHardWall:
    """取数必须有时限:DNS 解析或建连卡住时,socket 的默认超时管不到。"""

    def test_a_hanging_call_is_bounded(self):
        """卡死的调用必须在时限内返回,而不是一直挂着。"""
        from forgemind.core.data.fetch_guard import call_with_timeout

        started = time.monotonic()
        with pytest.raises(TimeoutError):
            call_with_timeout(lambda: time.sleep(30), 1.0)
        elapsed = time.monotonic() - started
        assert elapsed < 8, f"硬墙没生效,等了 {elapsed:.1f}s"

    def test_socket_default_is_restored_after_a_timeout(self):
        """超时之后 socket 的默认超时要还原,不能影响别处的取数。"""
        from forgemind.core.data.fetch_guard import call_with_timeout

        before = socket.getdefaulttimeout()
        with pytest.raises(TimeoutError):
            call_with_timeout(lambda: time.sleep(30), 0.5)
        assert socket.getdefaulttimeout() == before

    def test_the_exception_is_propagated_unchanged(self):
        """调用自己抛的异常要原样传出去,不能被超时包装掉。"""
        from forgemind.core.data.fetch_guard import call_with_timeout

        def boom():
            raise ValueError("坏了")

        with pytest.raises(ValueError, match="坏了"):
            call_with_timeout(boom, 2.0)


class TestStatsMeanThisRun:
    def test_klines_reports_this_run_not_the_accumulated_table(
        self, tmp_path, monkeypatch
    ):
        """库里有历史数据时,本次写入的行数不能被算成累计值。"""
        monkeypatch.chdir(tmp_path)

        monkeypatch.setattr(mod, "AKShareDataSource", lambda: _FakeDS(2))
        first = asyncio.run(AKShareETL().run(symbols=["600519"]))
        assert first["klines"] == 2
        assert first["klines_in_db"] == 2

        # 换一段日期,否则同一批 (date, symbol) 会被覆盖,表里不会累积
        monkeypatch.setattr(
            mod, "AKShareDataSource", lambda: _FakeDS(3, start="2024-03-01")
        )
        second = asyncio.run(AKShareETL().run(symbols=["600519"]))
        assert second["klines"] == 3, "本次写入的行数被累计值盖住了"
        assert second["klines_in_db"] == 5, "库里的累计行数应当另算一份"

    def test_stocks_reports_this_run_and_the_table_separately(
        self, tmp_path, monkeypatch
    ):
        """代码表同理:本次取到多少与表里累计多少,分开报。"""
        monkeypatch.chdir(tmp_path)
        # 真实的取数实现已经归一成 symbol / name,假数据源也要给这个形态
        stock_list = pd.DataFrame(
            [("600519", "贵州茅台"), ("000001", "平安银行")],
            columns=["symbol", "name"],
        )

        monkeypatch.setattr(
            mod, "AKShareDataSource", lambda: _FakeDS(1, stock_list)
        )
        first = asyncio.run(AKShareETL().run(symbols=["600519"]))
        assert first["stocks"] == 2, "本次取到的代码表条数不对"
        assert first["stocks_in_db"] == 2

        # 第二次拿不到代码表,表里的旧数据还在 —— 本次取到 0,表里仍是 2
        monkeypatch.setattr(mod, "AKShareDataSource", lambda: _FakeDS(1))
        second = asyncio.run(AKShareETL().run(symbols=["600519"]))
        assert second["stocks"] == 0, "没取到代码表却报出了条数"
        assert second["stocks_in_db"] == 2, "表里的累计条数应当另算一份"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
