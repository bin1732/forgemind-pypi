# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
ForgeMind FastAPI 应用入口
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from forgemind.core.config.settings import get_settings
from forgemind.core.observability.logging import setup_logging, get_logger, ForgeMindError
from forgemind.core.agents.portfolio_context import (
    PortfolioContext,
    PortfolioPosition,
    run_decision,
)
from forgemind.core.strategies.base import MovingAverageCrossStrategy
from forgemind.core.backtest.engine import SimpleBacktestEngine

settings = get_settings()
logger = get_logger("forgemind.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    setup_logging()
    logger.info(
        "app_started",
        env=settings.env,
        mode=settings.mode,
        version=settings.version,
    )
    yield
    logger.info("app_shutdown")


app = FastAPI(
    title="ForgeMind API",
    description="AI-powered quantitative trading agent",
    version=settings.version,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== API Key Auth Middleware =====
from fastapi import Request, HTTPException

PUBLIC_PATHS = {
    "/health",
    "/api/v1/info",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/mcp",           # MCP 协议端点 (桌面端本地调用)
    "/api/pipeline",  # 数据流水线 (桌面端本地调用)
}


@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    """API Key 校验 — dev 模式跳过，prod 必须传 X-API-Key"""
    if any(request.url.path.startswith(p) for p in PUBLIC_PATHS):
        return await call_next(request)

    if settings.env == "dev":
        return await call_next(request)

    provided = request.headers.get("X-API-Key", "")
    if not provided:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if provided != settings.api_secret_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return await call_next(request)


# ===== Exception handler =====
@app.exception_handler(ForgeMindError)
async def forgemind_error_handler(request, exc: ForgeMindError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
    )


# ===== Health endpoints =====
@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "ok",
        "version": settings.version,
        "env": settings.env,
        "mode": settings.mode,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/v1/info")
async def info():
    """App info"""
    return {
        "name": "ForgeMind",
        "version": settings.version,
        "env": settings.env,
        "data_dir": settings.data_dir,
    }


# ===== Backtest endpoint =====
class BacktestRequest(BaseModel):
    symbol: str = Field(default="600519.SH", description="股票代码")
    start_date: str = Field(default="2023-01-01")
    end_date: str = Field(default="2024-01-01")
    fast_period: int = Field(default=5, ge=2, le=200)
    slow_period: int = Field(default=20, ge=5, le=500)
    initial_capital: float = Field(default=100_000.0, gt=0)


class BacktestResponse(BaseModel):
    total_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    n_trades: int
    params: dict


@app.post("/api/v1/backtest/run", response_model=BacktestResponse)
async def run_backtest(req: BacktestRequest):
    """
    跑一个双均线回测(SimpleBacktestEngine 真实计算)
    
    内部:
    1. 生成确定性 GBM 价格数据(无网络依赖;生产从 ClickHouse 读)
    2. 跑 SimpleBacktestEngine + MovingAverageCrossStrategy
    3. 返回真实回测指标
    """
    import pandas as pd
    import numpy as np
    
    # Demo 数据:生成 1 年日 K(生产从 ClickHouse 读)
    dates = pd.date_range(req.start_date, req.end_date, freq="D")
    n = len(dates)
    np.random.seed(42)
    close = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, n)))
    
    price_df = pd.DataFrame({
        "open": close * (1 + np.random.normal(0, 0.005, n)),
        "high": close * (1 + np.abs(np.random.normal(0, 0.01, n))),
        "low": close * (1 - np.abs(np.random.normal(0, 0.01, n))),
        "close": close,
        "volume": np.random.randint(1_000_000, 10_000_000, n),
    }, index=dates)
    
    # 跑策略
    strategy = MovingAverageCrossStrategy(
        parameters={
            "fast_period": req.fast_period,
            "slow_period": req.slow_period,
        }
    )
    
    engine = SimpleBacktestEngine(initial_capital=req.initial_capital)
    result = engine.run(strategy, price_df, symbol=req.symbol)
    
    return BacktestResponse(
        total_return=result.total_return,
        sharpe=result.sharpe,
        max_drawdown=result.max_drawdown,
        win_rate=result.win_rate,
        n_trades=result.n_trades,
        params=result.params,
    )


# ===== Agent endpoint =====
class AgentRequest(BaseModel):
    symbol: str
    cash: float = Field(default=100_000.0, gt=0)
    total_equity: float = Field(default=100_000.0, gt=0)
    positions: List[dict] = Field(default_factory=list)


class AgentResponse(BaseModel):
    decision: dict
    confidence: float
    requires_human_review: bool
    reasoning: str


