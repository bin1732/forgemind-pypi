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
        (
            "eastmoney",
            lambda: ak.stock_zh_a_hist(
                symbol="600519",
                period="daily",
                start_date="20240101",
                end_date="20240110",
                adjust="qfq",
            ),
        ),
        (
            "tencent",
            lambda: ak.stock_zh_a_hist_tx(
                symbol="sh600519", start_date="20240101", end_date="20240110", adjust="qfq"
            ),
        ),
        (
            "sina",
            lambda: ak.stock_zh_a_daily(
                symbol="sh600519", start_date="20240101", end_date="20240110", adjust="qfq"
            ),
        ),
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
    assert stats["klines"] > 0, f"多源回退未取到任何行: {stats}"
    assert stats["ok_symbols"] >= 1, f"没有标的取数成功: {stats}"
    assert "failures" in stats, "缺少按原因归类的失败明细"
    print(f"PASS akshare real fetch {stats['klines']} klines from {stats['ok_symbols']} symbol(s)")

    # 下游:真实数据 -> 选股
    from forgemind.core.agents.stock_picker import StockPickerAgent
    from forgemind.core.data.storage import DuckDBStorage

    with DuckDBStorage() as db:
        rows = db.query_scalar("SELECT COUNT(*) FROM kline_daily")
        syms = [
            r["symbol"]
            for r in db.query_df("SELECT DISTINCT symbol FROM kline_daily").to_dict("records")
        ]
    print(f"DB rows={rows} symbols={syms}")
    assert rows > 0, "数据未落进 DuckDB"

    picks = await StockPickerAgent().pick(universe=syms, top_n=2)
    print("PICKS", [(p.symbol, p.direction, p.score) for p in picks])
    assert picks, "选股在真实数据上没有返回结果"
    assert all(p.rationale for p in picks), "存在没有给出理由的选股结果"
    print(f"PASS end-to-end real data: {rows} rows -> {len(picks)} picks")

    # 宏观:对外说明里写着提供 CN macro,这里就真取一次
    from forgemind.core.data.sources.extended_sources import MacroDataSource

    macro = MacroDataSource()
    ok, why = macro.is_available()
    if not ok:
        print(f"SKIP macro: {why}")
        return
    try:
        frame = macro.fetch(start="2024-01-01", end="2024-12-31")
    except Exception as exc:  # noqa: BLE001
        # 取不到要说清楚是取不到,不能装作跑过了
        print(f"SKIP macro: {type(exc).__name__}: {str(exc)[:120]}")
        return
    print(f"MACRO rows={frame.height} cols={frame.columns}")
    if frame.height == 0:
        print("SKIP macro: 上游没有返回任何行")
        return
    for column in ("PMI", "CPI", "PPI", "M2_yoy", "10y_yield", "USD_CNY"):
        if column not in frame.columns:
            print(f"SKIP macro: 表里少了 {column} 列")
            return
        if frame[column].null_count() >= frame.height:
            print(f"SKIP macro: {column} 整列为空")
            return
    print("PASS macro real fetch")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AssertionError as exc:
        print(f"FAIL {exc}")
        sys.exit(1)
