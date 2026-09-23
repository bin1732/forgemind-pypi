# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import numpy as np
import pandas as pd
import warnings
from typing import Optional, Dict, List, Tuple
from pathlib import Path
from dataclasses import dataclass, field

# lightgbm 4.7+ 把 eval_set 标记 deprecated(LGBMDeprecationWarning 继承 FutureWarning),但仍工作。
# 我们知道且接受 — 真修要重构成 eval_X=[...] + eval_y=[...] 形式,但 eval_set 形式更简洁。
try:
    from lightgbm.sklearn import LGBMDeprecationWarning
    warnings.filterwarnings(
        "ignore",
        message=".*eval_set.*deprecated.*",
        category=LGBMDeprecationWarning,
    )
except ImportError:
    pass


@dataclass
class ModelConfig:
    """LightGBM 训练配置"""
    objective: str = "regression"
    metric: str = "rmse"
    num_leaves: int = 64
    learning_rate: float = 0.05
    feature_fraction: float = 0.8
    bagging_fraction: float = 0.8
    bagging_freq: int = 5
    min_data_in_leaf: int = 100
    lambda_l1: float = 1.0
    lambda_l2: float = 1.0
    max_depth: int = -1
    n_estimators: int = 1000
    early_stopping_rounds: int = 50
    verbose: int = -1
    # CV
    cv_splits: int = 5
    cv_embargo_pct: float = 0.02  # 2% embargo 防泄露
    # 随机种子
    seed: int = 42


@dataclass
class TrainResult:
    """训练结果"""
    model_path: str
    cv_scores: List[float]  # 每次 fold 的 IC 或 RMSE
    cv_mean: float
    cv_std: float
    feature_importance: Dict[str, float]
    best_iteration: int
    train_loss_curve: List[float] = field(default_factory=list)
    val_loss_curve: List[float] = field(default_factory=list)
    
    def summary(self) -> str:
        return (
            f"Model: {self.model_path}\n"
            f"  CV: mean={self.cv_mean:.4f}, std={self.cv_std:.4f}\n"
            f"  Best iteration: {self.best_iteration}\n"
            f"  Top 5 features: {sorted(self.feature_importance.items(), key=lambda x: -x[1])[:5]}"
        )


