# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import numpy as np
import pandas as pd


def make_returns_series(n=252, mean=0.001, std=0.02, seed=42):
    np.random.seed(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    returns = np.random.normal(mean, std, n)
    return pd.Series(returns, index=dates)


class TestBacktestReport:
    def test_compute_metrics(self):
        from forgemind.core.backtest import BacktestReport
        returns = make_returns_series()
        metrics = BacktestReport.compute_metrics(returns)
        
        assert metrics.sharpe is not None
        assert metrics.max_drawdown <= 0
        assert metrics.volatility > 0
        assert metrics.cagr is not None
        assert 0 <= metrics.win_rate <= 1
    
    def test_metrics_with_benchmark(self):
        from forgemind.core.backtest import BacktestReport
        returns = make_returns_series(seed=42)
        benchmark = make_returns_series(seed=99)
        metrics = BacktestReport.compute_metrics(returns, benchmark_returns=benchmark)
        assert metrics.information_ratio is not None
    
    def test_metrics_summary(self):
        from forgemind.core.backtest import BacktestReport
        returns = make_returns_series()
        metrics = BacktestReport.compute_metrics(returns)
        s = metrics.summary()
        assert "Sharpe" in s
        assert "Total Return" in s


class TestWalkForward:
    def test_wfo_split(self):
        from forgemind.core.backtest import WalkForwardOptimizer
        opt = WalkForwardOptimizer(
            strategy_factory=lambda **p: p,
            backtest_fn=lambda s, d: pd.Series([0.001] * len(d)),
            n_folds=5,
        )
        df = make_returns_series(500)
        folds = opt._split_folds(len(df))
        assert len(folds) == 5
        for ts, te, vs, ve in folds:
            # train 段在 test 段之前(时序不重叠)
            assert te <= vs, f"train_end {te} > test_start {vs}"
            # test_end > test_start
            assert ve > vs
    
    def test_wfo_run(self):
        from forgemind.core.backtest import WalkForwardOptimizer
        
        def strategy_factory(lookback=10):
            return {"lookback": lookback}
        
        def backtest_fn(strategy, data):
            # 简化的 buy-and-hold
            return pd.Series([0.001] * len(data), index=data.index)
        
        opt = WalkForwardOptimizer(
            strategy_factory=strategy_factory,
            backtest_fn=backtest_fn,
            n_folds=3,
        )
        df = make_returns_series(500)
        result = opt.run(df, {"lookback": [10, 20, 30]}, primary_metric="sharpe")
        
        assert len(result.folds) > 0
        assert result.combined_metrics is not None


class TestMonteCarlo:
    def test_run(self):
        from forgemind.core.backtest import MonteCarloSimulator
        
        def strategy_factory(lookback=10, threshold=0.5):
            return (lookback, threshold)
        
        def backtest_fn(strategy, data):
            return pd.Series([0.001] * len(data), index=data.index)
        
        mc = MonteCarloSimulator(
            strategy_factory=strategy_factory,
            backtest_fn=backtest_fn,
            n_simulations=20,
        )
        df = make_returns_series(200)
        result = mc.run(df, {"lookback": 10, "threshold": 0.5})
        
        assert "sharpe_distribution" in result
        assert len(result["sharpe_distribution"]) > 0
        assert result["n_successful"] > 0


class TestSlippage:
    def test_fixed_slippage(self):
        from forgemind.core.backtest import SlippageModel
        price = SlippageModel.fixed_slippage(100.0, 100, bps=5.0)
        assert price == 100.05  # 5 bps = 0.05
    
    def test_linear_slippage(self):
        from forgemind.core.backtest import SlippageModel
        price = SlippageModel.linear_slippage(100.0, 1000, adv=10000, impact_bps=10.0)
        # adv_pct = 0.1, slippage = price * adv_pct * impact_bps / 10000
        # = 100 * 0.1 * 10 / 10000 = 0.01
        assert abs(price - 100.01) < 0.001
    
    def test_sqrt_slippage(self):
        from forgemind.core.backtest import SlippageModel
        price = SlippageModel.square_root_slippage(100.0, 1000, adv=10000, impact_bps=10.0)
        # slippage = price * sqrt(adv_pct) * impact_bps / 10000
        # = 100 * sqrt(0.1) * 10 / 10000 ≈ 0.0316
        assert abs(price - 100.0316) < 0.001


class TestPortfolioBacktest:
    def test_simple_portfolio(self):
        from forgemind.core.backtest import PortfolioBacktest
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        symbols = ["A", "B", "C"]
        
        # 权重每天均匀
        weights = pd.DataFrame(
            [[1/3, 1/3, 1/3]] * 100, index=dates, columns=symbols
        )
        # 价格随机走
        np.random.seed(42)
        prices = pd.DataFrame(
            100 * (1 + np.random.normal(0, 0.02, (100, 3))).cumprod(axis=0),
            index=dates, columns=symbols,
        )
        
        pf = PortfolioBacktest(weights, prices, rebalance_freq=5)
        returns = pf.run()
        assert len(returns) > 0
        # 收益应该与价格变动方向一致
        assert returns.std() > 0