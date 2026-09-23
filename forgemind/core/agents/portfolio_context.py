# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal, Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages

from forgemind.core.config.settings import get_settings
from forgemind.core.events.types import AIDecisionEvent
from forgemind.core.observability.logging import get_logger

logger = get_logger("forgemind.agents")

settings = get_settings()


# ===== PortfolioContext(§24 L2 P0-1)=====
class PortfolioPosition(BaseModel):
    symbol: str
    quantity: int
    avg_price: float
    unrealized_pnl: float = 0.0


class PortfolioContext(BaseModel):
    """
    任何 agent 的入参 — 必须带这个,不能 hidden state
    
    这是 §24 L2 P0-1 关键修复:agent 不能再"不知道用户已经持仓"
    """
    cash: float
    currency: Literal["CNY", "USD", "HKD", "EUR"] = "CNY"
    positions: list[PortfolioPosition] = Field(default_factory=list)
    total_equity: float = 0.0
    
    # 约束
    max_position_pct: float = 0.20  # 单标的最大 20%
    max_daily_loss_pct: float = -0.05
    allowed_symbols: list[str] = Field(default_factory=list)
    
    # 用户偏好
    risk_tolerance: Literal["low", "medium", "high"] = "medium"
    investment_horizon: Literal["short", "medium", "long"] = "medium"
    
    def get_position(self, symbol: str) -> Optional[PortfolioPosition]:
        for p in self.positions:
            if p.symbol == symbol:
                return p
        return None
    
    def has_position(self, symbol: str) -> bool:
        return self.get_position(symbol) is not None


# ===== Agent State(共享给 LangGraph)=====
from typing import TypedDict


class AgentState(TypedDict, total=False):
    """LangGraph 共享状态 — TypedDict(不用 BaseModel 因为 LangGraph 1.x 要求)
    
    关键:三个 sub-agent 并行写不会冲突,因为它们写不同字段
    """
    # 不可变上下文(每个节点读,不写)
    symbol: str
    as_of: datetime
    portfolio: dict  # PortfolioContext.model_dump()
    run_id: str  # UUID as str
    
    # 累加器(messages)
    messages: Annotated[list, add_messages]
    
    # 子 agent 输出
    fundamentals_analysis: dict
    technical_analysis: dict
    news_analysis: dict
    bull_case: dict
    bear_case: dict
    
    # PM 节点写
    pm_decision: dict
    requires_human_review: bool
    confidence: float
    decision_event: dict  # AIDecisionEvent.model_dump()


# ===== Decision Log Markdown(§24 L2 P0-3)=====
DECISION_LOG_DIR = Path("./data/decision_logs")


class DecisionLog:
    """
    Decision Log — 每个 ticker / date 的决策永久 Markdown 记录
    
    下次同 ticker 跑时,agent 自动看到上轮 realized return + 反思
    """
    
    def __init__(self, log_dir: Path = DECISION_LOG_DIR):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def append(self, symbol: str, decision: dict, realized: Optional[dict] = None,
               reflection: Optional[str] = None) -> Path:
        """
        追加一条决策
        
        Markdown 格式:
        ## SYMBOL DATE
        ### Decision
        {direction, quantity, confidence, ...}
        ### Realized(回填)
        {pnl, return_pct, ...}
        ### Reflection(回填)
        {lessons, improvements, ...}
        """
        log_file = self.log_dir / f"{symbol}.md"
        
        timestamp = decision.get("timestamp", datetime.now().isoformat())
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n## {symbol} @ {timestamp}\n")
            f.write(f"### Decision\n```json\n{json.dumps(decision, indent=2, ensure_ascii=False, default=str)}\n```\n")
            if realized:
                f.write(f"### Realized\n```json\n{json.dumps(realized, indent=2, ensure_ascii=False, default=str)}\n```\n")
            if reflection:
                f.write(f"### Reflection\n{reflection}\n")
        
        logger.info(
            "decision_log_appended",
            symbol=symbol,
            file=str(log_file),
        )
        return log_file
    
    def read(self, symbol: str, limit: int = 5) -> str:
        """读最近 N 条决策"""
        log_file = self.log_dir / f"{symbol}.md"
        if not log_file.exists():
            return ""
        
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 取最近 N 个 ## SYMBOL DATE
        sections = content.split("\n## ")
        if len(sections) <= limit:
            return content
        return "\n## ".join(sections[-limit:])


