# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""AI 决策 Agent 必须基于真实数据,而不是每个股票返回同一组常量

发现的状况:`portfolio_context` 六个节点全部返回硬编码字面量:

    fundamentals  pe_ratio=15.5, roe=0.18, revenue_growth_yoy=0.12
    technical      ma_cross="golden", rsi=55.0, macd_signal="positive"
    news           sentiment="positive",
                   key_events=["earnings beat", "new product launch"]
    bull           thesis="基本面+技术面+新闻均偏多,可建仓", target_weight=0.10
    bear           thesis="估值偏高 + 行业 beta 风险 + 监管不确定"

已验证 `forgemind agent` 对茅台(600519)、平安银行(000001)、工商银行
(601398) 输出**逐字节相同**。茅台真实 PE 约 25、ROE 约 30%,平安银行 PE 约 5、
ROE 约 10% —— 而三个标的拿到的是同一组 15.5 / 0.18。

LangGraph 的编排和人工审批 gating 是真的,但"分析"全是常量。
本项目并没有基本面与新闻数据源,所以正确做法不是编,而是如实报不可用;
技术面能由 OHLCV 推出,就该给真实读数。
"""

import pytest

from forgemind.core.agents.portfolio_context import (
    bear_node,
    bull_node,
    fundamentals_node,
    news_node,
    technical_node,
)


class TestNoHardcodedAnalysis:
    def test_fundamentals_reports_unavailable_instead_of_fake_numbers(self):
        r = fundamentals_node({"symbol": "600519"})["fundamentals_analysis"]
        assert r["status"] == "unavailable"
        # 绝不能出现编造的 PE / ROE
        for k in ("pe_ratio", "roe", "revenue_growth_yoy"):
            assert k not in r or r[k] is None, f"{k} 不该有值:{r}"
        assert r["confidence"] == 0.0
        assert r["next_step"], "不可用时要说明怎么才能可用"

    def test_news_reports_unavailable_instead_of_invented_headlines(self):
        r = news_node({"symbol": "600519"})["news_analysis"]
        assert r["status"] == "unavailable"
        assert "key_events" not in r or not r["key_events"]
        assert r["confidence"] == 0.0

    def test_technical_without_data_says_so(self):
        r = technical_node({"symbol": "NEVER_ETL_D_000000"})["technical_analysis"]
        assert r["status"] == "unavailable"
        assert r["signal"] is None
        assert "etl" in r["next_step"]

    def test_bull_bear_without_data_refuse_to_advise(self):
        st = {"symbol": "600519", "technical_analysis": {
            "status": "unavailable", "reason": "没有 K 线"}}
        b = bull_node(st)["bull_case"]
        s = bear_node(st)["bear_case"]
        assert b["target_weight"] == 0.0
        assert s["max_weight"] == 0.0
        assert b["confidence"] == 0.0 and s["confidence"] == 0.0


class TestTechnicalAnalysisIsComputed:
    @pytest.fixture
    def seeded(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from forgemind.core.data.storage import DuckDBStorage

        with DuckDBStorage() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS kline_daily (
                date DATE, symbol VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE,
                close DOUBLE, volume BIGINT, provider VARCHAR,
                PRIMARY KEY (date, symbol))""")
            # 一条**真实形态**的下跌序列:RSI 应进入超卖区
            import math
            px = 1800.0
            for i in range(90):
                px *= (1 - 0.008 - 0.002 * math.sin(i / 5))
                db.execute(
                    "INSERT OR REPLACE INTO kline_daily VALUES "
                    f"('2024-0{(i // 28) + 1}-{(i % 28) + 1:02d}','600519',"
                    f"{px},{px * 1.003},{px * 0.997},{px},1000000,'sina')")
        return tmp_path

    def test_reads_real_numbers_from_duckdb(self, seeded):
        r = technical_node({"symbol": "600519"})["technical_analysis"]
        assert r["status"] == "ok"
        assert r["n_bars"] == 90
        assert 0 <= r["rsi"] <= 100
        # 持续下跌 → MA5 必在 MA20 之下,MACD 必为负
        assert r["ma5"] < r["ma20"], "下跌序列里 MA5 应低于 MA20"
        assert r["macd_hist"] < 0
        assert r["signal"] in ("buy", "sell", "neutral")
        assert r["confidence"] > 0

    def test_two_different_series_give_different_readings(self, seeded):
        """同样长度但形状不同的序列,读数必须不同"""
        from forgemind.core.data.storage import DuckDBStorage

        with DuckDBStorage() as db:
            px = 50.0
            for i in range(90):
                px *= (1 + 0.010)
                db.execute(
                    "INSERT OR REPLACE INTO kline_daily VALUES "
                    f"('2024-0{(i // 28) + 1}-{(i % 28) + 1:02d}','000001',"
                    f"{px},{px * 1.003},{px * 0.997},{px},1000000,'sina')")

        a = technical_node({"symbol": "600519"})["technical_analysis"]
        b = technical_node({"symbol": "000001"})["technical_analysis"]
        assert a["ma5"] != b["ma5"], "不同价格量级的标的算出了同一个 MA5"
        assert a["ma5"] < a["ma20"] and b["ma5"] > b["ma20"], "涨跌方向应相反"

    def test_thesis_mentions_actual_readings(self, seeded):
        st = {"symbol": "600519",
              "technical_analysis": technical_node({"symbol": "600519"})["technical_analysis"]}
        bull = bull_node(st)["bull_case"]
        bear = bear_node(st)["bear_case"]
        assert bull["evidence"], "有技术面数据就该给出论据"
        assert "RSI" in " ".join(bull["evidence"] + bear["evidence"]) or \
               "MA" in " ".join(bull["evidence"] + bear["evidence"])
        # 论据里应出现真实数字
        nums = " ".join(bull["evidence"] + bear["evidence"])
        assert any(ch.isdigit() for ch in nums), f"论据里没有实际读数:{nums}"
        # thesis 必须由 evidence 派生,而不是另写一句。
        # 之前只查 evidence,于是"evidence 真实 + thesis 硬编码"能蒙混过关 ——
        # 注入硬编码的 thesis 后测试照样全绿。
        thesis = bull["thesis"]
        assert thesis == ";".join(bull["evidence"]) or thesis in (
            "技术面未提供看多证据",), (
            f"thesis 应由真实论据拼成,实际是独立文案:{thesis!r} vs "
            f"{bull['evidence']!r}")
        # 缺口必须被列出,不能假装三个维度都看过
        assert "fundamentals" in bull["gaps"] and "news" in bull["gaps"]


