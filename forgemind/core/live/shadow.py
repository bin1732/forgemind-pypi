# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import asyncio
from datetime import datetime
from typing import Optional, Callable, Awaitable
from uuid import UUID, uuid4

from forgemind.core.events.types import (
    BaseEvent, MarketTickEvent, FillEvent, OrderRequestEvent,
    SignalEvent,
)
from forgemind.core.strategies.base import Strategy
from forgemind.core.observability.logging import get_logger

logger = get_logger("forgemind.shadow_trader")


class VirtualMatchingEngine:
    """虚拟撮合 — 模拟成交"""
    
    def __init__(
        self,
        slippage_bps: float = 1.0,
        commission_bps: float = 1.5,
        fill_ratio: float = 0.95,
    ):
        self.slippage_bps = slippage_bps
        self.commission_bps = commission_bps
        self.fill_ratio = fill_ratio
    
    async def simulate_fill(
        self, order: OrderRequestEvent, tick: MarketTickEvent,
    ) -> FillEvent:
        """模拟一笔成交"""
        import random
        
        # 决定成交价(tick 价 + 滑点)
        if order.side == "buy":
            fill_price = tick.ask * (1 + self.slippage_bps / 10000)
        else:
            fill_price = tick.bid * (1 - self.slippage_bps / 10000)
        
        # 决定成交量
        if random.random() > self.fill_ratio:
            fill_qty = 0  # 未成交
        else:
            fill_qty = order.quantity
        
        commission = fill_qty * fill_price * (self.commission_bps / 10000)
        
        return FillEvent(
            event_id=uuid4(),
            event_type="FILL",
            timestamp=datetime.now(),
            session_id=order.session_id,
            symbol=order.symbol,
            client_order_id=order.client_order_id,
            broker_order_id=f"SHADOW-{uuid4().hex[:8]}",
            side=order.side,
            quantity=fill_qty,
            price=fill_price,
            commission=commission,
            is_virtual=True,  # 关键:标记为虚拟
            metadata={"shadow": True},
        )


class ShadowTrader:
    """
    影子交易器
    
    用法:
        shadow = ShadowTrader(strategy, broker)
        await shadow.start()
    """
    
    def __init__(
        self,
        strategy: Strategy,
        market_data_source: Callable[[str], Awaitable],
        shadow_id: Optional[UUID] = None,
        initial_capital: float = 1_000_000.0,
    ):
        self.strategy = strategy
        self.market_data_source = market_data_source
        self.shadow_id = shadow_id or uuid4()
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: dict[str, dict] = {}  # symbol → {qty, avg_price}
        self.matching = VirtualMatchingEngine()
        self.running = False
        self.total_trades = 0
        self.total_pnl = 0.0
    
    async def start(self, symbol: str):
        """启动影子 — 订阅一个 symbol"""
        self.running = True
        logger.info(
            "shadow_started",
            shadow_id=str(self.shadow_id),
            strategy=self.strategy.name,
            symbol=symbol,
            capital=self.initial_capital,
        )
        
        async for tick in self.market_data_source(symbol):
            if not self.running:
                break
            await self._on_tick(tick)
    
    async def stop(self):
        self.running = False
        logger.info(
            "shadow_stopped",
            shadow_id=str(self.shadow_id),
            total_pnl=self.total_pnl,
            total_trades=self.total_trades,
        )
    
    async def _on_tick(self, tick: MarketTickEvent):
        """处理 tick"""
        bar_dict = {
            "symbol": tick.symbol,
            "open": tick.last,
            "high": tick.last,
            "low": tick.last,
            "close": tick.last,
            "volume": tick.volume,
        }
        signal = await self._safe_on_bar(bar_dict)
        if signal and signal.direction != "hold":
            await self._execute_signal(signal, tick)
    
    async def _safe_on_bar(self, bar_dict: dict) -> Optional[SignalEvent]:
        """安全 on_bar(避免策略抛错炸整个 shadow)"""
        try:
            return self.strategy.on_bar(bar_dict)
        except Exception as e:
            logger.warning(
                "shadow_strategy_error",
                error=str(e),
                symbol=bar_dict.get("symbol"),
            )
            return None
    
    async def _execute_signal(self, signal: SignalEvent, tick: MarketTickEvent):
        """执行信号 — 模拟下单"""
        position = self.positions.get(signal.symbol, {"qty": 0, "avg_price": 0.0})
        
        if signal.direction == "buy":
            order_qty = signal.strength * 100  # 简化
        elif signal.direction == "sell":
            order_qty = -position["qty"]  # 平仓
        else:
            return
        
        if order_qty == 0:
            return
        
        order = OrderRequestEvent(
            symbol=signal.symbol,
            side="buy" if order_qty > 0 else "sell",
            quantity=abs(int(order_qty)),
            order_type="MARKET",
        )
        
        fill = await self.matching.simulate_fill(order, tick)
        if fill.quantity == 0:
            return
        
        # 更新持仓 + PnL
        if fill.side == "buy":
            new_qty = position["qty"] + fill.quantity
            new_avg = (
                (position["qty"] * position["avg_price"] + fill.quantity * fill.price)
                / new_qty if new_qty > 0 else 0
            )
            self.positions[signal.symbol] = {"qty": new_qty, "avg_price": new_avg}
        else:
            # sell — 实现 PnL
            pnl = (fill.price - position["avg_price"]) * fill.quantity - fill.commission
            self.total_pnl += pnl
            self.current_capital += pnl
            self.total_trades += 1
            position["qty"] -= fill.quantity
            if position["qty"] == 0:
                position["avg_price"] = 0.0
        
        logger.info(
            "shadow_fill",
            shadow_id=str(self.shadow_id),
            symbol=fill.symbol,
            side=fill.side,
            qty=fill.quantity,
            price=fill.price,
            pnl=self.total_pnl,
        )
    
    def get_metrics(self) -> dict:
        """获取影子指标"""
        return {
            "shadow_id": str(self.shadow_id),
            "total_pnl": self.total_pnl,
            "total_trades": self.total_trades,
            "current_capital": self.current_capital,
            "positions": self.positions.copy(),
        }


