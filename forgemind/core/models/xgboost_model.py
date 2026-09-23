# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import numpy as np
import pandas as pd
from typing import Optional, Dict, List
from pathlib import Path


class XGBoostModel:
    """XGBoost 量化预测模型"""
    
    def __init__(
        self,
        n_estimators: int = 1000,
        max_depth: int = 6,
        learning_rate: float = 0.05,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        reg_alpha: float = 1.0,
        reg_lambda: float = 1.0,
        tree_method: str = "hist",  # GPU: "gpu_hist"
        seed: int = 42,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.reg_alpha = reg_alpha
        self.reg_lambda = reg_lambda
        self.tree_method = tree_method
        self.seed = seed
        self.model = None
        self.feature_names: List[str] = []
    
    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> Dict:
        """训练"""
        try:
            import xgboost as xgb
        except ImportError:
            return self._train_sklearn(X, y)
        
        self.feature_names = list(X.columns)
        self.model = xgb.XGBRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            subsample=self.subsample,
            colsample_bytree=self.colsample_bytree,
            reg_alpha=self.reg_alpha,
            reg_lambda=self.reg_lambda,
            tree_method=self.tree_method,
            random_state=self.seed,
        )
        
        if X_val is not None:
            self.model.fit(X, y, eval_set=[(X_val, y_val)], verbose=False)
        else:
            self.model.fit(X, y)
        
        importance = dict(zip(self.feature_names, self.model.feature_importances_))
        return {"feature_importance": importance}
    
    def _train_sklearn(self, X, y):
        """fallback: sklearn GBR"""
        from sklearn.ensemble import GradientBoostingRegressor
        self.feature_names = list(X.columns)
        self.model = GradientBoostingRegressor(n_estimators=200, random_state=self.seed)
        self.model.fit(X, y)
        return {"feature_importance": dict(zip(self.feature_names, self.model.feature_importances_))}
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict(X)
    
    def save(self, path: str):
        import joblib
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "feature_names": self.feature_names}, path)
    
    @classmethod
    def load(cls, path: str) -> "XGBoostModel":
        import joblib
        data = joblib.load(path)
        instance = cls()
        instance.model = data["model"]
        instance.feature_names = data["feature_names"]
        return instance


class CatBoostModel:
    """CatBoost 量化预测模型(对类别特征友好)"""
    
    def __init__(
        self,
        iterations: int = 1000,
        depth: int = 6,
        learning_rate: float = 0.05,
        l2_leaf_reg: float = 3.0,
        random_seed: int = 42,
    ):
        self.iterations = iterations
        self.depth = depth
        self.learning_rate = learning_rate
        self.l2_leaf_reg = l2_leaf_reg
        self.random_seed = random_seed
        self.model = None
        self.feature_names = []
    
    def train(self, X, y, cat_features=None):
        try:
            from catboost import CatBoostRegressor
        except ImportError:
            return self._train_fallback(X, y)
        
        self.feature_names = list(X.columns)
        self.model = CatBoostRegressor(
            iterations=self.iterations,
            depth=self.depth,
            learning_rate=self.learning_rate,
            l2_leaf_reg=self.l2_leaf_reg,
            random_seed=self.random_seed,
            verbose=False,
        )
        self.model.fit(X, y, cat_features=cat_features or [])
        return {"feature_importance": dict(zip(self.feature_names, self.model.feature_importances_))}
    
    def _train_fallback(self, X, y):
        from sklearn.ensemble import GradientBoostingRegressor
        self.model = GradientBoostingRegressor(n_estimators=100, random_state=self.random_seed)
        self.model.fit(X, y)
        return {"feature_importance": dict(zip(list(X.columns), self.model.feature_importances_))}
    
    def predict(self, X):
        return self.model.predict(X)


class EnsembleModel:
    """模型集成 — 多模型 stacking
    
    对标 RD-Agent / Qlib ensemble 实践
    """
    
    def __init__(self, models: List, weights: Optional[List[float]] = None):
        self.models = models
        self.weights = weights or [1.0 / len(models)] * len(models)
    
    def train(self, X, y):
        for m in self.models:
            if hasattr(m, "train"):
                m.train(X, y)
    
    def predict(self, X):
        preds = np.array([m.predict(X) for m in self.models])
        # 加权平均
        weighted = np.zeros(len(X))
        for i, w in enumerate(self.weights):
            weighted += w * preds[i]
        return weighted
    
    def save(self, path: str):
        import joblib
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"models": self.models, "weights": self.weights}, path)