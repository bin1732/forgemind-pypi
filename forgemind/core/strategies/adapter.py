# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""把 extended_library 的 `generate_signal(df) -> Series` 适配成引擎要的
`generate_signals(df) -> DataFrame[entries, exits]`

extended_library 的 12 个策略用的是另一套接口(批量向量式),
base.Strategy 用的是 on_bar(逐根)。两者不能直接互换,这个适配层让
`forgemind backtest --strategy <扩展策略名>` 真的能跑。
"""

from __future__ import annotations

import pandas as pd

from forgemind.core.strategies.base import Strategy


class SignalSeriesAdapter(Strategy):
    """把 Series 形式的持仓信号(1=开仓 / -1=平仓 / 0=观望)转成引擎要的布尔列

    - positions 从 0→1 的那一根 → entries=True
    - positions 从 1→0(或 1→-1)的那一根 → exits=True
    """

    def __init__(self, inner, name: str | None = None, **parameters):
        self.inner = inner
        super().__init__(
            name=name or getattr(inner, "name", inner.__class__.__name__),
            parameters=parameters or {},
        )

    def generate_signals(self, price_df: pd.DataFrame) -> pd.DataFrame:
        raw = self.inner.generate_signal(self._normalize(price_df))
        pos = pd.Series(raw, index=price_df.index).fillna(0).astype(float)

        # 归一到 {0, 1}: 正数视为多头持仓,负数视为空头
        held = (pos > 0).astype(int)
        prev = held.shift(1).fillna(0).astype(int)

        entries = (held == 1) & (prev == 0)
        exits = (held == 0) & (prev == 1)
        return pd.DataFrame({
            "entries": entries.astype(bool),
            "exits": exits.astype(bool),
        })

    @staticmethod
    def _normalize(price_df: pd.DataFrame) -> pd.DataFrame:
        """扩展策略要 `date` / `symbol` 是真实列,而回测引擎把它们放在索引/常量上

        这里补齐列,让组合类策略(df.pivot(index="date", columns="symbol"))
        和横截面策略都能工作。
        """
        df = price_df.copy()
        if "date" not in df.columns:
            if isinstance(df.index, pd.DatetimeIndex):
                df["date"] = df.index
            else:
                df["date"] = pd.RangeIndex(len(df))
        if "symbol" not in df.columns:
            df["symbol"] = "DEMO"
        return df

    def validate_parameters(self) -> None:
        """扩展策略自己管参数,这里不做额外校验"""

    def on_bar(self, bar_dict):
        """逐根接口不支持 —— 扩展策略是批量的"""
        return None


def build_extended_strategy(name: str, **params) -> SignalSeriesAdapter:
    """按名字实例化扩展策略并套上适配层"""
    from forgemind.core.strategies.extended_library import list_strategies

    catalog = list_strategies()
    if name not in catalog:
        raise ValueError(
            f"Unknown extended strategy: {name}. Available: {sorted(catalog)}"
        )
    cls = catalog[name]
    return SignalSeriesAdapter(cls(**params), name=name, **params)
