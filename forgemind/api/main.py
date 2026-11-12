# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
ForgeMind FastAPI 应用入口
"""

import asyncio  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from datetime import datetime  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field, field_validator  # noqa: E402

from forgemind.core.agents.portfolio_context import (  # noqa: E402
    PortfolioContext,
    PortfolioPosition,
    resume_decision,
    run_decision,
)
from forgemind.core.backtest.engine import SimpleBacktestEngine  # noqa: E402
from forgemind.core.config.settings import get_settings  # noqa: E402
from forgemind.core.observability.logging import (  # noqa: E402
    ForgeMindError,
    get_logger,
    setup_logging,
)
from forgemind.core.strategies.base import MovingAverageCrossStrategy  # noqa: E402

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
    # 桌面 webview 通过 IPC,无 CORS 限制;但允许浏览器端调试需要 CORS。
    # 不用 cookie,allow_credentials=False 让 allow_origins="*" 合法
    allow_origins=settings.api_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== API Key Auth Middleware =====
from fastapi import HTTPException, Request  # noqa: E402

PUBLIC_PATHS = {
    "/health",
    "/api/v1/info",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/mcp",  # MCP 协议端点 (桌面端本地调用)
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
    symbol: str = Field(default="600519.SH", min_length=1, max_length=20, description="股票代码")
    start_date: str = Field(description="开始日期 YYYY-MM-DD")
    end_date: str = Field(description="结束日期 YYYY-MM-DD")
    fast_period: int = Field(default=5, ge=2, le=200)
    slow_period: int = Field(default=20, ge=5, le=500)
    initial_capital: float = Field(default=100_000.0, gt=0)

    @field_validator("start_date", "end_date")
    @classmethod
    def _validate_date(cls, v: str) -> str:
        try:
            from datetime import datetime

            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"日期格式错误: '{v}',应为 YYYY-MM-DD") from None
        return v

    @field_validator("end_date")
    @classmethod
    def _validate_date_range(cls, v: str, info) -> str:
        # info.data contains previously validated fields
        start = info.data.get("start_date")
        if start:
            from datetime import datetime

            s = datetime.strptime(start, "%Y-%m-%d")
            e = datetime.strptime(v, "%Y-%m-%d")
            if e <= s:
                raise ValueError(f"end_date ({v}) 必须晚于 start_date ({start})")
            if (e - s).days > 365 * 10:
                raise ValueError(f"日期范围不能超过 10 年 ({(e - s).days} 天)")
        return v

    @field_validator("slow_period")
    @classmethod
    def _validate_periods(cls, v: int, info) -> int:
        fast = info.data.get("fast_period")
        if fast and v <= fast:
            raise ValueError(f"slow_period ({v}) 必须大于 fast_period ({fast})")
        return v


class BacktestResponse(BaseModel):
    total_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    n_trades: int
    params: dict
    #: 行情来源。落盘数据优先,取不到才降级为合成行情。
    #: 不标出来的话,调用方会把这些数字当成真实回测结果 —— 换个种子就变。
    data_source: str = "synthetic_random_walk"
    is_real_data: bool = False
    n_bars: int = 0
    warning: str = (
        "本次使用随机生成的合成行情,非真实市场数据。结果仅用于验证链路可用,不是真实回测。"
    )


def _load_backtest_prices(symbol: str, start: str, end: str):
    """取回测要用的行情:优先用 DuckDB 里已落盘的真实 K 线。

    与命令行、MCP 工具走同一条路径(同一套代码归一化与降级口径):
    库里存的是 6 位代码,入参常带交易所后缀,归一化放在查询参数里,
    任何上游传 '600519.SH' 都能命中。

    Returns:
        (price_df 或 None, data_source, n_bars, 降级原因)
    """
    import pandas as pd

    from forgemind.core.data.storage import (
        DuckDBStorage,
        bare_symbol,
        market_data_unavailable_reason,
        market_data_unreadable_reason,
    )

    try:
        with DuckDBStorage() as db:
            found = db.query_df(
                "SELECT date, open, high, low, close, volume "
                "FROM kline_daily WHERE symbol = ? "
                "AND date BETWEEN ? AND ? ORDER BY date ASC",
                [bare_symbol(symbol), start, end],
            )
    except Exception:
        # 表还没建(没跑过 forgemind etl)或 schema 异常 —— 走降级路径。
        # 异常类型名不进响应:它是内部实现,写出去读的人只会以为程序坏了。
        return None, "synthetic_random_walk", 0, market_data_unreadable_reason()
    if found is None or found.empty:
        return None, "synthetic_random_walk", 0, market_data_unavailable_reason(symbol)
    frame = found.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.set_index("date").sort_index()
    frame.index.name = "date"
    frame["symbol"] = symbol
    return frame, "duckdb_kline_daily", len(frame), ""


@app.post("/api/v1/backtest/run", response_model=BacktestResponse)
async def run_backtest(req: BacktestRequest):
    """
    跑一个双均线回测

    行情优先取 DuckDB 里已落盘的真实 K 线(与命令行、MCP 工具同一条路径);
    库里没有该标的的数据时降级为合成行情,响应里的 data_source /
    is_real_data / warning 三个字段显式标注,避免被当作真实回测结果。
    """
    import numpy as np
    import pandas as pd

    try:
        price_df, data_source, n_bars, fallback_reason = _load_backtest_prices(
            req.symbol,
            req.start_date,
            req.end_date,
        )
        if price_df is None:
            dates = pd.date_range(req.start_date, req.end_date, freq="D")
            n = len(dates)
            np.random.seed(42)
            close = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, n)))
            price_df = pd.DataFrame(
                {
                    "open": close * (1 + np.random.normal(0, 0.005, n)),
                    "high": close * (1 + np.abs(np.random.normal(0, 0.01, n))),
                    "low": close * (1 - np.abs(np.random.normal(0, 0.01, n))),
                    "close": close,
                    "volume": np.random.randint(1_000_000, 10_000_000, n),
                },
                index=dates,
            )
            n_bars = n
        strategy = MovingAverageCrossStrategy(
            parameters={"fast_period": req.fast_period, "slow_period": req.slow_period}
        )
        engine = SimpleBacktestEngine(initial_capital=req.initial_capital)
        result = engine.run(strategy, price_df, symbol=req.symbol)
        is_real = data_source == "duckdb_kline_daily"
        if is_real:
            warning = ""
        else:
            warning = (
                f"本次使用随机生成的合成行情,非真实市场数据"
                f"({fallback_reason})。结果仅用于验证链路可用,不是真实回测。"
            )
        return BacktestResponse(
            total_return=result.total_return,
            sharpe=result.sharpe,
            max_drawdown=result.max_drawdown,
            win_rate=result.win_rate,
            n_trades=result.n_trades,
            params=result.params,
            data_source=data_source,
            is_real_data=is_real,
            n_bars=n_bars,
            warning=warning,
        )
    except Exception as e:
        logger.exception("backtest_failed", symbol=req.symbol)
        # 异常类型名留在日志里;响应里只说人话 —— 读者看到
        # "ValueError" 只以为程序坏了,而程序没坏。
        raise HTTPException(status_code=500, detail="回测失败,详情见服务日志") from e


class AgentRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    cash: float = Field(default=100_000.0, gt=0)
    total_equity: float = Field(default=100_000.0, gt=0)
    positions: list[dict] = Field(default_factory=list, max_length=100)


class AgentResponse(BaseModel):
    decision: dict
    confidence: float
    requires_human_review: bool
    reasoning: str


class AgentPrepareResponse(BaseModel):
    """prepare 阶段返回:决策停在 PM 之前,需要人工审批"""

    thread_id: str
    status: str  # "PENDING_HUMAN_REVIEW"
    bull_thesis: str
    bear_thesis: str
    confidence: float
    requires_human_review: bool = True
    reasoning: str


class AgentApprovalRequest(BaseModel):
    reviewer: str | None = None
    notes: str | None = None


class AgentApprovalResponse(BaseModel):
    thread_id: str
    approved: bool
    pm_decision: dict | None
    requires_human_review: bool
    reasoning: str
    # 落库结果:组合快照与 6 条决策明细写没写成。桌面端据此显示"已落盘"
    # 还是"落盘失败"(error 里有原因),不假装写成了。
    persisted: dict | None = None


@app.post("/api/v1/agent/decide", response_model=AgentPrepareResponse)
async def agent_decide(req: AgentRequest):
    """
    跑 AI 决策准备(LangGraph 3-Agent Harness)

    这是 prepare 阶段,只跑到 PM 节点前停下。返回 thread_id;
    真正拍板必须 POST /api/v1/agent/{thread_id}/approve 或 /reject。

    流程:
      1. /decide           → 返回 thread_id + status=PENDING_HUMAN_REVIEW
      2. /approve 或 /reject → 用同一 thread_id 拍板
    """
    portfolio = PortfolioContext(
        cash=req.cash,
        total_equity=req.total_equity,
        positions=[PortfolioPosition(**p) for p in req.positions],
    )

    state = await run_decision(
        symbol=req.symbol,
        as_of=datetime.now(),
        portfolio=portfolio,
    )
    thread_id = state.get("thread_id", "unknown")

    bull = state.get("bull_case", {}) or {}
    bear = state.get("bear_case", {}) or {}
    return AgentPrepareResponse(
        thread_id=thread_id,
        status="PENDING_HUMAN_REVIEW",
        bull_thesis=bull.get("thesis", ""),
        bear_thesis=bear.get("thesis", ""),
        confidence=state.get("confidence", 0.0),
        reasoning=(
            "PM 节点被 interrupt_before 拦住 — 任何交易动作(下单/调仓)"
            "必须先 POST /api/v1/agent/{thread_id}/approve 或 /reject"
        ),
    )


@app.post("/api/v1/agent/{thread_id}/approve", response_model=AgentApprovalResponse)
async def agent_approve(thread_id: str, req: AgentApprovalRequest):
    """人工审批通过 — 真正让 PM 节点跑完"""
    try:
        final = await resume_decision(
            thread_id=thread_id,
            approved=True,
            reviewer=req.reviewer,
            notes=req.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return AgentApprovalResponse(
        thread_id=thread_id,
        approved=True,
        pm_decision=final.get("pm_decision"),
        requires_human_review=False,
        reasoning=(final.get("decision_event", {}) or {}).get("reasoning", ""),
        persisted=final.get("persisted"),
    )


@app.post("/api/v1/agent/{thread_id}/reject", response_model=AgentApprovalResponse)
async def agent_reject(thread_id: str, req: AgentApprovalRequest):
    """人工拒绝 — 不跑 PM,记 decision_log 为 REJECTED"""
    try:
        await resume_decision(
            thread_id=thread_id,
            approved=False,
            reviewer=req.reviewer,
            notes=req.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return AgentApprovalResponse(
        thread_id=thread_id,
        approved=False,
        pm_decision=None,
        requires_human_review=False,
        reasoning="rejected — see decision log",
    )


# ===== Feature Store =====
@app.get("/api/v1/features/search")
async def search_features(query: str, limit: int = 10):
    """搜索因子 — 真实因子库搜索"""
    from forgemind.core.factors import factor_count, get_all_factors

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
    from forgemind.core.factors import factor_count, get_all_factors

    all_factors = get_all_factors()
    return {
        "total": factor_count(),
        "factors": [{"feature_id": f"feat-{f}", "feature_name": f} for f in all_factors[:limit]],
    }


# ===== Health for individual services =====
def _classify_error(e: Exception) -> str:
    """分类错误 — 不暴露敏感信息(密码/IP/路径)"""
    name = type(e).__name__
    msg = str(e)
    # 仅保留安全的错误类别,去掉敏感细节
    if "Connection" in name or "Connect" in msg:
        return "unreachable"
    if "Authentication" in name or "password" in msg.lower():
        return "auth_failed"
    if "timeout" in msg.lower() or "Timeout" in name:
        return "timeout"
    if "No module" in msg:
        return "driver_missing"
    return "error"


@app.get("/api/v1/health/services")
async def services_health():
    """各服务健康检查 — 仅返回状态,不暴露敏感信息"""
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
        services["clickhouse"] = _classify_error(e)

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
        services["postgresql"] = _classify_error(e)

    # Redis/Valkey
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()  # aclose for async
        services["redis"] = "ok"
    except Exception as e:
        services["redis"] = _classify_error(e)

    # NATS
    # nats-py 2.x 会在后台起重连任务;若不吞掉其异常,任务会在事件循环收尾时
    # 逃逸出 except,把整个 /health/services 打成 500。这里用 error_cb 兜底 + 硬超时。
    try:
        import nats

        async def _nats_error_cb(_e: Exception) -> None:
            return None  # 健康检查不关心重连细节,吞掉以免逃逸

        nc = await asyncio.wait_for(
            nats.connect(settings.nats_url, connect_timeout=2, error_cb=_nats_error_cb),
            timeout=5,
        )
        try:
            await asyncio.wait_for(nc.flush(timeout=2), timeout=3)
            services["nats"] = "ok"
        finally:
            await nc.close()
    except TimeoutError:
        services["nats"] = "timeout"
    except Exception as e:
        services["nats"] = _classify_error(e)

    return services


# ===== MCP HTTP 端点 (供 Tauri 桌面端调用) =====
# Tauri sidecar: python -m forgemind.api.main --port 8008
# MCP over HTTP: Tauri 调用 /mcp/tools/call
# 复用 ForgeMindMCPServer 的 handle_request() 逻辑，支持 JSON-RPC 2.0

# 懒加载，避免循环导入
_mcp_server = None  # type: ignore # lazy-loaded MCP server


def _get_mcp_server():  # type: ignore # returns ForgeMindMCPServer
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
    """与 EndToEndPipeline 真实产出的信号字段一致

    输出字段格式: symbol/date/direction/confidence/signal,
    而 pipeline 真正产出的是 signal_id/symbol/side/confidence/rationale/timestamp。
    端点跑完真实 pipeline 之后,把结果里的 signals 丢掉、自己另算一套
    "简单动量信号"返回 —— 于是 response_model 用默认值把 confidence 和
    signal 填成了 0.0,看起来完全正常,实际与刚跑完的计算毫无关系。
    """

    model_config = ConfigDict(extra="allow")

    symbol: str
    side: str | None = None
    confidence: float | None = None
    rationale: str | None = None
    timestamp: str | None = None
    signal_id: str | None = None
    date: str | None = None
    direction: str | None = None
    signal: float | None = None


class PipelineResult(BaseModel):
    symbols: list[str]
    n_symbols: int
    n_days: int
    n_bars: int
    sharpe: float
    max_drawdown: float
    signals: list[SignalOutput]
    #: 数据来源标识。真实行情 = "etl_duckdb";模拟 = "synthetic_gbm"
    data_source: str = "unknown"
    #: 非空即说明这些数字**不是**真实市场结果
    warning: str | None = None


class PipelineRequest(BaseModel):
    symbols: list[str]
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

    n_symbols = len(symbols)
    dates = pd.bdate_range(start, end)  # 只交易日
    n_days = len(dates)
    n_bars = n_symbols * n_days

    # 跑一次真正的研究流水线,信号与指标都取它的产出。之前指标来自一段
    # 随机游走、信号来自流水线,两套数据混在一个响应里 —— 指标与信号说的
    # 不是同一件事。
    real_signals: list[dict] = []
    pipeline_note = ""
    pipeline_sharpe = 0.0
    pipeline_max_drawdown = 0.0
    try:
        from forgemind.core.pipeline import EndToEndPipeline

        pipe = EndToEndPipeline(
            symbols=symbols, start=start, end=end, data_source="mock", top_n_signals=5
        )
        pipe_result = await asyncio.to_thread(pipe.run)
        real_signals = list(pipe_result.signals or [])
        pipeline_sharpe = float(pipe_result.sharpe or 0.0)
        pipeline_max_drawdown = float(pipe_result.max_drawdown or 0.0)
        pipeline_note = f" · 研究流水线耗时 {getattr(pipe_result, 'duration_seconds', 0):.1f}s"
    except Exception as exc:  # noqa: BLE001
        # 流水线跑不了就如实说,不能静默回落到自造信号
        pipeline_note = " · 研究流水线未成功,signals 为空"
        logger.warning("pipeline_run_signals_failed", error=str(exc))

    return PipelineResult(
        symbols=symbols,
        n_symbols=n_symbols,
        n_days=n_days,
        n_bars=n_bars,
        sharpe=round(pipeline_sharpe, 4),
        max_drawdown=round(pipeline_max_drawdown, 4),
        # 真实研究流水线的信号。没有就是空列表 —— 不拿自造的占位信号充数
        signals=[SignalOutput(**s) for s in (real_signals or [])],
        data_source="synthetic_gbm",
        warning=(
            "本端点当前用确定性模拟行情,尚未接入真实行情;"
            "sharpe / max_drawdown 基于模拟数据,不代表任何标的的真实表现。"
            f"signals 来自 EndToEndPipeline{pipeline_note}。"
        ),
    )


@app.post("/mcp/tools/call")
async def mcp_tools_call(req: MCPToolCallRequest):
    """
    MCP tools/call 的 HTTP 适配层(给桌面端 sidecar 用)。

    Tauri sidecar 发送简化格式:
        {"name": "run_backtest", "arguments": {...}}

    内部规范化为 JSON-RPC 2.0，交给 ForgeMindMCPServer.handle_request() 处理。

    这不是 MCP 的标准 HTTP 传输:工具执行失败时按 sidecar 的约定返回
    HTTP 500,响应体里仍保留 JSON-RPC 的 isError 标记。接标准 MCP 客户端
    请走 stdio。
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

    # 工具执行失败按 MCP 规范放在 result 里并标 isError,协议层是对的。
    # 但这一层是给桌面端 sidecar 用的 HTTP 适配,那边靠状态码判断成败 ——
    # 不翻译的话,失败会被当成正常结果显示出来。
    if result.get("result", {}).get("isError") is True:
        return JSONResponse(status_code=500, content=result)

    return result


