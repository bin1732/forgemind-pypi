# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    """事件类型枚举"""
    # 行情
    MARKET_TICK = "MARKET_TICK"
    MARKET_BAR = "MARKET_BAR"
    
    # 信号
    SIGNAL = "SIGNAL"
    
    # 订单
    ORDER_REQUEST = "ORDER_REQUEST"
    ORDER_UPDATE = "ORDER_UPDATE"
    
    # 成交
    FILL = "FILL"
    
    # 持仓
    POSITION = "POSITION"
    
    # 账户
    ACCOUNT = "ACCOUNT"
    
    # 风控
    RISK_VIOLATION = "RISK_VIOLATION"
    KILL_SWITCH = "KILL_SWITCH"
    
    # AI 决策
    AI_DECISION = "AI_DECISION"
    AI_REFLECTION = "AI_REFLECTION"
    
    # 系统
    SYSTEM_HEARTBEAT = "SYSTEM_HEARTBEAT"
    SYSTEM_ERROR = "SYSTEM_ERROR"


class BaseEvent(BaseModel):
    """事件基类 — 任何事件必须包含字段"""
    model_config = ConfigDict(
        use_enum_values=True,
    )
    
    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[UUID] = None
    symbol: Optional[str] = None
    strategy_id: Optional[UUID] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketTickEvent(BaseEvent):
    event_type: EventType = EventType.MARKET_TICK
    bid: float
    ask: float
    last: float
    volume: int
    bid_size: int = 0
    ask_size: int = 0


class MarketBarEvent(BaseEvent):
    event_type: EventType = EventType.MARKET_BAR
    timeframe: str = "1d"  # 1m / 5m / 1h / 1d
    open: float
    high: float
    low: float
    close: float
    volume: int


class SignalEvent(BaseEvent):
    event_type: EventType = EventType.SIGNAL
    direction: str  # "buy" / "sell" / "hold"
    strength: float  # 0.0 - 1.0
    confidence: float  # 0.0 - 1.0
    features: dict[str, float] = Field(default_factory=dict)
    rationale: str = ""


class OrderRequestEvent(BaseEvent):
    event_type: EventType = EventType.ORDER_REQUEST
    side: str  # "buy" / "sell"
    quantity: int
    order_type: str = "MARKET"  # MARKET / LIMIT / STOP
    price: Optional[float] = None
    time_in_force: str = "DAY"  # DAY / GTC / IOC / FOK
    client_order_id: str = Field(default_factory=lambda: str(uuid4()))


class OrderUpdateEvent(BaseEvent):
    event_type: EventType = EventType.ORDER_UPDATE
    client_order_id: str
    broker_order_id: Optional[str] = None
    status: str  # PENDING / SUBMITTED / FILLED / PARTIAL / CANCELLED / REJECTED
    filled_quantity: int = 0
    filled_price: Optional[float] = None
    reject_reason: Optional[str] = None


class FillEvent(BaseEvent):
    event_type: EventType = EventType.FILL
    client_order_id: str
    broker_order_id: str
    side: str
    quantity: int
    price: float
    commission: float = 0.0
    slippage_bps: float = 0.0
    is_virtual: bool = False  # 影子 / 回测标识


class PositionEvent(BaseEvent):
    event_type: EventType = EventType.POSITION
    symbol: str
    quantity: int
    avg_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


class AccountEvent(BaseEvent):
    event_type: EventType = EventType.ACCOUNT
    cash: float
    equity: float
    buying_power: float
    margin_used: float = 0.0


class RiskViolationEvent(BaseEvent):
    event_type: EventType = EventType.RISK_VIOLATION
    rule_name: str
    severity: str  # "WARNING" / "BLOCK"
    details: dict[str, Any] = Field(default_factory=dict)


class AIDecisionEvent(BaseEvent):
    event_type: EventType = EventType.AI_DECISION
    model_name: str  # "haiku" / "sonnet" / "opus" / "qwen-max"
    decision: dict[str, Any]  # agent 输出的结构化决策
    reasoning: str  # 推理过程
    requires_human_review: bool = True
    confidence: float = 0.0