# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import polars as pl

from forgemind.core.observability.logging import get_logger

logger = get_logger("forgemind.ic_monitor")

if TYPE_CHECKING:  # 仅类型注解,避免运行时重依赖
    import pandas as pd  # noqa: F401


@dataclass
class ICResult:
    """单因子 IC 评估结果"""

    factor: str
    ic_mean: float
    ic_std: float
    icir: float
    rank_ic_mean: float
    rank_icir: float
    positive_ratio: float  # IC > 0 的天数比例
    t_stat: float
    p_value: float
    decay: dict[int, float] = field(default_factory=dict)  # {days: ic}
    by_industry: dict[str, float] = field(default_factory=dict)
    # 逐期横截面 IC 序列 —— ic_std / icir / positive_ratio 都由它导出,
    # 不用它就无法得到有统计意义的 ICIR
    ic_series: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))

    def summary(self) -> str:
        return (
            f"Factor: {self.factor}\n"
            f"  IC:    mean={self.ic_mean:.4f}, std={self.ic_std:.4f}, ICIR={self.icir:.2f}\n"
            f"  RankIC:mean={self.rank_ic_mean:.4f}, RankICIR={self.rank_icir:.2f}\n"
            f"  Pos%={self.positive_ratio:.1%}, t={self.t_stat:.2f}, p={self.p_value:.4f}"
        )


def compute_ic(
    factor_df: pl.LazyFrame,
    factor_col: str,
    forward_returns_col: str = "fwd_return_1",
    by_industry_col: str | None = None,
) -> ICResult:
    """计算单因子的 IC 评估

    Args:
        factor_df: 包含 factor 和 forward returns 列的 df
        factor_col: 因子列名
        forward_returns_col: 未来 N 天收益率列
        by_industry_col: 行业列(可选)
    """
    # 逐期 IC 需要 date 列,必须一起取出来,下游按期分组计算 ICIR
    needed = [factor_col, forward_returns_col]
    has_date = False
    if "date" in factor_df.collect_schema().names():
        needed.append("date")
        has_date = True
    if by_industry_col:
        needed.append(by_industry_col)
    df = factor_df.select(needed).drop_nulls().collect().to_pandas()
    if not has_date:
        df = df.assign(date=None)

    if len(df) < 30:
        return ICResult(
            factor=factor_col,
            ic_mean=0.0,
            ic_std=0.0,
            icir=0.0,
            rank_ic_mean=0.0,
            rank_icir=0.0,
            positive_ratio=0.0,
            t_stat=0.0,
            p_value=1.0,
        )

    from scipy import stats

    x = df[factor_col].values
    y = df[forward_returns_col].values

    ic, _ = stats.pearsonr(x, y)
    rank_ic, _ = stats.spearmanr(x, y)

    # ICIR / positive_ratio 来自**逐期横截面 IC 时间序列**:
    #   * ICIR = mean(IC_t) / std(IC_t) 的时间序列统计量
    #   * positive_ratio = IC > 0 的天数比例
    # 按 date 逐期算横截面 IC,再对时间序列求均值/标准差。
    # 拿不到 date 列时(如调用方传的是已 pivot 的宽表)如实返回 0。
    ic_series = _cross_sectional_ic_series(df, factor_col, forward_returns_col)
    if len(ic_series) >= 2:
        ic_std = float(ic_series.std(ddof=1))
        icir = float(ic_series.mean() / ic_std) if ic_std > 0 else 0.0
        positive_ratio = float((ic_series > 0).mean())
    else:
        ic_std = 0.0
        icir = 0.0
        positive_ratio = 0.0

    n = len(df)
    t_stat = ic * np.sqrt(n) / np.sqrt(1 - ic**2 + 1e-9)
    p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df=n - 2))

    return ICResult(
        factor=factor_col,
        ic_mean=ic,
        ic_std=ic_std,
        icir=icir,
        rank_ic_mean=rank_ic,
        rank_icir=icir,
        positive_ratio=positive_ratio,
        t_stat=t_stat,
        p_value=p_value,
        ic_series=ic_series,
    )


