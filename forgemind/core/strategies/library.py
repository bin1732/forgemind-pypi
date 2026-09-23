# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from typing import Optional
import pandas as pd
import numpy as np

from forgemind.core.strategies.base import Strategy, MovingAverageCrossStrategy
from forgemind.core.events.types import SignalEvent


class MeanReversionStrategy(Strategy):
    """均值回归 — 价格偏离 N 日均线超过阈值时反向"""
    
    def validate_parameters(self) -> None:
        if "lookback" not in self.parameters:
            self.parameters["lookback"] = 20
        if "threshold" not in self.parameters:
            self.parameters["threshold"] = 2.0  # 2 个标准差
    
    def generate_signals(self, price_df: pd.DataFrame) -> pd.DataFrame:
        lookback = self.parameters["lookback"]
        threshold = self.parameters["threshold"]
        
        ma = price_df["close"].rolling(lookback).mean()
        std = price_df["close"].rolling(lookback).std()
        z_score = (price_df["close"] - ma) / std
        
        # Z-score > threshold → 价格过高 → sell
        # Z-score < -threshold → 价格过低 → buy
        entries = z_score < -threshold
        exits = z_score > threshold
        
        return pd.DataFrame({
            "entries": entries.fillna(False).astype(bool),
            "exits": exits.fillna(False).astype(bool),
        })
    
    def on_bar(self, bar_dict: dict) -> Optional[SignalEvent]:
        if not hasattr(self, "_prices"):
            self._prices = []
        self._prices.append(bar_dict["close"])
        
        lookback = self.parameters["lookback"]
        threshold = self.parameters["threshold"]
        
        if len(self._prices) < lookback:
            return None
        
        prices = np.array(self._prices[-lookback:])
        ma = prices.mean()
        std = prices.std()
        z_score = (bar_dict["close"] - ma) / std if std > 0 else 0
        
        if z_score < -threshold:
            return SignalEvent(
                symbol=bar_dict.get("symbol"),
                direction="buy",
                strength=min(1.0, abs(z_score) / 4.0),
                confidence=0.7,
                rationale=f"均值回归 Z={z_score:.2f} < -{threshold}",
            )
        elif z_score > threshold:
            return SignalEvent(
                symbol=bar_dict.get("symbol"),
                direction="sell",
                strength=min(1.0, abs(z_score) / 4.0),
                confidence=0.7,
                rationale=f"均值回归 Z={z_score:.2f} > {threshold}",
            )
        return None


class MomentumStrategy(Strategy):
    """动量 — 过去 N 日收益率为正则买入"""
    
    def validate_parameters(self) -> None:
        if "lookback" not in self.parameters:
            self.parameters["lookback"] = 60
        if "top_quantile" not in self.parameters:
            self.parameters["top_quantile"] = 0.7  # 涨幅超过 70% 才入场
    
    def generate_signals(self, price_df: pd.DataFrame) -> pd.DataFrame:
        lookback = self.parameters["lookback"]
        
        # N 日收益率
        returns = price_df["close"].pct_change(lookback)
        # 用 1 年滚动分位数确定阈值
        rolling_threshold = returns.rolling(252, min_periods=60).quantile(self.parameters["top_quantile"])
        
        entries = returns > rolling_threshold
        exits = returns < 0  # 收益为正 → 出场
        
        return pd.DataFrame({
            "entries": entries.fillna(False).astype(bool),
            "exits": exits.fillna(False).astype(bool),
        })
    
    def on_bar(self, bar_dict: dict) -> Optional[SignalEvent]:
        if not hasattr(self, "_prices"):
            self._prices = []
        self._prices.append(bar_dict["close"])
        
        lookback = self.parameters["lookback"]
        if len(self._prices) < lookback + 252:
            return None
        
        recent_return = (bar_dict["close"] - self._prices[-lookback]) / self._prices[-lookback]
        # 简化:固定阈值 5%
        if recent_return > 0.05:
            return SignalEvent(
                symbol=bar_dict.get("symbol"),
                direction="buy",
                strength=min(1.0, recent_return * 10),
                confidence=0.6,
                rationale=f"动量收益={recent_return:.2%}",
            )
        return None


class BollingerBandsStrategy(Strategy):
    """布林带策略 — 价格触及上下轨时反向"""
    
    def validate_parameters(self) -> None:
        if "period" not in self.parameters:
            self.parameters["period"] = 20
        if "std_multiplier" not in self.parameters:
            self.parameters["std_multiplier"] = 2.0
    
    def generate_signals(self, price_df: pd.DataFrame) -> pd.DataFrame:
        period = self.parameters["period"]
        std_mult = self.parameters["std_multiplier"]
        
        ma = price_df["close"].rolling(period).mean()
        std = price_df["close"].rolling(period).std()
        upper = ma + std_mult * std
        lower = ma - std_mult * std
        
        # 触及下轨 → 买入(预期反弹)
        entries = price_df["close"] <= lower
        # 触及中轨或上轨 → 卖出
        exits = price_df["close"] >= ma
        
        return pd.DataFrame({
            "entries": entries.fillna(False).astype(bool),
            "exits": exits.fillna(False).astype(bool),
        })
    
    def on_bar(self, bar_dict: dict) -> Optional[SignalEvent]:
        if not hasattr(self, "_prices"):
            self._prices = []
        self._prices.append(bar_dict["close"])
        
        period = self.parameters["period"]
        std_mult = self.parameters["std_multiplier"]
        
        if len(self._prices) < period:
            return None
        
        prices = np.array(self._prices[-period:])
        ma = prices.mean()
        std = prices.std()
        lower = ma - std_mult * std
        upper = ma + std_mult * std
        
        if bar_dict["close"] <= lower:
            return SignalEvent(
                symbol=bar_dict.get("symbol"),
                direction="buy",
                strength=0.8,
                confidence=0.7,
                rationale=f"触及布林下轨 {lower:.2f}",
            )
        elif bar_dict["close"] >= upper:
            return SignalEvent(
                symbol=bar_dict.get("symbol"),
                direction="sell",
                strength=0.8,
                confidence=0.7,
                rationale=f"触及布林上轨 {upper:.2f}",
            )
        return None


class BuyAndHoldStrategy(Strategy):
    """买入持有 — 基准策略,用于对比"""
    
    def validate_parameters(self) -> None:
        pass
    
    def generate_signals(self, price_df: pd.DataFrame) -> pd.DataFrame:
        entries = pd.Series(False, index=price_df.index)
        exits = pd.Series(False, index=price_df.index)
        # 第一天买入,最后一天卖出
        if len(price_df) > 0:
            entries.iloc[0] = True
            exits.iloc[-1] = True
        return pd.DataFrame({"entries": entries, "exits": exits})
    
    def on_bar(self, bar_dict: dict) -> Optional[SignalEvent]:
        if not hasattr(self, "_bought"):
            self._bought = False
        
        if not self._bought:
            self._bought = True
            return SignalEvent(
                symbol=bar_dict.get("symbol"),
                direction="buy",
                strength=1.0,
                confidence=1.0,
                rationale="买入持有",
            )
        return None


# 策略注册表
STRATEGY_REGISTRY = {
    "ma_cross": MovingAverageCrossStrategy,
    "mean_reversion": MeanReversionStrategy,
    "momentum": MomentumStrategy,
    "bollinger": BollingerBandsStrategy,
    "buy_hold": BuyAndHoldStrategy,
}


def get_strategy_class(name: str) -> type:
    """按名取策略类"""
    if name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(STRATEGY_REGISTRY.keys())}")
    return STRATEGY_REGISTRY[name]