@app.get("/mcp/tools/list")
async def mcp_tools_list():
    """MCP tools/list HTTP 端点 (列出所有可用工具)"""
    mcp = _get_mcp_server()
    return await mcp.handle_request(
        {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/list",
            "params": {},
        }
    )


@app.get("/mcp/resources/list")
async def mcp_resources_list():
    """MCP `resources/list` HTTP 端点,返回 6 个内置资源 (features / strategies /
    symbols / signals / brokers / portfolio)。"""
    mcp = _get_mcp_server()
    return await mcp.handle_request(
        {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "resources/list",
            "params": {},
        }
    )


@app.get("/mcp/prompts/list")
async def mcp_prompts_list():
    """MCP prompts/list HTTP 端点 (列出所有可用提示模板)"""
    mcp = _get_mcp_server()
    return await mcp.handle_request(
        {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "prompts/list",
            "params": {},
        }
    )


class MCPResourceReadRequest(BaseModel):
    """MCP resources/read HTTP 请求格式"""

    uri: str = Field(..., description="要读取的资源 URI,如 forgemind://features")


@app.post("/mcp/resources/read")
async def mcp_resources_read(req: MCPResourceReadRequest):
    """MCP resources/read HTTP 端点。

    Tauri 桌面端通过 read_mcp_resource command 调用,这里把 URI 透传给
    ForgeMindMCPServer.handle_request(),统一 MCP over stdio 与 MCP over HTTP 两条路径。
    """
    import uuid

    mcp = _get_mcp_server()
    jsonrpc_req = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "resources/read",
        "params": {"uri": req.uri},
    }
    return await mcp.handle_request(jsonrpc_req)


@app.get("/mcp")
async def mcp_health():
    """MCP 协议健康检查"""
    return {
        "name": "forgemind",
        "version": settings.version,
        "protocolVersion": "2024-11-05",
        "status": "ok",
    }


def _serve() -> None:
    """以模块方式启动:`python -m forgemind.api.main --host H --port P`"""
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(prog="forgemind.api")
    parser.add_argument("--host", default=settings.api_host)
    parser.add_argument("--port", type=int, default=settings.api_port)
    parser.add_argument("--reload", action="store_true", help="开发用热重载")
    args = parser.parse_args()

    uvicorn.run(
        "forgemind.api.main:app",  # reload 需要 import string
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    _serve()
