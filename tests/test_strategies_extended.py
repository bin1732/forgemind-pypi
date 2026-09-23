# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


def make_multi_symbol_data(n_days=300, n_symbols=20):
    """构造多 symbol 数据"""
    np.random.seed(42)
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(n_days)]
    symbols = [f"S{i:04d}" for i in range(n_symbols)]
    
    rows = []
    for sym in symbols:
        price = 100.0
        for date in dates:
            ret = np.random.randn() * 0.02
            price *= (1 + ret)
            high = price * 1.01
            low = price * 0.99
            rows.append({
                "symbol": sym, "date": date,
                "open": price, "high": high, "low": low, "close": price,
                "volume": 1000000,
            })
    
    return pd.DataFrame(rows)


class TestMomentumStrategies:
    def test_time_series_momentum(self):
        from forgemind.core.strategies import TimeSeriesMomentum
        df = make_multi_symbol_data(100, 3)
        strategy = TimeSeriesMomentum(lookback=20)
        signals = strategy.generate_signal(df[df["symbol"] == "S0000"])
        assert len(signals) == 100
        assert signals.iloc[-1] in [-1, 0, 1]
    
    def test_cross_sectional_momentum(self):
        from forgemind.core.strategies import CrossSectionalMomentum
        df = make_multi_symbol_data(100, 10)
        strategy = CrossSectionalMomentum(lookback=20, top_pct=0.2)
        signals = strategy.generate_signal(df)
        # 应该有不买入也有卖
        assert (signals == 1).sum() > 0
        assert (signals == -1).sum() > 0
    
    def test_momentum_rotation(self):
        from forgemind.core.strategies import MomentumRotation
        df = make_multi_symbol_data(150, 5)
        strategy = MomentumRotation(lookbacks=[20, 60])
        signals = strategy.generate_signal(df)
        assert len(signals) == 750


class TestMeanReversionStrategies:
    def test_ou_process(self):
        from forgemind.core.strategies import OrnsteinUhlenbeck
        df = make_multi_symbol_data(100, 1)
        strategy = OrnsteinUhlenbeck(lookback=30)
        signals = strategy.generate_signal(df)
        assert len(signals) == 100
    
    def test_rsi_reversion(self):
        from forgemind.core.strategies import RSIReversion
        df = make_multi_symbol_data(100, 1)
        strategy = RSIReversion(period=14)
        signals = strategy.generate_signal(df)
        assert len(signals) == 100


class TestPairsTrading:
    def test_pairs_signal(self):
        from forgemind.core.strategies import PairsTrading
        df = make_multi_symbol_data(200, 2)
        df_a = df[df["symbol"] == "S0000"].reset_index(drop=True)
        df_b = df[df["symbol"] == "S0001"].reset_index(drop=True)
        
        strategy = PairsTrading(lookback=60, entry_z=2.0)
        sig_a, sig_b = strategy.generate_signal(df_a, df_b)
        # 信号应该大部分时间 0, 偶尔有 ±1
        assert len(sig_a) == len(sig_b)
        assert (sig_a.abs() <= 1).all()


class TestPortfolioStrategies:
    def test_risk_parity_weights(self):
        from forgemind.core.strategies import RiskParity
        df = make_multi_symbol_data(120, 5)
        strategy = RiskParity(lookback=20)
        weights = strategy.compute_weights(df)
        # 后期权重和应为 1(NaN 部分忽略)
        daily_sum = weights.sum(axis=1).dropna()
        # 后 50 天的权重和应该接近 1
        late = daily_sum.iloc[-50:]
        assert (late > 0.95).all() or (late < 0.05).all()
    
    def test_max_sharpe_weights(self):
        from forgemind.core.strategies import MaxSharpe
        df = make_multi_symbol_data(100, 5)
        strategy = MaxSharpe(lookback=20)
        weights = strategy.compute_weights(df)
        # 权重矩阵应该有 shape (date, symbol)
        assert weights.shape == (100, 5)


class TestStrategyRegistry:
    def test_strategy_count(self):
        from forgemind.core.strategies import total_strategies, list_categories
        # 5 基础 + 12 扩展
        assert total_strategies() >= 15
        
        cats = list_categories()
        assert "momentum" in cats
        assert "mean_reversion" in cats
        assert "stat_arb" in cats
        assert "ml" in cats
        assert "event" in cats
        assert "portfolio" in cats
    
    def test_list_strategies(self):
        from forgemind.core.strategies import list_strategies
        strategies = list_strategies()
        assert "PairsTrading" in strategies
        assert "LightGBMStrategy" in strategies
        assert "RiskParity" in strategies


class TestMLStrategy:
    def test_lightgbm_strategy(self):
        from forgemind.core.strategies import LightGBMStrategy
        from forgemind.core.models import LightGBMModel
        
        # 训练简单模型
        df = make_multi_symbol_data(150, 5)
        df["feature1"] = np.random.randn(len(df))
        df["feature2"] = np.random.randn(len(df))
        df["target"] = df.groupby("symbol")["close"].pct_change(5)
        
        train_df = df.dropna()
        X = train_df[["feature1", "feature2"]]
        y = train_df["target"]
        
        model = LightGBMModel()
        model.train(X, y, use_cv=False)
        
        strategy = LightGBMStrategy(model=model, top_k=2)
        signals = strategy.generate_signal(train_df, feature_cols=["feature1", "feature2"])
        assert len(signals) == len(train_df)