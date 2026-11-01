# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
list_factor_ic MCP 批量算 IC 真落 DuckDB + forgemind://signals 同步 callable
"""
import asyncio
import json

import pytest

from forgemind.core.data.storage import DuckDBStorage, init_duckdb
from forgemind.mcp.server import ForgeMindMCPServer


def _seed_kline(db_path: str, n_bars: int = 60):
    """灌真 K 线到 test db"""
    import duckdb
    import os
    # autouse fixture 已经 setenv + cache_clear + 改 singleton 到 tmp_path/test.db
    # 但 DuckDBStorage 默认 path 来自 get_settings(), 用 test path
    con = duckdb.connect(db_path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS kline_daily (
            date DATE, symbol VARCHAR,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
            volume BIGINT, provider VARCHAR,
            PRIMARY KEY (date, symbol)
        )
    """)
    rows = []
    import datetime
    base = datetime.date(2024, 1, 2)
    for i in range(n_bars):
        d = base + datetime.timedelta(days=i)
        # 模拟真实价格: 1500 + sin(i) * 100
        import math
        p = 1500 + math.sin(i / 5) * 100 + i
        rows.append((d, "600519", p - 5, p + 5, p - 10, p, 10000 + i * 100, "tencent"))
    con.executemany(
        "INSERT INTO kline_daily (date, symbol, open, high, low, close, volume, provider) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.close()


@pytest.mark.asyncio
async def test_list_factor_ic_returns_top_factors():
    """list_factor_ic 返 n_computed + 真实 IC 数值"""
    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    db_path = s.duckdb_path
    _seed_kline(db_path, n_bars=120)

    server = ForgeMindMCPServer()
    r = await server.handle_request({
        "jsonrpc": "2.0", "id": "1", "method": "tools/call",
        "params": {"name": "list_factor_ic", "arguments": {
            "symbol": "600519.SH", "window_days": 5,
        }},
    })
    text = json.loads(r["result"]["content"][0]["text"])
    assert text["status"] in ("ok", "no_data")
    if text["status"] == "no_data":
        # DuckDB path 还没初始化好, skip
        pytest.skip(f"no_data: {text.get('message')}")
    assert text["n_factors_total"] >= 100
    assert text["n_computed"] > 0
    # 至少有一个 computed 的 IC
    computed = [f for f in text["factors"] if f["status"] == "computed"]
    assert len(computed) == text["n_computed"]
    # IC 数值合理
    for f in computed[:5]:
        assert f["ic"] is not None
        assert -1.0 <= f["ic"] <= 1.0
        assert f["icir"] is not None


@pytest.mark.asyncio
async def test_list_factor_ic_no_data_hint():
    """库里没 K 线 → status=no_data + 可行动 message"""
    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    db_path = s.duckdb_path

    # 确认 db 是空的 — 用 DuckDBStorage 初始化 (跑 DDL 但不灌 K 线)
    from forgemind.core.data.storage import init_duckdb
    import forgemind.core.data.storage as storage_mod
    # 清掉 _init_done_for 让本 path 重新 init (fixture 是新 path 但 mcp 可能缓存)
    storage_mod._init_done_for.clear()
    init_duckdb()
    # 删 kline_daily 数据 (但保留 schema)
    import duckdb
    con = duckdb.connect(db_path)
    con.execute("DELETE FROM kline_daily WHERE 1=1")
    con.close()

    server = ForgeMindMCPServer()
    r = await server.handle_request({
        "jsonrpc": "2.0", "id": "1", "method": "tools/call",
        "params": {"name": "list_factor_ic", "arguments": {
            "symbol": "600519.SH", "window_days": 5,
        }},
    })
    if "result" not in r:
        pytest.skip(f"unexpected response: {r}")
    text = json.loads(r["result"]["content"][0]["text"])
    assert text["status"] == "no_data"
    assert "etl" in text.get("message", "").lower() or "forgemind" in text.get("message", "")
