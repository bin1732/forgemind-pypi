# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import numpy as np
import polars as pl


def _rolling_rank_col(values, window: int):
    """滚动窗口内的百分位 rank — 用于 DataFrame

    对每个时间点,取当前值在过去 window 根 bar 中的百分位排名(0-1)。
    """
    import numpy as np

    arr = values.to_numpy()
    n = len(arr)
    result = np.empty(n)
    for i in range(n):
        start = max(0, i - window + 1)
        window_vals = arr[start : i + 1]
        result[i] = (window_vals < arr[i]).sum() / len(window_vals)
    return result


def _signed_power(s: pl.Expr, p: float) -> pl.Expr:
    return s.sign() * s.abs().pow(p)


def alpha_001(df: pl.LazyFrame) -> pl.LazyFrame:
    """Alpha#1: (rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) - 0.5)
    简化: 用 rolling_max 的排名代替 argmax
    """
    cond = pl.col("returns") < 0
    inner = pl.when(cond).then(pl.col("returns").rolling_std(20)).otherwise(pl.col("close"))
    signed = _signed_power(inner, 2.0)
    # 简化: signed 在 5 日内的最大值排名
    argmax_5 = signed.rolling_max(5)
    return df.with_columns(argmax_5.rank().over("symbol").alias("ALPHA001"))


def alpha_002(df: pl.LazyFrame) -> pl.LazyFrame:
    """Alpha#2: (-1 * correlation(rank(delta(log(volume), 2)), rank(((close - open) / open)), 6))"""
    inner = ((pl.col("close") - pl.col("open")) / pl.col("open")).rank().over("symbol")
    outer = pl.col("volume").log().diff(2).rank().over("symbol")
    return df.with_columns(-(pl.rolling_corr(outer, inner, window_size=6)).alias("ALPHA002"))


def alpha_006(df: pl.LazyFrame) -> pl.LazyFrame:
    """Alpha#6: (-1 * correlation(open, volume, 10))"""
    return df.with_columns(
        -(pl.rolling_corr(pl.col("open"), pl.col("volume"), window_size=10)).alias("ALPHA006")
    )


def alpha_007(df: pl.LazyFrame) -> pl.LazyFrame:
    """Alpha#7: where(adv20 < volume, -1 * ts_rank(abs(delta(close, 7)), 60) * sign(delta(close, 7)), -1)"""
    # rolling_rank 需要 eager 模式,先算中间结果
    df_eager = df.with_columns(
        [
            pl.col("volume").rolling_mean(20).alias("adv20"),
            pl.col("close").diff(7).alias("inner"),
        ]
    ).collect()

    inner_vals = df_eager["inner"].abs()
    adv20 = df_eager["adv20"]
    vol = df_eager["volume"]
    close_diff = df_eager["inner"]

    rr = _rolling_rank_col(inner_vals, 60)
    rr_max = pl.Series(rr).rolling_max(60).to_numpy()

    cond_np = adv20.to_numpy() < vol.to_numpy()
    result_np = np.where(cond_np, -(rr_max * np.sign(close_diff.to_numpy())), -1.0)

    return (
        df.with_columns(
            [
                pl.col("volume").rolling_mean(20).alias("adv20"),
                pl.col("close").diff(7).alias("inner"),
            ]
        )
        .with_columns(pl.lit(result_np).alias("ALPHA007"))
        .drop("adv20", "inner")
    )


def alpha_012(df: pl.LazyFrame) -> pl.LazyFrame:
    """Alpha#12: sign(delta(volume, 1)) * (-1 * delta(close, 1))"""
    return df.with_columns(
        (pl.col("volume").diff(1).sign() * -(pl.col("close").diff(1))).alias("ALPHA012")
    )


def alpha_033(df: pl.LazyFrame) -> pl.LazyFrame:
    """Alpha#33: rank(-(1 - (open / close)))"""
    inner = -(1 - pl.col("open") / pl.col("close"))
    return df.with_columns(inner.rank().over("symbol").alias("ALPHA033"))