class TestNodesActuallyReadTheirInput:
    """根因不是"常量写错了",而是**节点根本不看入参**

    扫描浮点字面量会误报(0.0 表示"无数据所以置信度为零",是正确值)。
    真正的不变量是:节点必须使用 `state` 里的 symbol —— 忽略入参的节点
    对任何股票必然给出同一份输出,改常量只是治标。
    """

    def test_each_node_uses_the_symbol_from_state(self):
        import ast
        import inspect

        import forgemind.core.agents.portfolio_context as mod

        tree = ast.parse(inspect.getsource(mod))
        for n in tree.body:
            if not (isinstance(n, ast.FunctionDef)
                    and n.name in {"technical_node", "bull_node", "bear_node"}):
                continue
            seg = ast.get_source_segment(inspect.getsource(mod), n) or ""
            assert "symbol" in seg, (
                f"{n.name} 从未引用 symbol —— 它对任何股票都会给出同一份结论")

    def test_technical_reads_klines_for_the_requested_symbol(self, tmp_path,
                                                             monkeypatch):
        """技术面必须按请求的 symbol 查库,而不是取第一只票

        用 monkeypatch.chdir 而不是 os.chdir:后者离开测试后不还原,
        临时目录一删,后续所有依赖 cwd 的测试全部失败 —— 我第一版就是这么
        写的,整轮全量跑里 test_data_sources_extended 跟着崩了 5 个。
        """
        import datetime as dt

        from forgemind.core.agents.portfolio_context import _load_kline
        from forgemind.core.data.storage import DuckDBStorage

        monkeypatch.chdir(tmp_path)
        with DuckDBStorage() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS kline_daily (
                date DATE, symbol VARCHAR, open DOUBLE, high DOUBLE,
                low DOUBLE, close DOUBLE, volume BIGINT, provider VARCHAR,
                PRIMARY KEY (date, symbol))""")
            # 日期必须递增:i % 28 会回绕,主键冲突后只剩 28 行,
            # 不到 _load_kline 要求的 30 根,看起来像"读不到数据"
            base_day = dt.date(2024, 1, 1)
            for sym, base in (("AAA", 10.0), ("BBB", 1000.0)):
                for i in range(40):
                    day = (base_day + dt.timedelta(days=i)).isoformat()
                    db.execute(
                        "INSERT OR REPLACE INTO kline_daily VALUES "
                        f"('{day}','{sym}',"
                        f"{base},{base * 1.01},{base * 0.99},{base},1,'sina')")
        a = _load_kline("AAA")
        b = _load_kline("BBB")
        assert a is not None and b is not None
        assert a["close"].iloc[-1] == pytest.approx(10.0)
        assert b["close"].iloc[-1] == pytest.approx(1000.0)
