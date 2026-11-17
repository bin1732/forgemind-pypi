# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""落进 DuckDB 的每一行 K 线必须自洽

ETL 是上游数据变成用户可见行情的**唯一入口**。这里出的问题会顺着
回撤、Sharpe、因子 IC 一路传下去,而库里只躺着"看起来正常"的数字 ——
没人知道错在哪一行。

自相矛盾的行长这样:最高价比收盘价还低、最低价比开盘价还高。
这种数据偶尔会从上游冒出来(复权、停牌、源自身的 bug)。

所以落库前有一道闸:矛盾的行不进库,并按原因计数,用户因此知道是上游
给了坏数据 —— 而不是自己算出了奇怪的指标。

**缺值不等于矛盾**:某个源本来就不给 high/low,那是"缺",照样落库
(别的列还有用),不该被当成坏数据丢掉。
"""

import asyncio

import pandas as pd
import pytest

from forgemind.core.data.storage import DuckDBStorage


def _frame(rows):
    df = pd.DataFrame(rows)
    df.attrs["provider"] = "eastmoney"
    return df


def _row(day, open_=10.0, high=10.5, low=9.8, close=10.3, volume=1000):
    return {
        "date": pd.Timestamp(day),
        "symbol": "600519",
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


class TestInconsistentRowsAreDropped:
    def test_high_below_close_is_dropped(self):
        from forgemind.core.data.akshare_etl import _drop_inconsistent_rows

        df = _frame([
            _row("2024-06-03"),
            _row("2024-06-04", high=10.0, close=10.3),  # 最高价低于收盘价
        ])
        kept, dropped = _drop_inconsistent_rows(df)
        assert dropped == 1
        assert len(kept) == 1
        assert kept.iloc[0]["date"] == pd.Timestamp("2024-06-03")

    def test_low_above_open_is_dropped(self):
        from forgemind.core.data.akshare_etl import _drop_inconsistent_rows

        df = _frame([
            _row("2024-06-03"),
            _row("2024-06-04", low=10.1, open_=10.0),  # 最低价高于开盘价
        ])
        kept, dropped = _drop_inconsistent_rows(df)
        assert dropped == 1
        assert len(kept) == 1

    def test_negative_close_and_negative_volume_are_dropped(self):
        from forgemind.core.data.akshare_etl import _drop_inconsistent_rows

        df = _frame([
            _row("2024-06-03"),
            _row("2024-06-04", close=-1.0),
            _row("2024-06-05", volume=-5),
        ])
        kept, dropped = _drop_inconsistent_rows(df)
        assert dropped == 2
        assert len(kept) == 1

    def test_consistent_rows_are_all_kept(self):
        from forgemind.core.data.akshare_etl import _drop_inconsistent_rows

        df = _frame([_row("2024-06-03"), _row("2024-06-04")])
        kept, dropped = _drop_inconsistent_rows(df)
        assert dropped == 0
        assert len(kept) == 2

    def test_missing_values_are_not_treated_as_contradictions(self):
        """缺 high/low 是"缺",不是"矛盾" —— 不该被当成坏数据丢掉"""
        from forgemind.core.data.akshare_etl import _drop_inconsistent_rows

        df = pd.DataFrame([
            {"date": pd.Timestamp("2024-06-03"), "symbol": "600519",
             "open": 10.0, "high": None, "low": None, "close": 10.3, "volume": 100},
        ])
        kept, dropped = _drop_inconsistent_rows(df)
        assert dropped == 0
        assert len(kept) == 1

    def test_provider_survives_the_filter(self):
        """过滤之后来源还在 —— 丢了它,库里就分不出这行来自哪个源"""
        from forgemind.core.data.akshare_etl import _drop_inconsistent_rows

        df = _frame([
            _row("2024-06-03"),
            _row("2024-06-04", high=10.0, close=10.3),
        ])
        kept, _dropped = _drop_inconsistent_rows(df)
        assert kept.attrs.get("provider") == "eastmoney"


class TestTheGateRunsDuringEtl:
    """闸要真的在落库的路上,不是个没人调用的函数"""

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
                d = _frame([
                    _row("2024-06-03"),
                    _row("2024-06-04", high=10.0, close=10.3),  # 矛盾行
                ])
                d["symbol"] = symbol
                return d

        monkeypatch.setattr(mod, "AKShareDataSource", FakeDS)
        return mod

    def test_bad_row_never_reaches_the_database(self, etl_env, tmp_path):
        from forgemind.core.data.storage import DuckDBStorage

        etl = etl_env.AKShareETL()
        result = asyncio.run(etl.run(symbols=["600519"], start="2024-01-01", end="2024-12-31"))

        with DuckDBStorage() as db:
            rows = db.query_df("SELECT date, close FROM kline_daily ORDER BY date")
        assert len(rows) == 1, f"矛盾的行不该进库,实际进了 {len(rows)} 行"
        assert result["klines"] == 1

    def test_failure_reason_says_the_data_was_inconsistent(self, etl_env):
        etl = etl_env.AKShareETL()
        result = asyncio.run(etl.run(symbols=["600519"], start="2024-01-01", end="2024-12-31"))
        reasons = " ".join(result.get("failures", {}))
        assert "data_inconsistent" in reasons, result.get("failures")
