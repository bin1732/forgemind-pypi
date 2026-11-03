# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Annotated, Literal
from uuid import uuid4  # noqa: E402

import pandas as pd  # noqa: E402
from langgraph.checkpoint.memory import MemorySaver  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402
from langgraph.graph.message import add_messages  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from forgemind.core.config.settings import get_settings  # noqa: E402
from forgemind.core.events.types import AIDecisionEvent  # noqa: E402
from forgemind.core.observability.logging import get_logger  # noqa: E402

logger = get_logger("forgemind.agents")

settings = get_settings()


# ===== 持仓上下文 =====
class PortfolioPosition(BaseModel):
    symbol: str
    quantity: int
    avg_price: float
    unrealized_pnl: float = 0.0


class PortfolioContext(BaseModel):
    """
    任何 agent 的入参 — 必须带这个,不能 hidden state

    agent 拿到的持仓是调用方给的,不是它自己猜的:持仓是明面上的输入,
    任何 agent 都能知道自己已经持有哪些标的。
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

    def get_position(self, symbol: str) -> PortfolioPosition | None:
        for p in self.positions:
            if p.symbol == symbol:
                return p
        return None

    def has_position(self, symbol: str) -> bool:
        return self.get_position(symbol) is not None


# ===== Agent State(共享给 LangGraph)=====
from typing import TypedDict  # noqa: E402


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


# ===== 决策记录(Markdown)=====


def decision_log_dir() -> Path:
    """决策日志目录 —— 从设置里的 data_dir 派生。

    以前写死 "./data/decision_logs",是相对**当前目录**的:作为服务跑的时候
    (桌面端的 sidecar),当前目录可能是只读的安装目录,日志写不进去。
    跟着 data_dir 走,桌面端把它指到用户自己的目录就跟着走 ✓
    """
    from forgemind.core.config.settings import get_settings

    return Path(get_settings().data_dir) / "decision_logs"


class DecisionLog:
    """
    Decision Log — 每个 ticker / date 的决策永久 Markdown 记录

    下次同 ticker 跑时,agent 自动看到上轮 realized return + 反思
    """

    def __init__(self, log_dir: Path | None = None):
        self.log_dir = log_dir if log_dir is not None else decision_log_dir()
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        symbol: str,
        decision: dict,
        realized: dict | None = None,
        reflection: str | None = None,
    ) -> Path:
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
            f.write(
                f"### Decision\n```json\n{json.dumps(decision, indent=2, ensure_ascii=False, default=str)}\n```\n"
            )
            if realized:
                f.write(
                    f"### Realized\n```json\n{json.dumps(realized, indent=2, ensure_ascii=False, default=str)}\n```\n"
                )
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

        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        # 取最近 N 个 ## SYMBOL DATE
        sections = content.split("\n## ")
        if len(sections) <= limit:
            return content
        return "\n## ".join(sections[-limit:])


# ===== 三个 agent 的协同(简化版)=====


def _load_kline(symbol: str, limit: int = 250) -> pd.DataFrame | None:
    """从 DuckDB 读该标的的真实 K 线(需先跑 forgemind etl)"""
    try:
        from forgemind.core.data.storage import DuckDBStorage, bare_symbol

        with DuckDBStorage() as db:
            df = db.query_df(
                "SELECT date, open, high, low, close, volume "
                "FROM kline_daily WHERE symbol = ? ORDER BY date DESC LIMIT ?",
                [bare_symbol(symbol), int(limit)],
            )
        if df is None or len(df) < 30:
            return None
        return df.iloc[::-1].reset_index(drop=True)  # 升序
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent_kline_load_failed", symbol=symbol, error_type=type(exc).__name__)
        return None


def fundamentals_node(state: AgentState) -> dict:
    """基本面分析节点

    **不返回编造的数字。** 本项目未接入基本面数据源(PE / ROE /
    营收增速无真实来源),如实报告 `status="unavailable"` 并注明缺失字段。
    """
    logger.info("agent_node", node="fundamentals", symbol=state.get("symbol"))
    return {
        "fundamentals_analysis": {
            "status": "unavailable",
            "reason": "本项目未接入基本面数据源(PE / ROE / 营收增速均无真实来源)",
            "next_step": "接入 TushareProSource(设置 TUSHARE_TOKEN)后此处可给出真实读数",
            "signal": None,
            "confidence": 0.0,
        }
    }


def technical_node(state: AgentState) -> dict:
    """技术面分析节点 — **从真实 K 线算**

    RSI / 均线 / MACD 全部可以由 OHLCV 推出,所以这里给的是实际读数。
    实际读数,不是硬编码 ma_cross="golden" / rsi=55.0 / macd="positive"
    对任何标的都一样。
    """
    symbol = state.get("symbol", "")
    logger.info("agent_node", node="technical", symbol=symbol)
    df = _load_kline(symbol)
    if df is None:
        return {
            "technical_analysis": {
                "status": "unavailable",
                "reason": f"本地没有 {symbol} 的 K 线(少于 30 根)",
                "next_step": f"先运行 `forgemind etl --symbols {symbol}` 拉取行情",
                "signal": None,
                "confidence": 0.0,
            }
        }

    close = df["close"].astype(float)
    ma5 = float(close.rolling(5).mean().iloc[-1])
    ma20 = float(close.rolling(20).mean().iloc[-1])
    ma60 = float(close.rolling(60).mean().iloc[-1]) if len(close) >= 60 else None

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    rsi = float(100 - 100 / (1 + rs.iloc[-1])) if len(rs.dropna()) else None

    ema12 = close.ewm(span=12, adjust=False).mean().iloc[-1]
    ema26 = close.ewm(span=26, adjust=False).mean().iloc[-1]
    macd_hist = float(ema12 - ema26)

    ma_cross = "golden" if ma5 > ma20 else "dead"
    if ma60 is not None:
        ma_cross += "_uptrend" if ma5 > ma20 > ma60 else "_downtrend"
    if rsi is None:
        signal, conf = None, 0.0
    else:
        # 由真实读数定信号:趋势、RSI、MACD 三者
        votes = (ma5 > ma20, rsi < 70, macd_hist > 0)
        signal = "buy" if sum(votes) >= 2 else ("sell" if sum(votes) == 0 else "neutral")
        conf = round(0.5 + 0.15 * abs(sum(votes) - 1.5), 3)

    return {
        "technical_analysis": {
            "status": "ok",
            "n_bars": int(len(df)),
            "last_close": float(close.iloc[-1]),
            "ma5": ma5,
            "ma20": ma20,
            "ma60": ma60,
            "ma_cross": ma_cross,
            "rsi": rsi,
            "macd_hist": macd_hist,
            "signal": signal,
            "confidence": conf,
        }
    }


def news_node(state: AgentState) -> dict:
    """新闻 / 情绪分析节点

    本项目未接入新闻源,如实报告 `status="unavailable"` 并注明缺失字段。
    """
    logger.info("agent_node", node="news", symbol=state.get("symbol"))
    return {
        "news_analysis": {
            "status": "unavailable",
            "reason": "本项目未接入新闻 / 情绪数据源",
            "next_step": "接入 NewsDataSource 的真实实现后此处可给出情绪读数",
            "signal": None,
            "confidence": 0.0,
        }
    }


def _evidence(state: AgentState) -> tuple[list[str], list[str], float]:
    """从**真实**的分析结果里收集看多/看空证据,以及整体置信度

    基本面与新闻不可用时,证据只能来自技术面 —— 这本身就是结论的一部分,
    不能假装三个维度都看过。
    """
    tech = state.get("technical_analysis", {}) or {}
    bull: list[str] = []
    bear: list[str] = []
    if tech.get("status") != "ok":
        return bull, bear, 0.0

    rsi = tech.get("rsi")
    if tech.get("ma5") is not None and tech.get("ma20") is not None:
        if tech["ma5"] > tech["ma20"]:
            bull.append(f"MA5({tech['ma5']:.2f}) 上穿 MA20({tech['ma20']:.2f})")
        else:
            bear.append(f"MA5({tech['ma5']:.2f}) 位于 MA20({tech['ma20']:.2f}) 之下")
    if tech.get("ma60") is not None and tech.get("ma20") is not None:
        if tech["ma20"] > tech["ma60"]:
            bull.append("中期均线多头排列")
        else:
            bear.append("中期均线空头排列")
    if rsi is not None:
        if rsi < 30:
            bull.append(f"RSI {rsi:.1f} 超卖")
        elif rsi > 70:
            bear.append(f"RSI {rsi:.1f} 超买")
        else:
            bull.append(f"RSI {rsi:.1f} 中性区间")
    if tech.get("macd_hist") is not None:
        if tech["macd_hist"] > 0:
            bull.append(f"MACD 柱 {tech['macd_hist']:+.3f} 多头")
        else:
            bear.append(f"MACD 柱 {tech['macd_hist']:+.3f} 空头")

    # 只有一个维度可用 → 置信度必须体现这一点
    return bull, bear, float(tech.get("confidence") or 0.0) * 0.5


def bull_node(state: AgentState) -> dict:
    """多方研究员 — 论据来自**真实**技术面读数

    thesis 是基于实际读数, 不是硬编码的"基本面+技术面+新闻均偏多,可建仓"
    基本面与新闻都没有数据源。现在只讲真实读数支持的部分,并列出缺口。
    """
    logger.info("agent_node", node="bull", symbol=state.get("symbol"))
    bull, _bear, conf = _evidence(state)
    tech = state.get("technical_analysis", {}) or {}
    if tech.get("status") != "ok":
        return {
            "bull_case": {
                "thesis": f"无技术面数据({tech.get('reason', '数据不可用')}),无法给出看多论据",
                "evidence": [],
                "target_weight": 0.0,
                "entry_trigger": None,
                "stop_loss_pct": None,
                "gaps": ["technical"],
                "confidence": 0.0,
            }
        }
    gaps = ["fundamentals", "news"]
    thesis = ";".join(bull) if bull else "技术面未提供看多证据"
    return {
        "bull_case": {
            "thesis": thesis,
            "evidence": bull,
            # 证据越少,目标仓位越低 —— 一个维度不该支撑满仓
            "target_weight": round(0.10 * (0.5 if bull else 0.0) * 2, 4) or 0.02,
            "entry_trigger": f"下一交易日确认 {state.get('symbol')} 站稳 MA20",
            "stop_loss_pct": -0.05,
            "gaps": gaps,
            "confidence": round(conf, 3),
        }
    }


def bear_node(state: AgentState) -> dict:
    """空方研究员 — 论据来自**真实**技术面读数"""
    logger.info("agent_node", node="bear", symbol=state.get("symbol"))
    _bull, bear, conf = _evidence(state)
    tech = state.get("technical_analysis", {}) or {}
    if tech.get("status") != "ok":
        return {
            "bear_case": {
                "thesis": f"无技术面数据({tech.get('reason', '数据不可用')}),无法给出看空论据",
                "concerns": [],
                "max_weight": 0.0,
                "gaps": ["technical"],
                "confidence": 0.0,
            }
        }
    thesis = ";".join(bear) if bear else "技术面未提供看空证据"
    return {
        "bear_case": {
            "thesis": thesis,
            "evidence": bear,
            "concerns": bear or ["技术面无明显看空信号,但缺少基本面与新闻验证"],
            # 只有一个维度可用,风险上限相应收紧
            "max_weight": 0.05,
            "gaps": ["fundamentals", "news"],
            "confidence": round(conf, 3),
        }
    }


def persist_approved_decision(final: dict) -> dict:
    """把一次**已批准**的决策落进 DuckDB。

    落两样:
      * portfolio snapshot —— 决策当时的组合(现金、总权益、持仓)
      * portfolio_decision —— 6 个 Agent 各自的票、置信度与论据

    桌面端的"组合概览"与"多 Agent 决策"面板读的就是这两张表(经
    query_portfolio)。所以这段必须放在**共用层**:CLI 的审批与 API 的
    /approve 是同一件事,以前只有 CLI 落库,API 那条路批完了组合却不动 ——
    面板上看到的还是上一次的组合。

    失败不抛出:决策已经拍板了,落盘失败不该把它变成"决策失败"。失败
    原因随返回值带出去,由调用方如实展示。
    """
    from forgemind.core.data.storage import (
        save_portfolio_decisions,
        save_portfolio_snapshot,
    )

    portfolio = final.get("portfolio") or {}
    # state 里存的是 model_dump 后的 dict,而落盘函数要的是带属性的对象 ——
    # 还原回来,两条路(CLI 传模型、API 传 dict)都落到同一件事上。
    if isinstance(portfolio, dict):
        known = {k: v for k, v in portfolio.items() if k in PortfolioContext.model_fields}
        portfolio = PortfolioContext(**known)
    try:
        snap = save_portfolio_snapshot(portfolio)
    except Exception as exc:  # noqa: BLE001
        logger.warning("portfolio_snapshot_save_failed", exc_type=type(exc).__name__)
        return {
            "snapshot_id": None,
            "decisions_written": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }

    # 6 个 Agent 各自的票 / 置信度 / 论据
    fundamentals = final.get("fundamentals_analysis") or {}
    technical = final.get("technical_analysis") or {}
    news = final.get("news_analysis") or {}
    bull = final.get("bull_case") or {}
    bear = final.get("bear_case") or {}
    pm = final.get("pm_decision") or {}

    def _vote_from_signal(sig: dict) -> str | None:
        if not sig:
            return None
        # Technical signal ∈ {"buy", "sell", "neutral"}
        # UI 只认 buy/sell/hold,neutral 归一化到 hold
        v = sig.get("signal")
        if v == "neutral":
            return "hold"
        return v

    def _score_0_5(confidence: float | None) -> float:
        # score 0-5 = 5 × confidence (0-1)
        if confidence is None:
            return 0.0
        return round(min(5.0, max(0.0, float(confidence) * 5.0)), 2)

    def _thesis_with_fallback(*parts: str) -> str | None:
        text = " | ".join(p for p in parts if p)
        return text or None

    rows = [
        {
            # Fundamentals unavailable → vote=None (说明缺数据,不算投票)。
            # 否则按 status 推断:positive→buy / negative→sell / neutral→hold
            "agent": "Fundamentals",
            "vote": (
                None
                if (not fundamentals.get("status") or fundamentals.get("status") == "unavailable")
                else {"positive": "buy", "negative": "sell"}.get(fundamentals.get("status"), "hold")
            ),
            "score": _score_0_5(fundamentals.get("confidence")),
            "confidence": fundamentals.get("confidence"),
            "thesis": _thesis_with_fallback(
                str(fundamentals.get("status") or ""),
                str(fundamentals.get("reason") or ""),
            ),
            "evidence": str(fundamentals.get("next_step") or "") or None,
        },
        {
            "agent": "Technical",
            "vote": _vote_from_signal(technical),
            "score": _score_0_5(technical.get("confidence")),
            "confidence": technical.get("confidence"),
            "thesis": _thesis_with_fallback(
                f"MA5={technical.get('ma5'):.2f}" if technical.get("ma5") is not None else None,
                f"MA20={technical.get('ma20'):.2f}" if technical.get("ma20") is not None else None,
                f"RSI={technical.get('rsi'):.1f}" if technical.get("rsi") is not None else None,
                f"signal={technical.get('signal')}" if technical.get("signal") else None,
            ),
            "evidence": str(technical.get("reason") or "") or None,
        },
        {
            "agent": "News",
            "vote": _vote_from_signal(news),
            "score": _score_0_5(news.get("confidence")),
            "confidence": news.get("confidence"),
            "thesis": _thesis_with_fallback(
                str(news.get("status") or ""),
                str(news.get("reason") or ""),
            ),
            "evidence": str(news.get("next_step") or "") or None,
        },
        {
            # Bull 偏多 Agent:有 thesis 且 confidence > 0.5 → buy;有 thesis 但弱信号 → hold;
            # 没 thesis → None(完全没观点,不计入投票)。
            # PM 综合判定只看 5 个 agent, 容易被低估。
            "agent": "Bull",
            "vote": (
                "buy" if bull.get("confidence", 0) > 0.5 else "hold" if bull.get("thesis") else None
            ),
            "score": _score_0_5(bull.get("confidence")),
            "confidence": bull.get("confidence"),
            "thesis": str(bull.get("thesis") or "") or None,
            "evidence": "; ".join(bull.get("evidence") or []) or None,
        },
        {
            # Bear 偏空 Agent:同 Bull 推理,但方向反过来 ——
            # 有 thesis 且 confidence > 0.5 → sell;否则 hold;
            # 没 thesis → None(完全没观点,不计入投票)
            "agent": "Bear",
            "vote": (
                "sell"
                if bear.get("confidence", 0) > 0.5
                else "hold"
                if bear.get("thesis")
                else None
            ),
            "score": _score_0_5(bear.get("confidence")),
            "confidence": bear.get("confidence"),
            "thesis": str(bear.get("thesis") or "") or None,
            "evidence": "; ".join(bear.get("evidence") or []) or None,
        },
        {
            "agent": "PM",
            "vote": str(pm.get("direction") or "").lower() or None,
            "score": _score_0_5(pm.get("confidence")),
            "confidence": pm.get("confidence"),
            "thesis": str(pm.get("rationale") or "") or None,
            "evidence": f"quantity={pm.get('quantity')} final_weight={pm.get('final_weight', 0):.2%}",
        },
    ]

    try:
        written = save_portfolio_decisions(snap, rows)
    except Exception as exc:  # noqa: BLE001
        logger.warning("portfolio_decisions_save_failed", exc_type=type(exc).__name__)
        return {
            "snapshot_id": snap,
            "decisions_written": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"snapshot_id": snap, "decisions_written": written, "error": None}


def _decision_price(state: AgentState, current_position: dict | None) -> float:
    """决策用的股价 —— 真价格,拿不到就返回 0。

    优先用技术面读到的最新收盘价(那是市场真价);没有技术面时退回持仓的
    均价。两者都没有就返回 0 —— 调用方据此不给下单数量。
    """
    tech = state.get("technical_analysis", {}) or {}
    price = tech.get("last_close")
    try:
        price = float(price) if price is not None else 0.0
    except (TypeError, ValueError):
        price = 0.0
    if price > 0:
        return price
    if current_position:
        try:
            return float(current_position.get("avg_price", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def portfolio_manager_node(state: AgentState) -> dict:
    """
    PM 综合决策 — 强制 interrupt_before(人工审批 gating)

    人工审批是闸门,不是替代:不批就不落盘。
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
    current_position = next((p for p in positions if p.get("symbol") == symbol), None)
    total_equity = portfolio_dict.get("total_equity", 0)
    current_weight = 0
    if current_position and total_equity > 0:
        current_weight = (
            current_position.get("quantity", 0)
            * current_position.get("avg_price", 0)
            / total_equity
        )

    delta_weight = final_weight - current_weight

    # 下单数量 = 目标金额 / **股价**。
    #
    # 早先这里拿 PE 比率当除数(pe_ratio 缺省 10):14 万的目标金额除出来
    # 是 14000 股,而按真股价(约 1500)该卖 90 多股 —— 下单量差了一百多
    # 倍。界面上只看到一个数字,单子却离谱,所以没有任何测试盯过它。
    #
    # 没有真价格就不给数量:宁可报"没有价格",也不拿别的东西冒充股价。
    price = _decision_price(state, current_position)

    if abs(delta_weight) < 0.005:
        direction = "hold"
        quantity = 0
    elif price <= 0:
        direction = "hold"
        quantity = 0
    elif delta_weight > 0:
        direction = "buy"
        quantity = int((delta_weight * total_equity) / price)
    else:
        direction = "sell"
        quantity = int((abs(delta_weight) * total_equity) / price)

    confidence = min(
        fund.get("confidence", 0) if fund else 0,
        tech.get("confidence", 0) if tech else 0,
        news.get("confidence", 0) if news else 0,
    )

    pm_decision = {
        "direction": direction,
        "quantity": quantity,
        # 下单用的股价与算出来的股数放在一起,看的人能自己核:
        # 股数 ≈ |目标金额 - 当前市值| / 股价
        "price": price,
        "final_weight": final_weight,
        "current_weight": current_weight,
        "delta_weight": delta_weight,
        "confidence": confidence,
        "rationale": f"综合 bull={bull_weight:.2%} / bear={bear_max:.2%},最终权重={final_weight:.2%}",
    }
    if price <= 0:
        pm_decision["rationale"] += ";无真价格,不下单(数量记 0)"
        pm_decision["no_price_reason"] = "技术面无最新收盘价,持仓也没有均价"

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
    thread_id: str | None = None,
) -> dict:
    """
    跑一次 AI 决策 — interrupt_before human_review gating

    这是 graph 的"准备"阶段:sub-agent 跑完后**停在 PM 节点**,
    返回 requires_human_review=True 且 pm_decision=None。
    真正拍板要走 resume_decision(approved=True) 或 resume_decision(approved=False)。

    thread_id=None 时自动生成,避免多用户共享 "default" 互相踩。
    """
    from langchain_core.runnables import RunnableConfig

    if not thread_id:
        thread_id = f"thread-{uuid4().hex[:12]}"

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
    result = await graph.ainvoke(initial_state, config=config)
    result["thread_id"] = thread_id

    logger.info(
        "agent_run_completed",
        symbol=symbol,
        thread_id=thread_id,
        requires_review=result.get("requires_human_review", True),
        confidence=result.get("confidence", 0),
    )
    return result


