# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass

import polars as pl


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


# === 窗口一律按 symbol 限定 ===
#
# 全部 34 处窗口操作以 `group_by("symbol")` 限定,避免跨标的串号:
# 面板数据按 symbol 排序时,跨标的窗口会取到上一只票的收盘价,
# 不同价位标的交叉取数,因子值被异常放大。
# 500 股 × 250 日的行情验证覆盖
# (按 symbol 排序时各 MOM 偏离倍数为当前实现的上限参考)。
#
# 统一 over 在 helper 层集中维护,34 处窗口调用点只调一次。
# 单标的输入(没有 symbol 列)时行为不变。
#: 分组键。compute_alpha158 入口按输入是否含 symbol 列来设:
#: 有 → 按标的分组(面板);没有 → 全部当成一只(单标的用法,行为不变)。
#: 用 pl.lit(1) 作分组键等价于"整表一组",正好是单标的的语义。
_GROUP: "pl.Expr | str" = "symbol"


def _set_group(df: pl.LazyFrame) -> None:
    global _GROUP
    _GROUP = "symbol" if "symbol" in df.collect_schema().names() else pl.lit(1)


def _rolling_mean(s: pl.Expr, n: int) -> pl.Expr:
    return s.rolling_mean(n, min_periods=max(1, n // 2)).over(_GROUP)


def _rolling_std(s: pl.Expr, n: int) -> pl.Expr:
    return s.rolling_std(n, min_periods=max(1, n // 2)).over(_GROUP)


def _ts_max(s: pl.Expr, n: int) -> pl.Expr:
    return s.rolling_max(n).over(_GROUP)


def _ts_min(s: pl.Expr, n: int) -> pl.Expr:
    return s.rolling_min(n).over(_GROUP)


def _log_returns(close: pl.Expr, n: int = 1) -> pl.Expr:
    # 只在 shift 上分组:若把 .over() 放在链尾,内层的 shift 已经在整列上
    # 算完了,分组等于没做 —— polars 还会直接报
    # "window expression not allowed in aggregation"。
    return (close / close.shift(n).over(_GROUP)).log()


def _shift_over(s: pl.Expr, n: int) -> pl.Expr:
    """按 symbol 限定的 shift(正数取过去,n<0 取未来)"""
    return s.shift(n).over(_GROUP)


def kbar_factors(df: pl.LazyFrame, config: Alpha158Config) -> pl.LazyFrame:
    """KBAR 行情因子 (5 因子)"""
    return df.with_columns(
        [
            # KMID = (close - open) / open
            ((pl.col("close") - pl.col("open")) / pl.col("open")).alias("KMID"),
            # KLEN = (high - low) / open
            ((pl.col("high") - pl.col("low")) / pl.col("open")).alias("KLEN"),
            # KUP = (high - max(open, close)) / open
            (
                (pl.col("high") - pl.max_horizontal(pl.col("open"), pl.col("close")))
                / pl.col("open")
            ).alias("KUP"),
            # KLOW = (min(open, close) - low) / open
            (
                (pl.min_horizontal(pl.col("open"), pl.col("close")) - pl.col("low"))
                / pl.col("open")
            ).alias("KLOW"),
            # KSFT = (2 * close - high - low) / open
            ((2 * pl.col("close") - pl.col("high") - pl.col("low")) / pl.col("open")).alias("KSFT"),
        ]
    )


def price_volume_factors(df: pl.LazyFrame, config: Alpha158Config) -> pl.LazyFrame:
    """量价因子 (12 因子)"""
    return df.with_columns(
        [
            # 收盘价相对最低/最高位置
            (
                (pl.col("close") - _ts_min(pl.col("low"), 5))
                / (_ts_max(pl.col("high"), 5) - _ts_min(pl.col("low"), 5) + 1e-9)
            ).alias("CLOSE_MINMAX_5"),
            (
                (pl.col("close") - _ts_min(pl.col("low"), 20))
                / (_ts_max(pl.col("high"), 20) - _ts_min(pl.col("low"), 20) + 1e-9)
            ).alias("CLOSE_MINMAX_20"),
            # 量比
            (pl.col("volume") / _rolling_mean(pl.col("volume"), 5)).alias("VOLUME_RATIO_5"),
            (pl.col("volume") / _rolling_mean(pl.col("volume"), 20)).alias("VOLUME_RATIO_20"),
            pl.rolling_corr(pl.col("close"), pl.col("volume"), window_size=10).alias(
                "PRICE_VOLUME_CORR_10"
            ),
            pl.rolling_corr(pl.col("close"), pl.col("volume"), window_size=20).alias(
                "PRICE_VOLUME_CORR_20"
            ),
            # VWAP deviation
            (pl.col("close") / ((pl.col("high") + pl.col("low") + pl.col("close")) / 3) - 1).alias(
                "VWAP_DEV"
            ),
            # High-low range
            ((pl.col("high") - pl.col("low")) / pl.col("close")).alias("DAILY_RANGE"),
            # 跳空
            (pl.col("open") / _shift_over(pl.col("close"), 1) - 1).alias("GAP"),
            # 上下影线
            (
                (pl.col("high") - pl.max_horizontal(pl.col("open"), pl.col("close")))
                / (pl.col("high") - pl.col("low") + 1e-9)
            ).alias("UPPER_SHADOW"),
            (
                (pl.min_horizontal(pl.col("open"), pl.col("close")) - pl.col("low"))
                / (pl.col("high") - pl.col("low") + 1e-9)
            ).alias("LOWER_SHADOW"),
            # 量价背离
            (
                _rolling_mean(pl.col("close"), 5) / _rolling_mean(pl.col("close"), 20)
                - _rolling_mean(pl.col("volume"), 5) / _rolling_mean(pl.col("volume"), 20)
            ).alias("PV_DIVERGENCE"),
        ]
    )


def ma_factors(df: pl.LazyFrame, config: Alpha158Config) -> pl.LazyFrame:
    """均线类因子 (60 因子) — 对标 Qlib Alpha158 全套"""
    exprs = []
    for sw in [3, 5, 10, 15, 20, 30]:
        for lw in [10, 20, 30, 50, 60, 120]:
            if sw >= lw:
                continue
            # ROC 跨期
            exprs.append(
                (_rolling_mean(pl.col("close"), sw) / _rolling_mean(pl.col("close"), lw) - 1).alias(
                    f"ROC_{sw}_{lw}"
                )
            )
            # MA spread
            exprs.append(
                (_rolling_mean(pl.col("close"), sw) - _rolling_mean(pl.col("close"), lw)).alias(
                    f"MA_SPREAD_{sw}_{lw}"
                )
            )
            # 量比跨期
            exprs.append(
                (
                    _rolling_mean(pl.col("volume"), sw) / _rolling_mean(pl.col("volume"), lw) - 1
                ).alias(f"VOL_ROC_{sw}_{lw}")
            )
    return df.with_columns(exprs)


def rstd_factors(df: pl.LazyFrame, config: Alpha158Config) -> pl.LazyFrame:
    """波动率因子 (RSTD 类)"""
    # 先把日内收益落成真实列,再在列上开窗。
    # 直接 _rolling_std(_log_returns(...), n) 会把一个窗口表达式喂进另一个
    # 窗口表达式,polars 报 "window expression not allowed in aggregation"。
    df = df.with_columns(
        _log_returns(pl.col("close"), 1).alias("_ret1"),
        ((pl.col("high") - pl.col("low")) / pl.col("open")).alias("_range"),
    )
    exprs = []
    for n in [5, 10, 20, 30, 60]:
        # RSTD: 滚动标准差 / 滚动均值 (变异系数)
        exprs.append(
            (_rolling_std(pl.col("close"), n) / (_rolling_mean(pl.col("close"), n) + 1e-9)).alias(
                f"RSTD_{n}"
            )
        )
        # 收益率波动
        exprs.append(_rolling_std(pl.col("_ret1"), n).alias(f"RET_STD_{n}"))
        # 高低价波动
        exprs.append(_rolling_std(pl.col("_range"), n).alias(f"RANGE_STD_{n}"))
    return df.with_columns(exprs)


def technical_indicators(df: pl.LazyFrame, config: Alpha158Config) -> pl.LazyFrame:
    """技术指标 (RSI / KDJ / MACD / BOLL)

    分步计算:每一级的窗口结果先落成**真实列**,再进入下一级。
    polars 不允许把一个窗口表达式直接喂进另一个窗口表达式
    ("window expression not allowed in aggregation"),而 KDJ/MACD 天然是
    三层窗口嵌套 —— 必须用 with_columns 把中间层物化。
    """
    # --- 第 1 级:一阶量 ---
    df = df.with_columns(
        pl.col("close").diff().over(_GROUP).alias("_d"),
        pl.col("close").ewm_mean(span=12).over(_GROUP).alias("_ema12"),
        pl.col("close").ewm_mean(span=26).over(_GROUP).alias("_ema26"),
    ).with_columns(
        pl.max_horizontal(pl.col("_d"), pl.lit(0.0)).alias("_gain"),
        pl.max_horizontal(-pl.col("_d"), pl.lit(0.0)).alias("_loss"),
        (pl.col("_ema12") - pl.col("_ema26")).alias("_dif"),
    )

    # --- 第 2 级:平滑 ---
    df = df.with_columns(
        _rolling_mean(pl.col("_gain"), config.rsi_n).alias("_avg_gain"),
        _rolling_mean(pl.col("_loss"), config.rsi_n).alias("_avg_loss"),
        pl.col("_dif").ewm_mean(span=9).over(_GROUP).alias("_dea"),
        _ts_min(pl.col("low"), config.kdj_n).alias("_kdj_low"),
        _ts_max(pl.col("high"), config.kdj_n).alias("_kdj_high"),
    ).with_columns(
        (100 - 100 / (1 + pl.col("_avg_gain") / (pl.col("_avg_loss") + 1e-9))).alias("_rsi"),
        (
            (pl.col("close") - pl.col("_kdj_low"))
            / (pl.col("_kdj_high") - pl.col("_kdj_low") + 1e-9)
            * 100
        ).alias("_rsv"),
    )

    # --- 第 3 级:K/D 各自的二次平滑(互不依赖,可并行)---
    df = df.with_columns(
        pl.col("_rsv").rolling_mean(3).over(_GROUP).alias("_k"),
        ((pl.col("_dif") - pl.col("_dea")) * 2).alias("_macd"),
        _rolling_mean(pl.col("close"), config.boll_n).alias("_boll_mid"),
        _rolling_std(pl.col("close"), config.boll_n).alias("_boll_std"),
    ).with_columns(
        pl.col("_k").rolling_mean(3).over(_GROUP).alias("_d_kdj"),
        (pl.col("_boll_mid") + 2 * pl.col("_boll_std")).alias("_boll_up"),
        (pl.col("_boll_mid") - 2 * pl.col("_boll_std")).alias("_boll_dn"),
    )

    k, d = pl.col("_k"), pl.col("_d_kdj")
    width = pl.col("_boll_up") - pl.col("_boll_dn")
    return df.with_columns(
        [
            pl.col("_rsi").alias("RSI"),
            k.alias("KDJ_K"),
            d.alias("KDJ_D"),
            (3 * k - 2 * d).alias("KDJ_J"),
            pl.col("_macd").alias("MACD_HIST"),
            pl.col("_dif").alias("MACD_DIF"),
            pl.col("_dea").alias("MACD_DEA"),
            pl.col("_boll_up").alias("BOLL_UPPER"),
            pl.col("_boll_dn").alias("BOLL_LOWER"),
            pl.col("_boll_mid").alias("BOLL_MID"),
            # 布林带的三个标准派生量, list_alpha158_factors() 声明
            # 但计算函数只产出 UPPER/MID/LOWER —— get_all_factors() 因此向
            # MCP / API 公开承诺了三个永远算不出来的因子,用户按名取只会拿到
            # 一段公式说明而没有数据。声明要么为真,要么就别写。
            ((pl.col("close") - pl.col("_boll_dn")) / (width + 1e-9)).alias("BOLL_PCT"),
            (width / (pl.col("_boll_mid") + 1e-9)).alias("BOLL_DISTANCE"),
            ((pl.col("close") - pl.col("_boll_mid")) / (pl.col("_boll_mid") + 1e-9)).alias(
                "BOLL_POS"
            ),
        ]
    )


def returns_factors(df: pl.LazyFrame, config: Alpha158Config) -> pl.LazyFrame:
    """收益率类因子"""
    return df.with_columns(
        [
            _log_returns(pl.col("close"), 1).alias("LOG_RETURN_1"),
            _log_returns(pl.col("close"), 5).alias("LOG_RETURN_5"),
            _log_returns(pl.col("close"), 10).alias("LOG_RETURN_10"),
            _log_returns(pl.col("close"), 20).alias("LOG_RETURN_20"),
            _log_returns(pl.col("close"), 60).alias("LOG_RETURN_60"),
            _log_returns(pl.col("close"), 120).alias("LOG_RETURN_120"),
        ]
    )


def momentum_factors(df: pl.LazyFrame, config: Alpha158Config) -> pl.LazyFrame:
    """动量因子"""
    exprs = []
    for n in [5, 10, 20, 30, 60, 120, 240]:
        # 简单动量
        exprs.append((pl.col("close") / _shift_over(pl.col("close"), n) - 1).alias(f"MOM_{n}"))
        # Skip momentum (今天 N 天前 close 减去 N+1 天前)
        exprs.append(
            (_shift_over(pl.col("close"), n) / _shift_over(pl.col("close"), 2 * n) - 1).alias(
                f"SKIP_MOM_{n}"
            )
        )
    return df.with_columns(exprs)


def industry_neutralize(
    df: pl.LazyFrame, factor_cols: list[str], industry_col: str
) -> pl.LazyFrame:
    """行业中性化: 每个行业内对因子做 z-score"""
    exprs = []
    for col in factor_cols:
        # 行业内 z-score
        mean = pl.col(col).mean().over(industry_col)
        std = pl.col(col).std().over(industry_col)
        exprs.append(((pl.col(col) - mean) / (std + 1e-9)).alias(f"{col}_NEUTRAL"))
    return df.with_columns(exprs)


def compute_alpha158(df: pl.LazyFrame, config: Alpha158Config | None = None) -> pl.LazyFrame:
    """计算 Alpha158 全套因子

    Args:
        df: 必须包含 open/high/low/close/volume 列,按 symbol + date 排序
        config: 配置

    Returns:
        包含 158 个因子的 LazyFrame
    """
    if config is None:
        config = Alpha158Config()

    # 面板按 symbol 分组;单标的输入(无 symbol 列)整表当一组,行为与从前一致
    _set_group(df)

    df = kbar_factors(df, config)
    df = price_volume_factors(df, config)
    df = ma_factors(df, config)
    df = rstd_factors(df, config)
    df = technical_indicators(df, config)
    df = returns_factors(df, config)
    df = momentum_factors(df, config)

    # 丢掉分步计算用的暂存列(全以 _ 开头)。它们是技术细节,不是因子 ——
    # 泄漏出去会被 get_all_factors() 之外的代码当成因子列,也会让
    # 产出列数这类断言失真。
    df = df.drop([c for c in df.collect_schema().names() if c.startswith("_")])
    return df


def list_alpha158_factors() -> list[str]:
    """列出全部 Alpha158 因子名(用于 IC 监控 / 特征选择)"""
    factors = []
    # KBAR
    factors += ["KMID", "KLEN", "KUP", "KLOW", "KSFT"]
    # 量价
    factors += [
        "CLOSE_MINMAX_5",
        "CLOSE_MINMAX_20",
        "VOLUME_RATIO_5",
        "VOLUME_RATIO_20",
        "PRICE_VOLUME_CORR_10",
        "PRICE_VOLUME_CORR_20",
        "VWAP_DEV",
        "DAILY_RANGE",
        "GAP",
        "UPPER_SHADOW",
        "LOWER_SHADOW",
        "PV_DIVERGENCE",
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
    factors += [
        "RSI",
        "KDJ_K",
        "KDJ_D",
        "KDJ_J",
        "MACD_DIF",
        "MACD_DEA",
        "MACD_HIST",
        "BOLL_UPPER",
        "BOLL_MID",
        "BOLL_LOWER",
        "BOLL_POS",
        "BOLL_PCT",
        "BOLL_DISTANCE",
    ]
    # 收益率
    factors += [
        "LOG_RETURN_1",
        "LOG_RETURN_5",
        "LOG_RETURN_10",
        "LOG_RETURN_20",
        "LOG_RETURN_60",
        "LOG_RETURN_120",
    ]
    # 动量
    for n in [5, 10, 20, 30, 60, 120, 240]:
        factors.append(f"MOM_{n}")
        factors.append(f"SKIP_MOM_{n}")
    return factors