class PromotionGate:
    """
    Promotion Gate — 影子 → 实盘的晋级门控 (§28 §2.2)
    """
    
    def __init__(
        self,
        min_days: int = 14,
        min_sharpe: float = 1.5,
        max_drawdown: float = -0.10,
        min_win_rate: float = 0.55,
        max_backtest_diff_pct: float = 5.0,
    ):
        self.min_days = min_days
        self.min_sharpe = min_sharpe
        self.max_drawdown = max_drawdown
        self.min_win_rate = min_win_rate
        self.max_backtest_diff_pct = max_backtest_diff_pct
    
    async def evaluate(
        self,
        shadow_metrics: dict,
        backtest_metrics: dict,
    ) -> dict:
        """
        评估影子交易是否可晋级到实盘
        
        Returns:
            {"passed": bool, "reason": str, "metrics": dict}
        """
        days = shadow_metrics.get("days_running", 0)
        if days < self.min_days:
            return {"passed": False, "reason": f"影子天数不足 {days} < {self.min_days}"}
        
        sharpe = shadow_metrics.get("sharpe", 0)
        if sharpe < self.min_sharpe:
            return {"passed": False, "reason": f"Sharpe 太低 {sharpe:.2f} < {self.min_sharpe}"}
        
        max_dd = shadow_metrics.get("max_drawdown", 0)
        if max_dd < self.max_drawdown:
            return {"passed": False, "reason": f"回撤过大 {max_dd:.2%} < {self.max_drawdown:.2%}"}
        
        win_rate = shadow_metrics.get("win_rate", 0)
        if win_rate < self.min_win_rate:
            return {"passed": False, "reason": f"胜率太低 {win_rate:.2%} < {self.min_win_rate:.2%}"}
        
        # 影子 vs 回测 差异
        shadow_pnl = shadow_metrics.get("total_pnl", 0)
        bt_pnl = backtest_metrics.get("total_pnl", 1)
        diff_pct = abs(shadow_pnl - bt_pnl) / abs(bt_pnl) * 100 if bt_pnl != 0 else 0
        if diff_pct > self.max_backtest_diff_pct:
            return {"passed": False, "reason": f"影子 vs 回测 差异 {diff_pct:.1f}% > {self.max_backtest_diff_pct}%"}
        
        return {
            "passed": True,
            "reason": "All thresholds met",
            "metrics": {
                "days": days,
                "sharpe": sharpe,
                "max_drawdown": max_dd,
                "win_rate": win_rate,
                "diff_pct": diff_pct,
            },
        }