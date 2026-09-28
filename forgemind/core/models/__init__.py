# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""Models — light-weight imports by default.

Transformer imports torch lazily (heavy). Import it explicitly:
    from forgemind.core.models.transformer_model import TransformerModel
"""
from .lightgbm_model import (
    LightGBMModel,
    ModelConfig,
    ModelRegistry,
    TrainResult,
)
from .xgboost_model import (
    CatBoostModel,
    EnsembleModel,
    XGBoostModel,
)


def _load_transformer():
    """Lazy import transformer (requires torch)."""
    from .transformer_model import (
        PositionalEncoding,
        TransformerModel,
        TransformerTimeSeries,
    )
    return TransformerModel, TransformerTimeSeries, PositionalEncoding


__all__ = [
    "LightGBMModel",
    "ModelConfig",
    "TrainResult",
    "ModelRegistry",
    "XGBoostModel",
    "CatBoostModel",
    "TransformerModel",
    "TransformerTimeSeries",
    "PositionalEncoding",
    "EnsembleModel",
]