# ===== 3-Agent Harness(§24 L2 P1-12 简化版)=====

def fundamentals_node(state: AgentState) -> dict:
    """基本面分析节点 — 返回增量 dict(避免 BaseModel 字段冲突)"""
    logger.info("agent_node", node="fundamentals", symbol=state.get("symbol"))
    return {
        "fundamentals_analysis": {
            "pe_ratio": 15.5,
            "roe": 0.18,
            "revenue_growth_yoy": 0.12,
            "signal": "neutral",
            "confidence": 0.7,
        }
    }


def technical_node(state: AgentState) -> dict:
    """技术面分析节点"""
    logger.info("agent_node", node="technical", symbol=state.get("symbol"))
    return {
        "technical_analysis": {
            "ma_cross": "golden",
            "rsi": 55.0,
            "macd_signal": "positive",
            "signal": "buy",
            "confidence": 0.65,
        }
    }


def news_node(state: AgentState) -> dict:
    """新闻 / 情绪分析节点"""
    logger.info("agent_node", node="news", symbol=state.get("symbol"))
    return {
        "news_analysis": {
            "sentiment": "positive",
            "key_events": ["earnings beat", "new product launch"],
            "signal": "buy",
            "confidence": 0.6,
        }
    }


def bull_node(state: AgentState) -> dict:
    """多方研究员 — 综合看多证据"""
    logger.info("agent_node", node="bull", symbol=state.get("symbol"))
    return {
        "bull_case": {
            "thesis": "基本面+技术面+新闻均偏多,可建仓",
            "target_weight": 0.10,
            "entry_trigger": "回踩 5 日均线",
            "stop_loss_pct": -0.05,
        }
    }


def bear_node(state: AgentState) -> dict:
    """空方研究员 — 综合看空证据"""
    logger.info("agent_node", node="bear", symbol=state.get("symbol"))
    return {
        "bear_case": {
            "thesis": "估值偏高 + 行业 beta 风险 + 监管不确定",
            "concerns": ["宏观流动性收紧", "行业政策风险"],
            "max_weight": 0.05,
        }
    }


