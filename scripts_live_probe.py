#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""真实上游取数探测 + ETL 端到端验证(在有网络的 CI 上跑)"""

import asyncio
import sys

import akshare as ak

from forgemind.core.data.akshare_etl import AKShareETL

SYMBOLS = ["600519", "000001"]
START, END = "2023-01-01", "2024-12-31"


def probe_providers():
    """逐个探测三个源 —— 确认回退链上哪几个真的可用"""
    for name, fn in [
        ("eastmoney", lambda: ak.stock_zh_a_hist(
            symbol="600519", period="daily",
            start_date="20240101", end_date="20240110", adjust="qfq")),
        ("tencent", lambda: ak.stock_zh_a_hist_tx(
            symbol="sh600519", start_date="20240101", end_date="20240110", adjust="qfq")),
        ("sina", lambda: ak.stock_zh_a_daily(
            symbol="sh600519", start_date="20240101", end_date="20240110", adjust="qfq")),
    ]:
        try:
            df = fn()
            print(f"PROBE {name}: OK rows={len(df)}")
        except Exception as exc:
            print(f"PROBE {name}: {type(exc).__name__}: {str(exc)[:80]}")


async def main():
    probe_providers()
    stats = await AKShareETL().run(symbols=SYMBOLS, start=START, end=END)
    print("STATS", stats)
    assert stats["klines"] > 0, f"multi-source fallback still got 0 rows: {stats}"
    assert stats["ok_symbols"] >= 1, f"no symbol succeeded: {stats}"
    assert "failures" in stats, "missing failure breakdown"
    print(f"PASS akshare real fetch {stats['klines']} klines "
          f"from {stats['ok_symbols']} symbol(s)")

    # 下游:真实数据 -> 选股
    from forgemind.core.agents.stock_picker import StockPickerAgent
    from forgemind.core.data.storage import DuckDBStorage

    with DuckDBStorage() as db:
        rows = db.query_scalar("SELECT COUNT(*) FROM kline_daily")
        syms = [r["symbol"] for r in db.query_df(
            "SELECT DISTINCT symbol FROM kline_daily").to_dict("records")]
    print(f"DB rows={rows} symbols={syms}")
    assert rows > 0, "no rows landed in duckdb"

    picks = await StockPickerAgent().pick(universe=syms, top_n=2)
    print("PICKS", [(p.symbol, p.direction, p.score) for p in picks])
    assert picks, "stock_pick returned nothing on real data"
    assert all(p.rationale for p in picks), "a pick has an empty rationale"
    print(f"PASS end-to-end real data: {rows} rows -> {len(picks)} picks")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AssertionError as exc:
        print(f"FAIL {exc}")
        sys.exit(1)
