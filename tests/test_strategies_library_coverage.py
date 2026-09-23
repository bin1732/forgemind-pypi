# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def _make_price_df(n=300, seed=42):
    """构造 K 线"""
    np.random.seed(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, n)))
    open_ = close * (1 + np.random.randn(n) * 0.005)
    high = close * (1 + np.abs(np.random.randn(n) * 0.01))
    low = close * (1 - np.abs(np.random.randn(n) * 0.01))
    volume = np.random.randint(1_000_000, 10_000_000, n)
    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "date": dates,
    }).set_index("date")


class TestMeanReversionStrategy:
    def test_create_default_params(self):
        from forgemind.core.strategies.library import MeanReversionStrategy
        s = MeanReversionStrategy()
        s.validate_parameters()
        assert s.parameters["lookback"] == 20
        assert s.parameters["threshold"] == 2.0
    
    def test_generate_signals_basic(self):
        from forgemind.core.strategies.library import MeanReversionStrategy
        s = MeanReversionStrategy()
        df = _make_price_df(300)
        signals = s.generate_signals(df)
        assert "entries" in signals.columns
        assert "exits" in signals.columns
        assert signals["entries"].dtype == bool
    
    def test_on_bar_insufficient_prices(self):
        """bar 数不足应返回 None"""
        from forgemind.core.strategies.library import MeanReversionStrategy
        s = MeanReversionStrategy(parameters={"lookback": 20, "threshold": 2.0})
        # 只 5 个 bar,不够
        result = s.on_bar({"symbol": "X", "close": 100.0})
        assert result is None
    
    def test_on_bar_buy_signal(self):
        """z_score < -threshold → buy"""
        from forgemind.core.strategies.library import MeanReversionStrategy
        from forgemind.core.events.types import SignalEvent
        s = MeanReversionStrategy(parameters={"lookback": 20, "threshold": 1.0})
        # 喂 20 个稳定价格,然后暴跌触发
        for i in range(20):
            s.on_bar({"symbol": "X", "close": 100.0})
        # 暴跌到 50
        signal = s.on_bar({"symbol": "X", "close": 50.0})
        assert signal is not None
        assert signal.direction == "buy"
        assert "均值回归" in signal.rationale
    
    def test_on_bar_sell_signal(self):
        """z_score > threshold → sell"""
        from forgemind.core.strategies.library import MeanReversionStrategy
        s = MeanReversionStrategy(parameters={"lookback": 20, "threshold": 1.0})
        for i in range(20):
            s.on_bar({"symbol": "X", "close": 100.0})
        # 暴涨到 200
        signal = s.on_bar({"symbol": "X", "close": 200.0})
        assert signal is not None
        assert signal.direction == "sell"


class TestMomentumStrategy:
    def test_create_default_params(self):
        from forgemind.core.strategies.library import MomentumStrategy
        s = MomentumStrategy()
        s.validate_parameters()
        assert s.parameters["lookback"] == 60
        assert s.parameters["top_quantile"] == 0.7
    
    def test_generate_signals(self):
        from forgemind.core.strategies.library import MomentumStrategy
        s = MomentumStrategy()
        df = _make_price_df(500)  # 需要 252 滚动
        signals = s.generate_signals(df)
        assert signals["entries"].dtype == bool
    
    def test_on_bar_insufficient_data(self):
        from forgemind.core.strategies.library import MomentumStrategy
        s = MomentumStrategy(parameters={"lookback": 10})
        # 仅 5 bars
        for i in range(5):
            result = s.on_bar({"symbol": "X", "close": 100.0})
        assert result is None
    
    def test_on_bar_no_signal(self):
        """return <= 5% → 无信号"""
        from forgemind.core.strategies.library import MomentumStrategy
        s = MomentumStrategy(parameters={"lookback": 10})
        for i in range(300):
            s.on_bar({"symbol": "X", "close": 100.0})
        # 小波动 → 不应触发
        signal = s.on_bar({"symbol": "X", "close": 100.5})
        assert signal is None
    
    def test_on_bar_momentum_signal(self):
        """return > 5% → buy"""
        from forgemind.core.strategies.library import MomentumStrategy
        # 喂足 bars(lookback + 252 = 262)
        s = MomentumStrategy(parameters={"lookback": 10})
        for i in range(262):
            s.on_bar({"symbol": "X", "close": 100.0})
        # 喂一个价格,让 return > 5%
        s.on_bar({"symbol": "X", "close": 100.0})  # 11 前的 ref
        s.on_bar({"symbol": "X", "close": 110.0})  # 10% 涨幅
        signal = s.on_bar({"symbol": "X", "close": 110.0})  # 触发
        assert signal is not None
        assert signal.direction == "buy"
        assert "动量" in signal.rationale