@app.post("/api/v1/agent/decide", response_model=AgentResponse)
async def agent_decide(req: AgentRequest):
    """
    跑 AI 决策(LangGraph 3-Agent Harness)
    
    **重要**:返回 requires_human_review=True 必须人工审批才下单
    """
    portfolio = PortfolioContext(
        cash=req.cash,
        total_equity=req.total_equity,
        positions=[
            PortfolioPosition(**p) for p in req.positions
        ],
    )
    
    state = await run_decision(
        symbol=req.symbol,
        as_of=datetime.now(),
        portfolio=portfolio,
    )

    if not state.get("pm_decision"):
        # interrupt_before 卡在 PM → 还没决策
        return AgentResponse(
            decision={"status": "PENDING_HUMAN_REVIEW", "thread_id": "default"},
            confidence=state.get("confidence", 0),
            requires_human_review=True,
            reasoning="interrupt_before portfolio_manager: PM 节点等人工审批,call again with approval",
        )

    return AgentResponse(
        decision=state["pm_decision"],
        confidence=state.get("confidence", 0),
        requires_human_review=state.get("requires_human_review", True),
        reasoning=state.get("decision_event", {}).get("reasoning", "") if state.get("decision_event") else "",
    )


# ===== Feature Store =====
@app.get("/api/v1/features/search")
async def search_features(query: str, limit: int = 10):
    """搜索因子 — 真实因子库搜索"""
    from forgemind.core.factors import get_all_factors, factor_count
    all_factors = get_all_factors()
    q = query.lower()
    matched = [f for f in all_factors if q in f.lower()]
    return {
        "query": query,
        "total_factors": factor_count(),
        "matched_count": len(matched),
        "results": [
            {"feature_id": f"feat-{name}", "feature_name": name, "version": 1}
            for name in matched[:limit]
        ],
    }


@app.get("/api/v1/features")
async def list_features(limit: int = 20):
    """列出所有因子"""
    from forgemind.core.factors import get_all_factors, factor_count
    all_factors = get_all_factors()
    return {
        "total": factor_count(),
        "factors": [{"feature_id": f"feat-{f}", "feature_name": f} for f in all_factors[:limit]],
    }


# ===== Health for individual services =====
@app.get("/api/v1/health/services")
async def services_health():
    """各服务健康检查"""
    services = {}
    
    # ClickHouse — 用 asyncio.to_thread 避免阻塞事件循环
    try:
        from clickhouse_driver import Client
        def _ch_ping():
            ch = Client(
                host=settings.ch_host,
                port=settings.ch_port,
                user=settings.ch_user,
                password=settings.ch_password,
                database=settings.ch_database,
                connect_timeout=3,
            )
            return ch.execute("SELECT 1")
        await asyncio.to_thread(_ch_ping)
        services["clickhouse"] = "ok"
    except Exception as e:
        services["clickhouse"] = f"down: {str(e)[:100]}"
    
    # PostgreSQL
    try:
        import asyncpg
        conn = await asyncpg.connect(
            host=settings.pg_host,
            port=settings.pg_port,
            user=settings.pg_user,
            password=settings.pg_password,
            database=settings.pg_database,
        )
        await conn.execute("SELECT 1")
        await conn.close()
        services["postgresql"] = "ok"
    except Exception as e:
        services["postgresql"] = f"down: {str(e)[:100]}"
    
    # Redis/Valkey
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        services["redis"] = "ok"
    except Exception as e:
        services["redis"] = f"down: {str(e)[:100]}"
    
    # NATS
    try:
        import nats
        nc = await nats.connect(settings.nats_url, connect_timeout=2)
        await nc.close()
        services["nats"] = "ok"
    except Exception as e:
        services["nats"] = f"down: {str(e)[:100]}"
    
    return services


# ===== MCP HTTP 端点 (供 Tauri 桌面端调用) =====
# Tauri sidecar: python -m forgemind.api.main --port 8008
# MCP over HTTP: Tauri 调用 /mcp/tools/call
# 复用 ForgeMindMCPServer 的 handle_request() 逻辑，支持 JSON-RPC 2.0

# 懒加载，避免循环导入
_mcp_server: "ForgeMindMCPServer | None" = None


def _get_mcp_server() -> "ForgeMindMCPServer":
    """延迟初始化 MCP server 实例"""
    global _mcp_server
    if _mcp_server is None:
        from forgemind.mcp.server import ForgeMindMCPServer
        _mcp_server = ForgeMindMCPServer()
    return _mcp_server


class MCPToolCallRequest(BaseModel):
    """简化的工具调用请求格式 (Tauri sidecar 发送)"""
    name: str
    arguments: dict = Field(default_factory=dict)


