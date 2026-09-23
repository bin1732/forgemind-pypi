# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from forgemind.core.events.types import (
    MarketTickEvent, SignalEvent, OrderRequestEvent,
    FillEvent, AIDecisionEvent, EventType,
)
from forgemind.core.strategies.base import MovingAverageCrossStrategy
from forgemind.core.agents.portfolio_context import (
    PortfolioContext, PortfolioPosition,
    AgentState, build_agent_graph, get_agent_graph,
)


class TestEvents:
    def test_market_tick(self):
        e = MarketTickEvent(symbol="600519.SH", bid=100.0, ask=100.5, last=100.3, volume=1000)
        assert e.event_type == EventType.MARKET_TICK
        assert e.symbol == "600519.SH"
        assert e.bid == 100.0
    
    def test_signal_event(self):
        s = SignalEvent(
            symbol="600519.SH", direction="buy",
            strength=0.8, confidence=0.9, rationale="test"
        )
        assert s.direction == "buy"
        assert s.confidence == 0.9
    
    def test_order_request(self):
        o = OrderRequestEvent(symbol="600519.SH", side="buy", quantity=100, price=100.5)
        assert o.side == "buy"
        assert o.quantity == 100
        assert o.price == 100.5
        assert len(o.client_order_id) > 0


class TestStrategy:
    def test_create(self):
        s = MovingAverageCrossStrategy(parameters={"fast_period": 5, "slow_period": 20})
        assert s.parameters["fast_period"] == 5
        assert s.parameters["slow_period"] == 20
    
    def test_default_params(self):
        s = MovingAverageCrossStrategy()
        assert s.parameters["fast_period"] == 5
        assert s.parameters["slow_period"] == 20
    
    def test_generate_signals(self):
        s = MovingAverageCrossStrategy(parameters={"fast_period": 3, "slow_period": 10})
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        np.random.seed(42)
        price_df = pd.DataFrame({
            "open": np.random.uniform(95, 105, 100),
            "high": np.random.uniform(100, 110, 100),
            "low": np.random.uniform(90, 100, 100),
            "close": np.random.uniform(95, 105, 100),
            "volume": np.random.randint(1000000, 5000000, 100),
        }, index=dates)
        
        signals = s.generate_signals(price_df)
        assert len(signals) == 100
        assert "entries" in signals.columns
        assert "exits" in signals.columns
    
    def test_on_bar(self):
        s = MovingAverageCrossStrategy(parameters={"fast_period": 3, "slow_period": 5})
        bar = {"symbol": "TEST", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000}
        sig = s.on_bar(bar)
        # 第 1 根 bar 数据不足,应该返回 None
        assert sig is None


class TestPortfolioContext:
    def test_create(self):
        p = PortfolioContext(cash=100000.0, total_equity=100000.0)
        assert p.cash == 100000.0
        assert len(p.positions) == 0
    
    def test_has_position(self):
        pos = PortfolioPosition(symbol="600519.SH", quantity=100, avg_price=100.0)
        p = PortfolioContext(cash=50000.0, total_equity=60000.0, positions=[pos])
        assert p.has_position("600519.SH")
        assert not p.has_position("000001.SZ")
    
    def test_get_position(self):
        pos = PortfolioPosition(symbol="600519.SH", quantity=100, avg_price=100.0)
        p = PortfolioContext(cash=50000.0, total_equity=60000.0, positions=[pos])
        result = p.get_position("600519.SH")
        assert result is not None
        assert result.quantity == 100


class TestAgentGraph:
    def test_compile(self):
        graph = build_agent_graph()
        assert graph is not None
    
    def test_singleton(self):
        g1 = get_agent_graph()
        g2 = get_agent_graph()
        assert g1 is g2  # 单例


@pytest.mark.asyncio
class TestAgentRun:
    async def test_interrupt_before(self):
        """测试 interrupt_before 卡在 PM 节点"""
        graph = get_agent_graph()
        from langchain_core.runnables import RunnableConfig
        from uuid import uuid4
        
        pos = PortfolioPosition(symbol="600519.SH", quantity=100, avg_price=1500.0)
        portfolio = PortfolioContext(
            cash=80000.0, total_equity=200000.0, positions=[pos],
        )
        
        config = RunnableConfig(configurable={"thread_id": f"test-{uuid4()}"})
        initial_state: AgentState = {
            "symbol": "600519.SH",
            "as_of": datetime.now(),
            "portfolio": portfolio.model_dump(mode="json"),
            "run_id": str(uuid4()),
            "messages": [],
            "requires_human_review": True,
            "confidence": 0.0,
        }
        
        # 第一次 invoke → 卡在 PM
        result = await graph.ainvoke(initial_state, config=config)
        
        # 三个 sub-agent 应该跑完,PM 没跑
        assert result.get("bull_case") is not None
        assert result.get("bear_case") is not None
        assert result.get("fundamentals_analysis") is not None
        assert result.get("technical_analysis") is not None
        assert result.get("news_analysis") is not None
        # PM 没跑
        assert result.get("pm_decision") is None
        # 强制人工审批
        assert result.get("requires_human_review") is True
    
    async def test_full_run_with_approval(self):
        """测试人工审批通过后,PM 节点跑完"""
        graph = get_agent_graph()
        from langchain_core.runnables import RunnableConfig
        from uuid import uuid4
        
        pos = PortfolioPosition(symbol="600519.SH", quantity=100, avg_price=1500.0)
        portfolio = PortfolioContext(
            cash=80000.0, total_equity=200000.0, positions=[pos],
        )
        
        config = RunnableConfig(configurable={"thread_id": f"test-{uuid4()}"})
        initial_state: AgentState = {
            "symbol": "600519.SH",
            "as_of": datetime.now(),
            "portfolio": portfolio.model_dump(mode="json"),
            "run_id": str(uuid4()),
            "messages": [],
            "requires_human_review": True,
            "confidence": 0.0,
        }
        
        # 第一次 → 卡在 PM
        result = await graph.ainvoke(initial_state, config=config)
        assert result.get("pm_decision") is None
        
        # 第二次 → None 表示通过审批
        result_final = await graph.ainvoke(None, config=config)
        assert result_final.get("pm_decision") is not None
        assert result_final.get("decision_event") is not None


class TestSettings:
    def test_singleton(self):
        from forgemind.core.config.settings import get_settings
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
    
    def test_defaults(self):
        from forgemind.core.config.settings import get_settings
        s = get_settings()
        assert s.env == "dev"
        assert s.mode == "server"
        assert s.api_port == 8000
        assert s.ch_port == 9000
    
    def test_pg_dsn(self):
        from forgemind.core.config.settings import get_settings
        s = get_settings()
        assert "postgresql" in s.pg_dsn
        assert s.pg_user in s.pg_dsn
    
    def test_redis_url(self):
        from forgemind.core.config.settings import get_settings
        s = get_settings()
        assert "redis://" in s.redis_url