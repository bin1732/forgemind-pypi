# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import numpy as np
import pandas as pd
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from scipy.stats import pearsonr, spearmanr


# === 基础接口 ===
class BaseStrategy:
    """策略基类"""
    name: str = "BaseStrategy"
    category: str = "base"
    
    def __init__(self, **kwargs):
        self.params = kwargs
    
    def generate_signal(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        """生成交易信号(1=buy, -1=sell, 0=hold)"""
        raise NotImplementedError


# === 1. 动量策略 ===
class TimeSeriesMomentum(BaseStrategy):
    """时序动量: 单一品种的历史收益方向"""
    name = "TimeSeriesMomentum"
    category = "momentum"
    
    def __init__(self, lookback: int = 20, threshold: float = 0.0, **kwargs):
        super().__init__(lookback=lookback, threshold=threshold, **kwargs)
        self.lookback = lookback
        self.threshold = threshold
    
    def generate_signal(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        ret = df["close"].pct_change(self.lookback)
        return np.sign(ret - self.threshold)


class CrossSectionalMomentum(BaseStrategy):
    """截面动量: 买入过去 N 天收益最高的, 卖出最低的"""
    name = "CrossSectionalMomentum"
    category = "momentum"
    
    def __init__(self, lookback: int = 60, top_pct: float = 0.2, **kwargs):
        super().__init__(lookback=lookback, top_pct=top_pct, **kwargs)
        self.lookback = lookback
        self.top_pct = top_pct
    
    def generate_signal(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        ret = df.groupby("symbol")["close"].pct_change(self.lookback)
        # 截面排序: top_pct 买入, bottom_pct 卖出
        ranks = ret.groupby(df["date"]).rank(pct=True)
        signals = pd.Series(0, index=df.index)
        signals[ranks > 1 - self.top_pct] = 1  # buy
        signals[ranks < self.top_pct] = -1  # sell
        return signals


class MomentumRotation(BaseStrategy):
    """行业轮动: 选动量最强的行业 ETF"""
    name = "MomentumRotation"
    category = "momentum"
    
    def __init__(self, lookbacks: List[int] = None, **kwargs):
        super().__init__(**kwargs)
        self.lookbacks = lookbacks or [20, 60, 120]
    
    def generate_signal(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        score = pd.Series(0.0, index=df.index)
        for lb in self.lookbacks:
            ret = df.groupby("symbol")["close"].pct_change(lb)
            score = score.add(ret.fillna(0), fill_value=0)
        return np.sign(score)


# === 2. 均值回归 ===
class PairsTrading(BaseStrategy):
    """配对交易 — EG 协整检验 + spread z-score
    
    经典统计套利:
    1. 找协整对(cointegrated pair)
    2. 计算 spread = P_a - β * P_b
    3. spread z-score < -2: 做多 a, 做空 b
    4. spread z-score > 2: 做空 a, 做多 b
    5. spread z-score 接近 0: 平仓
    
    回测时需要传入两个 symbol 的 close price
    """
    name = "PairsTrading"
    category = "stat_arb"
    
    def __init__(
        self,
        lookback: int = 60,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
        hedge_method: str = "ols",  # "ols" 或 "kalman"
        **kwargs,
    ):
        super().__init__(lookback=lookback, entry_z=entry_z, exit_z=exit_z, hedge_method=hedge_method, **kwargs)
        self.lookback = lookback
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.hedge_method = hedge_method
    
    def compute_hedge_ratio(self, pa: pd.Series, pb: pd.Series) -> float:
        """OLS hedge ratio"""
        # 移除 NaN
        df = pd.DataFrame({"a": pa, "b": pb}).dropna()
        if len(df) < self.lookback:
            return 1.0
        # beta = cov(a,b) / var(b)
        cov = df["a"].cov(df["b"])
        var = df["b"].var()
        return cov / var if var > 0 else 1.0
    
    def generate_signal(
        self,
        df_a: pd.DataFrame,  # symbol a 的 OHLCV
        df_b: pd.DataFrame,  # symbol b 的 OHLCV
    ) -> Tuple[pd.Series, pd.Series]:
        """返回 (signal_a, signal_b)"""
        # 对齐
        merged = pd.DataFrame({
            "a": df_a["close"].values,
            "b": df_b["close"].values,
        }).dropna()
        
        # 计算 rolling beta
        betas = []
        spreads = []
        for i in range(self.lookback, len(merged)):
            window = merged.iloc[i - self.lookback:i]
            beta = self.compute_hedge_ratio(window["a"], window["b"])
            betas.append(beta)
            spread = window["a"].iloc[-1] - beta * window["b"].iloc[-1]
            spreads.append(spread)
        
        # 用 z-score
        spread_series = pd.Series(spreads)
        spread_mean = spread_series.rolling(self.lookback).mean()
        spread_std = spread_series.rolling(self.lookback).std()
        z_score = (spread_series - spread_mean) / (spread_std + 1e-9)
        
        # 信号
        signal_a = pd.Series(0, index=z_score.index)
        signal_b = pd.Series(0, index=z_score.index)
        
        # z < -2: long a, short b
        signal_a[z_score < -self.entry_z] = 1
        signal_b[z_score < -self.entry_z] = -1
        
        # z > 2: short a, long b
        signal_a[z_score > self.entry_z] = -1
        signal_b[z_score > self.entry_z] = 1
        
        # 接近 0: 平仓
        signal_a[z_score.abs() < self.exit_z] = 0
        signal_b[z_score.abs() < self.exit_z] = 0
        
        return signal_a, signal_b


class OrnsteinUhlenbeck(BaseStrategy):
    """OU 过程均值回归 — 适合 spread / pair trading"""
    name = "OrnsteinUhlenbeck"
    category = "mean_reversion"
    
    def __init__(self, lookback: int = 60, entry_z: float = 2.0, **kwargs):
        super().__init__(lookback=lookback, entry_z=entry_z, **kwargs)
        self.lookback = lookback
        self.entry_z = entry_z
    
    def generate_signal(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        price = df["close"]
        mu = price.rolling(self.lookback).mean()
        sigma = price.rolling(self.lookback).std()
        z = (price - mu) / (sigma + 1e-9)
        # z < -entry_z: 买入(预期均值回归)
        # z > entry_z: 卖出
        return -np.sign(z)


class RSIReversion(BaseStrategy):
    """RSI 均值回归"""
    name = "RSIReversion"
    category = "mean_reversion"
    
    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70, **kwargs):
        super().__init__(period=period, oversold=oversold, overbought=overbought, **kwargs)
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
    
    def generate_signal(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(self.period).mean()
        avg_loss = loss.rolling(self.period).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        signals = pd.Series(0, index=df.index, dtype=int)
        signals[rsi < self.oversold] = 1
        signals[rsi > self.overbought] = -1
        return signals


# === 3. ML 策略 ===
class LightGBMStrategy(BaseStrategy):
    """LightGBM 预测 alpha 的 ML 策略
    
    流程:
    1. 用 features 训练 LightGBM 模型(预测未来 N 日收益)
    2. 选预测收益 Top-K 买入, Bottom-K 卖出
    """
    name = "LightGBMStrategy"
    category = "ml"
    
    def __init__(
        self,
        model,
        top_k: int = 30,
        rebalance_freq: int = 5,  # 每 5 天调仓
        **kwargs,
    ):
        super().__init__(top_k=top_k, rebalance_freq=rebalance_freq, **kwargs)
        self.model = model
        self.top_k = top_k
        self.rebalance_freq = rebalance_freq
    
    def generate_signal(self, df: pd.DataFrame, feature_cols: List[str], **kwargs) -> pd.Series:
        # 预测
        X = df[feature_cols].fillna(0)
        preds = self.model.predict(X)
        
        # 截面选股: 用 reset_index 避免索引对齐问题
        df_reset = df.reset_index(drop=True)
        df_reset["pred"] = preds
        ranks = df_reset.groupby("date")["pred"].rank(method="first", ascending=False)
        signals = pd.Series(0, index=df.index, dtype=int)
        # 用 reset_index 后的 ranks 对齐到原 index
        signals_reset = pd.Series(0, index=df_reset.index, dtype=int)
        signals_reset[ranks <= self.top_k] = 1
        counts = df_reset.groupby("date")["pred"].transform("count")
        signals_reset[ranks > counts - self.top_k] = -1
        signals[:] = signals_reset.values
        return signals


class OnlineLearningStrategy(BaseStrategy):
    """在线学习策略 — 增量更新模型
    
    工作流:
    1. 维护滑动窗口(W bars 历史)
    2. 每 N bars(retrain_freq)增量重训一次模型
    3. 模型预测 top/bottom K 股票,生成多空信号
    
    适用场景:
    - 概念漂移快(风格轮动、宏观变化)
    - 数据持续生成(分钟线 / tick)
    - 需要快速响应(实盘滚动训练)
    
    用法:
        factory = lambda: LightGBMModel(n_estimators=200, max_depth=4)
        strategy = OnlineLearningStrategy(model_factory=factory, retrain_freq=20)
        signals = strategy.generate_signal(df)  # df 含 factor 列
    """
    name = "OnlineLearningStrategy"
    category = "ml"
    
    def __init__(
        self,
        model_factory,
        retrain_freq: int = 20,
        window_size: int = 252,
        top_k: int = 20,
        bottom_k: int = 20,
        feature_cols: Optional[List[str]] = None,
        target_col: str = "fwd_ret_5",
        min_train_samples: int = 60,
        random_state: int = 42,
        **kwargs,
    ):
        super().__init__(
            retrain_freq=retrain_freq,
            window_size=window_size,
            top_k=top_k,
            bottom_k=bottom_k,
            feature_cols=feature_cols,
            target_col=target_col,
            min_train_samples=min_train_samples,
            random_state=random_state,
            **kwargs,
        )
        self.model_factory = model_factory
        self.retrain_freq = retrain_freq
        self.window_size = window_size
        self.top_k = top_k
        self.bottom_k = bottom_k
        self.feature_cols = feature_cols  # None → 自动检测(排除 OHLCV/target)
        self.target_col = target_col
        self.min_train_samples = min_train_samples
        self.random_state = random_state
        
        self.current_model = None
        self.last_train_idx = -1
        self.feature_names: List[str] = []
        self.train_history: List[Dict] = []
    
    def _auto_detect_features(self, df: pd.DataFrame) -> List[str]:
        """自动检测特征列 — 排除元数据列"""
        exclude = {
            "symbol", "ts", "date", "open", "high", "low", "close", "vwap",
            "volume", "amount", "turnover",
            self.target_col,
            "fwd_ret_1", "fwd_ret_5", "fwd_ret_10", "fwd_ret_20",
            "label",
        }
        return [c for c in df.columns if c not in exclude]
    
    def _train_model(self, train_df: pd.DataFrame, idx: int):
        """增量训练模型"""
        if self.feature_cols is None:
            self.feature_names = self._auto_detect_features(train_df)
        else:
            self.feature_names = self.feature_cols
        
        # 缺失值处理
        X = train_df[self.feature_names].fillna(0).values
        y = train_df[self.target_col].fillna(0).values
        
        # 训练
        try:
            model = self.model_factory()
            model.fit(X, y)
            self.current_model = model
            self.last_train_idx = idx
            
            # 训练指标
            if hasattr(model, "predict"):
                preds = model.predict(X)
                from sklearn.metrics import mean_squared_error
                train_mse = mean_squared_error(y, preds)
            else:
                train_mse = None
            
            self.train_history.append({
                "idx": idx,
                "n_train": len(train_df),
                "train_mse": train_mse,
                "n_features": len(self.feature_names),
            })
            return True
        except Exception as e:
            # 训练失败 — 保留上一个模型(或 None → 全零)
            self.train_history.append({
                "idx": idx,
                "error": str(e),
                "error_type": type(e).__name__,
            })
            return False
    
    def generate_signal(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        """生成信号 — 在每个再训练点训练一次,然后预测当前 bars"""
        signals = pd.Series(0, index=df.index, dtype=int)
        
        if len(df) < self.min_train_samples:
            return signals
        
        # 按时间排序(必须的,在线学习前提)
        if "date" in df.columns:
            df_sorted = df.sort_values("date").reset_index(drop=True)
        elif "ts" in df.columns:
            df_sorted = df.sort_values("ts").reset_index(drop=True)
        else:
            df_sorted = df.reset_index(drop=True)
        
        n = len(df_sorted)
        
        # 触发重训的位置
        train_positions = list(range(
            self.window_size, n, self.retrain_freq
        ))
        
        if not train_positions:
            # 数据不够长,直接在全部历史训练一次
            train_positions = [n - 1]
        
        # 信号生成:每个时间点用当时的最新模型
        signal_col = []
        for i in range(n):
            # 是否到了再训练点
            if i in train_positions or (i > 0 and i - self.last_train_idx >= self.retrain_freq):
                train_df = df_sorted.iloc[max(0, i - self.window_size):i]
                if len(train_df) >= self.min_train_samples:
                    self._train_model(train_df, i)
            
            # 当前时刻预测
            if i < self.window_size:
                signal_col.append(0)
                continue
            
            if self.current_model is None:
                signal_col.append(0)
                continue
            
            try:
                row = df_sorted.iloc[i:i + 1]
                X_row = row[self.feature_names].fillna(0).values
                pred = self.current_model.predict(X_row)
                if hasattr(pred, "__len__"):
                    pred_val = float(pred[0])
                else:
                    pred_val = float(pred)
                signal_col.append(pred_val)
            except Exception:
                signal_col.append(0)
        
        # 转成 {-1, 0, 1} 信号(基于 rank)
        df_sorted["pred"] = signal_col
        
        # 用 top_k / bottom_k
        df_sorted["signal"] = 0
        # 按 date 横截面排序
        if "date" in df_sorted.columns:
            for _, group in df_sorted.groupby("date"):
                if len(group) < self.top_k + self.bottom_k:
                    continue
                ranks = group["pred"].rank(method="first", ascending=True)
                n_grp = len(group)
                df_sorted.loc[group.index[ranks > n_grp - self.top_k], "signal"] = 1
                df_sorted.loc[group.index[ranks <= self.bottom_k], "signal"] = -1
        else:
            # 无 date 列 — 直接全期排序
            ranks = df_sorted["pred"].rank(method="first", ascending=True)
            df_sorted.loc[ranks > n - self.top_k, "signal"] = 1
            df_sorted.loc[ranks <= self.bottom_k, "signal"] = -1
        
        # 恢复原始顺序
        if "date" in df.columns:
            df_sorted["orig_idx"] = df.sort_values("date").index
        else:
            df_sorted["orig_idx"] = df.index
        signals.loc[df_sorted["orig_idx"].values] = df_sorted["signal"].values
        
        return signals.astype(int)
    
    def get_train_history(self) -> List[Dict]:
        return self.train_history.copy()


# === 4. 事件驱动 ===
class EarningsAnnouncement(BaseStrategy):
    """财报公告事件策略 — 需要基本面数据"""
    name = "EarningsAnnouncement"
    category = "event"
    
    def __init__(self, surprise_threshold: float = 0.05, **kwargs):
        super().__init__(surprise_threshold=surprise_threshold, **kwargs)
        self.surprise_threshold = surprise_threshold
    
    def generate_signal(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        # 需要 surprise_pct 列(EPS 实际 vs 一致预期)
        if "surprise_pct" not in df.columns:
            return pd.Series(0, index=df.index, dtype=int)
        
        signals = pd.Series(0, index=df.index, dtype=int)
        # 财报日 + 超预期 → 买入
        is_earnings = df.get("is_earnings_day", pd.Series(0, index=df.index))
        surprise = df["surprise_pct"]
        signals[(is_earnings == 1) & (surprise > self.surprise_threshold)] = 1
        signals[(is_earnings == 1) & (surprise < -self.surprise_threshold)] = -1
        return signals


class IndexInclusion(BaseStrategy):
    """纳入指数事件 — 短期内通常有正向超额收益"""
    name = "IndexInclusion"
    category = "event"
    
    def generate_signal(self, df: pd.DataFrame, **kwargs) -> pd.Series:
        if "index_inclusion" not in df.columns:
            return pd.Series(0, index=df.index, dtype=int)
        signals = pd.Series(0, index=df.index, dtype=int)
        signals[df["index_inclusion"] == 1] = 1
        return signals


# === 5. 资产组合 ===
class RiskParity(BaseStrategy):
    """风险平价 — 每资产贡献相同风险"""
    name = "RiskParity"
    category = "portfolio"
    
    def __init__(self, lookback: int = 60, **kwargs):
        super().__init__(lookback=lookback, **kwargs)
        self.lookback = lookback
    
    def compute_weights(self, df: pd.DataFrame) -> pd.DataFrame:
        """返回权重矩阵(date x symbol)"""
        pivot = df.pivot(index="date", columns="symbol", values="close")
        returns = pivot.pct_change()
        # vol = rolling std
        vol = returns.rolling(self.lookback).std()
        # 风险平价: weight ∝ 1/vol
        inv_vol = 1.0 / (vol + 1e-9)
        weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)
        return weights.fillna(0)


class MaxSharpe(BaseStrategy):
    """最大夏普组合"""
    name = "MaxSharpe"
    category = "portfolio"
    
    def __init__(self, lookback: int = 60, **kwargs):
        super().__init__(lookback=lookback, **kwargs)
        self.lookback = lookback
    
    def compute_weights(self, df: pd.DataFrame) -> pd.DataFrame:
        pivot = df.pivot(index="date", columns="symbol", values="close")
        returns = pivot.pct_change()
        # Mean-variance 优化(简化: 倒数波动加权)
        vol = returns.rolling(self.lookback).std()
        inv_vol = 1.0 / (vol + 1e-9)
        weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)
        return weights.fillna(0)


# === 策略工厂 ===
def list_strategies() -> Dict[str, type]:
    """列出所有策略"""
    return {
        cls.__name__: cls
        for cls in BaseStrategy.__subclasses__()
    }


def list_categories() -> Dict[str, List[str]]:
    """按类别列出策略"""
    result = {}
    for name, cls in list_strategies().items():
        cat = cls.category
        if cat not in result:
            result[cat] = []
        result[cat].append(name)
    return result