def _cross_sectional_ic_series(
    df: "pd.DataFrame",
    factor_col: str,
    forward_returns_col: str,
    min_names: int = 5,
) -> "np.ndarray":
    """逐期(date)横截面 IC 序列 —— ICIR / positive_ratio 的唯一合法来源

    没有 date 列、或任一期的截面样本太少时返回空数组,由调用方如实置 0。
    """
    if "date" not in df.columns or df["date"].isna().all():
        return np.array([], dtype=float)

    # 逐期(截面)算 x 与 y 的皮尔森相关。中心化后做点积实现
    # r = Σxy / √(Σx²·Σy²),仅算相关系数,不带显著性检验与边界处理。
    #
    # 同样关键的是不要在循环里做 pandas 的逐组切片:250 期就是 250 次
    # DataFrame 子集构造 + dropna。这里一次 factorize + argsort 把面板
    # 排好序,再用 numpy 切片逐段处理,循环体里不再碰 pandas。
    import pandas as _pd  # 局部导入:模块顶部只在 TYPE_CHECKING 下引 pandas

    codes, uniques = _pd.factorize(df["date"], sort=True)
    xv_all = df[factor_col].to_numpy(dtype=float)
    yv_all = df[forward_returns_col].to_numpy(dtype=float)

    keep = ~np.isnan(xv_all) & ~np.isnan(yv_all)
    codes_k = codes[keep]
    if codes_k.size == 0:
        return np.array([], dtype=float)
    order = np.argsort(codes_k, kind="stable")
    xs = xv_all[keep][order]
    ys = yv_all[keep][order]
    cs = codes_k[order]

    starts = np.searchsorted(cs, np.arange(len(uniques)), side="left")
    ends = np.searchsorted(cs, np.arange(len(uniques)), side="right")

    out: list[float] = []
    for s, e in zip(starts, ends):
        if e - s < min_names:
            continue
        xc = xs[s:e]
        yc = ys[s:e]
        xc = xc - xc.mean()
        yc = yc - yc.mean()
        denom = np.sqrt((xc * xc).sum() * (yc * yc).sum())
        if denom <= 0:
            continue
        val = float((xc * yc).sum() / denom)
        if np.isfinite(val):
            out.append(val)
    return np.array(out, dtype=float)


def compute_ic_decay(
    factor_df: pl.LazyFrame,
    factor_col: str,
    forward_returns_cols: list[str],
) -> dict[int, float]:
    """计算 IC 衰减曲线

    Args:
        factor_df: 包含多个 forward_returns 列(fwd_return_1, fwd_return_5, ...)
        factor_col: 因子列
        forward_returns_cols: 多个 forward returns 列名列表(对应不同天数)

    Returns:
        {days: ic} 字典
    """
    decay = {}
    for col in forward_returns_cols:
        result = compute_ic(factor_df, factor_col, col)
        # 从列名提取天数
        days = int(col.replace("fwd_return_", ""))
        decay[days] = result.ic_mean
    return decay


def compute_ic_by_industry(
    factor_df: pl.LazyFrame,
    factor_col: str,
    forward_returns_col: str,
    industry_col: str,
) -> dict[str, float]:
    """分行业 IC"""
    df = (
        factor_df.select([factor_col, forward_returns_col, industry_col])
        .drop_nulls()
        .collect()
        .to_pandas()
    )
    result = {}
    for industry, group in df.groupby(industry_col):
        if len(group) < 30:
            continue
        from scipy import stats

        ic, _ = stats.pearsonr(group[factor_col].values, group[forward_returns_col].values)
        result[industry] = ic
    return result


def batch_compute_ic(
    factor_df: pl.LazyFrame,
    factor_cols: list[str],
    forward_returns_col: str = "fwd_return_1",
    by_industry_col: str | None = None,
    decay_cols: list[str] | None = None,
) -> list[ICResult]:
    """批量计算多因子 IC"""
    results = []
    for fc in factor_cols:
        try:
            decay = compute_ic_decay(factor_df, fc, decay_cols) if decay_cols else {}
            industry_ic = (
                compute_ic_by_industry(factor_df, fc, forward_returns_col, by_industry_col)
                if by_industry_col
                else {}
            )
            r = compute_ic(factor_df, fc, forward_returns_col)
            r.decay = decay
            r.by_industry = industry_ic
            results.append(r)
        except Exception as exc:
            # 出错因子在日志显式记录,不静默丢弃
            logger.warning("ic_compute_failed", factor=fc, error=type(exc).__name__)
    return results


def compute_forward_returns(
    df: pl.LazyFrame,
    horizons: list[int] | None = None,
) -> pl.LazyFrame:
    """计算前向收益率(用 close / shift(horizon) - 1)

    **必须按 symbol 分组**:面板数据里若直接对整列 shift(-h),每个标的
    末 h 行会取到**下一个标的**的首日价格。真实 A 股价格从 3 元到 2000 元
    都有,串号后收益率能偏离真实值近 400 倍,而 IC 依然算得"很顺利"——
    不崩,只是彻底错了(500 股 × 250 日、horizon=20 时 6.7% 的行是垃圾)。
    因此这里用 over("symbol") 限定窗口;单标的输入时行为不变。

    Args:
        df: 包含 close 列,按 symbol 排序;有 symbol 列时按其分组
        horizons: 前瞻期列表

    Returns:
        新增 fwd_return_1, fwd_return_5, ... 列
    """
    if horizons is None:
        horizons = [1, 5, 10, 20]
    schema = df.collect_schema().names()
    exprs = []
    for h in horizons:
        col = pl.col("close")
        future = col.shift(-h)
        if "symbol" in schema:
            future = future.over("symbol")
        exprs.append((future / col - 1).alias(f"fwd_return_{h}"))
    return df.with_columns(exprs)


def rank_factors_by_ic(results: list[ICResult]) -> list[ICResult]:
    """按 |Rank IC| 排序"""
    return sorted(results, key=lambda r: abs(r.rank_ic_mean), reverse=True)


def filter_significant_factors(
    results: list[ICResult], min_abs_ic: float = 0.02, max_p_value: float = 0.05
) -> list[ICResult]:
    """过滤显著因子"""
    return [r for r in results if abs(r.ic_mean) >= min_abs_ic and r.p_value <= max_p_value]
