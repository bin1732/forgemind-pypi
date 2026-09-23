# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import polars as pl
import numpy as np
from datetime import datetime, timedelta


def make_test_data(n_days: int = 200, n_symbols: int = 10) -> pl.LazyFrame:
    """构造测试数据"""
    np.random.seed(42)
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(n_days)]
    symbols = [f"S{i:04d}" for i in range(n_symbols)]
    
    rows = []
    for sym in symbols:
        price = 100.0
        for date in dates:
            ret = np.random.randn() * 0.02
            price *= (1 + ret)
            high = price * (1 + abs(np.random.randn() * 0.01))
            low = price * (1 - abs(np.random.randn() * 0.01))
            open_ = price * (1 + np.random.randn() * 0.005)
            close = price
            volume = int(np.random.lognormal(10, 1))
            rows.append({
                "symbol": sym, "date": date,
                "open": open_, "high": high, "low": low,
                "close": close, "volume": volume,
            })
    
    df = pl.LazyFrame(rows).sort(["symbol", "date"]).with_columns([
        pl.col("close").pct_change().over("symbol").alias("returns"),
    ])
    return df


class TestAlpha158:
    def test_factor_count(self):
        from forgemind.core.factors import list_alpha158_factors, factor_count
        factors = list_alpha158_factors()
        assert len(factors) >= 100  # 至少 100 因子
        assert factor_count() >= 150
    
    def test_compute_runs(self):
        from forgemind.core.factors import compute_alpha158, Alpha158Config
        df = make_test_data(60, 5)
        result = compute_alpha158(df, Alpha158Config()).collect()
        # 必须有 close 列保留
        assert "close" in result.columns
        assert "KMID" in result.columns
        assert "RSI" in result.columns
        assert "MACD_DIF" in result.columns
        assert "LOG_RETURN_20" in result.columns
        # MA 类因子应存在
        ma_factors = [c for c in result.columns if c.startswith("ROC_")]
        assert len(ma_factors) >= 20
    
    def test_kbar_factors(self):
        from forgemind.core.factors import compute_alpha158, Alpha158Config
        df = make_test_data(30, 3)
        result = compute_alpha158(df).collect()
        for k in ["KMID", "KLEN", "KUP", "KLOW", "KSFT"]:
            assert k in result.columns, f"缺 {k}"


class TestAlpha101:
    def test_factor_count(self):
        from forgemind.core.factors import list_alpha101_factors
        factors = list_alpha101_factors()
        assert len(factors) >= 10
    
    def test_compute_runs(self):
        from forgemind.core.factors import compute_alpha101
        df = make_test_data(60, 5)
        result = compute_alpha101(df).collect()
        for f in ["ALPHA001", "ALPHA006", "ALPHA033", "ALPHA101"]:
            assert f in result.columns, f"缺 {f}"


class TestBarra:
    def test_factor_count(self):
        from forgemind.core.factors import list_barra_factors
        factors = list_barra_factors(has_fundamentals=True)
        assert len(factors) >= 10
    
    def test_compute_no_fundamentals(self):
        from forgemind.core.factors import compute_barra
        df = make_test_data(252, 5).with_columns([
            pl.lit(1e10).alias("mkt_cap"),
        ])
        # 加 mkt_returns 列
        import random
        df = df.with_columns([pl.col("close").pct_change().alias("mkt_returns")])
        result = compute_barra(df, has_fundamentals=False).collect()
        for f in ["BARRA_SIZE", "BARRA_BETA", "BARRA_MOMENTUM"]:
            assert f in result.columns


class TestICMonitor:
    def test_compute_forward_returns(self):
        from forgemind.core.factors import compute_forward_returns
        df = make_test_data(60, 3)
        result = compute_forward_returns(df, [1, 5]).collect()
        assert "fwd_return_1" in result.columns
        assert "fwd_return_5" in result.columns
    
    def test_compute_ic(self):
        from forgemind.core.factors import compute_ic, compute_forward_returns
        df = make_test_data(120, 5)
        df = compute_forward_returns(df, [1])
        result = compute_ic(df, "close", "fwd_return_1")
        assert result.factor == "close"
        # IC 应该在 [-1, 1]
        assert -1 <= result.ic_mean <= 1
    
    def test_batch_ic(self):
        from forgemind.core.factors import (
            compute_alpha158, compute_forward_returns,
            batch_compute_ic, list_alpha158_factors, Alpha158Config,
        )
        df = make_test_data(120, 10)
        df_with_factors = compute_alpha158(df, Alpha158Config())
        df_with_returns = compute_forward_returns(df_with_factors, [1])
        factors = [f for f in list_alpha158_factors()[:20] if f in [c for c in df_with_returns.collect_schema().names()]]
        results = batch_compute_ic(df_with_returns, factors)
        assert len(results) >= 1


class TestIntegration:
    """端到端集成测试"""
    def test_full_pipeline(self):
        """完整流水线:原始数据 → Alpha158 → forward returns → IC"""
        from forgemind.core.factors import (
            compute_alpha158, compute_forward_returns,
            batch_compute_ic, list_alpha158_factors,
            Alpha158Config, factor_count,
        )
        df = make_test_data(252, 20)
        # 加 industries
        import random
        df = df.with_columns([
            pl.lit("tech").alias("industry"),
        ])
        
        df_factor = compute_alpha158(df, Alpha158Config())
        df_with_ret = compute_forward_returns(df_factor, [1, 5, 10, 20])
        df_collected = df_with_ret.collect()
        
        # 至少 100 个因子列
        factor_cols = [c for c in df_collected.columns 
                      if c in list_alpha158_factors()]
        assert len(factor_cols) >= 100
        
        # IC 评估
        results = batch_compute_ic(df_with_ret, factor_cols[:30], decay_cols=["fwd_return_1", "fwd_return_5", "fwd_return_10", "fwd_return_20"])
        assert len(results) >= 1
        
        # 总因子数报告
        print(f"\n  ✓ Total factors: {factor_count()}")
        print(f"  ✓ Alpha158 factors tested: {len(factor_cols)}")
        print(f"  ✓ IC evaluations: {len(results)}")