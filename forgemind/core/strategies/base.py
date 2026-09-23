# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd
import numpy as np

from forgemind.core.events.types import SignalEvent


class Strategy(ABC):
    """
    策略基类 — 所有策略继承这个
    
    双接口:
    - generate_signals(price_df) → 向量回测
    - on_bar(bar) → 事件驱动实盘(nautilus)
    """
    
    def __init__(self, name: str = "base", parameters: Optional[dict] = None):
        self.name = name
        self.parameters = parameters or {}
        self.validate_parameters()
    
    @abstractmethod
    def validate_parameters(self) -> None:
        """校验参数 — 子类实现"""
        pass
    
    @abstractmethod
    def generate_signals(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """
        Vectorized 向量接口
        输入:price_df(date index, columns: open/high/low/close/volume)
        输出:signals_df(同 index, columns: entries/exits)
        """
        pass
    
    @abstractmethod
    def on_bar(self, bar_dict: dict) -> Optional[SignalEvent]:
        """
        Event-driven 接口 — nautilus / 实盘用
        输入:bar_dict (open/high/low/close/volume + symbol + timestamp)
        输出:SignalEvent 或 None(无信号)
        """
        pass
    
    def __repr__(self) -> str:
        return f"<Strategy name={self.name} params={self.parameters}>"


class MovingAverageCrossStrategy(Strategy):
    """经典双均线策略 — P0 示例"""
    
    def validate_parameters(self) -> None:
        if "fast_period" not in self.parameters:
            self.parameters["fast_period"] = 5
        if "slow_period" not in self.parameters:
            self.parameters["slow_period"] = 20
    
    def generate_signals(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """双均线交叉"""
        fast_p = self.parameters["fast_period"]
        slow_p = self.parameters["slow_period"]
        
        fast_ma = price_df["close"].rolling(fast_p).mean()
        slow_ma = price_df["close"].rolling(slow_p).mean()
        
        entries = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
        exits = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
        
        return pd.DataFrame({
            "entries": entries.fillna(False).astype(bool),
            "exits": exits.fillna(False).astype(bool),
        })
    
    def on_bar(self, bar_dict: dict) -> Optional[SignalEvent]:
        """实盘 — 维护滚动窗口"""
        if not hasattr(self, "_closes"):
            self._closes = []
        
        self._closes.append(bar_dict["close"])
        
        fast_p = self.parameters["fast_period"]
        slow_p = self.parameters["slow_period"]
        
        if len(self._closes) < slow_p + 1:
            return None
        
        closes = np.array(self._closes[-(slow_p + 1):])
        fast_now = closes[-fast_p:].mean()
        slow_now = closes[-slow_p:].mean()
        fast_prev = closes[-(fast_p + 1):-1].mean()
        slow_prev = closes[-(slow_p + 1):-1].mean()
        
        if fast_now > slow_now and fast_prev <= slow_prev:
            return SignalEvent(
                symbol=bar_dict.get("symbol"),
                direction="buy",
                strength=1.0,
                confidence=0.8,
                rationale=f"金叉:fast={fast_now:.2f} > slow={slow_now:.2f}",
            )
        elif fast_now < slow_now and fast_prev >= slow_prev:
            return SignalEvent(
                symbol=bar_dict.get("symbol"),
                direction="sell",
                strength=1.0,
                confidence=0.8,
                rationale=f"死叉:fast={fast_now:.2f} < slow={slow_now:.2f}",
            )
        return None