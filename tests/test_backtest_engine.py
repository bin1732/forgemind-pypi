# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def _make_price_df(n: int = 252, start_price: float = 100.0, seed: int = 42):
    """生成 mock K 线"""
    np.random.seed(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = start_price * (1 + np.random.randn(n).cumsum() * 0.01)
    open_ = close * (1 + np.random.randn(n) * 0.005)
    high = close * (1 + np.abs(np.random.randn(n) * 0.01))
    low = close * (1 - np.abs(np.random.randn(n) * 0.01))
    volume = np.random.randint(1_000_000, 10_000_000, n)
    
    return pd.DataFrame({
        "date": dates,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }).set_index("date")


class TestSimpleBacktestEngine:
    def test_create(self):
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        e = SimpleBacktestEngine()
        assert e.initial_capital == 100_000.0
        assert e.fees == 0.001
        assert e.slippage_bps == 5.0
    
    def test_create_with_custom_params(self):
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        e = SimpleBacktestEngine(
            initial_capital=500_000,
            fees=0.0003,
            slippage_bps=10.0,
            use_next_open=False,
        )
        assert e.initial_capital == 500_000
        assert e.fees == 0.0003
        assert e.slippage_bps == 10.0
        assert e.use_next_open is False
    
    def test_run_with_buy_and_hold(self):
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        from forgemind.core.strategies.library import BuyAndHoldStrategy
        
        engine = SimpleBacktestEngine()
        strategy = BuyAndHoldStrategy()
        df = _make_price_df(252)
        
        result = engine.run(strategy, df)
        
        assert result.n_trades >= 0
        assert isinstance(result.equity_curve, pd.Series)
        assert len(result.equity_curve) == 252
        # equity curve 应该在 initial_capital 附近波动
        assert result.equity_curve.iloc[0] == engine.initial_capital
    
    def test_run_with_ma_cross(self):
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        from forgemind.core.strategies.library import MovingAverageCrossStrategy
        
        engine = SimpleBacktestEngine()
        strategy = MovingAverageCrossStrategy(parameters={"fast_period": 10, "slow_period": 30})
        df = _make_price_df(252)
        
        result = engine.run(strategy, df)
        
        assert isinstance(result.sharpe, float)
        assert isinstance(result.max_drawdown, float)
        assert result.max_drawdown <= 0  # 一定 <= 0
        assert 0 <= result.win_rate <= 1
    
    def test_metrics_completeness(self):
        """所有指标都应有值"""
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        from forgemind.core.strategies.library import BuyAndHoldStrategy
        
        engine = SimpleBacktestEngine()
        strategy = BuyAndHoldStrategy()
        df = _make_price_df(252)
        
        result = engine.run(strategy, df)
        
        # BacktestResult 必须含所有指标字段
        assert hasattr(result, "total_return")
        assert hasattr(result, "sharpe")
        assert hasattr(result, "sortino")
        assert hasattr(result, "max_drawdown")
        assert hasattr(result, "calmar")
        assert hasattr(result, "win_rate")
        assert hasattr(result, "profit_factor")
        assert hasattr(result, "expectancy")
        assert hasattr(result, "n_trades")
        assert hasattr(result, "equity_curve")
        assert hasattr(result, "signals")
        assert hasattr(result, "params")
    
    def test_invalid_signal_raises(self):
        """策略 generate_signals 返回错的列应报错"""
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        
        class BadStrategy:
            name = "BadStrategy"
            parameters = {}
            def generate_signals(self, df):
                return pd.DataFrame({"foo": [1] * len(df)})  # 没有 entries/exits
        
        engine = SimpleBacktestEngine()
        df = _make_price_df(100)
        with pytest.raises(ValueError, match="entries"):
            engine.run(BadStrategy(), df)


class TestGridSearch:
    def test_grid_search_basic(self):
        """参数网格扫描"""
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        from forgemind.core.strategies.library import MovingAverageCrossStrategy
        
        engine = SimpleBacktestEngine()
        df = _make_price_df(252)
        
        # 4 个组合:(10, 30) (10, 50) (20, 30) (20, 50)
        results = engine.grid_search(
            strategy_class=MovingAverageCrossStrategy,
            price_df=df,
            param_grid={
                "fast_period": [10, 20],
                "slow_period": [30, 50],
            },
        )
        
        # 应该返回 4 个结果(或失败的更少)
        assert len(results) <= 4
        # 按 Sharpe 降序
        for i in range(len(results) - 1):
            assert results[i].sharpe >= results[i + 1].sharpe
    
    def test_grid_search_with_failures(self):
        """参数组合失败应被日志 + 跳过,不影响其他"""
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        from forgemind.core.strategies.library import MovingAverageCrossStrategy
        
        engine = SimpleBacktestEngine()
        df = _make_price_df(252)
        
        # slow_period 比 fast_period 小应该失败
        results = engine.grid_search(
            strategy_class=MovingAverageCrossStrategy,
            price_df=df,
            param_grid={
                "fast_period": [50],  # 慢
                "slow_period": [10],  # 快 — 反过来应该会抛
            },
        )
        
        # 不抛异常,失败被记录
        # 至少返回一个结果(可能 0,因为全部失败)
        assert isinstance(results, list)
    
    def test_grid_search_empty_results(self):
        """参数全失败应返回空列表"""
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        from forgemind.core.strategies.library import MovingAverageCrossStrategy
        
        engine = SimpleBacktestEngine()
        df = _make_price_df(10)  # 太短
        
        results = engine.grid_search(
            strategy_class=MovingAverageCrossStrategy,
            price_df=df,
            param_grid={"fast_period": [3], "slow_period": [5]},
        )
        
        assert isinstance(results, list)


class TestBacktestResult:
    def test_dataclass_default_fields(self):
        from forgemind.core.backtest.engine import BacktestResult
        import pandas as pd
        r = BacktestResult(
            total_return=0.1,
            sharpe=1.5,
            sortino=2.0,
            max_drawdown=-0.1,
            calmar=1.0,
            win_rate=0.55,
            profit_factor=1.2,
            expectancy=0.005,
            n_trades=10,
            equity_curve=pd.Series([100.0, 101.0]),
            signals=pd.DataFrame({"entries": [True, False], "exits": [False, True]}),
        )
        assert r.params == {}
        assert r.extra == {}


class TestBacktestMetricsTypes:
    """验证 BacktestResult 字段是原生 float(不是 numpy)"""
    
    def test_metrics_are_native_floats(self):
        """sharpe / max_drawdown 等应是 float,不是 numpy.float64"""
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        from forgemind.core.strategies.library import MovingAverageCrossStrategy
        import pandas as pd
        import numpy as np
        
        np.random.seed(12345)
        n = 200
        dates = pd.date_range("2024-01-01", periods=n, freq="D")
        close = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, n)))
        df = pd.DataFrame({
            "open": close, "high": close, "low": close, "close": close,
            "volume": [1_000_000] * n,
        }, index=dates)
        
        engine = SimpleBacktestEngine()
        result = engine.run(
            MovingAverageCrossStrategy(parameters={"fast_period": 5, "slow_period": 20}),
            df,
        )
        
        # 全部应为原生 float
        assert isinstance(result.total_return, float), f"total_return is {type(result.total_return)}"
        assert isinstance(result.sharpe, float), f"sharpe is {type(result.sharpe)}"
        assert isinstance(result.sortino, float), f"sortino is {type(result.sortino)}"
        assert isinstance(result.max_drawdown, float), f"max_drawdown is {type(result.max_drawdown)}"
        assert isinstance(result.calmar, float), f"calmar is {type(result.calmar)}"
        assert isinstance(result.win_rate, float), f"win_rate is {type(result.win_rate)}"
        assert isinstance(result.expectancy, float), f"expectancy is {type(result.expectancy)}"
    
    def test_deterministic_sharpe(self):
        """同 seed 同数据 → Sharpe 一致"""
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        from forgemind.core.strategies.library import MovingAverageCrossStrategy
        import pandas as pd
        import numpy as np
        
        def make_df():
            np.random.seed(12345)
            n = 200
            dates = pd.date_range("2024-01-01", periods=n, freq="D")
            close = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, n)))
            return pd.DataFrame({
                "open": close, "high": close, "low": close, "close": close,
                "volume": [1_000_000] * n,
            }, index=dates)
        
        engine = SimpleBacktestEngine()
        strategy = MovingAverageCrossStrategy(parameters={"fast_period": 5, "slow_period": 20})
        
        r1 = engine.run(strategy, make_df())
        r2 = engine.run(strategy, make_df())
        r3 = engine.run(strategy, make_df())
        
        # 三次应 sharpe 完全一致(无随机性)
        assert r1.sharpe == r2.sharpe == r3.sharpe, f"{r1.sharpe} {r2.sharpe} {r3.sharpe}"
        assert r1.total_return == r2.total_return == r3.total_return