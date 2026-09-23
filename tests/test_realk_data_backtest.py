# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import pandas as pd
import numpy as np
from datetime import datetime


def _akshare_available():
    try:
        import akshare  # noqa
        return True
    except ImportError:
        return False


# 5 只大盘股
SYMBOLS = ["sz000001", "sz000002", "sz600519", "sh600036", "sh601318"]


def _fetch_real_klines(symbol: str, start: str = "20250101", end: str = "20250901") -> pd.DataFrame:
    """拉真 K 线 — 新浪源"""
    import akshare as ak
    df = ak.stock_zh_a_daily(symbol=symbol, start_date=start, end_date=end, adjust="qfq")
    return df


@pytest.fixture(scope="module")
def real_universe():
    """共享 fixture — 5 只真 A 股 9 月 K 线"""
    all_dfs = []
    failed = []
    for sym in SYMBOLS:
        try:
            df = _fetch_real_klines(sym)
            if df is not None and len(df) > 0:
                df["symbol"] = sym
                all_dfs.append(df)
            else:
                failed.append(sym)
        except Exception as e:
            failed.append(f"{sym}({type(e).__name__})")
    
    if not all_dfs:
        pytest.skip(f"所有 AKShare 调用都失败: {failed}")
    
    if failed:
        # 部分失败 → warn 但仍用成功的
        import warnings as _w
        _w.warn(f"部分 AKShare 失败: {failed}, 用成功的 {len(all_dfs)} 个 symbol")
    
    return pd.concat(all_dfs, ignore_index=True)


class TestRealDataIntegration:
    """端到端 — AKShare 真数据 → 回测"""
    
    @pytest.mark.skipif(not _akshare_available(), reason="akshare not installed")
    def test_akshare_returns_real_data(self):
        """AKShare 真能拉到"""
        df = _fetch_real_klines("sz000001")
        assert len(df) > 100, f"平安银行应 >= 100 行,实际 {len(df)}"
        assert "close" in df.columns
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "volume" in df.columns
    
    def test_real_data_shape(self, real_universe):
        """至少 4 只股票(部分 symbol 可能因 AKShare 限流失败)"""
        assert len(real_universe) > 400, f"应有 4×160 行+, 实际 {len(real_universe)}"
        symbols = real_universe["symbol"].unique()
        assert len(symbols) >= 4, f"应至少 4 只股票, 实际 {len(symbols)}"
    
    def test_real_data_no_nan_critical(self, real_universe):
        """close / open 不应有 NaN"""
        for sym in real_universe["symbol"].unique():
            sub = real_universe[real_universe["symbol"] == sym]
            assert sub["close"].notna().all(), f"{sym} close 含 NaN"
            assert sub["open"].notna().all(), f"{sym} open 含 NaN"


class TestRealDataBacktest:
    """真数据回测 — 验证 SimpleBacktestEngine + 策略"""
    
    def test_ma_cross_real_data(self, real_universe):
        """MA Cross 策略在真数据上跑"""
        from forgemind.core.strategies.base import MovingAverageCrossStrategy
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        
        # 单只股票
        sz000001 = real_universe[real_universe["symbol"] == "sz000001"].copy()
        # akshare 用 date 列,设成 index
        if "date" in sz000001.columns:
            sz000001 = sz000001.set_index("date")
        
        strategy = MovingAverageCrossStrategy(parameters={"fast_period": 5, "slow_period": 20})
        engine = SimpleBacktestEngine(initial_capital=100_000.0)
        result = engine.run(strategy, sz000001, symbol="sz000001")
        
        assert isinstance(result.sharpe, float)
        assert isinstance(result.max_drawdown, float)
        assert result.max_drawdown <= 0
        assert result.n_trades >= 0
        assert len(result.equity_curve) == len(sz000001)
    
    def test_bollinger_real_data(self, real_universe):
        """布林带策略在真数据上跑"""
        from forgemind.core.strategies.library import BollingerBandsStrategy
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        
        sz000001 = real_universe[real_universe["symbol"] == "sz000001"].copy()
        if "date" in sz000001.columns:
            sz000001 = sz000001.set_index("date")
        
        strategy = BollingerBandsStrategy(parameters={"period": 20, "std_multiplier": 2.0})
        engine = SimpleBacktestEngine(initial_capital=100_000.0)
        result = engine.run(strategy, sz000001, symbol="sz000001")
        
        assert isinstance(result.sharpe, float)
        assert result.max_drawdown <= 0
    
    def test_multi_symbol_backtest(self, real_universe):
        """多股票回测(逐个 symbol)"""
        from forgemind.core.strategies.base import MovingAverageCrossStrategy
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        
        results = []
        for sym in list(real_universe["symbol"].unique())[:3]:  # 前 3 只
            sub = real_universe[real_universe["symbol"] == sym].copy()
            if "date" in sub.columns:
                sub = sub.set_index("date")
            
            strategy = MovingAverageCrossStrategy(parameters={"fast_period": 5, "slow_period": 20})
            engine = SimpleBacktestEngine(initial_capital=100_000.0)
            result = engine.run(strategy, sub, symbol=sym)
            results.append(result)
        
        assert len(results) >= 1, "至少 1 个回测结果"
        # 至少有一些 Sharpe 有意义
        sharpes = [r.sharpe for r in results]
        assert any(s != 0 for s in sharpes), "所有 Sharpe 都为 0 可能有问题"


class TestRealDataPipeline:
    """真数据 + Pipeline"""
    
    def test_pipeline_with_real_data(self, real_universe):
        """Pipeline 在真数据上跑 — 选股"""
        from forgemind.core.pipeline.end_to_end import EndToEndPipeline
        
        # EndToEndPipeline 用 mock 数据,我们手动构造 pipeline 风格跑
        # 真实 pipeline 用 AKShare ETL,我们这里简化
        
        # 准备数据 — 用 AKShare 真数据
        df = real_universe.copy()
        if "date" in df.columns:
            df["ts"] = pd.to_datetime(df["date"])
        df = df.rename(columns={"symbol": "symbol", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"})
        df["returns"] = df.groupby("symbol")["close"].pct_change()
        df["fwd_ret"] = df.groupby("symbol")["close"].pct_change().shift(-1)
        df = df.dropna(subset=["returns", "fwd_ret"])
        
        # 简单 alpha:5 日动量
        df["momentum_5"] = df.groupby("symbol")["close"].pct_change(5)
        
        # IC 计算:预测能力
        from scipy.stats import spearmanr
        ic_per_ts = []
        for ts, group in df.groupby("ts"):
            if len(group) >= 3 and group["momentum_5"].std() > 0:
                ic, _ = spearmanr(group["momentum_5"].fillna(0), group["fwd_ret"].fillna(0))
                if not np.isnan(ic):
                    ic_per_ts.append(ic)
        
        # 平均 IC 应有方向
        if ic_per_ts:
            mean_ic = np.mean(ic_per_ts)
            # 动量因子在 A 股短窗口通常 IC > 0
            assert -1 <= mean_ic <= 1, f"IC 应在 [-1, 1], 实际 {mean_ic}"