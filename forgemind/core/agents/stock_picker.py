# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from forgemind.core.observability.logging import get_logger
from forgemind.core.events.types import SignalEvent
from forgemind.core.strategies.base import Strategy
from forgemind.core.data.storage import DuckDBStorage

logger = get_logger("forgemind.stock_picker")


class StockPick(BaseModel):
    """选股结果"""
    symbol: str
    score: float  # 综合评分 0-1
    direction: str  # "buy" / "hold" / "sell"
    confidence: float  # 0-1
    rationale: str  # 自然语言解释
    factors: Dict[str, float] = Field(default_factory=dict)  # 各因子得分


class StockPickerAgent:
    """
    选股 Agent — 不需要 LLM,纯规则 + 多策略投票
    
    多策略:
    1. 动量策略(过去 20/60 日收益)
    2. 均值回归(偏离均线)
    3. 趋势跟踪(MA 交叉)
    4. 量价配合(放量上涨)
    
    综合评分 → Top N
    """
    
    def __init__(self, db: Optional[DuckDBStorage] = None):
        self.db = db or DuckDBStorage()
        self.lookbacks = [5, 20, 60]  # 多窗口
        logger.info("stock_picker_init")
    
    async def pick(
        self,
        universe: List[str],
        top_n: int = 10,
        as_of: Optional[str] = None,
    ) -> List[StockPick]:
        """
        从 universe 选 top N 个
        
        Args:
            universe: 候选股票代码列表("600519" 格式,不带交易所后缀)
            top_n: 返回 top N
            as_of: 截至日期(None = 最新)
        
        Returns:
            StockPick 列表,按 score 降序
        """
        picks = []
        
        for symbol in universe:
            pick = await self._evaluate_symbol(symbol, as_of)
            if pick:
                picks.append(pick)
        
        picks.sort(key=lambda p: p.score, reverse=True)
        top = picks[:top_n]
        
        logger.info(
            "stock_picker_complete",
            universe_size=len(universe),
            top_n=len(top),
            top_score=top[0].score if top else 0,
        )
        return top
    
    async def _evaluate_symbol(self, symbol: str, as_of: Optional[str]) -> Optional[StockPick]:
        """评估一个 symbol"""
        # 拉 K 线
        df = self._get_kline(symbol, as_of)
        if df is None or len(df) < 60:
            return None
        
        close = df["close"]
        volume = df["volume"]
        
        # === 因子 1:动量 ===
        mom_20 = (close.iloc[-1] / close.iloc[-20] - 1) if len(close) >= 20 else 0
        mom_60 = (close.iloc[-1] / close.iloc[-60] - 1) if len(close) >= 60 else 0
        momentum_score = self._normalize_score(mom_20 * 0.6 + mom_60 * 0.4)
        
        # === 因子 2:趋势(MA 交叉)===
        ma5 = close.rolling(5).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma60 = close.rolling(60).mean().iloc[-1]
        
        # 多头排列:ma5 > ma20 > ma60
        if ma5 > ma20 > ma60:
            trend_score = 0.9
        elif ma5 < ma20 < ma60:
            trend_score = 0.1  # 空头排列
        else:
            trend_score = 0.5  # 震荡
        
        # === 因子 3:量价 ===
        recent_vol = volume.iloc[-5:].mean()
        avg_vol = volume.iloc[-60:].mean()
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1
        if close.iloc[-1] > close.iloc[-5:].mean() and vol_ratio > 1.2:
            vp_score = 0.8  # 放量上涨
        elif close.iloc[-1] < close.iloc[-5:].mean() and vol_ratio > 1.2:
            vp_score = 0.2  # 放量下跌
        else:
            vp_score = 0.5
        
        # === 因子 4:波动率(低波动加分)===
        returns = close.pct_change().dropna()
        vol = returns.std()
        vol_score = max(0, 1 - vol * 10)  # 越低越好
        
        # === 因子 5:均值回归 ===
        ma20_val = close.rolling(20).mean().iloc[-1]
        z_score = (close.iloc[-1] - ma20_val) / close.rolling(20).std().iloc[-1] if close.rolling(20).std().iloc[-1] > 0 else 0
        # 适度低估 → 加分
        if -1 < z_score < 0:
            mr_score = 0.7
        elif 0 <= z_score < 1:
            mr_score = 0.5
        else:
            mr_score = 0.3
        
        # === 综合 ===
        factors = {
            "momentum": momentum_score,
            "trend": trend_score,
            "volume_price": vp_score,
            "volatility": vol_score,
            "mean_reversion": mr_score,
        }
        
        weights = {
            "momentum": 0.30,
            "trend": 0.30,
            "volume_price": 0.20,
            "volatility": 0.10,
            "mean_reversion": 0.10,
        }
        
        score = sum(factors[k] * weights[k] for k in factors)
        
        # 决策
        if score >= 0.65:
            direction = "buy"
        elif score <= 0.40:
            direction = "sell"
        else:
            direction = "hold"
        
        confidence = abs(score - 0.5) * 2  # 距 0.5 越远越确信
        
        # 自然语言解释(规则版,无 LLM)
        rationale = self._make_rationale(symbol, factors, weights, score)
        
        return StockPick(
            symbol=symbol,
            score=round(score, 3),
            direction=direction,
            confidence=round(confidence, 3),
            rationale=rationale,
            factors=factors,
        )
    
    def _normalize_score(self, value: float, scale: float = 0.05) -> float:
        """归一化到 [0, 1]"""
        # 假设 value ∈ [-0.3, 0.3] 比较合理
        normalized = 0.5 + value / (2 * scale)
        return max(0.0, min(1.0, normalized))
    
    def _make_rationale(
        self,
        symbol: str,
        factors: Dict[str, float],
        weights: Dict[str, float],
        score: float,
    ) -> str:
        """自然语言解释(规则版)"""
        sorted_factors = sorted(factors.items(), key=lambda x: x[1], reverse=True)
        top_factor = sorted_factors[0]
        bottom_factor = sorted_factors[-1]
        
        lines = [f"📊 {symbol} 综合评分 {score:.2f}"]
        lines.append(f"  ✅ 主要加分: {top_factor[0]}={top_factor[1]:.2f} (权重{weights[top_factor[0]]:.0%})")
        lines.append(f"  ⚠️  主要减分: {bottom_factor[0]}={bottom_factor[1]:.2f} (权重{weights[bottom_factor[0]]:.0%})")
        
        # 强信号
        if factors["trend"] >= 0.7:
            lines.append("  📈 多头排列,趋势向上")
        elif factors["trend"] <= 0.3:
            lines.append("  📉 空头排列,趋势向下")
        
        if factors["momentum"] >= 0.7:
            lines.append("  🚀 动量强劲,过去 20/60 日涨幅明显")
        elif factors["momentum"] <= 0.3:
            lines.append("  🐌 动量疲弱,近期下跌")
        
        if factors["volume_price"] >= 0.7:
            lines.append("  💰 放量上涨,资金流入")
        elif factors["volume_price"] <= 0.3:
            lines.append("  ⚠️  放量下跌,资金流出")
        
        return "\n".join(lines)
    
    def _get_kline(self, symbol: str, as_of: Optional[str]) -> Optional["pd.DataFrame"]:
        """从 DuckDB 拉 K 线"""
        try:
            with self.db as db:
                if as_of:
                    df = db.query_df(
                        "SELECT * FROM kline_daily WHERE symbol = ? AND date <= ? ORDER BY date DESC LIMIT 100",
                        [symbol, as_of],
                    )
                else:
                    df = db.query_df(
                        "SELECT * FROM kline_daily WHERE symbol = ? ORDER BY date DESC LIMIT 100",
                        [symbol],
                    )
                return df if not df.empty else None
        except Exception as e:
            logger.warning("kline_query_failed", symbol=symbol, error=str(e))
            return None