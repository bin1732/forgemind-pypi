# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import numpy as np
import pandas as pd


def make_test_features(n=1000, n_features=20, n_symbols=10):
    """构造合成特征和标签"""
    np.random.seed(42)
    n_per_symbol = n // n_symbols
    rows = []
    for sym in range(n_symbols):
        for i in range(n_per_symbol):
            features = np.random.randn(n_features).tolist()
            # 标签与特征线性相关
            label = sum(features[:5]) / 5 + np.random.randn() * 0.1
            rows.append([f"S{sym:04d}", i] + features + [label])
    
    cols = ["symbol", "time_idx"] + [f"F{i}" for i in range(n_features)] + ["label"]
    df = pd.DataFrame(rows, columns=cols)
    return df


class TestLightGBMModel:
    def test_train_with_cv(self):
        from forgemind.core.models import LightGBMModel, ModelConfig
        df = make_test_features(1000, 10, 5)
        X = df[[f"F{i}" for i in range(10)]]
        y = df["label"]
        
        config = ModelConfig(n_estimators=100, cv_splits=3)
        model = LightGBMModel(config)
        result = model.train(X, y, use_cv=True)
        
        assert result is not None
        assert len(result.cv_scores) > 0
        assert result.cv_mean is not None
        assert len(result.feature_importance) == 10
    
    def test_purged_kfold_split(self):
        from forgemind.core.models import LightGBMModel, ModelConfig
        model = LightGBMModel(ModelConfig(cv_splits=5))
        splits = model._purged_kfold_split(1000, 5, embargo=0.05)
        # 每个 split 的 train idx 都应该在 val idx 之前(时序)
        for train_idx, val_idx in splits:
            # train_idx max < val_idx min
            assert max(train_idx) < min(val_idx), f"train max {max(train_idx)} >= val min {min(val_idx)}"
            # embargo: train_idx max 应该离 val_idx min 有一定距离
            gap = min(val_idx) - max(train_idx)
            assert gap >= 1, f"embargo gap 应 >= 1, 实际 {gap}"
    
    def test_predict(self):
        from forgemind.core.models import LightGBMModel
        df = make_test_features(500, 10, 3)
        X = df[[f"F{i}" for i in range(10)]]
        y = df["label"]
        
        model = LightGBMModel()
        model.train(X, y, use_cv=False)
        preds = model.predict(X)
        assert len(preds) == len(X)
    
    def test_save_load(self):
        from forgemind.core.models import LightGBMModel
        import tempfile
        
        df = make_test_features(300, 5, 3)
        X = df[[f"F{i}" for i in range(5)]]
        y = df["label"]
        
        model = LightGBMModel()
        model.train(X, y, use_cv=False)
        
        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = f.name
            model.save(path)
            loaded = LightGBMModel.load(path)
            assert loaded.feature_names == model.feature_names
            # 预测一致性
            preds1 = model.predict(X)
            preds2 = loaded.predict(X)
            assert np.allclose(preds1, preds2)


class TestXGBoost:
    def test_train(self):
        from forgemind.core.models import XGBoostModel
        df = make_test_features(500, 10, 3)
        X = df[[f"F{i}" for i in range(10)]]
        y = df["label"]
        
        model = XGBoostModel(n_estimators=100)
        result = model.train(X, y)
        assert "feature_importance" in result
        assert len(model.feature_names) == 10


class TestCatBoost:
    def test_train(self):
        from forgemind.core.models import CatBoostModel
        df = make_test_features(500, 10, 3)
        X = df[[f"F{i}" for i in range(10)]]
        y = df["label"]
        
        model = CatBoostModel(iterations=100)
        result = model.train(X, y)
        assert "feature_importance" in result


class TestEnsemble:
    def test_ensemble(self):
        from forgemind.core.models import LightGBMModel, XGBoostModel, EnsembleModel
        df = make_test_features(500, 5, 3)
        X = df[[f"F{i}" for i in range(5)]]
        y = df["label"]
        
        lgbm = LightGBMModel()
        lgbm.train(X, y, use_cv=False)
        
        xgb = XGBoostModel(n_estimators=50)
        xgb.train(X, y)
        
        ensemble = EnsembleModel([lgbm, xgb], weights=[0.6, 0.4])
        preds = ensemble.predict(X)
        assert len(preds) == len(X)


class TestRegistry:
    def test_register_and_get(self):
        from forgemind.core.models import ModelRegistry
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmp:
            registry = ModelRegistry(base_path=tmp)
            registry.register(
                name="lgbm_v1",
                version=1,
                model_path="/tmp/lgbm_v1.pkl",
                metrics={"rank_ic": 0.05},
                tags={"type": "lightgbm"},
            )
            registry.register(
                name="lgbm_v1",
                version=2,
                model_path="/tmp/lgbm_v2.pkl",
                metrics={"rank_ic": 0.07},
                tags={"type": "lightgbm"},
            )
            
            latest = registry.get_latest("lgbm_v1")
            assert latest["version"] == 2
            assert latest["metrics"]["rank_ic"] == 0.07
            
            models = registry.list_models()
            assert "lgbm_v1" in models


class TestSHAP:
    def test_compute_shap(self):
        from forgemind.core.models import LightGBMModel
        df = make_test_features(500, 10, 3)
        X = df[[f"F{i}" for i in range(10)]]
        y = df["label"]
        
        model = LightGBMModel()
        model.train(X, y, use_cv=False)
        shap = model.compute_shap(X.head(100), top_n=5)
        assert len(shap) <= 5
        assert len(shap) >= 1