# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import pandas as pd
import numpy as np

from forgemind.core.strategies.library import (
    MeanReversionStrategy, MomentumStrategy,
    BollingerBandsStrategy, BuyAndHoldStrategy,
    get_strategy_class, STRATEGY_REGISTRY,
)


def make_price_df(n=200, seed=42):
    """生成测试数据"""
    np.random.seed(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, n)))
    return pd.DataFrame({
        "open": close * (1 + np.random.normal(0, 0.005, n)),
        "high": close * (1 + np.abs(np.random.normal(0, 0.01, n))),
        "low": close * (1 - np.abs(np.random.normal(0, 0.01, n))),
        "close": close,
        "volume": np.random.randint(1_000_000, 10_000_000, n),
    }, index=dates)


class TestMeanReversion:
    def test_create(self):
        s = MeanReversionStrategy(parameters={"lookback": 20, "threshold": 2.0})
        assert s.parameters["lookback"] == 20
    
    def test_signals(self):
        s = MeanReversionStrategy(parameters={"lookback": 20, "threshold": 1.5})
        df = make_price_df(200)
        signals = s.generate_signals(df)
        assert len(signals) == 200
        assert "entries" in signals.columns
    
    def test_on_bar(self):
        s = MeanReversionStrategy(parameters={"lookback": 20, "threshold": 1.5})
        df = make_price_df(50)
        # 模拟 25 根 bar
        for i in range(25):
            bar = {"symbol": "TEST", "close": df["close"].iloc[i]}
            sig = s.on_bar(bar)
            # 数据不足时返回 None
        assert hasattr(s, "_prices")


class TestMomentum:
    def test_create(self):
        s = MomentumStrategy()
        assert "lookback" in s.parameters
    
    def test_signals(self):
        s = MomentumStrategy(parameters={"lookback": 30})
        df = make_price_df(300)
        signals = s.generate_signals(df)
        assert len(signals) == 300


class TestBollinger:
    def test_create(self):
        s = BollingerBandsStrategy(parameters={"period": 20, "std_multiplier": 2.0})
        assert s.parameters["period"] == 20
    
    def test_signals(self):
        s = BollingerBandsStrategy(parameters={"period": 20, "std_multiplier": 2.0})
        df = make_price_df(100)
        signals = s.generate_signals(df)
        assert len(signals) == 100


class TestBuyHold:
    def test_signals(self):
        s = BuyAndHoldStrategy()
        df = make_price_df(100)
        signals = s.generate_signals(df)
        # 第一根 + 最后一根
        assert signals["entries"].sum() == 1
        assert signals["exits"].sum() == 1
        assert signals["entries"].iloc[0] == True


class TestRegistry:
    def test_get_strategy_class(self):
        cls = get_strategy_class("ma_cross")
        from forgemind.core.strategies.base import MovingAverageCrossStrategy
        assert cls is MovingAverageCrossStrategy
    
    def test_unknown_strategy(self):
        with pytest.raises(ValueError):
            get_strategy_class("unknown_strategy")
    
    def test_all_strategies(self):
        assert "ma_cross" in STRATEGY_REGISTRY
        assert "mean_reversion" in STRATEGY_REGISTRY
        assert "momentum" in STRATEGY_REGISTRY
        assert "bollinger" in STRATEGY_REGISTRY
        assert "buy_hold" in STRATEGY_REGISTRY