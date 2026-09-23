# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from .alpha158 import (
    compute_alpha158,
    list_alpha158_factors,
    Alpha158Config,
    industry_neutralize,
)
from .alpha101 import (
    compute_alpha101,
    list_alpha101_factors,
)
from .barra import (
    compute_barra,
    list_barra_factors,
)
from .ic_monitor import (
    compute_ic,
    compute_ic_decay,
    compute_ic_by_industry,
    batch_compute_ic,
    compute_forward_returns,
    rank_factors_by_ic,
    filter_significant_factors,
    ICResult,
)


__all__ = [
    "compute_alpha158",
    "list_alpha158_factors",
    "Alpha158Config",
    "industry_neutralize",
    "compute_alpha101",
    "list_alpha101_factors",
    "compute_barra",
    "list_barra_factors",
    "compute_ic",
    "compute_ic_decay",
    "compute_ic_by_industry",
    "batch_compute_ic",
    "compute_forward_returns",
    "rank_factors_by_ic",
    "filter_significant_factors",
    "ICResult",
]


def get_all_factors() -> list:
    """返回所有可用因子名"""
    return list_alpha158_factors() + list_alpha101_factors() + list_barra_factors()


def factor_count() -> int:
    """因子总数(Alpha158 + Alpha101 + Barra)"""
    return len(get_all_factors())