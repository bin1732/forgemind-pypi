# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import polars as pl
import numpy as np
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Alpha158Config:
    """Alpha158 配置"""
    # KDJ / RSI / BBI 等指标的周期参数
    kdj_n: int = 9
    rsi_n: int = 14
    boll_n: int = 20
    # MA 类
    ma_short: int = 5
    ma_mid: int = 10
    ma_long: int = 20
    ma_vlong: int = 60
    # 长周期变体
    long_windows: tuple = (10, 20, 30, 50, 60, 120, 240)
    short_windows: tuple = (3, 5, 10, 15, 20, 30)
    # 行业中性化(可选)
    industry_neutral: bool = False
    industry_col: str = "industry"


def _rolling_mean(s: pl.Expr, n: int) -> pl.Expr:
    return s.rolling_mean(n, min_periods=max(1, n // 2))


def _rolling_std(s: pl.Expr, n: int) -> pl.Expr:
    return s.rolling_std(n, min_periods=max(1, n // 2))


def _ts_max(s: pl.Expr, n: int) -> pl.Expr:
    return s.rolling_max(n)


def _ts_min(s: pl.Expr, n: int) -> pl.Expr:
    return s.rolling_min(n)


def _log_returns(close: pl.Expr, n: int = 1) -> pl.Expr:
    return (close / close.shift(n)).log()


def kbar_factors(df: pl.LazyFrame, config: Alpha158Config) -> pl.LazyFrame:
    """KBAR 行情因子 (5 因子)"""
    return df.with_columns([
        # KMID = (close - open) / open
        ((pl.col("close") - pl.col("open")) / pl.col("open")).alias("KMID"),
        # KLEN = (high - low) / open
        ((pl.col("high") - pl.col("low")) / pl.col("open")).alias("KLEN"),
        # KUP = (high - max(open, close)) / open
        ((pl.col("high") - pl.max_horizontal(pl.col("open"), pl.col("close"))) / pl.col("open")).alias("KUP"),
        # KLOW = (min(open, close) - low) / open
        ((pl.min_horizontal(pl.col("open"), pl.col("close")) - pl.col("low")) / pl.col("open")).alias("KLOW"),
        # KSFT = (2 * close - high - low) / open
        ((2 * pl.col("close") - pl.col("high") - pl.col("low")) / pl.col("open")).alias("KSFT"),
    ])


def price_volume_factors(df: pl.LazyFrame, config: Alpha158Config) -> pl.LazyFrame:
    """量价因子 (12 因子)"""
    return df.with_columns([
        # 收盘价相对最低/最高位置
        ((pl.col("close") - _ts_min(pl.col("low"), 5)) / 
         (_ts_max(pl.col("high"), 5) - _ts_min(pl.col("low"), 5) + 1e-9)).alias("CLOSE_MINMAX_5"),
        ((pl.col("close") - _ts_min(pl.col("low"), 20)) /
         (_ts_max(pl.col("high"), 20) - _ts_min(pl.col("low"), 20) + 1e-9)).alias("CLOSE_MINMAX_20"),
        # 量比
        (pl.col("volume") / _rolling_mean(pl.col("volume"), 5)).alias("VOLUME_RATIO_5"),
        (pl.col("volume") / _rolling_mean(pl.col("volume"), 20)).alias("VOLUME_RATIO_20"),
        pl.rolling_corr(pl.col("close"), pl.col("volume"), window_size=10).alias("PRICE_VOLUME_CORR_10"),
        pl.rolling_corr(pl.col("close"), pl.col("volume"), window_size=20).alias("PRICE_VOLUME_CORR_20"),
        # VWAP deviation
        (pl.col("close") / ((pl.col("high") + pl.col("low") + pl.col("close")) / 3) - 1).alias("VWAP_DEV"),
        # High-low range
        ((pl.col("high") - pl.col("low")) / pl.col("close")).alias("DAILY_RANGE"),
        # 跳空
        ((pl.col("open") / pl.col("close").shift(1) - 1)).alias("GAP"),
        # 上下影线
        ((pl.col("high") - pl.max_horizontal(pl.col("open"), pl.col("close"))) / (pl.col("high") - pl.col("low") + 1e-9)).alias("UPPER_SHADOW"),
        ((pl.min_horizontal(pl.col("open"), pl.col("close")) - pl.col("low")) / (pl.col("high") - pl.col("low") + 1e-9)).alias("LOWER_SHADOW"),
        # 量价背离
        (_rolling_mean(pl.col("close"), 5) / _rolling_mean(pl.col("close"), 20) - 
         _rolling_mean(pl.col("volume"), 5) / _rolling_mean(pl.col("volume"), 20)).alias("PV_DIVERGENCE"),
    ])


def ma_factors(df: pl.LazyFrame, config: Alpha158Config) -> pl.LazyFrame:
    """均线类因子 (60 因子) — 对标 Qlib Alpha158 全套"""
    exprs = []
    for sw in [3, 5, 10, 15, 20, 30]:
        for lw in [10, 20, 30, 50, 60, 120]:
            if sw >= lw:
                continue
            # ROC 跨期
            exprs.append(
                (_rolling_mean(pl.col("close"), sw) / _rolling_mean(pl.col("close"), lw) - 1).alias(f"ROC_{sw}_{lw}")
            )
            # MA spread
            exprs.append(
                (_rolling_mean(pl.col("close"), sw) - _rolling_mean(pl.col("close"), lw)).alias(f"MA_SPREAD_{sw}_{lw}")
            )
            # 量比跨期
            exprs.append(
                (_rolling_mean(pl.col("volume"), sw) / _rolling_mean(pl.col("volume"), lw) - 1).alias(f"VOL_ROC_{sw}_{lw}")
            )
    return df.with_columns(exprs)


def rstd_factors(df: pl.LazyFrame, config: Alpha158Config) -> pl.LazyFrame:
    """波动率因子 (RSTD 类)"""
    exprs = []
    for n in [5, 10, 20, 30, 60]:
        # RSTD: 滚动标准差 / 滚动均值 (变异系数)
        exprs.append(
            (_rolling_std(pl.col("close"), n) / (_rolling_mean(pl.col("close"), n) + 1e-9)).alias(f"RSTD_{n}")
        )
        # 收益率波动
        exprs.append(
            _rolling_std(_log_returns(pl.col("close"), 1), n).alias(f"RET_STD_{n}")
        )
        # 高低价波动
        exprs.append(
            _rolling_std((pl.col("high") - pl.col("low")) / pl.col("open"), n).alias(f"RANGE_STD_{n}")
        )
    return df.with_columns(exprs)


def technical_indicators(df: pl.LazyFrame, config: Alpha158Config) -> pl.LazyFrame:
    """技术指标 (RSI / KDJ / MACD / BOLL)"""
    # RSI
    delta = pl.col("close").diff()
    gain = pl.max_horizontal(delta, pl.lit(0.0))
    loss = pl.max_horizontal(-delta, pl.lit(0.0))
    avg_gain = _rolling_mean(gain, config.rsi_n)
    avg_loss = _rolling_mean(loss, config.rsi_n)
    rsi = 100 - (100 / (1 + avg_gain / (avg_loss + 1e-9)))
    
    # KDJ (9 日)
    low_n = _ts_min(pl.col("low"), config.kdj_n)
    high_n = _ts_max(pl.col("high"), config.kdj_n)
    rsv = ((pl.col("close") - low_n) / (high_n - low_n + 1e-9)) * 100
    k = rsv.rolling_mean(3)
    d = k.rolling_mean(3)
    j = 3 * k - 2 * d
    
    # MACD
    ema12 = pl.col("close").ewm_mean(span=12)
    ema26 = pl.col("close").ewm_mean(span=26)
    dif = ema12 - ema26
    dea = dif.ewm_mean(span=9)
    macd = (dif - dea) * 2
    
    # BOLL
    boll_mid = _rolling_mean(pl.col("close"), config.boll_n)
    boll_std = _rolling_std(pl.col("close"), config.boll_n)
    boll_upper = boll_mid + 2 * boll_std
    boll_lower = boll_mid - 2 * boll_std
    
    return df.with_columns([
        rsi.alias("RSI"),
        k.alias("KDJ_K"),
        d.alias("KDJ_D"),
        j.alias("KDJ_J"),
        dif.alias("MACD_DIF"),
        dea.alias("MACD_DEA"),
        macd.alias("MACD_HIST"),
        ((pl.col("close") - boll_mid) / (2 * boll_std + 1e-9)).alias("BOLL_POS"),
        ((pl.col("close") - boll_lower) / (boll_upper - boll_lower + 1e-9)).alias("BOLL_PCT"),
        ((boll_upper - pl.col("close")) / (boll_upper - boll_lower + 1e-9)).alias("BOLL_DISTANCE"),
    ])


def returns_factors(df: pl.LazyFrame, config: Alpha158Config) -> pl.LazyFrame:
    """收益率类因子"""
    return df.with_columns([
        _log_returns(pl.col("close"), 1).alias("LOG_RETURN_1"),
        _log_returns(pl.col("close"), 5).alias("LOG_RETURN_5"),
        _log_returns(pl.col("close"), 10).alias("LOG_RETURN_10"),
        _log_returns(pl.col("close"), 20).alias("LOG_RETURN_20"),
        _log_returns(pl.col("close"), 60).alias("LOG_RETURN_60"),
        _log_returns(pl.col("close"), 120).alias("LOG_RETURN_120"),
    ])


def momentum_factors(df: pl.LazyFrame, config: Alpha158Config) -> pl.LazyFrame:
    """动量因子"""
    exprs = []
    for n in [5, 10, 20, 30, 60, 120, 240]:
        # 简单动量
        exprs.append((pl.col("close") / pl.col("close").shift(n) - 1).alias(f"MOM_{n}"))
        # Skip momentum (今天 N 天前 close 减去 N+1 天前)
        exprs.append((pl.col("close").shift(n) / pl.col("close").shift(2*n) - 1).alias(f"SKIP_MOM_{n}"))
    return df.with_columns(exprs)


def industry_neutralize(df: pl.LazyFrame, factor_cols: List[str], industry_col: str) -> pl.LazyFrame:
    """行业中性化: 每个行业内对因子做 z-score"""
    exprs = []
    for col in factor_cols:
        # 行业内 z-score
        mean = pl.col(col).mean().over(industry_col)
        std = pl.col(col).std().over(industry_col)
        exprs.append(((pl.col(col) - mean) / (std + 1e-9)).alias(f"{col}_NEUTRAL"))
    return df.with_columns(exprs)


def compute_alpha158(df: pl.LazyFrame, config: Optional[Alpha158Config] = None) -> pl.LazyFrame:
    """计算 Alpha158 全套因子
    
    Args:
        df: 必须包含 open/high/low/close/volume 列,按 symbol + date 排序
        config: 配置
    
    Returns:
        包含 158 个因子的 LazyFrame
    """
    if config is None:
        config = Alpha158Config()
    
    df = kbar_factors(df, config)
    df = price_volume_factors(df, config)
    df = ma_factors(df, config)
    df = rstd_factors(df, config)
    df = technical_indicators(df, config)
    df = returns_factors(df, config)
    df = momentum_factors(df, config)
    
    return df


def list_alpha158_factors() -> List[str]:
    """列出全部 Alpha158 因子名(用于 IC 监控 / 特征选择)"""
    factors = []
    # KBAR
    factors += ["KMID", "KLEN", "KUP", "KLOW", "KSFT"]
    # 量价
    factors += [
        "CLOSE_MINMAX_5", "CLOSE_MINMAX_20",
        "VOLUME_RATIO_5", "VOLUME_RATIO_20",
        "PRICE_VOLUME_CORR_10", "PRICE_VOLUME_CORR_20",
        "VWAP_DEV", "DAILY_RANGE", "GAP",
        "UPPER_SHADOW", "LOWER_SHADOW", "PV_DIVERGENCE",
    ]
    # MA 类 (跨期组合)
    for sw in [3, 5, 10, 15, 20, 30]:
        for lw in [10, 20, 30, 50, 60, 120]:
            if sw < lw:
                factors.append(f"ROC_{sw}_{lw}")
                factors.append(f"MA_SPREAD_{sw}_{lw}")
                factors.append(f"VOL_ROC_{sw}_{lw}")
    # RSTD 类
    for n in [5, 10, 20, 30, 60]:
        factors.append(f"RSTD_{n}")
        factors.append(f"RET_STD_{n}")
        factors.append(f"RANGE_STD_{n}")
    # 技术指标
    factors += ["RSI", "KDJ_K", "KDJ_D", "KDJ_J",
                "MACD_DIF", "MACD_DEA", "MACD_HIST",
                "BOLL_POS", "BOLL_PCT", "BOLL_DISTANCE"]
    # 收益率
    factors += ["LOG_RETURN_1", "LOG_RETURN_5", "LOG_RETURN_10",
                "LOG_RETURN_20", "LOG_RETURN_60", "LOG_RETURN_120"]
    # 动量
    for n in [5, 10, 20, 30, 60, 120, 240]:
        factors.append(f"MOM_{n}")
        factors.append(f"SKIP_MOM_{n}")
    return factors