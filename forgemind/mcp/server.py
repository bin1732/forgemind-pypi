# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
ForgeMind MCP Server — Anthropic Model Context Protocol 官方实现

对齐:Claude Desktop / Cursor / Open Code / Zed / Continue

⚠️ **定位:研究层 Agent 框架,不替用户下单**
GitHub 头部 Agent(Vibe-Trading / OpenBB / TradingAgents / RD-Agent / FinRL / Qlib)
都只输出**交易信号 JSON**,下单交给用户。Agent 框架不和券商耦合。

支持:
- 资源(Resources)、工具(Tools)、提示(Prompts)三大原语
  清单以 tools/list、resources/list、prompts/list 的返回为准 ——
  在这里抄一份名字,只会抄到某个时刻的快照,过一阵子就成了过期说法。

启动:python -m forgemind.mcp.server
"""

import asyncio  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
from collections.abc import Callable  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Any  # noqa: E402

from forgemind.core.data.storage import (  # noqa: E402
    bare_symbol,
    market_data_unavailable_reason,
    market_data_unreadable_reason,
)
from forgemind.core.observability.logging import get_logger  # noqa: E402


def _version() -> str:
    """版本单一真源,避免与 pyproject / __init__ 脱节"""
    try:
        from forgemind import __version__

        return __version__
    except Exception:  # pragma: no cover
        return "unknown"


logger = get_logger("forgemind.mcp")


# ===== 因子元数据辅助 =====
def _infer_factor_category(name: str) -> str:
    """根据因子名推断类别"""
    name_lower = name.lower()
    if any(k in name_lower for k in ["roc", "return", "corr", "rank"]):
        return "momentum"
    if any(k in name_lower for k in ["rev", "mean", "sma"]):
        return "mean_reversion"
    if any(k in name_lower for k in ["kdj", "rsi", "boll", "macd"]):
        return "technical"
    if any(k in name_lower for k in ["size", "beta", "book", "roe", "eps"]):
        return "fundamental"
    return "price_volume"


def _get_factor_formula(name: str) -> str:
    """返回因子计算公式描述"""
    formula_map = {
        "ROC_20_20": "close / close.shift(20) - 1",
        "MA_5": "close.rolling_mean(5)",
        "MA_10": "close.rolling_mean(10)",
        "MA_20": "close.rolling_mean(20)",
        "RSI_14": "1 - 1 / (1 + rs) where rs = avg_gain / avg_loss over 14 periods",
        "BOLL_20_2": "close > close.rolling_mean(20) + 2 * close.rolling_std(20)",
    }
    return formula_map.get(name, f"Polars expression for {name} (see forgemind/core/factors/)")


# ===== MCP 协议基础(不依赖官方 mcp 库,自己实现 stdio)=====


@dataclass
class MCPTool:
    """MCP Tool 定义"""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPResource:
    """MCP Resource"""

    uri: str  # e.g. "forgemind://features/momentum_20d"
    name: str
    description: str
    mime_type: str = "application/json"
    content: Any = None  # 静态内容(字符串或 dict)


@dataclass
class MCPPrompt:
    """MCP Prompt 模板"""

    name: str
    description: str
    template: str
    arguments: list[dict] = field(default_factory=list)


def _render_prompt(template: str, arguments: dict) -> tuple[str, list[str]]:
    """把 arguments 填进模板,返回 (渲染结果, 缺失的占位符列表)

    不用 str.format:模板里任何一个没提供的占位符都会让整个调用抛
    KeyError。这里逐个替换,缺失的原样保留并如实上报。
    """
    import re as _re

    missing: list[str] = []

    def _sub(m):
        key = m.group(1)
        if key in arguments:
            return str(arguments[key])
        if key not in missing:
            missing.append(key)
        return m.group(0)

    return _re.sub(r"\{(\w+)\}", _sub, template), missing


def _json_safe(value: Any) -> Any:
    """把 NaN / Inf 换成 None —— JSON 里没有这两个东西。

    Python 的 json.dumps 默认把 NaN 写成 NaN(不合 JSON 规范),Python 自己
    的 json.loads 还能读回去,JavaScript 的 JSON.parse 却直接抛错。pandas
    从带 NULL 的列里取出来的空值就是 NaN,于是工具结果到了桌面端就
    解析不了 —— 明明数据是好的,界面上却写着"取数失败"。

    这里在序列化前统一清一遍,所有工具的输出都受管,不用指望每个取数
    函数都记得自己处理空值。
    """
    if isinstance(value, float):
        return None if (math.isnan(value) or math.isinf(value)) else value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _dumps(value: Any) -> str:
    """工具与资源的 JSON 序列化入口 —— 一律先清 NaN。"""
    return json.dumps(_json_safe(value), ensure_ascii=False, default=str)


def _template_arguments(template: str) -> list[dict]:
    """从模板占位符推出参数声明。

    MCP 规范里 prompts/list 要带上 arguments,客户端就是从那里知道
    该给这条提示词传什么参数的。参数直接从模板占位符推导,声明与
    模板就不会走偏。
    """
    import re as _re

    names: list[str] = []
    for name in _re.findall(r"\{(\w+)\}", template):
        if name not in names:
            names.append(name)
    return [
        {"name": name, "description": f"模板占位符 {{{name}}}", "required": True} for name in names
    ]


def _tool_execution_failed(req_id: Any, tool_name: str, exc: BaseException) -> dict[str, Any]:
    """工具执行失败:在 result 里回 isError,而不是抛协议层错误。

    MCP 规范把失败分成两条通道:调用本身不合法(未知工具、参数非法)
    走 JSON-RPC 错误;工具跑了但工作失败(取数失败、无数据、上游报错)
    必须放进 result 并标 isError,host 才会把它回灌给模型,由模型自己
    调整参数重试。抛成协议错误的话,模型看不到失败原因,对话就断在
    那儿了。
    """
    # 异常类型名不进正文:它是内部实现。失败原因要留给模型(它要据此
    # 调整参数重试),但不该让它以为是服务端坏了。
    detail = str(exc).strip() or "没有更多细节"
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": f"工具 '{tool_name}' 执行失败:{detail}",
                }
            ],
            "isError": True,
        },
    }


class ForgeMindMCPServer:
    """
    ForgeMind MCP Server

    对齐 Anthropic MCP 规范(2025):
    - JSON-RPC 2.0 over stdio(HTTP 那条路径由 API 的 /mcp/* 端点承载)
    - resources / tools / prompts 三大原语
    """

    def __init__(self):
        self.tools: dict[str, MCPTool] = {}
        self.resources: dict[str, MCPResource] = {}
        self.prompts: dict[str, MCPPrompt] = {}
        self.handlers: dict[str, Callable] = {}
        self._tool_required: dict[str, list] = {}
        self._register_all()
        logger.info(
            "mcp_server_init",
            tools=len(self.tools),
            resources=len(self.resources),
            prompts=len(self.prompts),
        )

    def _register_all(self):
        """注册所有 tools / resources / prompts"""
        # === Tools ===
        self._tool(
            "search_features",
            "搜索特征(按名/标签)",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "tags": {"type": "object", "description": "可选标签过滤"},
                },
                "required": ["query"],
            },
            self._tool_search_features,
        )
        self._tool(
            "get_feature",
            "取特征定义(按名 + 版本)",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "version": {"type": "integer", "default": None},
                },
                "required": ["name"],
            },
            self._tool_get_feature,
        )
        self._tool(
            "trace_feature_usage",
            "追一个 feature 被哪些 model / strategy 用过",
            {
                "type": "object",
                "properties": {
                    "feature_id": {"type": "string"},
                },
                "required": ["feature_id"],
            },
            self._tool_trace_feature_usage,
        )
        self._tool(
            "run_backtest",
            "跑一个回测",
            {
                "type": "object",
                "properties": {
                    "strategy": {
                        "type": "string",
                        "description": "策略名(ma_cross / momentum / bollinger / mean_reversion)",
                    },
                    "symbol": {"type": "string"},
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "params": {"type": "object"},
                },
                "required": ["strategy", "symbol", "start", "end"],
            },
            self._tool_run_backtest,
        )
        self._tool(
            "output_signal",
            "输出交易信号 JSON(不替用户下单 — Agent 框架定位是研究层,执行交给用户)",
            {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码"},
                    "side": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
                    "confidence": {"type": "number", "description": "0-1 置信度"},
                    "rationale": {"type": "string", "description": "自然语言决策理由"},
                },
                "required": ["symbol", "side", "confidence", "rationale"],
            },
            self._tool_output_signal,
        )
        self._tool(
            "check_ic_decay",
            "检查特征 IC 衰减(回退预警)",
            {
                "type": "object",
                "properties": {
                    "feature_name": {"type": "string"},
                    "window_days": {"type": "integer", "default": 30},
                },
                "required": ["feature_name"],
            },
            self._tool_check_ic_decay,
        )
        self._tool(
            "list_factor_ic",
            "批量算因子 IC/ICIR (按 symbol + window)",
            {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "default": "600519"},
                    "window_days": {"type": "integer", "default": 5},
                },
                "required": [],
            },
            self._tool_list_factor_ic,
        )
        self._tool(
            "get_kline",
            "历史 K 线 — 读 DuckDB 中 `forgemind etl` 落盘的真实数据",
            {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "6 位代码,如 600519(不带交易所后缀)",
                    },
                    "start": {"type": "string", "description": "起始日 YYYY-MM-DD"},
                    "end": {"type": "string", "description": "截止日 YYYY-MM-DD"},
                    "limit": {"type": "integer", "default": 250},
                },
                "required": ["symbol"],
            },
            self._tool_get_kline,
        )
        self._tool(
            "query_portfolio",
            "查当前组合",
            {
                "type": "object",
                "properties": {},
            },
            self._tool_query_portfolio,
        )
        self._tool(
            "agent_decide",
            "AI 决策准备 — 3-Agent 取证后停在人工审批前,返回 thread_id",
            {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "标的代码,如 600519.SH"},
                    "cash": {"type": "number", "default": 100000},
                    "total_equity": {"type": "number", "default": 0},
                    "positions": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "当前持仓,如 {symbol, quantity, avg_price}",
                    },
                },
                "required": ["symbol"],
            },
            self._tool_agent_decide,
        )
        self._tool(
            "agent_approve",
            "人工审批 — 按决策准备阶段返回的 thread id 拍板;approved=True 让 PM 节点跑完并落库",
            {
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string"},
                    "approved": {"type": "boolean", "default": True},
                    "reviewer": {"type": "string"},
                },
                "required": ["thread_id"],
            },
            self._tool_agent_approve,
        )

        self._tool(
            "stock_pick",
            "选股 — Top N 推荐",
            {
                "type": "object",
                "properties": {
                    "universe": {"type": "array", "items": {"type": "string"}},
                    "top_n": {"type": "integer", "default": 5},
                },
                "required": ["universe"],
            },
            self._tool_stock_pick,
        )

        # === Resources ===
        # 里面写"166 因子 (Alpha158 149 + Alpha101 11 + Barra 6)",而真实
        # 数字是 169 = 152 + 11 + 6。桌面端 factor-grid 面板原本要接的
        # 正是这个 resource,拿到的是一份过期摘要。
        # 现在全部从注册表派生 —— 结构上不可能再漂移。
        self._resource(
            "forgemind://features",
            "All Features",
            "All registered factor definitions, derived from the live registry",
            content=self._feature_catalog(),
        )
        self._resource(
            "forgemind://strategies",
            "Available Strategies",
            "All registered strategies, derived from the live registry. "
            "Each entry says whether the command line can run it "
            "(cli_runnable) and, when it cannot, why (unusable_reason).",
            content=self._strategy_catalog(),
        )
        # === 当前 DuckDB 已 ETL 过的真实标的列表 ===
        # 桌面 header <select> 用这个派生候选标的
        self._resource(
            "forgemind://symbols",
            "ETL'd Symbols",
            "Distinct symbols that have at least one bar in kline_daily",
            content=self._symbol_catalog,  # callable, 每次读 DuckDB 实时算
        )
        # === 真信号历史 ===
        # 桌面 signal-table 拉这个,不再用 store 默认 []
        self._resource(
            "forgemind://signals",
            "Recent Signals",
            "Most recent N signals emitted via output_signal / forgemind signal",
            content=self._signal_catalog,  # callable, 每次读 DuckDB 实时算
        )
        self._resource(
            "forgemind://brokers",
            "Connected Brokers",
            "Currently connected brokers — ForgeMind 主框架是研究层(0 broker),用户执行用 vnpy/nautilus_trader",
            content={
                "main_framework_brokers": 0,
                "note": "用户自接 vnpy / nautilus_trader / 自己 broker SDK",
            },
        )
        self._resource(
            "forgemind://portfolio",
            "Current Portfolio",
            "Live portfolio state (来自 shadow trader 或用户接入的执行层)",
            content={
                "status": "research_layer",
                "shadow_trader_supported": True,
            },
        )

        # === Prompts ===
        self._prompt(
            "stock_analysis",
            "股票分析模板",
            """分析 {symbol} 当前投资价值。

按以下步骤:
1. 用 get_feature 查询 PE / ROE / 增长因子
2. 用 query_portfolio 看当前持仓
3. 用 run_backtest 测试 momentum / bollinger 策略
4. 综合分析后给出建议(buy/hold/sell)
5. 用自然语言解释为什么
""",
        )
        self._prompt(
            "risk_check",
            "风控检查模板",
            """对当前组合做风控检查:

1. 用 query_portfolio 获取全部持仓
2. 检查单标的集中度(任何 > 20%?)
3. 检查行业集中度
4. 检查 PnL 波动
5. 用 check_ic_decay 看最近用的因子是否失效
6. 给出风险等级(低/中/高)+ 建议
""",
        )
        self._prompt(
            "factor_research",
            "因子研究模板",
            """研究新因子 {feature_name}:

1. 用 search_features 看是否已存在类似因子
2. 用 get_feature 看计算逻辑
3. 用 trace_feature_usage 看已有用法
4. 用 check_ic_decay 评估历史表现
5. 用 run_backtest 在样本外测试
6. 决定:保留 / 改进 / 废弃
""",
        )

    @staticmethod
    def _feature_catalog() -> dict:
        """从真实注册表派生因子清单(不手写,避免与实现漂移)"""
        from forgemind.core.factors import (
            get_all_factors,
            list_alpha101_factors,
            list_alpha158_factors,
        )

        names = sorted(get_all_factors())
        a158 = sorted(list_alpha158_factors())
        a101 = sorted(list_alpha101_factors())
        in_a101 = set(a101)
        in_a158 = set(a158)
        barra = [n for n in names if n not in in_a101 and n not in in_a158]
        return {
            "total": len(names),
            "breakdown": {
                "alpha158": len(a158),
                "alpha101": len(a101),
                "barra": len(barra),
            },
            "factors": [
                {"name": n, "feature_id": f"feat-{n}", "category": _infer_factor_category(n)}
                for n in names
            ],
        }

    @staticmethod
    def _symbol_catalog() -> str:
        """读 DuckDB kline_daily 的 distinct symbols

        桌面 header 的标的切换下拉,需要的是用户在 DuckDB 里有真实 K 线的
        标的, symbol 来自真 DuckDB kline_daily 派生
        "601318.SH", "300750.SZ"] 一份不可编辑的列表,实际切换后 K 线面板
        会说 "暂无数据"。

        现在的实现:distinct kline_daily.symbol,补上 .SH / .SZ 后缀。
        """
        from forgemind.core.data.storage import DuckDBStorage, init_duckdb

        def _fetch():
            init_duckdb()
            with DuckDBStorage() as db:
                rows = db.query_df("SELECT DISTINCT symbol FROM kline_daily ORDER BY symbol")
            return [r["symbol"] for _, r in rows.iterrows()]

        try:
            syms = _fetch()
        except Exception:  # noqa: BLE001
            syms = []

        # DuckDB kline_daily 里 symbol 是 6 位(600519),但 UI / API 用 600519.SH
        # 没有交易所 metadata 表就保留 6 位;真机里 kline_etl 写盘可能带
        # 后缀与否取决于上游 provider。我们直接把 6 位补成 .SH / .SZ 兜底。
        # 上交所:5/6/9 开头; 深交所:0/3 开头
        out = []
        for s in syms:
            s = str(s).strip()
            if "." in s:
                out.append(s)
            elif s.isdigit() and len(s) == 6:
                if s[0] in ("5", "6", "9"):
                    out.append(f"{s}.SH")
                else:
                    out.append(f"{s}.SZ")
            else:
                out.append(s)
        return _dumps({"total": len(out), "symbols": out})

    def _signal_catalog(self) -> str:
        """读 DuckDB signal_history 最近 100 条

        signal-table 从 MCP
        resources/read forgemind://signals 拉真落盘的信号。
        """
        from forgemind.core.data.storage import load_recent_signals

        try:
            sigs = load_recent_signals(limit=100)
        except Exception:  # noqa: BLE001
            sigs = []
        return _dumps({"total": len(sigs), "signals": sigs})

    def _strategy_catalog(self) -> dict:
        """从真实注册表派生策略清单

        清单要带上"命令行能不能跑它"以及跑不了的原因:这份资源是给
        模型和客户端读的,拿到一份不带可跑性的清单,模型就会挑一个
        多标的策略去调 run_backtest,然后被拒 —— 而它无从知道为什么。
        """
        from forgemind.core.strategies import STRATEGY_REGISTRY
        from forgemind.core.strategies.extended_library import list_strategies
        from forgemind.core.strategies.library import (
            cli_runnable_strategies,
            strategy_unusable_reason,
        )

        names = sorted(set(STRATEGY_REGISTRY) | set(list_strategies()))
        runnable = cli_runnable_strategies()
        out = []
        for n in names:
            entry = {
                "name": n,
                "kind": "bar" if n in STRATEGY_REGISTRY else "extended",
                # 命令行喂不了多标的策略,这里要写清原因,不是只写个名字
                "cli_runnable": n in runnable,
            }
            reason = strategy_unusable_reason(n)
            if reason:
                entry["unusable_reason"] = reason
            out.append(entry)
        return {
            "count": len(names),
            "cli_runnable_count": len(runnable),
            "strategies": out,
        }

    # ===== 注册辅助 =====
    def _tool(self, name, description, parameters, handler):
        self.tools[name] = MCPTool(name=name, description=description, parameters=parameters)
        self.handlers[f"tool/{name}"] = handler
        # 记下 schema 里声明的必填参数,供参数错误时给出可读提示
        self._tool_required[name] = list((parameters or {}).get("required", []))

    def _resource(self, uri, name, description, mime_type="application/json", content=None):
        self.resources[uri] = MCPResource(
            uri=uri,
            name=name,
            description=description,
            mime_type=mime_type,
            content=content,
        )

    def _prompt(self, name, description, template):
        self.prompts[name] = MCPPrompt(
            name=name,
            description=description,
            template=template,
            arguments=_template_arguments(template),
        )

    # ===== Tool handlers =====
    async def _tool_search_features(self, query: str, tags: dict | None = None) -> dict:
        """搜索因子库 — 真实因子名匹配"""
        from forgemind.core.factors import get_all_factors

        all_factors = get_all_factors()
        q = query.lower()
        matched = [f for f in all_factors if q in f.lower()]
        return {
            "query": query,
            "total": len(all_factors),
            "matched_count": len(matched),
            "results": [
                {
                    "feature_id": f"feat-{name}",
                    "name": name,
                    "version": 1,
                    "category": _infer_factor_category(name),
                }
                for name in matched[:20]
            ],
        }

    async def _tool_get_feature(self, name: str, version: int | None = None) -> dict:
        """取因子定义 — 真实因子元数据

        真实的 Alpha158 因子名是 KMID / VWAP_DEV / CLOSE_MINMAX_5 这类,
        而不是用户直觉的 momentum_5。支持大小写不敏感与去掉 feat- 前缀,
        找不到时给出候选列表,避免只回一句 not found。
        """
        from forgemind.core.factors import get_all_factors

        all_factors = get_all_factors()
        resolved = self._resolve_factor_name(name, all_factors)
        if resolved is None:
            return {
                "error": f"Factor '{name}' not found.",
                "available_count": len(all_factors),
                "sample_available": sorted(all_factors)[:10],
                "hint": "用 forgemind MCP 的 search_features 工具按关键词搜索。",
            }
        return {
            "feature_name": resolved,
            "requested_name": name,
            "version": version or 1,
            "category": _infer_factor_category(resolved),
            "formula": _get_factor_formula(resolved),
            "source": "Alpha158 / Alpha101 / Barra",
        }

    @staticmethod
    def _resolve_factor_name(name: str, all_factors) -> str | None:
        """宽松匹配因子名:去前缀 / 大小写 / 精确"""
        if name in all_factors:
            return name
        stripped = name.replace("feat-", "", 1) if name.startswith("feat-") else name
        if stripped in all_factors:
            return stripped
        upper = {f.upper(): f for f in all_factors}
        if stripped.upper() in upper:
            return upper[stripped.upper()]
        return None

    async def _tool_trace_feature_usage(self, feature_id: str) -> dict:
        """追踪因子使用 — 只报告代码中真实存在的引用


        ["LightGBMModel","XGBoostModel"] / ["StockPickerAgent",...] 关联,
        等于凭空捏造使用关系且没有任何标记。这个工具扫描的是真实代码
        引用,不是猜出来的关系。
        """
        from forgemind.core.factors import get_all_factors

        all_factors = get_all_factors()
        name = self._resolve_factor_name(feature_id, all_factors)
        if name is None:
            return {
                "error": f"Factor '{feature_id}' not found.",
                "available_count": len(all_factors),
                "sample_available": sorted(all_factors)[:10],
            }

        refs = self._find_real_references(name)
        return {
            "feature_id": feature_id,
            "feature_name": name,
            "models": refs["models"],
            "strategies": refs["strategies"],
            "pipelines": refs["pipelines"],
            "referenced_by_file_count": len(refs["files"]),
            "note": (
                "以上为源码中对该因子的真实引用;空列表表示该因子目前未被任何"
                "模型/策略/流水线显式引用。"
            ),
        }

    @staticmethod
    def _find_real_references(name: str) -> dict:
        """在 forgemind 包内 grep 该因子名,返回真实引用方"""
        import re as _re
        from pathlib import Path as _Path

        import forgemind as _fm

        root = _Path(_fm.__file__).parent
        pattern = _re.compile(rf"(?<![A-Za-z0-9_]){_re.escape(name)}(?![A-Za-z0-9_])")
        models: set[str] = set()
        strategies: set[str] = set()
        pipelines: set[str] = set()
        files: list[str] = []

        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if not pattern.search(text):
                continue
            rel = str(path.relative_to(root))
            files.append(rel)
            stem = path.stem
            if "model" in stem:
                models.add(path.name)
            elif "strateg" in rel:
                strategies.add(path.name)
            elif "pipeline" in rel:
                pipelines.add(path.name)

        return {
            "models": sorted(models),
            "strategies": sorted(strategies),
            "pipelines": sorted(pipelines),
            "files": sorted(files),
        }

    async def _tool_run_backtest(
        self, strategy: str, symbol: str, start: str, end: str, params: dict | None = None
    ) -> dict:
        """跑回测 — 优先用 DuckDB 里的真行情,没有才降级到合成行情"""
        import numpy as np
        import pandas as pd

        from forgemind.core.backtest.engine import SimpleBacktestEngine
        from forgemind.core.data.storage import DuckDBStorage, bare_symbol
        from forgemind.core.strategies.library import resolve_backtest_strategy

        # 策略解析只有一份,在命令行与 MCP 共用(见
        # forgemind/core/strategies/library.py)。以前这里自己解析,只认
        # 5 个基础策略,还把"存在但这个命令喂不了"的说成"未知策略"——
        # 而同一个服务给的策略清单里明明列着它,两处说法自相矛盾。
        strategy_instance, refusal = resolve_backtest_strategy(strategy, params=params)
        if refusal is not None:
            return refusal

        # 优先查 DuckDB 真数据。ETL 落库用 6 位代码,入参常带交易所后缀
        # (.SH / .SZ),归一化放在查询参数里,任何上游传 '600519.SH' 都能命中。
        # 查得到就用真数据跑 —— 引擎与指标本来就能吃真行情,没有理由
        # 在用户已经拉过数据的情况下还给他一组随机游走。
        price_df = None
        data_source = "synthetic_random_walk"
        n_bars = 0
        try:
            with DuckDBStorage() as _db:
                found = _db.query_df(
                    "SELECT date, open, high, low, close, volume "
                    "FROM kline_daily WHERE symbol = ? "
                    "AND date BETWEEN ? AND ? ORDER BY date ASC",
                    [bare_symbol(symbol), start, end],
                )
        except Exception:
            # 表不存在(init_duckdb 没跑)或 schema 异常 —— 走降级路径
            found = None
        if found is not None and not found.empty:
            price_df = found.copy()
            price_df["date"] = pd.to_datetime(price_df["date"])
            price_df = price_df.set_index("date").sort_index()
            price_df.index.name = "date"
            price_df["symbol"] = symbol
            data_source = "duckdb_kline_daily"
            n_bars = len(price_df)

        if price_df is None:
            # 降级:确定性 GBM 合成行情(**非真实市场**,见返回里的 warning)
            # 种子用 crc32 而不是内置 hash:字符串 hash 每个进程加盐,
            # 同一标的两次调用会得到不同的行情,"确定性"就成了空话。
            import zlib as _zlib

            dates = pd.date_range(start, end, freq="B")
            n = len(dates)
            np.random.seed(_zlib.crc32(symbol.encode("utf-8")))
            close = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.018, n)))
            price_df = pd.DataFrame(
                {
                    "open": close * (1 + np.random.normal(0, 0.003, n)),
                    "high": close * (1 + np.abs(np.random.normal(0, 0.008, n))),
                    "low": close * (1 - np.abs(np.random.normal(0, 0.008, n))),
                    "close": close,
                    "volume": np.random.randint(1_000_000, 10_000_000, n),
                },
                index=dates,
            )

        engine = SimpleBacktestEngine()
        result = engine.run(strategy_instance, price_df, symbol=symbol)

        out = {
            "strategy": strategy,
            "symbol": symbol,
            "start": start,
            "end": end,
            "params": params or {},
            "total_return": result.total_return,
            "sharpe": result.sharpe,
            "max_drawdown": result.max_drawdown,
            "win_rate": result.win_rate,
            "n_trades": result.n_trades,
            "sortino": result.sortino,
            # 数据来源必须如实标注:用了 DuckDB 真行情与用了合成行情,
            # 调用方(LLM 或人)对结论的信任程度完全不同。
            "data_source": data_source,
            "is_real_data": data_source == "duckdb_kline_daily",
            "n_bars": n_bars,
        }
        if out["is_real_data"]:
            out["note"] = f"行情取自 DuckDB 的 kline_daily,{n_bars} 根 K 线,区间 {start}~{end}。"
        else:
            out["warning"] = (
                "本地没有该标的的行情数据,行情由确定性随机游走生成,"
                "非真实市场数据。结果仅验证链路可用,不代表任何标的的真实历史表现。"
                "真实数据请先跑 forgemind etl。"
            )
        return out

    async def _tool_output_signal(
        self, symbol: str, side: str, confidence: float, rationale: str
    ) -> dict:
        """输出交易信号 JSON(不替用户下单) — 真落 DuckDB

        信号经 save_signal() 落进 signal_history,返回带 signal_id 的
        真信号。桌面的 forgemind://signals resource 拉最近 N 条,
        signal-table 随即显示。
        """
        import uuid

        from forgemind.core.data.storage import save_signal

        # 校验 side / confidence,避免乱传
        side_upper = side.upper() if side else side
        if side_upper not in ("BUY", "SELL", "HOLD"):
            return {
                "status": "failed",
                "error": f"side 必须是 BUY / SELL / HOLD,收到 {side!r}",
            }
        side = side_upper
        if not (0.0 <= confidence <= 1.0):
            return {
                "status": "failed",
                "error": f"confidence 必须在 [0, 1],收到 {confidence}",
            }
        if not symbol:
            return {"status": "failed", "error": "symbol 必填"}

        sig_id = f"sig_{uuid.uuid4().hex[:12]}_{symbol}"
        sid = await asyncio.to_thread(
            save_signal,
            sig_id,
            symbol,
            side,
            confidence,
            rationale,
        )
        return {
            "status": "ok",
            "signal_id": sid,
            "symbol": symbol,
            "side": side,
            "confidence": confidence,
            "rationale": rationale,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "execution": "USER_RESPONSIBILITY",  # Agent 不下单
            "downstream_options": [
                "vnpy: copy signal → CTP / broker",
                "nautilus_trader: signal → strategy.submit",
                "manual: 在券商终端按信号执行",
            ],
        }

    async def _tool_list_factor_ic(self, symbol: str = "600519", window_days: int = 5) -> dict:
        """批量算一组因子的 IC / ICIR — 因子面板一次拉全部

        因子卡的 IC 来自 list_factor_ic 真算
        因为 forgemind://features resource 只返 name+category,不算 IC。
        桌面端加载 factor-grid 后, 后台拉一次所有因子 IC, 写到
        store.factors[].ic, 面板直接显示。

        性能:每个因子算 IC 大约 30ms,169 因子约 5s。缓存到 store 后
        切换 symbol 才重新算。
        """
        from forgemind.core.data.storage import DuckDBStorage
        from forgemind.core.factors import get_all_factors

        all_factors = get_all_factors()
        if not all_factors:
            return {"status": "no_factors", "factors": []}

        # 限流: 最多 100 个,防止 LLM 误传 universe 太大卡死 MCP
        n_compute = min(len(all_factors), 100)
        compute_list = all_factors[:n_compute]

        # DuckDB 一次性读 K 线,后续算 IC 不重复 IO
        # 表可能还没建(没跑过 forgemind etl)。缺表要如实报无数据,
        # 不能把 CatalogException 抛给调用方 —— 那看着像服务端坏了,
        # 实际只是还没拉数据。
        try:
            with DuckDBStorage() as db:
                n_bars = db.query_scalar(
                    "SELECT COUNT(*) FROM kline_daily WHERE symbol = ?",
                    [bare_symbol(symbol)],
                )
        except Exception as exc:
            return {
                "status": "no_data",
                "symbol": symbol,
                "factors": [],
                "message": market_data_unreadable_reason(),
                "hint": "先运行 `forgemind etl --symbols ...` 拉取 K 线,再重试。",
            }
        if not n_bars:
            return {
                "status": "no_data",
                "symbol": symbol,
                "factors": [],
                "message": f"{market_data_unavailable_reason(symbol)},先跑 forgemind etl。",
            }

        # 并行算 IC (asyncio.gather)
        async def _one(fname: str) -> dict:
            r = await self._tool_check_ic_decay(fname, window_days)
            if r.get("status") == "computed":
                return {
                    "name": fname,
                    "ic": r.get("ic_mean"),
                    "icir": r.get("icir"),
                    "status": "computed",
                }
            return {"name": fname, "status": r.get("status", "failed"), "ic": None, "icir": None}

        results = await asyncio.gather(
            *[_one(n) for n in compute_list],
            return_exceptions=True,
        )
        factors = [r if isinstance(r, dict) else {"name": "?", "status": "failed"} for r in results]
        n_ok = sum(1 for f in factors if f.get("status") == "computed")
        return {
            "status": "ok" if n_ok else "no_data",
            "symbol": symbol,
            "window_days": window_days,
            "n_factors_total": len(all_factors),
            "n_factors_returned": len(factors),
            "n_computed": n_ok,
            "factors": factors,
        }

    async def _tool_check_ic_decay(self, feature_name: str, window_days: int = 30) -> dict:
        """IC 衰减 — 调用 `compute_ic_decay` 真实计算,无数据时返回结构化错误。

        Returns:
            `{"status": "ok", "by_day": {day: ic}}` 或 `{"status": "empty", "reason": ...}`
        """
        import polars as pl

        from forgemind.core.data.storage import DuckDBStorage
        from forgemind.core.factors import (
            compute_forward_returns,
            get_all_factors,
        )
        from forgemind.core.factors.ic_monitor import compute_ic_decay

        all_factors = get_all_factors()
        resolved = self._resolve_factor_name(feature_name, all_factors)
        if resolved is None:
            return {
                "error": f"Factor '{feature_name}' not found.",
                "available_count": len(all_factors),
                "sample_available": sorted(all_factors)[:10],
            }
        feature_name = resolved

        try:
            with DuckDBStorage() as db:
                n_bars = db.query_scalar("SELECT COUNT(*) FROM kline_daily")
                if not n_bars:
                    return {
                        "error": "本地没有行情数据,无法计算 IC 衰减。",
                        "feature_name": feature_name,
                        "status": "no_data",
                        "n_bars": 0,
                        "hint": "先运行 `forgemind etl` 拉取 K 线,再重试。",
                    }
                pdf = db.query_df(
                    "SELECT symbol, date, open, high, low, close, volume "
                    "FROM kline_daily ORDER BY symbol, date"
                )
        except Exception as exc:
            return {
                "error": f"读取行情失败:{exc}",
                "feature_name": feature_name,
                "status": "failed",
                "hint": "确认已运行 `forgemind etl`,且 data/duckdb/main.db 可读。",
            }

        lf = pl.from_pandas(pdf).lazy()
        # 因子列由 alpha158 族生成:get_all_factors() 列出的名字
        # 正是 compute_alpha158 产出的列,两者必须对得上
        from forgemind.core.factors.alpha158 import compute_alpha158

        try:
            with_factors = compute_alpha158(lf)
        except Exception as exc:
            return {
                "error": f"因子计算失败:{exc}",
                "feature_name": feature_name,
                "status": "failed",
                "n_bars": int(n_bars),
            }
        if feature_name not in with_factors.collect_schema().names():
            return {
                "error": f"因子 '{feature_name}' 未能从行情数据算出。",
                "feature_name": feature_name,
                "status": "not_computable",
                "n_bars": int(n_bars),
                "hint": "该因子可能需要额外数据源(如财务、行业分类)。",
            }

        horizons = sorted({1, 5, 10, 20} | {window_days})
        horizons = [h for h in horizons if h > 0]
        with_returns = compute_forward_returns(with_factors, horizons)
        cols = [f"fwd_return_{h}" for h in horizons]

        try:
            decay = compute_ic_decay(with_returns, feature_name, cols)
        except Exception as exc:
            return {
                "error": f"IC 衰减计算失败:{exc}",
                "feature_name": feature_name,
                "status": "failed",
                "n_bars": int(n_bars),
            }

        series = {str(d): v for d, v in sorted(decay.items()) if v is not None}
        real = [v for v in decay.values() if v is not None]
        if not series:
            return {
                "error": "因子无有效样本,无法计算 IC。",
                "feature_name": feature_name,
                "status": "no_data",
                "n_bars": int(n_bars),
                "hint": "样本期太短或因子全为常数。",
            }
        ic_mean = sum(real) / len(real)
        icir = (
            ic_mean / (sum((v - ic_mean) ** 2 for v in real) / len(real)) ** 0.5
            if len(real) > 1 and (sum((v - ic_mean) ** 2 for v in real) / len(real)) ** 0.5 > 0
            else 0.0
        )
        return {
            "feature_name": feature_name,
            "window_days": window_days,
            "ic_by_horizon": series,
            "ic_mean": ic_mean,
            "icir": icir,
            "decay_trend": "decaying" if len(real) > 1 and real[-1] < real[0] else "stable",
            "n_bars": int(n_bars),
            "status": "computed",
        }

    @staticmethod
    def _epoch_seconds(d, date_str: str) -> int:
        """日期 → UNIX 秒(lightweight-charts 要这个)。date 可能是 date/datetime/str。"""
        import datetime as _dt
        import math as _math

        if hasattr(d, "timestamp"):
            return _math.floor(d.timestamp())
        try:
            return _math.floor(
                _dt.datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=_dt.UTC).timestamp()
            )
        except ValueError:
            return _math.floor(_dt.datetime(1970, 1, 1, tzinfo=_dt.UTC).timestamp())

    async def _tool_get_kline(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        limit: int = 250,
    ) -> dict:
        """历史 K 线 — 只读 DuckDB 里 `forgemind etl` 落盘的真实数据

        仅读 DuckDB 中 `forgemind etl` 落盘的真实 K 线;无数据时如实报
        `empty`,不补随机数。
        """
        if not symbol:
            return {"error": "symbol 不能为空", "status": "failed"}

        from forgemind.core.data.storage import DuckDBStorage, bare_symbol

        def _fetch():
            with DuckDBStorage() as db:
                total = db.query_scalar("SELECT COUNT(*) FROM kline_daily")
                if not total:
                    return None, []
                # provider 一并取出来:调用方要知道这批价格来自哪个源
                # (三个源的复权基准并不相同,混用会悄悄改变数值)
                sql = (
                    "SELECT date, open, high, low, close, volume, provider "
                    "FROM kline_daily WHERE symbol = ?"
                )
                params = [bare_symbol(symbol)]
                if start:
                    sql += " AND date >= ?"
                    params.append(start)
                if end:
                    sql += " AND date <= ?"
                    params.append(end)
                sql += " ORDER BY date DESC LIMIT ?"
                params.append(int(max(1, min(limit, 2000))))
                df = db.query_df(sql, params)
                return total, df

        try:
            total, df = await asyncio.to_thread(_fetch)
        except Exception as exc:
            msg = str(exc)
            # 表都不存在是很常见的状态(还没跑过 etl),给它自己的说法,
            # 别把 DuckDB 的原始 CatalogException 甩给用户
            if "does not exist" in msg or "Catalog Error" in msg:
                return {
                    "status": "no_data",
                    "symbol": symbol,
                    "bars": [],
                    "message": (
                        "还没有行情库。先运行 `forgemind etl` "
                        "建立 data/duckdb/main.db 并拉取 K 线。"
                    ),
                }
            return {
                "error": f"读取行情失败:{exc}",
                "symbol": symbol,
                "status": "failed",
                "hint": "确认已运行 `forgemind etl` 拉取数据,且 data/duckdb/main.db 可读。",
            }

        if total is None:
            return {
                "status": "no_data",
                "symbol": symbol,
                "bars": [],
                "message": "本地没有任何行情数据。先运行 `forgemind etl` 拉取 K 线。",
            }
        if df is None or len(df) == 0:
            return {
                "status": "empty",
                "symbol": symbol,
                "bars": [],
                "n_bars_in_db": int(total),
                "message": (
                    f"库里有 {int(total)} 根 K 线,但没有 {symbol} 的。"
                    "代码请用 6 位(如 600519)—— DuckDB 存的是不带后缀的形式。"
                ),
            }

        bars = []
        for r in df.to_dict("records"):
            d = r["date"]
            date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
            bars.append(
                {
                    "date": date_str,
                    "time": self._epoch_seconds(d, date_str),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["volume"] or 0),
                }
            )
        bars.reverse()  # 升序:图表要时间正序
        return {
            "status": "ok",
            "symbol": symbol,
            "n_bars": len(bars),
            "start": bars[0]["date"],
            "end": bars[-1]["date"],
            "provider": df["provider"].iloc[-1] if "provider" in df.columns else None,
            "bars": bars,
        }

    async def _tool_query_portfolio(self) -> dict:
        """组合快照 + 6 Agent 决策 + 最近一次回测指标

        数据来源:
            portfolio_snapshot / portfolio_position  ← forgemind agent 落盘
            portfolio_decision                       ← forgemind agent 落盘
            backtest_run                             ← forgemind backtest 落盘

        没有真数据时如实返回 status=empty + 空数组,绝不编造指标。
        桌面 UI 风险指标读最近一次 backtest_run。
        """
        from forgemind.core.data.storage import (
            load_latest_backtest_run,
            load_latest_decisions,
            load_latest_portfolio,
        )

        # 6 Agent 决策 + 最近一次回测指标是无 snapshot 时也可能有用的参考数据
        # (用户可能先跑 forgemind backtest 再跑 agent,反过来也可能),所以始终加载
        decisions = await asyncio.to_thread(load_latest_decisions)
        risk_metrics = await asyncio.to_thread(load_latest_backtest_run)

        snapshot = await asyncio.to_thread(load_latest_portfolio)
        if snapshot is None:
            return {
                "status": "empty",
                "cash": None,
                "total_equity": None,
                "positions": [],
                "decisions": decisions,  # 即便没组合快照,backtest 可能已经跑过
                "risk_metrics": risk_metrics,
                "message": (
                    "尚无组合快照。请先运行 `forgemind agent --symbol <code> "
                    "--cash <金额> [--position-qty N --position-price P]`,"
                    "该命令会把组合状态落盘到 DuckDB,本工具随后即可读取。"
                ),
            }

        # 有 portfolio snapshot 时,risk_metrics 按持仓标的匹配(若空则取任意最近)
        symbol_hint = snapshot["positions"][0]["symbol"] if snapshot["positions"] else None
        if symbol_hint:
            risk_metrics = (
                await asyncio.to_thread(lambda: load_latest_backtest_run(symbol_hint))
                or risk_metrics
            )

        return {
            "status": "ok",
            "snapshot_id": snapshot["snapshot_id"],
            "cash": snapshot["cash"],
            "currency": snapshot["currency"],
            "total_equity": snapshot["total_equity"],
            "positions": snapshot["positions"],
            "decisions": decisions,
            "risk_metrics": risk_metrics,
        }

    async def _tool_agent_decide(
        self,
        symbol: str,
        cash: float = 100000.0,
        total_equity: float = 0.0,
        positions: list | None = None,
    ) -> dict:
        """AI 决策的准备阶段 —— 停在人工审批前,返回 thread_id。

        这一步**不下单**:PM 节点还没跑,pm_decision 是空的。真正拍板要用
        thread_id 调 agent_approve。人工审批是 gating,不是替代。
        """
        from datetime import datetime

        from forgemind.core.agents.portfolio_context import (
            PortfolioContext,
            PortfolioPosition,
            run_decision,
        )

        # 输入校验跟 API 的 AgentRequest 同一口径:负现金、负权益、空代码
        # 都是说不通的组合,照单全收的话,后面算出来的权重与股数全是废数,
        # 而界面看上去还像个正常决策。
        if not str(symbol).strip():
            raise ValueError("symbol 不能为空")
        if float(cash) <= 0:
            raise ValueError(f"cash 必须大于 0,收到 {cash}")
        if float(total_equity) < 0:
            raise ValueError(f"total_equity 不能为负,收到 {total_equity}")
        held = []
        for pos in positions or []:
            quantity = float(pos.get("quantity", 0))
            avg_price = float(pos.get("avg_price", 0))
            if quantity < 0:
                raise ValueError(f"持仓数量不能为负,收到 {quantity}")
            if quantity == 0:
                continue
            if avg_price < 0:
                raise ValueError(f"持仓均价不能为负,收到 {avg_price}")
            held.append(
                PortfolioPosition(
                    symbol=str(pos.get("symbol", symbol)),
                    quantity=quantity,
                    avg_price=avg_price,
                )
            )
        equity = (
            float(total_equity)
            if total_equity
            else float(cash) + sum(p.quantity * p.avg_price for p in held)
        )
        state = await run_decision(
            symbol=symbol,
            as_of=datetime.now(),
            portfolio=PortfolioContext(
                cash=float(cash),
                total_equity=equity,
                positions=held,
            ),
        )
        bull = state.get("bull_case", {}) or {}
        bear = state.get("bear_case", {}) or {}
        return {
            "status": "PENDING_HUMAN_REVIEW",
            "thread_id": state.get("thread_id", ""),
            "symbol": symbol,
            "bull_thesis": bull.get("thesis", ""),
            "bear_thesis": bear.get("thesis", ""),
            "confidence": state.get("confidence", 0),
            "requires_human_review": True,
            "next_step": "用 agent_approve 带 thread_id 拍板",
        }

    async def _tool_agent_approve(
        self,
        thread_id: str,
        approved: bool = True,
        reviewer: str | None = None,
    ) -> dict:
        """人工审批 —— approved=True 让 PM 节点跑完并落库。

        落库(组合快照 + 6 条决策明细)在共用层做,CLI 与 API 与 MCP 走的是
        同一条路,所以桌面端批完,组合概览与多 Agent 面板立刻能读到。
        """
        from forgemind.core.agents.portfolio_context import resume_decision

        final = await resume_decision(
            thread_id=thread_id,
            approved=bool(approved),
            reviewer=reviewer,
            notes=None,
        )
        pm = final.get("pm_decision") or {}
        return {
            "status": "APPROVED" if approved else "REJECTED",
            "thread_id": thread_id,
            "pm_decision": pm,
            "requires_human_review": False,
            "reasoning": (final.get("decision_event", {}) or {}).get("reasoning", ""),
            "persisted": final.get("persisted"),
        }

    async def _tool_stock_pick(self, universe: list[str], top_n: int = 5) -> dict:
        from forgemind.core.agents.stock_picker import StockPickerAgent

        # DuckDB 里的代码是 6 位("600519"),而 MCP 其它工具
        # (run_backtest / output_signal)都用 "600519.SH" 带交易所后缀。
        # 同一套协议里两种写法,不归一化的话这里会静默返回 0 picks ——
        # 用户完全看不出是格式不对还是真没数据。
        normalized = [self._bare_symbol(s) for s in universe]
        picker = StockPickerAgent()
        picks = await picker.pick(universe=normalized, top_n=top_n)

        out: dict[str, Any] = {
            "top_n": top_n,
            "universe": normalized,
            "picks": [
                {
                    "symbol": p.symbol,
                    "direction": p.direction,
                    "score": p.score,
                    "confidence": p.confidence,
                    "rationale": p.rationale,
                }
                for p in picks
            ],
        }
        if not picks:
            skipped = dict(getattr(picker, "last_insufficient", {}) or {})
            if skipped:
                detail = "、".join(
                    f"{k}({v} 根 K 线)" if v else f"{k}(无数据)"
                    for k, v in list(skipped.items())[:6]
                )
                out["status"] = "insufficient_data"
                out["skipped"] = skipped
                out["hint"] = (
                    f"以下标的被跳过:{detail}。先运行 `forgemind etl` 拉取更长区间的 K 线再重试。"
                )
            else:
                out["status"] = "empty"
        else:
            out["status"] = "ok"
        return out

    @staticmethod
    def _bare_symbol(symbol: str) -> str:
        """'600519.SH' / 'sh600519' / '600519.SH' → '600519'"""
        s = str(symbol).strip().upper()
        for sep in (".", "-", "_"):
            if sep in s:
                s = s.split(sep)[0]
        for pre in ("SH", "SZ", "BJ"):
            if s.startswith(pre) and s[2:].isdigit():
                s = s[2:]
        return s.strip()

    # ===== MCP JSON-RPC 处理 =====
    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """处理 JSON-RPC 2.0 请求"""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "forgemind", "version": _version()},
                    "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                },
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "inputSchema": t.parameters,
                        }
                        for t in self.tools.values()
                    ],
                },
            }

        if method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "resources": [
                        {
                            "uri": r.uri,
                            "name": r.name,
                            "description": r.description,
                            "mimeType": r.mime_type,
                        }
                        for r in self.resources.values()
                    ],
                },
            }

        if method == "prompts/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "prompts": [
                        {
                            "name": p.name,
                            "description": p.description,
                            "arguments": p.arguments,
                        }
                        for p in self.prompts.values()
                    ],
                },
            }

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments")
            if arguments is None:
                arguments = {}
            handler = self.handlers.get(f"tool/{tool_name}")
            if not handler:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                }
            if not isinstance(arguments, dict):
                # arguments 必须是对象;传成 null 或数组是调用不合法
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32602,
                        "message": "Invalid arguments: expected a JSON object",
                    },
                }
            try:
                result = await handler(**arguments)
                # 工具跑起来了,但工作失败了(因子不存在、策略不存在、取数
                # 失败、参数取值不合法……):按 MCP 规范放进 result 并标
                # isError,host 才会把它回灌给模型,模型自己就能改参数重试。
                #
                # 工具内部有一十几处直接返回 {"error": ...},以前全被包成
                # "成功的结果" —— 协议层看不出失败,失败原因只混在一段
                # JSON 文本里,host 与模型都可能当成正常数据继续走。
                # 这里统一判一次:返回体带 error 就是失败。
                #
                # 注意别把"没有数据"也当成失败:{"status": "no_data",
                # "message": "先跑 forgemind etl"} 是工具正常跑完了的
                # 回答,标成失败会让模型以为工具坏了。
                failed = isinstance(result, dict) and bool(result.get("error"))
                payload: dict[str, Any] = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": _dumps(result),
                            }
                        ]
                    },
                }
                if failed:
                    payload["result"]["isError"] = True
                return payload
            except TypeError as e:
                # 缺参/多参:只回工具名和缺了什么,不暴露内部方法签名
                msg = str(e)
                if "required positional argument" in msg or "unexpected keyword" in msg:
                    required = list(self._tool_required.get(tool_name, []))
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32602,
                            "message": (
                                f"Invalid arguments for tool '{tool_name}'. "
                                f"Required: {required or 'see tools/list schema'}"
                            ),
                            "data": {"tool": tool_name, "required": required},
                        },
                    }
                return _tool_execution_failed(req_id, tool_name, e)
            except Exception as e:
                return _tool_execution_failed(req_id, tool_name, e)

        if method == "prompts/get":
            prompt_name = params.get("name")
            p = self.prompts.get(prompt_name)
            if not p:
                # 方法本身存在,坏的是参数名 —— 属于参数错误,不是方法不存在
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": f"Unknown prompt: {prompt_name}"},
                }
            # 必须把 arguments 渲染进模板,字面量的 `{symbol}` 等占位符
            # 在响应里直接出现,会让 Claude Desktop 拿到残缺提示词。
            text, missing = _render_prompt(p.template, params.get("arguments") or {})
            if missing:
                # 缺参数就整个请求失败。半渲染的提示词比报错更糟:
                # 调用方会把没替换的 {symbol} 当正文发给模型。
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32602,
                        "message": (
                            f"Missing required arguments for prompt '{prompt_name}': "
                            f"{', '.join(missing)}"
                        ),
                        "data": {"prompt": prompt_name, "missing": missing},
                    },
                }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "messages": [{"role": "user", "content": {"type": "text", "text": text}}]
                },
            }

        if method == "resources/read":
            uri = params.get("uri")
            r = self.resources.get(uri)
            if not r:
                # 资源不存在用规范专用的 -32002;方法本身是存在的
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32002, "message": f"Unknown resource: {uri}"},
                }
            # content 是 callable 时每次新算(支持 DuckDB 实时变化);
            # 否则是静态值直接用(features/strategies/brokers/portfolio 这些
            # 注册时拍快照即可,不会随时间变)。
            content = r.content() if callable(r.content) else r.content
            if isinstance(content, str):
                text = content
            elif isinstance(content, (dict, list)):
                text = _dumps(content)
            else:
                text = _dumps(content)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "contents": [
                        {
                            "uri": r.uri,
                            "mimeType": r.mime_type,
                            "text": text,
                        }
                    ],
                },
            }

        if method == "notifications/initialized":
            # 客户端通知,不需要 response
            logger.info("mcp_client_initialized", server="forgemind")
            return None

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"},
        }


def _redirect_logging_to_stderr() -> None:
    """stdio 模式下,所有日志必须走 stderr

    structlog 与标准 logging 默认都写 stdout;一旦日志混入 stdout,MCP 客户端
    解析 JSON-RPC 的第一包就报 `Extra data`。
    """
    import logging
    import sys

    root = logging.getLogger()
    for handler in list(root.handlers):
        stream = getattr(handler, "stream", None)
        if stream is sys.stdout:
            handler.setStream(sys.stderr)
    if not root.handlers:
        root.addHandler(logging.StreamHandler(sys.stderr))
    root.setLevel(logging.WARNING)  # stdio 模式默认安静

    try:
        import structlog

        structlog.configure(
            logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
            cache_logger_on_first_use=True,
        )
    except Exception:  # pragma: no cover - structlog 缺失时忽略
        pass


def _serve_stdio(server: "ForgeMindMCPServer") -> int:
    """真正的 MCP stdio 传输:按行读 JSON-RPC,结果写回 stdout


    进程 0.5 秒结束 —— 对外的 MCP 能力实际不可用;而且日志与横幅都
    打在 stdout 上,即使有响应也会污染 JSON-RPC 协议流。

    约定:stdout **只能**出现 JSON-RPC 响应;一切日志/横幅走 stderr。
    """
    import sys

    out = sys.stdout
    # 启动横幅写 stderr,避免污染协议
    print(
        f"ForgeMind MCP Server (stdio) — {len(server.tools)} tools, "
        f"{len(server.resources)} resources, {len(server.prompts)} prompts",
        file=sys.stderr,
    )

    async def _respond(payload: dict) -> None:
        resp = await server.handle_request(payload)
        if resp is not None:
            # 走 _dumps:响应里带 NaN 会写出非法 JSON,客户端解析不了
            out.write(_dumps(resp) + "\n")
            out.flush()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                # 非法 JSON 也要回一个规范的 JSON-RPC 错误
                out.write(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {"code": -32700, "message": f"Parse error: {exc.msg}"},
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                out.flush()
                continue
            # notification(无 id)不回复
            if isinstance(payload, dict) and "id" not in payload:
                try:
                    loop.run_until_complete(_respond(payload))
                except Exception as exc:  # pragma: no cover
                    print(f"[mcp] notification 处理失败: {exc}", file=sys.stderr)
                continue
            try:
                loop.run_until_complete(_respond(payload))
            except Exception as exc:  # pragma: no cover
                print(f"[mcp] 请求处理异常: {exc}", file=sys.stderr)
                # 请求必须有回音:不回的话客户端会一直等这个 id,
                # 表现成"卡住",比报错更难排查。
                out.write(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": payload.get("id") if isinstance(payload, dict) else None,
                            "error": {"code": -32603, "message": "Internal error"},
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                out.flush()
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            loop.close()
    return 0


# CLI 入口
def main():
    import sys

    # Windows 控制台是 GBK/cp1252,打印中文/emoji 会崩 —— 与 CLI 同一处理
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover
            pass

    # structlog / logging 默认可能写 stdout,stdio 模式下必须改道 stderr
    _redirect_logging_to_stderr()

    server = ForgeMindMCPServer()

    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        print("=== ForgeMind MCP Server Demo ===\n")
        print(f"Tools: {len(server.tools)}")
        for t in server.tools.values():
            print(f"  - {t.name}: {t.description}")
        print(f"\nResources: {len(server.resources)}")
        for r in server.resources.values():
            print(f"  - {r.uri}")
        print(f"\nPrompts: {len(server.prompts)}")
        for p in server.prompts.values():
            print(f"  - {p.name}: {p.description}")

        # Demo: invoke stock_pick
        print("\n=== Demo: stock_pick ===")

        async def demo():
            result = await server._tool_stock_pick(
                universe=["600519", "000001", "601318", "600036"],
                top_n=2,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))

        asyncio.run(demo())
        return 0

    return _serve_stdio(server)


if __name__ == "__main__":
    raise SystemExit(main())
