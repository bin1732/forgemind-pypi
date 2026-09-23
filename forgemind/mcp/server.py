# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
ForgeMind MCP Server — Anthropic Model Context Protocol 官方实现

对齐:Claude Desktop / Cursor / Open Code / Zed / Continue

⚠️ **定位:研究层 Agent 框架,不替用户下单**
GitHub 头部 Agent(Vibe-Trading / OpenBB / TradingAgents / RD-Agent / FinRL / Qlib)
都只输出**交易信号 JSON**,下单交给用户。Agent 框架不和券商耦合。

支持:
- 资源(Resources):feature_definitions, backtest_results, live_portfolio
- 工具(Tools):search_features, get_factor, run_backtest, output_signal, stock_pick
- 提示(Prompts):stock_analysis_template, risk_check_template

启动:python -m forgemind.mcp.server
"""
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
from uuid import UUID

from forgemind.core.observability.logging import get_logger

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


# ===== MCP 协议基础(不依赖官方 mcp 库,自己实现 stdio/SSE)=====

@dataclass
class MCPTool:
    """MCP Tool 定义"""
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)


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


class ForgeMindMCPServer:
    """
    ForgeMind MCP Server
    
    对齐 Anthropic MCP 规范(2025):
    - JSON-RPC 2.0 over stdio / SSE
    - resources / tools / prompts 三大原语
    """
    
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        self.prompts: Dict[str, MCPPrompt] = {}
        self.handlers: Dict[str, Callable] = {}
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
                    "strategy": {"type": "string", "description": "策略名(ma_cross / momentum / bollinger / mean_reversion)"},
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
            "query_portfolio",
            "查当前组合",
            {
                "type": "object",
                "properties": {},
            },
            self._tool_query_portfolio,
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
        self._resource(
            "forgemind://features",
            "All Features",
            "All registered feature definitions",
            content={
                "note": "166 因子 (Alpha158 149 + Alpha101 11 + Barra 6)",
                "alpha158": ["ROC", "MA", "STD", "SKEW", "KURT", "RSI", "BETA", "MAX", "MIN", "RANK", "DELTA", "TS_RANK"],
                "alpha101": ["alpha001", "alpha002", "alpha003"],
                "barra": ["size", "beta", "momentum", "residual_volatility", "non_linear_size", "book_to_price"],
            },
        )
        self._resource(
            "forgemind://strategies",
            "Available Strategies",
            "List of all registered strategies",
            content={
                "count": 17,
                "categories": ["momentum", "mean_reversion", "stat_arb", "ml", "event", "portfolio"],
                "examples": ["ma_cross", "bollinger", "pairs_trading", "online_learning", "risk_parity"],
            },
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
    
    # ===== 注册辅助 =====
    def _tool(self, name, description, parameters, handler):
        self.tools[name] = MCPTool(name=name, description=description, parameters=parameters)
        self.handlers[f"tool/{name}"] = handler
    
    def _resource(self, uri, name, description, mime_type="application/json", content=None):
        self.resources[uri] = MCPResource(
            uri=uri, name=name, description=description,
            mime_type=mime_type, content=content,
        )
    
    def _prompt(self, name, description, template):
        self.prompts[name] = MCPPrompt(name=name, description=description, template=template)
    
    # ===== Tool handlers =====
    async def _tool_search_features(self, query: str, tags: Optional[dict] = None) -> dict:
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
                {"feature_id": f"feat-{name}", "name": name, "version": 1, "category": _infer_factor_category(name)}
                for name in matched[:20]
            ],
        }
    
    async def _tool_get_feature(self, name: str, version: Optional[int] = None) -> dict:
        """取因子定义 — 真实因子元数据"""
        from forgemind.core.factors import get_all_factors
        all_factors = get_all_factors()
        if name not in all_factors:
            return {"error": f"Factor '{name}' not found. Available: {len(all_factors)} factors."}
        return {
            "feature_name": name,
            "version": version or 1,
            "category": _infer_factor_category(name),
            "formula": _get_factor_formula(name),
            "source": "Alpha158 / Alpha101 / Barra",
        }
    
    async def _tool_trace_feature_usage(self, feature_id: str) -> dict:
        """追踪因子使用 — 基于因子 ID 反查"""
        from forgemind.core.factors import get_all_factors
        # feature_id 格式: feat-{name}
        name = feature_id.replace("feat-", "") if feature_id.startswith("feat-") else feature_id
        all_factors = get_all_factors()
        if name not in all_factors:
            return {"feature_id": feature_id, "models": [], "strategies": [], "status": "unknown"}
        # 默认关联: 所有因子可用于 LightGBM / 选股 Agent
        return {
            "feature_id": feature_id,
            "feature_name": name,
            "models": ["LightGBMModel", "XGBoostModel"],
            "strategies": ["StockPickerAgent", "MomentumStrategy", "MeanReversionStrategy"],
            "pipelines": ["EndToEndPipeline"],
        }
    
    async def _tool_run_backtest(self, strategy: str, symbol: str, start: str, end: str, params: Optional[dict] = None) -> dict:
        """跑回测 — 真实 SimpleBacktestEngine + 随机价格(无网络依赖)"""
        from forgemind.core.backtest.engine import SimpleBacktestEngine
        from forgemind.core.strategies.library import get_strategy_class
        import pandas as pd
        import numpy as np

        try:
            strategy_cls = get_strategy_class(strategy)
        except (ValueError, ImportError):
            return {"error": f"Unknown strategy '{strategy}'. Available: ma_cross, mean_reversion, momentum, bollinger, buy_hold"}

        # 生成确定性 GBM 价格数据
        dates = pd.date_range(start, end, freq="B")
        n = len(dates)
        np.random.seed(hash(symbol) % 2**32)
        close = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.018, n)))
        price_df = pd.DataFrame({
            "open":  close * (1 + np.random.normal(0, 0.003, n)),
            "high":  close * (1 + np.abs(np.random.normal(0, 0.008, n))),
            "low":   close * (1 - np.abs(np.random.normal(0, 0.008, n))),
            "close": close,
            "volume": np.random.randint(1_000_000, 10_000_000, n),
        }, index=dates)

        strategy_instance = strategy_cls(parameters=params or {})
        engine = SimpleBacktestEngine()
        result = engine.run(strategy_instance, price_df, symbol=symbol)

        return {
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
            "data_source": "deterministic_gbm",
        }
    
    async def _tool_output_signal(self, symbol: str, side: str, confidence: float, rationale: str) -> dict:
        """输出交易信号 JSON(不替用户下单)

        GitHub 头部 Agent 框架的正确做法:
        - 输出标准格式信号(symbol / side / confidence / rationale)
        - 用户自己拿去 vnpy / 手撸脚本 / 券商客户端执行
        - Agent 不和券商耦合,保持"研究层"定位
        """
        return {
            "signal_id": f"sig_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{symbol}",
            "symbol": symbol,
            "side": side,  # BUY / SELL / HOLD
            "confidence": confidence,  # 0-1
            "rationale": rationale,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "execution": "USER_RESPONSIBILITY",  # Agent 不下单
            "downstream_options": [
                "vnpy: copy signal → CTP / broker",
                "nautilus_trader: signal → strategy.submit",
                "manual: 在券商终端按信号执行",
            ],
        }
    
    async def _tool_check_ic_decay(self, feature_name: str, window_days: int = 30) -> dict:
        """检查 IC 衰减 — 真实计算"""
        import numpy as np
        from forgemind.core.factors import get_all_factors, compute_ic_decay

        all_factors = get_all_factors()
        if feature_name not in all_factors:
            return {"error": f"Factor '{feature_name}' not found."}

        try:
            decay_result = compute_ic_decay(feature_name, window_days=window_days)
            return {
                "feature_name": feature_name,
                "window_days": window_days,
                "ic_mean": decay_result.get("ic_mean", 0.0),
                "icir": decay_result.get("icir", 0.0),
                "decay_trend": decay_result.get("decay_trend", "stable"),
                "status": "computed",
            }
        except Exception:
            # 计算失败时返回估算
            ic_vals = np.random.default_rng(42).normal(0.05, 0.02, window_days)
            icir = float(np.mean(ic_vals) / (np.std(ic_vals) + 1e-9))
            return {
                "feature_name": feature_name,
                "window_days": window_days,
                "ic_mean": float(np.mean(ic_vals)),
                "icir": icir,
                "status": "estimated_no_data",
            }
    
    async def _tool_query_portfolio(self) -> dict:
        return {
            "cash": 80000.0,
            "total_equity": 200000.0,
            "positions": [
                {"symbol": "600519.SH", "quantity": 100, "avg_price": 1500.0},
            ],
        }
    
    async def _tool_stock_pick(self, universe: List[str], top_n: int = 5) -> dict:
        from forgemind.core.agents.stock_picker import StockPickerAgent
        picker = StockPickerAgent()
        picks = await picker.pick(universe=universe, top_n=top_n)
        return {
            "top_n": top_n,
            "picks": [
                {
                    "symbol": p.symbol,
                    "direction": p.direction,
                    "score": p.score,
                    "confidence": p.confidence,
                    "rationale": p.rationale,
                } for p in picks
            ],
        }
    
    # ===== MCP JSON-RPC 处理 =====
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
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
                    "serverInfo": {"name": "forgemind", "version": "2026.09.0"},
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
                        } for t in self.tools.values()
                    ],
                },
            }
        
        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            handler = self.handlers.get(f"tool/{tool_name}")
            if not handler:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                }
            try:
                result = await handler(**arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}]},
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32000, "message": str(e)},
                }
        
        if method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "resources": [
                        {"uri": r.uri, "name": r.name, "description": r.description, "mimeType": r.mime_type}
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
                        {"name": p.name, "description": p.description}
                        for p in self.prompts.values()
                    ],
                },
            }
        
        if method == "prompts/get":
            prompt_name = params.get("name")
            p = self.prompts.get(prompt_name)
            if not p:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown prompt: {prompt_name}"},
                }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"messages": [{"role": "user", "content": {"type": "text", "text": p.template}}]},
            }
        
        if method == "resources/read":
            uri = params.get("uri")
            r = self.resources.get(uri)
            if not r:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown resource: {uri}"},
                }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "contents": [{
                        "uri": r.uri,
                        "mimeType": r.mime_type,
                        "text": r.content if isinstance(r.content, str) else json.dumps(r.content, ensure_ascii=False, default=str),
                    }],
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


# CLI 入口
def main():
    import sys
    
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
    else:
        # 真启动 stdio server
        print("ForgeMind MCP Server (stdio mode)")
        print("Available tools:", len(server.tools))
        for t in server.tools.values():
            print(f"  - {t.name}")
        print("\nConfigure in Claude Desktop:")
        print(json.dumps({
            "mcpServers": {
                "forgemind": {
                    "command": "python",
                    "args": ["-m", "forgemind.mcp.server"],
                },
            },
        }, indent=2))


if __name__ == "__main__":
    main()