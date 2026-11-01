# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from .base import Strategy as BaseStrategy
from .extended_library import (
    CrossSectionalMomentum,
    EarningsAnnouncement,
    IndexInclusion,
    LightGBMStrategy,
    MaxSharpe,
    MomentumRotation,
    OnlineLearningStrategy,
    OrnsteinUhlenbeck,
    PairsTrading,
    RiskParity,
    RSIReversion,
    TimeSeriesMomentum,
    list_categories,
    list_strategies,
)
from .library import (
    STRATEGY_REGISTRY,
    BollingerBandsStrategy,
    BuyAndHoldStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    MovingAverageCrossStrategy,
    get_strategy_class,
)

__all__ = [
    # 原有
    "BaseStrategy",
    "MovingAverageCrossStrategy",
    "MeanReversionStrategy",
    "MomentumStrategy",
    "BollingerBandsStrategy",
    "BuyAndHoldStrategy",
    "get_strategy_class",
    "STRATEGY_REGISTRY",
    # 扩展
    "TimeSeriesMomentum",
    "CrossSectionalMomentum",
    "MomentumRotation",
    "PairsTrading",
    "OrnsteinUhlenbeck",
    "RSIReversion",
    "LightGBMStrategy",
    "OnlineLearningStrategy",
    "EarningsAnnouncement",
    "IndexInclusion",
    "RiskParity",
    "MaxSharpe",
    "list_strategies",
    "list_categories",
]


def total_strategies() -> int:
    return len(list_strategies()) + 5  # 基础 5 个 + 扩展 12 个
