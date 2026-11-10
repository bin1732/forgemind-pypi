# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""内置样例行情的核对器:三件事都要能抓住

- 日期序列不一致 → 报出来(编造的数据编不出同一串交易日)
- 成交量不一致 → 报出来(复权只调价格不动成交量,这一项对不上就不是真实成交)
- 收盘价偏差超过容差 → 报出来(数据被改过或口径变了)

容差之内的小偏差不算问题:前复权价会因分红除权而重算。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_sample_data_is_real as sample  # noqa: E402


def _row(date: str, close: float = 100.0, volume: float = 1234.0) -> dict:
    return {
        "date": date, "open": close, "close": close,
        "high": close, "low": close, "volume": volume,
    }


class TestCompare:
    def test_identical_passes(self):
        rows = [_row("2024-01-02"), _row("2024-01-03")]
        assert sample.compare(rows, [dict(r) for r in rows], 0.005) == []

    def test_missing_day_is_reported(self):
        local = [_row("2024-01-02"), _row("2024-01-03")]
        upstream = [_row("2024-01-02"), _row("2024-01-04")]
        problems = sample.compare(local, upstream, 0.005)
        assert problems, "日期序列不一致要报出来"
        assert "日期序列不一致" in problems[0]

    def test_different_volume_is_reported(self):
        local = [_row("2024-01-02", volume=1000.0)]
        upstream = [_row("2024-01-02", volume=2000.0)]
        problems = sample.compare(local, upstream, 0.005)
        assert problems, "成交量对不上要报出来"
        assert "成交量" in problems[0]

    def test_close_beyond_tolerance_is_reported(self):
        local = [_row("2024-01-02", close=100.0)]
        upstream = [_row("2024-01-02", close=110.0)]
        problems = sample.compare(local, upstream, 0.005)
        assert problems, "收盘价偏差超容差要报出来"
        assert "收盘价偏差" in problems[0]

    def test_close_within_tolerance_is_accepted(self):
        """前复权价会因分红除权而重算,小偏差不算问题"""
        local = [_row("2024-01-02", close=100.0)]
        upstream = [_row("2024-01-02", close=100.4)]
        assert sample.compare(local, upstream, 0.005) == []


class TestRealBundledData:
    def test_bundled_csv_has_a_plausible_shape(self):
        rows = sample.read_csv(sample.DEFAULT_CSV)
        assert len(rows) == 242, f"应有 242 根日线,实际 {len(rows)}"
        assert rows[0]["date"] == "2024-01-02"
        assert rows[-1]["date"] == "2024-12-31"
        # 价格量级对得上茅台
        assert all(500 < r["close"] < 3000 for r in rows), "价格量级不对"
        assert all(r["volume"] > 0 for r in rows), "成交量不该为 0"

    def test_bundled_csv_is_self_consistent(self):
        """high/low/open/close 的自洽:与 OHLC 体检那条同一件事,这里独立再看一遍"""
        rows = sample.read_csv(sample.DEFAULT_CSV)
        for r in rows:
            assert r["high"] >= max(r["open"], r["close"]), r
            assert r["low"] <= min(r["open"], r["close"]), r


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
