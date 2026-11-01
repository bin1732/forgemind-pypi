# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""模型必须报告**实际使用的后端**,而不只是自称

LightGBMModel / XGBoostModel / CatBoostModel 在主库缺失时会静默降级到
sklearn。流水线对外一律写 `model_name="LightGBM"`,于是用户会把
sklearn 的结果当成 LightGBM 的结果 —— 两者实现不同、性能不同、
可解释性也不同,这个差别不该被藏起来。

已验证:CatBoost 未安装时,`CatBoostModel` 内部跑的是 sklearn,
但对象自称 CatBoost,不查无从分辨。
"""

import numpy as np
import pandas as pd
import pytest


def _data(n=600, k=4, seed=0):
    rng = np.random.default_rng(seed)
    X = pd.DataFrame(rng.normal(0, 1, (n, k)), columns=[f"f{i}" for i in range(k)])
    y = pd.Series(X["f0"] * 0.6 - X["f1"] * 0.3 + rng.normal(0, 0.1, n))
    return X, y


class TestModelsReportTheirBackend:
    @pytest.mark.parametrize("import_path,cls_name", [
        ("forgemind.core.models", "LightGBMModel"),
        ("forgemind.core.models", "XGBoostModel"),
        ("forgemind.core.models", "CatBoostModel"),
    ])
    def test_backend_is_recorded_after_training(self, import_path, cls_name):
        import importlib

        cls = getattr(importlib.import_module(import_path), cls_name)
        X, y = _data()
        m = cls()
        assert m.backend == "unknown", "训练前应为 unknown"
        m.train(X, y)
        assert m.backend and m.backend != "unknown", (
            f"{cls_name} 训练后没有记录实际后端 —— 无法判断跑的是不是它自己")
        # 声明的名字与实际后端必须能对上
        if m.backend != "sklearn_fallback":
            assert m.backend == cls_name.replace("Model", "").lower(), (
                f"{cls_name} 声称用了 {m.backend}")

    def test_fallback_is_marked_not_silent(self):
        """降级时必须能看出是降级"""

        from forgemind.core.models import CatBoostModel

        m = CatBoostModel()
        X, y = _data()
        m.train(X, y)
        if "catboost" not in _installed():
            assert m.backend == "sklearn_fallback", (
                f"catboost 未安装却没标降级,backend={m.backend}")

    def test_pipeline_result_carries_the_backend(self):
        import dataclasses

        from forgemind.core.pipeline.end_to_end import PipelineResult

        names = [f.name for f in dataclasses.fields(PipelineResult)]
        assert "model_backend" in names
        # 摘要里也要能看到
        src = (PipelineResult.__module__ and
               __import__("inspect").getsource(PipelineResult.summary))
        assert "model_backend" in src, "摘要里没有显示实际后端"


def _installed() -> set:
    import importlib.util
    return {m for m in ("lightgbm", "xgboost", "catboost")
            if importlib.util.find_spec(m)}
