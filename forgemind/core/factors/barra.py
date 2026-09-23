# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import polars as pl
import numpy as np
from typing import Optional


def barra_size(df: pl.LazyFrame, mkt_cap_col: str = "mkt_cap") -> pl.LazyFrame:
    """Size: ln(market_cap)"""
    return df.with_columns(
        pl.col(mkt_cap_col).log().alias("BARRA_SIZE")
    )


def barra_beta(df: pl.LazyFrame, returns_col: str = "returns", mkt_returns_col: str = "mkt_returns") -> pl.LazyFrame:
    """Beta: cov(stock_returns, market_returns) / var(market_returns)"""
    cov = pl.rolling_cov(pl.col(returns_col), pl.col(mkt_returns_col), window_size=252)
    var = pl.col(mkt_returns_col).rolling_var(252)
    return df.with_columns((cov / (var + 1e-9)).alias("BARRA_BETA"))


def barra_momentum(df: pl.LazyFrame, returns_col: str = "returns") -> pl.LazyFrame:
    """Momentum: cumulative returns over past 504 days (skip first 30)"""
    # Skip first 30 days momentum (反转效应消除)
    cum_ret = (1 + pl.col(returns_col).shift(30)).cum_prod() / (1 + pl.col(returns_col).shift(504)).cum_prod()
    return df.with_columns(
        cum_ret.log().alias("BARRA_MOMENTUM")
    )


def barra_residual_vol(df: pl.LazyFrame, returns_col: str = "returns", mkt_returns_col: str = "mkt_returns") -> pl.LazyFrame:
    """Residual Volatility: std of regression residuals over 252 days"""
    # 残差 = returns - beta * mkt_returns
    cov = pl.rolling_cov(pl.col(returns_col), pl.col(mkt_returns_col), window_size=252)
    var = pl.col(mkt_returns_col).rolling_var(252)
    beta = cov / (var + 1e-9)
    residual = pl.col(returns_col) - beta * pl.col(mkt_returns_col)
    res_vol = residual.rolling_std(252)
    return df.with_columns(
        res_vol.alias("BARRA_RESIDUAL_VOL")
    )


def barra_non_linear_size(df: pl.LazyFrame, mkt_cap_col: str = "mkt_cap") -> pl.LazyFrame:
    """Non-Linear Size: cubic term of size"""
    size = pl.col(mkt_cap_col).log()
    return df.with_columns(
        (size.pow(3)).alias("BARRA_NONLINEAR_SIZE")
    )


def barra_book_to_price(df: pl.LazyFrame, book_col: str = "book_value", price_col: str = "mkt_cap") -> pl.LazyFrame:
    """Book-to-Price: ln(book_value / mkt_cap)"""
    return df.with_columns(
        (pl.col(book_col) / pl.col(price_col)).log().alias("BARRA_BP")
    )


def barra_liquidity(df: pl.LazyFrame, volume_col: str = "volume", mkt_cap_col: str = "mkt_cap") -> pl.LazyFrame:
    """Liquidity: 20-day average of turnover (volume / shares outstanding)
    用 mkt_cap / close 估算 shares outstanding
    """
    shares_out = pl.col(mkt_cap_col) / pl.col("close")
    turnover = pl.col(volume_col) / (shares_out + 1e-9)
    return df.with_columns(
        turnover.rolling_mean(20).log().alias("BARRA_LIQUIDITY")
    )


def barra_earnings_yield(df: pl.LazyFrame, eps_col: str = "eps", price_col: str = "close") -> pl.LazyFrame:
    """Earnings Yield: eps / price"""
    return df.with_columns(
        (pl.col(eps_col) / pl.col(price_col)).alias("BARRA_EARNYLD")
    )


def barra_growth(df: pl.LazyFrame, eps_col: str = "eps") -> pl.LazyFrame:
    """Growth: 5-year EPS growth rate"""
    return df.with_columns(
        (pl.col(eps_col) / pl.col(eps_col).shift(252 * 5) - 1).alias("BARRA_GROWTH")
    )


def barra_leverage(df: pl.LazyFrame, debt_col: str = "total_debt", mkt_cap_col: str = "mkt_cap") -> pl.LazyFrame:
    """Leverage: debt / mkt_cap"""
    return df.with_columns(
        (pl.col(debt_col) / (pl.col(mkt_cap_col) + 1e-9)).alias("BARRA_LEVERAGE")
    )


def compute_barra(df: pl.LazyFrame, has_fundamentals: bool = False) -> pl.LazyFrame:
    """计算 Barra USE5 风险因子
    
    Args:
        df: 含 price/volume 数据
        has_fundamentals: 是否有 fundamentals(EPS/book_value 等),
                          缺则跳过 B-P/EarnYld/Growth/Leverage
    """
    df = barra_size(df)
    df = barra_beta(df)
    df = barra_momentum(df)
    df = barra_residual_vol(df)
    df = barra_non_linear_size(df)
    df = barra_liquidity(df)
    
    if has_fundamentals:
        df = barra_book_to_price(df)
        df = barra_earnings_yield(df)
        df = barra_growth(df)
        df = barra_leverage(df)
    
    return df


def list_barra_factors(has_fundamentals: bool = False) -> list:
    """列出 Barra 因子"""
    factors = [
        "BARRA_SIZE", "BARRA_BETA", "BARRA_MOMENTUM",
        "BARRA_RESIDUAL_VOL", "BARRA_NONLINEAR_SIZE", "BARRA_LIQUIDITY",
    ]
    if has_fundamentals:
        factors += ["BARRA_BP", "BARRA_EARNYLD", "BARRA_GROWTH", "BARRA_LEVERAGE"]
    return factors