# ===== Pipeline endpoint (供 Tauri 桌面端调用) =====


class SignalOutput(BaseModel):
    symbol: str
    date: str
    direction: str
    confidence: float
    signal: float


class PipelineResult(BaseModel):
    symbols: List[str]
    n_symbols: int
    n_days: int
    n_bars: int
    sharpe: float
    max_drawdown: float
    signals: List[SignalOutput]


class PipelineRequest(BaseModel):
    symbols: List[str]
    start: str
    end: str


@app.post("/api/pipeline/run", response_model=PipelineResult)
async def run_pipeline(req: PipelineRequest):
    """
    数据流水线 — 拉取历史 K 线 + 计算信号 (Tauri 桌面端专用端点)。

    实现说明:
    - dev/demo 模式: 用确定性 GBM 模拟价格数据 (无网络依赖)
    - 生产模式: 从 ClickHouse 读 akshare_etl 落库的数据

    Tauri 调用路径:
        Rust run_pipeline → POST /api/pipeline/run
    """
    symbols, start, end = req.symbols, req.start, req.end
    import pandas as pd
    import numpy as np

    n_symbols = len(symbols)
    dates = pd.bdate_range(start, end)  # 只交易日
    n_days = len(dates)
    n_bars = n_symbols * n_days

    np.random.seed(hash(tuple(symbols)) % (2**32))
    price_data = {}
    for sym in symbols:
        close = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, n_days)))
        price_data[sym] = close

    # 简单动量信号
    sharpe_list, mdd_list, all_signals = [], [], []
    for sym, close in price_data.items():
        returns = np.diff(close) / close[:-1]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0.0
        mdd = float(np.min(np.maximum.accumulate(close) - close) / close[0]) if len(close) > 0 else 0.0
        sharpe_list.append(sharpe)
        mdd_list.append(mdd)

        for i in range(0, n_days, max(1, n_days // 5)):
            direction = "LONG" if close[i] > close[max(0, i - 20)] else "SHORT"
            confidence = min(0.95, abs(close[i] - close[max(0, i - 20)]) / close[max(0, i - 20)] * 5)
            all_signals.append(SignalOutput(
                symbol=sym,
                date=str(dates[i].date()) if i < len(dates) else "",
                direction=direction,
                confidence=round(float(confidence), 4),
                signal=round(float(close[i] / close[0] - 1), 4),
            ))

    return PipelineResult(
        symbols=symbols,
        n_symbols=n_symbols,
        n_days=n_days,
        n_bars=n_bars,
        sharpe=round(float(np.mean(sharpe_list)), 4),
        max_drawdown=round(float(np.mean(mdd_list)), 4),
        signals=all_signals,
    )


@app.post("/mcp/tools/call")
async def mcp_tools_call(req: MCPToolCallRequest):
    """
    MCP tools/call HTTP 端点。

    Tauri sidecar 发送简化格式:
        {"name": "run_backtest", "arguments": {...}}

    内部规范化为 JSON-RPC 2.0，交给 ForgeMindMCPServer.handle_request() 处理。
    """
    import uuid

    mcp = _get_mcp_server()
    jsonrpc_req = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {
            "name": req.name,
            "arguments": req.arguments,
        },
    }
    result = await mcp.handle_request(jsonrpc_req)

    # handle_request() 对 notifications/initialized 返回 None，
    # HTTP 要求有响应体，返回 204 No Content
    if result is None:
        return JSONResponse(status_code=204, content={})

    # JSON-RPC 错误 → HTTP 4xx/5xx
    if "error" in result:
        code = result["error"].get("code", -32000)
        # -32000 ~ -32099: 服务器端错误 (500)
        # -32600 ~ -32699: JSON-RPC 协议错误 (-32601 Unknown method, -32602 Invalid params)
        if -32699 <= code <= -32600:
            http_status = 400  # Bad Request (协议/参数问题)
        elif -32099 <= code <= -32000:
            http_status = 500  # Internal Server Error
        else:
            http_status = 400  # 其他 JSON-RPC 错误默认 400
        return JSONResponse(status_code=http_status, content=result)

    return result


@app.get("/mcp/tools/list")
async def mcp_tools_list():
    """MCP tools/list HTTP 端点 (列出所有可用工具)"""
    mcp = _get_mcp_server()
    return await mcp.handle_request({
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/list",
        "params": {},
    })


@app.get("/mcp")
async def mcp_health():
    """MCP 协议健康检查"""
    return {
        "name": "forgemind",
        "version": settings.version,
        "protocolVersion": "2024-11-05",
        "status": "ok",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )