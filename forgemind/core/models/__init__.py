# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""Models — 模块级惰性导入 (PEP 562 `__getattr__`)。

仅当实际取用类时 (例如 `from forgemind.core.models import LightGBMModel`)
才触发对应子模块 import,避免 `forgemind.core.models.transformer_model`
间接拉起 lightgbm / sklearn / xgboost。
"""

from importlib import import_module
from typing import Any

_LAZY = {
    "LightGBMModel": ".lightgbm_model",
    "ModelConfig": ".lightgbm_model",
    "ModelRegistry": ".lightgbm_model",
    "TrainResult": ".lightgbm_model",
    "XGBoostModel": ".xgboost_model",
    "CatBoostModel": ".xgboost_model",
    "EnsembleModel": ".xgboost_model",
    "TransformerModel": ".transformer_model",
    "TransformerTimeSeries": ".transformer_model",
    "PositionalEncoding": ".transformer_model",
}

__all__ = list(_LAZY)


def __getattr__(name: str) -> Any:
    """按需解析:只有访问具体类时才 import 对应子模块"""
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module, __name__), name)
    globals()[name] = value  # 缓存,后续直接命中
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