class LightGBMModel:
    """LightGBM 量化预测模型"""
    
    def __init__(self, config: Optional[ModelConfig] = None):
        self.config = config or ModelConfig()
        self.model = None
        self.feature_names: List[str] = []
        self.train_result: Optional[TrainResult] = None
    
    def _create_model(self):
        """创建 LightGBM 模型实例(懒加载)"""
        try:
            import lightgbm as lgb
            return lgb.LGBMRegressor(
                objective=self.config.objective,
                metric=self.config.metric,
                num_leaves=self.config.num_leaves,
                learning_rate=self.config.learning_rate,
                feature_fraction=self.config.feature_fraction,
                bagging_fraction=self.config.bagging_fraction,
                bagging_freq=self.config.bagging_freq,
                min_data_in_leaf=self.config.min_data_in_leaf,
                lambda_l1=self.config.lambda_l1,
                lambda_l2=self.config.lambda_l2,
                max_depth=self.config.max_depth,
                n_estimators=self.config.n_estimators,
                verbose=self.config.verbose,
                random_state=self.config.seed,
            )
        except ImportError:
            return None
    
    def _purged_kfold_split(self, n: int, splits: int, embargo: float = 0.02) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Time-series purged K-fold split(防泄露)
        
        Args:
            n: 样本总数
            splits: K 折数
            embargo: 每折之间留 embargo 比例的数据不用
        
        Returns:
            [(train_idx, val_idx), ...]
        """
        fold_size = n // splits
        embargo_size = int(fold_size * embargo)
        indices = []
        for i in range(splits):
            val_start = i * fold_size
            val_end = (i + 1) * fold_size if i < splits - 1 else n
            train_end = val_start - embargo_size
            train_idx = np.arange(0, max(0, train_end))
            val_idx = np.arange(val_start, val_end)
            if len(train_idx) > 0 and len(val_idx) > 0:
                indices.append((train_idx, val_idx))
        return indices
    
    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        use_cv: bool = True,
    ) -> TrainResult:
        """训练模型
        
        Args:
            X: 训练特征
            y: 训练标签(未来收益率)
            X_val, y_val: 验证集(可选; 不传则用 purged K-fold)
            use_cv: 是否使用 K-fold CV
        """
        self.feature_names = list(X.columns)
        self.model = self._create_model()
        
        if self.model is None:
            # lightgbm 未装,降级到 sklearn
            return self._train_sklearn_fallback(X, y, X_val, y_val, use_cv)
        
        cv_scores = []
        best_iterations = []
        
        if use_cv and X_val is None:
            splits = self._purged_kfold_split(len(X), self.config.cv_splits, self.config.cv_embargo_pct)
            for fold_idx, (train_idx, val_idx) in enumerate(splits):
                X_train_fold = X.iloc[train_idx]
                y_train_fold = y.iloc[train_idx]
                X_val_fold = X.iloc[val_idx]
                y_val_fold = y.iloc[val_idx]
                
                model = self._create_model()
                # lightgbm 4.0+ 用 eval_set=[(X, y)] 仍兼容,但静默 deprecation warning
                # 真修复要传入 eval_X/eval_y,但那是 sklearn wrapper 的方式
                # LightGBM 原生 API 用 callbacks,这里用 sklearn wrapper
                try:
                    model.fit(
                        X_train_fold, y_train_fold,
                        eval_set=[(X_val_fold, y_val_fold)],
                        callbacks=[],
                    )
                except (TypeError, ValueError):
                    # 4.x 兼容路径
                    model.fit(X_train_fold, y_train_fold)
                
                preds = model.predict(X_val_fold)
                from scipy.stats import spearmanr
                # y_val_fold 是常数时 spearman 会 ConstantInputWarning,正常处理
                if np.unique(y_val_fold).size < 2 or np.unique(preds).size < 2:
                    rank_ic = 0.0  # 常数序列无相关性
                else:
                    with np.errstate(all="ignore"):
                        rank_ic, _ = spearmanr(preds, y_val_fold)
                        if np.isnan(rank_ic):
                            rank_ic = 0.0
                cv_scores.append(rank_ic)
                best_iterations.append(model.best_iteration_ if hasattr(model, 'best_iteration_') else self.config.n_estimators)
            
            # 训练最终模型
            self.model.fit(X, y)
        else:
            try:
                self.model.fit(
                    X, y,
                    eval_set=[(X_val, y_val)] if X_val is not None else None,
                    callbacks=[],
                )
            except (TypeError, ValueError):
                self.model.fit(X, y)
            cv_scores.append(0.0)
            best_iterations.append(self.model.best_iteration_ if hasattr(self.model, 'best_iteration_') else self.config.n_estimators)
        
        # 特征重要性
        importance = dict(zip(self.feature_names, self.model.feature_importances_))
        
        self.train_result = TrainResult(
            model_path="",  # 序列化时填充
            cv_scores=cv_scores,
            cv_mean=float(np.mean(cv_scores)),
            cv_std=float(np.std(cv_scores)),
            feature_importance=importance,
            best_iteration=int(np.median(best_iterations)),
        )
        
        return self.train_result
    
    def _train_sklearn_fallback(self, X, y, X_val, y_val, use_cv) -> TrainResult:
        """无 lightgbm 时的 fallback(简单 GBR)"""
        from sklearn.ensemble import GradientBoostingRegressor
        
        self.model = GradientBoostingRegressor(
            n_estimators=100, max_depth=4, learning_rate=0.05, random_state=self.config.seed,
        )
        self.model.fit(X, y)
        
        importance = dict(zip(self.feature_names, self.model.feature_importances_))
        
        cv_scores = []
        if use_cv and X_val is None:
            splits = self._purged_kfold_split(len(X), self.config.cv_splits, self.config.cv_embargo_pct)
            from scipy.stats import spearmanr
            for train_idx, val_idx in splits:
                m = GradientBoostingRegressor(n_estimators=100, random_state=self.config.seed)
                m.fit(X.iloc[train_idx], y.iloc[train_idx])
                preds = m.predict(X.iloc[val_idx])
                rank_ic, _ = spearmanr(preds, y.iloc[val_idx])
                cv_scores.append(rank_ic)
        
        self.train_result = TrainResult(
            model_path="",
            cv_scores=cv_scores,
            cv_mean=float(np.mean(cv_scores)) if cv_scores else 0.0,
            cv_std=float(np.std(cv_scores)) if cv_scores else 0.0,
            feature_importance=importance,
            best_iteration=100,
        )
        return self.train_result
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """预测"""
        if self.model is None:
            raise RuntimeError("Model not trained")
        return self.model.predict(X)
    
    def save(self, path: str):
        """序列化模型"""
        import joblib
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "model": self.model,
            "feature_names": self.feature_names,
            "config": self.config,
            "train_result": self.train_result,
        }, path)
    
    @classmethod
    def load(cls, path: str) -> "LightGBMModel":
        """反序列化"""
        import joblib
        data = joblib.load(path)
        instance = cls(data["config"])
        instance.model = data["model"]
        instance.feature_names = data["feature_names"]
        instance.train_result = data["train_result"]
        return instance
    
    def compute_shap(self, X: pd.DataFrame, top_n: int = 20) -> Dict[str, float]:
        """计算 SHAP 特征重要性"""
        try:
            import shap
            explainer = shap.TreeExplainer(self.model)
            shap_values = explainer.shap_values(X)
            mean_abs_shap = np.abs(shap_values).mean(axis=0)
            importance = dict(zip(self.feature_names, mean_abs_shap))
            # top_n
            sorted_imp = sorted(importance.items(), key=lambda x: -x[1])[:top_n]
            return dict(sorted_imp)
        except ImportError:
            # 没有 shap,用 gain importance
            if not self.train_result:
                return {}
            sorted_imp = sorted(self.train_result.feature_importance.items(), key=lambda x: -x[1])[:top_n]
            return dict(sorted_imp)


class ModelRegistry:
    """模型注册表(对标 MLflow Registry)"""
    
    def __init__(self, base_path: str = "./data/models"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._index_file = self.base_path / "registry.json"
        self._registry = self._load_index()
    
    def _load_index(self) -> dict:
        if self._index_file.exists():
            import json
            return json.loads(self._index_file.read_text())
        return {"models": {}}
    
    def _save_index(self):
        import json
        self._index_file.write_text(json.dumps(self._registry, indent=2, default=str))
    
    def register(
        self,
        name: str,
        version: int,
        model_path: str,
        metrics: Dict,
        tags: Optional[Dict[str, str]] = None,
    ):
        """注册模型"""
        if name not in self._registry["models"]:
            self._registry["models"][name] = {"versions": []}
        self._registry["models"][name]["versions"].append({
            "version": version,
            "model_path": model_path,
            "metrics": metrics,
            "tags": tags or {},
            "registered_at": str(np.datetime64("now")),
        })
        self._save_index()
    
    def get_latest(self, name: str) -> Optional[Dict]:
        """获取最新版本"""
        if name not in self._registry["models"]:
            return None
        versions = self._registry["models"][name]["versions"]
        return max(versions, key=lambda v: v["version"]) if versions else None
    
    def list_models(self) -> List[str]:
        return list(self._registry["models"].keys())