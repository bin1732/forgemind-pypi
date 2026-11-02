# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""回测端点必须优先用已落盘的真实行情。

命令行与 MCP 工具都走 DuckDB 里的真实 K 线,HTTP 端点原来却永远用
合成行情:用户明明已经跑过 forgemind etl,接口给出的仍是随机生成的
数字。端点有标注字段说明来源,但能力本身缺失,三条路径口径也不一致。

另外:落库存的是 6 位代码,入参常带交易所后缀,归一化放在查询参数里,
任何上游传 '600519.SH' 都要能命中。
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest
from _path_setup import child_env, inline_path_setup
from fastapi.testclient import TestClient

from forgemind.api.main import app
from forgemind.core.data.storage import DuckDBStorage


def _seed(symbol: str = "600519", days: int = 120):
    """落一段有涨有跌的 K 线,波动不为零才能算出非零 Sharpe。"""
    rows = []
    for i in range(days):
        d = date(2024, 1, 2) + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        close = 100.0 * (1.003 ** i) * (1 + 0.02 * math.sin(i / 3.0))
        rows.append((d, symbol, close * 0.998, close * 1.005, close * 0.995,
                     round(close, 4), 1_000_000, "test"))
    with DuckDBStorage() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS kline_daily (
                date DATE, symbol VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE,
                close DOUBLE, volume BIGINT, provider VARCHAR,
                PRIMARY KEY (date, symbol))""")
        for row in rows:
            db.execute(
                "INSERT INTO kline_daily (date, symbol, open, high, low, close, "
                "volume, provider) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", list(row))
    return len(rows)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestBacktestDataSource:
    def test_uses_stored_klines(self, client):
        n = _seed()
        r = client.post("/api/v1/backtest/run", json={
            "strategy": "ma_cross", "symbol": "600519",
            "start_date": "2024-01-01", "end_date": "2024-06-30",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["is_real_data"] is True, (
            f"本地有 {n} 根 K 线,接口却没用真数据: {d['data_source']}")
        assert d["data_source"] == "duckdb_kline_daily"
        assert d["n_bars"] > 0
        assert not d.get("warning"), "走了真数据还挂着降级警告"

    def test_symbol_with_exchange_suffix_hits_stored_rows(self, client):
        _seed("600519")
        r = client.post("/api/v1/backtest/run", json={
            "strategy": "ma_cross", "symbol": "600519.SH",
            "start_date": "2024-01-01", "end_date": "2024-06-30",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["is_real_data"] is True, (
            f"带后缀的代码没命中落盘数据: {d['data_source']}")

    def test_falls_back_and_says_why(self, client):
        # 建一张空的行情表:表在、但没有该标的的 K 线,
        # 降级说明里应当指出缺的是哪个标的
        with DuckDBStorage() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS kline_daily (
                    date DATE, symbol VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE,
                    close DOUBLE, volume BIGINT, provider VARCHAR,
                    PRIMARY KEY (date, symbol))""")
        r = client.post("/api/v1/backtest/run", json={
            "strategy": "ma_cross", "symbol": "999999",
            "start_date": "2024-01-01", "end_date": "2024-06-30",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["is_real_data"] is False
        assert d["data_source"] == "synthetic_random_walk"
        assert d.get("warning"), "降级到合成行情却没有声明"
        assert "999999" in d["warning"], (
            f"降级说明里没有指出缺哪个标的的数据: {d['warning']}")

    def test_real_data_response_has_no_fabrication_markers(self, client):
        _seed()
        r = client.post("/api/v1/backtest/run", json={
            "strategy": "ma_cross", "symbol": "600519",
            "start_date": "2024-01-01", "end_date": "2024-06-30",
        })
        body = r.text.lower()
        for marker in ("mock data", "placeholder", "dummy", "示例数据"):
            assert marker not in body, f"响应里有编造标记 {marker}"
        # 内部路径与凭据不能泄露
        for leak in ("127.0", "::1", "password", "traceback", "site-packages",
                     "/workspace"):
            assert leak not in body, f"响应泄露 {leak}"


class TestPipelineIsDeterministic:
    """流水线端点自称"确定性",那就必须跨进程也一致。

    种子来自内置 hash,而字符串/元组的 hash 每个进程加盐 —— 同一组标的
    换个进程就会得到不同的行情,页面一刷新数字就变。
    """

    def test_same_symbols_give_same_numbers_across_processes(self):
        import subprocess
        import sys
        from pathlib import Path

        repo = Path(__file__).resolve().parent.parent
        script = (
            "import json, sys;"
            f"{inline_path_setup()}"
            "from fastapi.testclient import TestClient;"
            "from forgemind.api.main import app;"
            "c = TestClient(app);"
            "r = c.post('/api/pipeline/run', json={'symbols':['600519','000001'],"
            "'start':'2024-01-01','end':'2024-03-31'});"
            "d = r.json();"
            "print(json.dumps([d.get('sharpe'), d.get('max_drawdown'),"
            "d.get('n_bars')]))"
        )
        env = child_env({"PYTHONHASHSEED": "random", "PATH": "/usr/bin:/bin"})
        outs = []
        for _ in range(2):
            proc = subprocess.run([sys.executable, "-c", script],
                                  capture_output=True, text=True, timeout=300,
                                  env=env, cwd=str(repo))
            assert proc.returncode == 0, proc.stderr[-400:]
            outs.append(proc.stdout.strip().splitlines()[-1])
        assert outs[0] == outs[1], (
            f"两个进程算出的结果不一样: {outs}")

    def test_declares_its_data_source(self, client):
        r = client.post("/api/pipeline/run", json={
            "symbols": ["600519"], "start": "2024-01-01", "end": "2024-03-31"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("data_source"), "流水线响应没有标注数据来源"
        assert d.get("warning"), "流水线响应没有说明合成行情的局限"