async def resume_decision(
    thread_id: str,
    approved: bool,
    reviewer: str | None = None,
    notes: str | None = None,
) -> dict:
    """
    人工审批后真正落定决策

    approved=True  → graph.ainvoke(None, config) 让 PM 节点跑完,
                       返回 pm_decision 填好的终态
    approved=False → 终止,不跑 PM,记 decision_log 为 REJECTED

    thread_id 必须由 run_decision 派发;伪造的 thread_id 或没跑过准备
    阶段的 thread_id 会因 graph 没状态而失败,我们捕获后转成 404 语义。
    """
    from langchain_core.runnables import RunnableConfig

    graph = get_agent_graph()
    config = RunnableConfig(configurable={"thread_id": thread_id})
    result: dict = {
        "thread_id": thread_id,
        "approved": approved,
        "reviewer": reviewer,
        "notes": notes,
    }

    # reject 也得确认 thread 真存在 —— 否则伪造 /reject 不会报错
    state_snapshot = graph.get_state(config)
    if not state_snapshot or not getattr(state_snapshot, "values", None):
        raise LookupError(
            f"thread_id={thread_id} 找不到待审批的决策(可能没先跑 /decide,或 checkpointer 未初始化)"
        )

    if approved:
        try:
            final = await graph.ainvoke(None, config=config)
        except Exception as exc:  # noqa: BLE001
            raise LookupError(
                f"thread_id={thread_id} 找不到待审批的决策 "
                f"(可能没先跑 /decide,或 checkpointer 未初始化):{exc}"
            ) from exc
        # 必须真有人拍板了,才把 pm_decision 暴露出去
        if not final.get("pm_decision"):
            raise RuntimeError(
                f"thread_id={thread_id} resume 后 PM 节点仍未产出决策;graph 状态可能已损坏"
            )
        final["thread_id"] = thread_id
        final["approved_by"] = reviewer
        final["approval_notes"] = notes
        DecisionLog().append(
            symbol=final.get("symbol", "?"),
            decision={
                **final["pm_decision"],
                "approval_status": "APPROVED",
                "approved_by": reviewer,
                "notes": notes,
                "thread_id": thread_id,
            },
        )
        # 落库放在这里(共用层):CLI 的审批与 API 的 /approve 是同一件事。
        # 以前只有 CLI 落库,API 那条路批完了组合却不动 —— 桌面端的面板
        # 读的就是这两张表,于是看到的还是上一次的组合。
        final["persisted"] = persist_approved_decision(final)
        return final

    # 拒绝:不跑 PM,记录状态
    DecisionLog().append(
        symbol="?",
        decision={
            "approval_status": "REJECTED",
            "thread_id": thread_id,
            "rejected_by": reviewer,
            "notes": notes,
        },
    )
    return {**result, "pm_decision": None, "requires_human_review": False}
