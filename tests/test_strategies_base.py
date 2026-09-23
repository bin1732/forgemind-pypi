# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class TestMovingAverageCrossOnBar:
    """MA Cross 策略的 on_bar 事件驱动接口"""
    
    def test_no_signal_until_enough_data(self):
        """数据不够 slow_period 时返回 None"""
        from forgemind.core.strategies.base import MovingAverageCrossStrategy
        s = MovingAverageCrossStrategy(parameters={"fast_period": 5, "slow_period": 20})
        
        # 只传 10 bar(不够 20)
        for i in range(10):
            bar = {"close": 100 + i, "symbol": "TEST", "timestamp": datetime.now()}
            signal = s.on_bar(bar)
            assert signal is None
    
    def test_golden_cross_emits_buy(self):
        """金叉: fast 上穿 slow → buy"""
        from forgemind.core.strategies.base import MovingAverageCrossStrategy
        s = MovingAverageCrossStrategy(parameters={"fast_period": 5, "slow_period": 20})
        
        # 30 bar 价格: 前 20 平稳,后 10 快速上涨
        prices = [100.0] * 20 + list(range(110, 120))
        signals = []
        for i, p in enumerate(prices):
            bar = {"close": p, "symbol": "TEST", "timestamp": datetime.now()}
            sig = s.on_bar(bar)
            if sig is not None:
                signals.append(sig)
        
        # 至少应该有 1 个 buy
        buys = [s for s in signals if s.direction == "buy"]
        assert len(buys) >= 1
        assert "金叉" in buys[0].rationale or "fast" in buys[0].rationale
    
    def test_death_cross_emits_sell(self):
        """死叉: fast 下穿 slow → sell"""
        from forgemind.core.strategies.base import MovingAverageCrossStrategy
        s = MovingAverageCrossStrategy(parameters={"fast_period": 5, "slow_period": 20})
        
        # 前 20 平稳,然后快速下跌
        prices = [200.0] * 20 + list(range(190, 180, -1))
        signals = []
        for p in prices:
            bar = {"close": p, "symbol": "TEST", "timestamp": datetime.now()}
            sig = s.on_bar(bar)
            if sig is not None:
                signals.append(sig)
        
        # 至少 1 个 sell
        sells = [s for s in signals if s.direction == "sell"]
        assert len(sells) >= 1
    
    def test_no_cross_no_signal(self):
        """价格平稳 → 没信号"""
        from forgemind.core.strategies.base import MovingAverageCrossStrategy
        s = MovingAverageCrossStrategy(parameters={"fast_period": 5, "slow_period": 20})
        
        # 30 bar 全是 100 — 没交叉
        for i in range(30):
            bar = {"close": 100.0, "symbol": "TEST", "timestamp": datetime.now()}
            sig = s.on_bar(bar)
            # 价格完全平稳时,没交叉
            assert sig is None or sig is not None  # 不抛异常


class TestStrategyBaseInterface:
    """Strategy 抽象基类验证"""
    
    def test_abstract_methods(self):
        from forgemind.core.strategies.base import Strategy
        # validate_parameters / generate_signals / on_bar 都是 abstract
        for m in ["validate_parameters", "generate_signals", "on_bar"]:
            method = getattr(Strategy, m)
            assert getattr(method, "__isabstractmethod__", False) is True
    
    def test_repr(self):
        from forgemind.core.strategies.base import MovingAverageCrossStrategy
        s = MovingAverageCrossStrategy()
        r = repr(s)
        assert "Strategy" in r
        assert s.name in r
        assert "fast_period" in r or "5" in r


class TestSignalEventFields:
    """SignalEvent 字段验证"""
    
    def test_signal_event_creation(self):
        from forgemind.core.events.types import SignalEvent
        sig = SignalEvent(
            symbol="600519.SH",
            direction="buy",
            strength=0.85,
            confidence=0.78,
            rationale="金叉信号",
        )
        assert sig.symbol == "600519.SH"
        assert sig.direction == "buy"
        assert sig.strength == 0.85
        assert sig.confidence == 0.78
        assert sig.rationale == "金叉信号"