def alpha_038(df: pl.LazyFrame) -> pl.LazyFrame:
    """Alpha#38: -rank(ts_rank(close, 10)) * rank(close / open)"""
    df_eager = df.collect()
    rr = _rolling_rank_col(df_eager["close"].abs(), 10)
    inner_rank_np = rr  # 已经是 rank 值,不需要再 rank
    outer_rank_np = (df_eager["close"] / df_eager["open"]).rank().to_numpy()
    result_np = -inner_rank_np * outer_rank_np
    df_eager = df_eager.with_columns(pl.Series(result_np).alias("ALPHA038"))
    return df_eager.lazy()


def alpha_041(df: pl.LazyFrame) -> pl.LazyFrame:
    """Alpha#41: power(high * low, 0.5) - vwap"""
    return df.with_columns(
        (
            (pl.col("high") * pl.col("low")).sqrt()
            - (pl.col("high") + pl.col("low") + pl.col("close")) / 3
        ).alias("ALPHA041")
    )


def alpha_053(df: pl.LazyFrame) -> pl.LazyFrame:
    """Alpha#53: -1 * delta(((close - low) - (high - close)) / (close - low), 9)"""
    inner = ((pl.col("close") - pl.col("low")) - (pl.col("high") - pl.col("close"))) / (
        pl.col("close") - pl.col("low") + 1e-9
    )
    return df.with_columns(-(inner.diff(9)).alias("ALPHA053"))


def alpha_054(df: pl.LazyFrame) -> pl.LazyFrame:
    """Alpha#54: -1 * (low - close) * power(open, 5) / ((low - high) * power(close, 5))"""
    inner = (
        -(pl.col("low") - pl.col("close"))
        * pl.col("open").pow(5)
        / ((pl.col("low") - pl.col("high")) * pl.col("close").pow(5) + 1e-9)
    )
    return df.with_columns(inner.alias("ALPHA054"))


def alpha_101(df: pl.LazyFrame) -> pl.LazyFrame:
    """Alpha#101: (close - open) / (high - low + 0.001)"""
    return df.with_columns(
        ((pl.col("close") - pl.col("open")) / (pl.col("high") - pl.col("low") + 0.001)).alias(
            "ALPHA101"
        )
    )


def _compute_alpha101_one(df: pl.LazyFrame) -> pl.LazyFrame:
    """对**单一标的**计算全部因子(不做任何跨标的分组)

    窗口运算全部在这里执行,因此调用方必须保证 df 只含一只股票。
    """
    df = alpha_001(df)
    df = alpha_002(df)
    df = alpha_006(df)
    df = alpha_007(df)
    df = alpha_012(df)
    df = alpha_033(df)
    df = alpha_038(df)
    df = alpha_041(df)
    df = alpha_053(df)
    df = alpha_054(df)
    df = alpha_101(df)
    return df


def compute_alpha101(df: pl.LazyFrame) -> pl.LazyFrame:
    """Alpha101 因子 — 按 symbol 隔离后逐标的计算

    polars 表达式与 numpy 路径在文件内混用 (alpha_007 / alpha_038 会
    `.collect()` 后走 numpy),给每个窗口加 `.over("symbol")` 需要改十几处
    调用点,集中维护易漏。

    改在结构上修:入口按 symbol 切分,逐只计算再纵向拼接,内部 polars
    与 numpy 路径都不存在跨标的计算。
    没有 symbol 列的输入按单标的处理,行为与多标的一致。

    代价:因子数从 O(1) 次表达式变成 O(标的数) 次。面板越大越慢,
    但正确性优先。
    """
    schema = df.collect_schema().names()
    if "symbol" not in schema:
        return _compute_alpha101_one(df)

    # 保留 symbol 列:alpha_001 内部会引用 pl.col("symbol"),
    # 去掉就报 ColumnNotFoundError。单值列对逐行运算无影响。
    collected = df.collect()
    parts = [
        _compute_alpha101_one(part.lazy()).collect()
        for part in collected.partition_by("symbol", maintain_order=True)
    ]
    if not parts:
        return df
    return pl.concat(parts, how="vertical_relaxed").lazy()


def list_alpha101_factors() -> list:
    """列出全部实现的 Alpha101 因子"""
    return [
        "ALPHA001",
        "ALPHA002",
        "ALPHA006",
        "ALPHA007",
        "ALPHA012",
        "ALPHA033",
        "ALPHA038",
        "ALPHA041",
        "ALPHA053",
        "ALPHA054",
        "ALPHA101",
    ]
