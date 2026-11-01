# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""代码格式必须统一 —— 否则用户照文档跑就是"查不到数据"

真实用户旅程(照 README 从零装一遍)抓到的:

    $ forgemind etl --symbols 600519 ...        # 落库 symbol='600519'
    $ forgemind agent --symbol 600519.SH        # 命令**默认值**,带后缀
    本地没有 600519.SH 的 K 线(少于 30 根)     ← 数据其实就在库里

ETL 存 6 位代码,CLI / API / MCP 的入参常带交易所后缀。不归一化时,
用户看到的提示是"没有行情数据"—— 像是没拉成功,其实是格式不匹配,
于是用户会反复重跑 etl、换日期区间,永远查不出来。

归一化必须放在**查询前**由存储层统一做,而不是指望每个调用方记得剥后缀。
"""

import pytest


class TestBareSymbol:
    @pytest.mark.parametrize("raw,expected", [
        ("600519.SH", "600519"),
        ("600519.sh", "600519"),
        ("sh600519", "600519"),
        ("SH600519", "600519"),
        ("000001.SZ", "000001"),
        ("sz000001", "000001"),
        ("600519", "600519"),
        ("  600519  ", "600519"),
        ("600519-SH", "600519"),
        ("600519_SH", "600519"),
        ("", ""),
    ])
    def test_normalises(self, raw, expected):
        from forgemind.core.data.storage import bare_symbol

        assert bare_symbol(raw) == expected

    def test_does_not_mangle_non_symbols(self):
        from forgemind.core.data.storage import bare_symbol

        # 非代码字符串不应被破坏成空串
        assert bare_symbol("DEMO") == "DEMO"
        assert bare_symbol("AAPL") == "AAPL"


class TestQueriesNormaliseBeforeLookingUp:
    """每一处按 symbol 查库的地方都必须先归一化"""

    SOURCES = [
        "forgemind/core/agents/portfolio_context.py",
        "forgemind/core/agents/stock_picker.py",
        "forgemind/mcp/server.py",
    ]

    @pytest.mark.parametrize("rel", SOURCES)
    def test_source_uses_bare_symbol(self, rel):
        src = (pytest.importorskip("pathlib").Path(__file__).resolve().parent.parent
               / rel).read_text(encoding="utf-8")
        assert "bare_symbol(" in src, f"{rel} 查询前没有归一化"
        assert "WHERE symbol = ?" in src

    def test_no_raw_symbol_reaches_the_query(self):
        """源码里不应再有 [symbol] 直接进 WHERE 的写法"""
        import pathlib
        import re

        root = pathlib.Path(__file__).resolve().parent.parent / "forgemind"
        bad = []
        for p in root.rglob("*.py"):
            if "build" in p.parts:
                continue
            src = p.read_text(encoding="utf-8")
            for m in re.finditer(r"WHERE symbol = \?[^\n]*\n(?:\s*\n)?\s*(\[[^\]]*\])", src):
                args = m.group(1)
                if "bare_symbol(" not in args and "symbol" in args:
                    bad.append(f"{p.relative_to(root.parent)}: {args}")
        assert not bad, "这些查询把未归一化的 symbol 送进了 WHERE:\n  " + "\n  ".join(bad)


class TestEndToEndLookup:
    @pytest.fixture
    def seeded(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from forgemind.core.data.storage import DuckDBStorage

        with DuckDBStorage() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS kline_daily (
                date DATE, symbol VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE,
                close DOUBLE, volume BIGINT, provider VARCHAR,
                PRIMARY KEY (date, symbol))""")
            import datetime as dt
            for i in range(90):
                day = (dt.date(2024, 1, 1) + dt.timedelta(days=i)).isoformat()
                db.execute("INSERT OR REPLACE INTO kline_daily VALUES "
                           f"('{day}','600519',10,10.1,9.9,10.05,1000,'sina')")

    def test_agent_finds_data_regardless_of_how_the_user_types_it(self, seeded):
        """用户写 600519 / 600519.SH / sh600519 都必须查到同一批数据"""
        from forgemind.core.agents.portfolio_context import _load_kline

        for s in ("600519", "600519.SH", "sh600519", "SH600519"):
            df = _load_kline(s)
            assert df is not None, f"{s} 查不到数据,而库里明明有"
            assert len(df) == 90, f"{s} 拿到 {len(df)} 行,应为 90"

    def test_picker_finds_data_for_suffixed_symbol(self, seeded):
        import asyncio

        from forgemind.core.agents.stock_picker import StockPickerAgent

        picks = asyncio.run(StockPickerAgent().pick(universe=["600519.SH"], top_n=1))
        assert picks, "带后缀的代码在有数据时不该返回空"