def portfolio_manager_node(state: AgentState) -> dict:
    """
    PM 综合决策 — 强制 interrupt_before(人工审批 gating)
    
    §24 L2 P0-9 关键:人工审批是 gating,不是替代
    """
    symbol = state.get("symbol", "")
    portfolio_dict = state.get("portfolio", {})
    bull = state.get("bull_case", {})
    bear = state.get("bear_case", {})
    fund = state.get("fundamentals_analysis", {})
    tech = state.get("technical_analysis", {})
    news = state.get("news_analysis", {})
    
    logger.info("agent_node", node="portfolio_manager", symbol=symbol)
    
    # 综合 bull / bear
    bull_weight = bull.get("target_weight", 0) if bull else 0
    bear_max = bear.get("max_weight", 1) if bear else 1
    final_weight = min(bull_weight, bear_max)
    
    # 当前持仓
    positions = portfolio_dict.get("positions", [])
    current_position = next(
        (p for p in positions if p.get("symbol") == symbol), None
    )
    total_equity = portfolio_dict.get("total_equity", 0)
    current_weight = 0
    if current_position and total_equity > 0:
        current_weight = (
            current_position.get("quantity", 0) * current_position.get("avg_price", 0)
            / total_equity
        )
    
    delta_weight = final_weight - current_weight
    
    if abs(delta_weight) < 0.005:
        direction = "hold"
        quantity = 0
    elif delta_weight > 0:
        direction = "buy"
        pe = max(fund.get("pe_ratio", 10), 1)
        quantity = int((delta_weight * total_equity) / pe)
    else:
        direction = "sell"
        pe = max(fund.get("pe_ratio", 10), 1)
        quantity = int((abs(delta_weight) * total_equity) / pe)
    
    confidence = min(
        fund.get("confidence", 0) if fund else 0,
        tech.get("confidence", 0) if tech else 0,
        news.get("confidence", 0) if news else 0,
    )
    
    pm_decision = {
        "direction": direction,
        "quantity": quantity,
        "final_weight": final_weight,
        "current_weight": current_weight,
        "delta_weight": delta_weight,
        "confidence": confidence,
        "rationale": f"综合 bull={bull_weight:.2%} / bear={bear_max:.2%},最终权重={final_weight:.2%}",
    }
    
    decision_event = AIDecisionEvent(
        symbol=symbol,
        model_name="haiku-sonnet-opus-router",
        decision=pm_decision,
        reasoning=f"Bull: {bull.get('thesis') if bull else 'N/A'} | "
                  f"Bear: {bear.get('thesis') if bear else 'N/A'}",
        requires_human_review=True,
        confidence=confidence,
    )
    
    DecisionLog().append(
        symbol=symbol,
        decision=pm_decision,
    )
    
    return {
        "pm_decision": pm_decision,
        "requires_human_review": True,
        "confidence": confidence,
        "decision_event": decision_event.model_dump(mode="json"),
    }


def build_agent_graph(checkpointer=None):
    """构建 3-Agent LangGraph"""
    graph = StateGraph(AgentState)
    
    graph.add_node("fundamentals", fundamentals_node)
    graph.add_node("technical", technical_node)
    graph.add_node("news", news_node)
    graph.add_node("bull", bull_node)
    graph.add_node("bear", bear_node)
    graph.add_node("portfolio_manager", portfolio_manager_node)
    
    graph.add_edge(START, "fundamentals")
    graph.add_edge(START, "technical")
    graph.add_edge(START, "news")
    graph.add_edge("fundamentals", "bull")
    graph.add_edge("technical", "bull")
    graph.add_edge("news", "bull")
    graph.add_edge("fundamentals", "bear")
    graph.add_edge("technical", "bear")
    graph.add_edge("news", "bear")
    graph.add_edge("bull", "portfolio_manager")
    graph.add_edge("bear", "portfolio_manager")
    graph.add_edge("portfolio_manager", END)
    
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["portfolio_manager"],  # 强制人工审批 gating
    )
    
    logger.info("agent_graph_compiled", nodes=6)
    return compiled


_agent_graph = None


def get_agent_graph():
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_agent_graph()
    return _agent_graph


async def run_decision(
    symbol: str,
    as_of: datetime,
    portfolio: PortfolioContext,
    thread_id: str = "default",
) -> dict:
    """
    跑一次 AI 决策 — interrupt_before human_review gating
    """
    from langchain_core.runnables import RunnableConfig
    
    graph = get_agent_graph()
    config = RunnableConfig(configurable={"thread_id": thread_id})
    
    initial_state: AgentState = {
        "symbol": symbol,
        "as_of": as_of,
        "portfolio": portfolio.model_dump(mode="json"),
        "run_id": str(uuid4()),
        "messages": [],
        "requires_human_review": True,
        "confidence": 0.0,
    }
    
    logger.info("agent_run_started", symbol=symbol, thread_id=thread_id)
    
    # 关键:interrupt_before=portfolio_manager 会卡住,等待人工审批
    # 这里用 None 表示不 invoke 卡住的部分,只跑 sub-agent
    result = await graph.ainvoke(initial_state, config=config)
    
    logger.info(
        "agent_run_completed",
        symbol=symbol,
        requires_review=result.get("requires_human_review", True),
        confidence=result.get("confidence", 0),
    )
    
    return result