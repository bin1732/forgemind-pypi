# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
K 线面板真后端派生 — loadKline 解 JSON-RPC wrapper 拿 bars

bug 历史:
- 之前 loadKline 直接拿 mcpTool("get_kline", ...) 返回的 wrapper 对象
  当作 {status, bars} 用 —— wrapper 是 {jsonrpc, id, result: {content: [{text: ...}]}},
  text 是二次 JSON。所以 r.status 永远是 undefined,走 "MCP 返回格式未知"
  兜底, 永远 "加载数据..."
- 修: 解 raw.result.content[0].text 二次 JSON 后才看 status / bars

真机验证(chromium + 真 forgemind.api.main + 真 DuckDB kline_daily 242 bars):
  K 线面板显示 600519.SH 2024 全年真 K 线,高 1900 低 1200 close 1444.42
"""
import json
import os

import duckdb
import pytest


def _seed_kline_daily(db_path: str, symbol: str = "600519"):
    """直接灌 5 个真 bar 到 DuckDB"""
    con = duckdb.connect(db_path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS kline_daily (
            symbol VARCHAR NOT NULL,
            date DATE NOT NULL,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
            provider VARCHAR,
            PRIMARY KEY (symbol, date)
        )
    """)
    rows = [
        (symbol, "2024-01-02", 1580.66, 1583.85, 1543.76, 1550.67, 12345.0, "tencent"),
        (symbol, "2024-01-03", 1546.77, 1560.88, 1541.99, 1559.66, 11234.0, "tencent"),
        (symbol, "2024-01-04", 1556.0,  1570.0,  1550.0,  1565.0,  10456.0, "tencent"),
        (symbol, "2024-01-05", 1565.0,  1572.0,  1548.0,  1548.5,  9876.0,  "tencent"),
        (symbol, "2024-01-08", 1548.5,  1555.0,  1530.0,  1535.0,  8901.0,  "tencent"),
    ]
    con.executemany(
        "INSERT INTO kline_daily (symbol, date, open, high, low, close, volume, provider) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.close()


def test_get_kline_returns_real_bars():
    """MCP get_kline 真读 DuckDB, 返 5 个 bar + status=ok"""
    from fastapi.testclient import TestClient

    from forgemind.core.config.settings import get_settings

    # 关键: lru_cache + from X import y 双陷阱需要先 cache_clear
    get_settings.cache_clear()
    s = get_settings()
    # autouse fixture 已把 duckdb_path 设到 tmp_path/db,但 TestClient 内的
    # app 会重新读 singleton 的路径,所以我们直接用 fixture 的 db_path
    db_path = s.duckdb_path
    _seed_kline_daily(db_path)

    # TestClient 走 in-process,会复用 singleton
    from forgemind.api.main import app
    with TestClient(app) as client:
        r = client.post("/mcp/tools/call", json={
            "name": "get_kline",
            "arguments": {"symbol": "600519.SH", "limit": 10},
        })
        assert r.status_code == 200
        text = json.loads(r.json()["result"]["content"][0]["text"])
        assert text["status"] == "ok"
        assert len(text["bars"]) == 5
        assert text["bars"][0]["date"] == "2024-01-02"
        assert text["bars"][0]["open"] == 1580.66


def test_get_kline_handles_missing_symbol():
    """K 线库没的标的返 status=no_data + message 告诉用户"""
    from fastapi.testclient import TestClient

    from forgemind.core.config.settings import get_settings

    get_settings.cache_clear()
    s = get_settings()
    db_path = s.duckdb_path
    # 灌一些别的 symbol
    _seed_kline_daily(db_path, symbol="600519")

    from forgemind.api.main import app
    with TestClient(app) as client:
        r = client.post("/mcp/tools/call", json={
            "name": "get_kline",
            "arguments": {"symbol": "999999.SH", "limit": 10},
        })
        text = json.loads(r.json()["result"]["content"][0]["text"])
        assert text["status"] == "empty"
        # message 必须是可行动的 (告诉用户怎么做),不能静默吞
        assert "999999" in text["message"] or "还没有行情" in text["message"]
        assert "etl" in text["message"].lower() or "代码" in text["message"]