class TestBollingerBandsStrategy:
    def test_create_default_params(self):
        from forgemind.core.strategies.library import BollingerBandsStrategy
        s = BollingerBandsStrategy()
        s.validate_parameters()
        assert s.parameters["period"] == 20
        assert s.parameters["std_multiplier"] == 2.0
    
    def test_generate_signals(self):
        from forgemind.core.strategies.library import BollingerBandsStrategy
        s = BollingerBandsStrategy()
        df = _make_price_df(300)
        signals = s.generate_signals(df)
        assert signals["entries"].dtype == bool
    
    def test_on_bar_insufficient_prices(self):
        from forgemind.core.strategies.library import BollingerBandsStrategy
        s = BollingerBandsStrategy(parameters={"period": 20})
        for i in range(10):
            result = s.on_bar({"symbol": "X", "close": 100.0})
        assert result is None
    
    def test_on_bar_lower_band_buy(self):
        """价格 <= lower band → buy"""
        from forgemind.core.strategies.library import BollingerBandsStrategy
        s = BollingerBandsStrategy(parameters={"period": 20, "std_multiplier": 2.0})
        # 20 个 100,然后暴跌到 50(下轨外)
        for i in range(20):
            s.on_bar({"symbol": "X", "close": 100.0})
        signal = s.on_bar({"symbol": "X", "close": 50.0})
        assert signal is not None
        assert signal.direction == "buy"
    
    def test_on_bar_upper_band_sell(self):
        """价格 >= upper band → sell"""
        from forgemind.core.strategies.library import BollingerBandsStrategy
        s = BollingerBandsStrategy(parameters={"period": 20, "std_multiplier": 2.0})
        for i in range(20):
            s.on_bar({"symbol": "X", "close": 100.0})
        signal = s.on_bar({"symbol": "X", "close": 200.0})
        assert signal is not None
        assert signal.direction == "sell"


class TestBuyAndHoldStrategy:
    def test_validate_params(self):
        from forgemind.core.strategies.library import BuyAndHoldStrategy
        s = BuyAndHoldStrategy()
        s.validate_parameters()  # 空 pass,不抛错
    
    def test_generate_signals(self):
        from forgemind.core.strategies.library import BuyAndHoldStrategy
        s = BuyAndHoldStrategy()
        df = _make_price_df(100)
        signals = s.generate_signals(df)
        assert signals["entries"].iloc[0] == True
        assert signals["exits"].iloc[-1] == True
        assert signals["entries"].iloc[1] == False
    
    def test_on_bar_buy_once(self):
        from forgemind.core.strategies.library import BuyAndHoldStrategy
        s = BuyAndHoldStrategy()
        # 第一次应 buy
        sig1 = s.on_bar({"symbol": "X", "close": 100.0})
        assert sig1 is not None
        assert sig1.direction == "buy"
        # 第二次应 None
        sig2 = s.on_bar({"symbol": "X", "close": 101.0})
        assert sig2 is None


class TestStrategyRegistry:
    def test_get_strategy_class(self):
        from forgemind.core.strategies.library import get_strategy_class, STRATEGY_REGISTRY
        for name in STRATEGY_REGISTRY:
            cls = get_strategy_class(name)
            assert cls is not None
            assert cls.__name__ in STRATEGY_REGISTRY[name].__name__
    
    def test_unknown_strategy_raises(self):
        from forgemind.core.strategies.library import get_strategy_class
        with pytest.raises(ValueError, match="Unknown strategy"):
            get_strategy_class("non_existent_strategy")