# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0


import polars as pl


def barra_size(df: pl.LazyFrame, mkt_cap_col: str = "mkt_cap") -> pl.LazyFrame:
    """Size: ln(market_cap)"""
    return df.with_columns(pl.col(mkt_cap_col).log().alias("BARRA_SIZE"))


#: 窗口一律按 symbol 限定。理由见 alpha158:面板按 symbol 排序时,
#: 每只票开头的窗口会取到上一只票的收益 —— 已验证 252 日窗口下,
#: 第 2 只票的**第一行**就出了 beta 值(窗口本该填不满)。
_GROUP = "symbol"


def barra_beta(
    df: pl.LazyFrame, returns_col: str = "returns", mkt_returns_col: str = "mkt_returns"
) -> pl.LazyFrame:
    """Beta: cov(stock_returns, market_returns) / var(market_returns)"""
    cov = pl.rolling_cov(pl.col(returns_col), pl.col(mkt_returns_col), window_size=252).over(_GROUP)
    var = pl.col(mkt_returns_col).rolling_var(252).over(_GROUP)
    return df.with_columns((cov / (var + 1e-9)).alias("BARRA_BETA"))


def barra_momentum(df: pl.LazyFrame, returns_col: str = "returns") -> pl.LazyFrame:
    """Momentum: cumulative returns over past 504 days (skip first 30)"""
    # Skip first 30 days momentum (反转效应消除)
    # shift 与 cum_prod 都要按 symbol 限定:cum_prod 是累乘,跨标的后
    # 一只票的动量会被前面所有票的累计收益完全污染。
    # 分两步:先把位移结果落成真实列,再在列上按 symbol 累乘 ——
    # polars 不允许窗口表达式直接套窗口(见 alpha158 里同样的坑)。
    df = df.with_columns(
        (1 + pl.col(returns_col).shift(30).over(_GROUP)).alias("_mom_skip"),
        (1 + pl.col(returns_col).shift(504).over(_GROUP)).alias("_mom_base"),
    )
    return df.with_columns(
        (pl.col("_mom_skip").cum_prod().over(_GROUP) / pl.col("_mom_base").cum_prod().over(_GROUP))
        .log()
        .alias("BARRA_MOMENTUM")
    )


def barra_residual_vol(
    df: pl.LazyFrame, returns_col: str = "returns", mkt_returns_col: str = "mkt_returns"
) -> pl.LazyFrame:
    """Residual Volatility: std of regression residuals over 252 days"""
    # 残差 = returns - beta * mkt_returns
    # 分两步:beta 先落成真实列,再算残差的滚动标准差。
    # 直接 residual.rolling_std().over(...) 会把窗口表达式套进另一个
    # 窗口,polars 拒绝("window expression not allowed in aggregation")。
    cov = pl.rolling_cov(pl.col(returns_col), pl.col(mkt_returns_col), window_size=252).over(_GROUP)
    var = pl.col(mkt_returns_col).rolling_var(252).over(_GROUP)
    df = df.with_columns((cov / (var + 1e-9)).alias("_beta"))
    df = df.with_columns(
        (pl.col(returns_col) - pl.col("_beta") * pl.col(mkt_returns_col)).alias("_resid")
    )
    return df.with_columns(
        pl.col("_resid").rolling_std(252).over(_GROUP).alias("BARRA_RESIDUAL_VOL")
    )


def barra_non_linear_size(df: pl.LazyFrame, mkt_cap_col: str = "mkt_cap") -> pl.LazyFrame:
    """Non-Linear Size: cubic term of size"""
    size = pl.col(mkt_cap_col).log()
    return df.with_columns((size.pow(3)).alias("BARRA_NONLINEAR_SIZE"))


def barra_book_to_price(
    df: pl.LazyFrame, book_col: str = "book_value", price_col: str = "mkt_cap"
) -> pl.LazyFrame:
    """Book-to-Price: ln(book_value / mkt_cap)"""
    return df.with_columns((pl.col(book_col) / pl.col(price_col)).log().alias("BARRA_BP"))


def barra_liquidity(
    df: pl.LazyFrame, volume_col: str = "volume", mkt_cap_col: str = "mkt_cap"
) -> pl.LazyFrame:
    """Liquidity: 20-day average of turnover (volume / shares outstanding)
    用 mkt_cap / close 估算 shares outstanding
    """
    shares_out = pl.col(mkt_cap_col) / pl.col("close")
    turnover = pl.col(volume_col) / (shares_out + 1e-9)
    return df.with_columns(turnover.rolling_mean(20).log().alias("BARRA_LIQUIDITY"))


def barra_earnings_yield(
    df: pl.LazyFrame, eps_col: str = "eps", price_col: str = "close"
) -> pl.LazyFrame:
    """Earnings Yield: eps / price"""
    return df.with_columns((pl.col(eps_col) / pl.col(price_col)).alias("BARRA_EARNYLD"))


def barra_growth(df: pl.LazyFrame, eps_col: str = "eps") -> pl.LazyFrame:
    """Growth: 5-year EPS growth rate"""
    return df.with_columns(
        (pl.col(eps_col) / pl.col(eps_col).shift(252 * 5) - 1).alias("BARRA_GROWTH")
    )


def barra_leverage(
    df: pl.LazyFrame, debt_col: str = "total_debt", mkt_cap_col: str = "mkt_cap"
) -> pl.LazyFrame:
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
        "BARRA_SIZE",
        "BARRA_BETA",
        "BARRA_MOMENTUM",
        "BARRA_RESIDUAL_VOL",
        "BARRA_NONLINEAR_SIZE",
        "BARRA_LIQUIDITY",
    ]
    if has_fundamentals:
        factors += ["BARRA_BP", "BARRA_EARNYLD", "BARRA_GROWTH", "BARRA_LEVERAGE"]
    return factors
