"use client";
/**
 * 把 Rust/Python 后端接进 store
 *
 * 挂载时:启 sidecar → 等 ready → 拉系统状态 → 拉真实持仓
 * 接 forgemind.api.main 真后端: query_portfolio / MCP / DuckDB
 */
import { useEffect, useState } from "react";
import { call, mcpTool, on, isTauri, readResource } from "@/lib/tauri";
import { useAppStore, type FactorMeta, type PortfolioPosition, type AgentDecision, type RiskMetrics, type Signal } from "@/lib/store";

/** 记下取数失败的原因。模块级函数拿不到 hook,直接从 store 取。 */
function noteDataError(message: string) {
  useAppStore.getState().setDataError(message);
}

export type BackendState = "unsupported" | "starting" | "ready" | "failed";

export function useBackend(): BackendState {
  const [state, setState] = useState<BackendState>("unsupported");
  const setPortfolio = useAppStore((s) => s.setPortfolio);
  const setCash = useAppStore((s) => s.setCash);
  const setPipelineResult = useAppStore((s) => s.setPipelineResult);
  const setAgentDecisions = useAppStore((s) => s.setAgentDecisions);
  const setRiskMetrics = useAppStore((s) => s.setRiskMetrics);

  const setFactors = useAppStore((s) => s.setFactors);
  const setStrategies = useAppStore((s) => s.setStrategies);
  const setSymbols = useAppStore((s) => s.setSymbols);
  // 整个 signals 数组替换 —— 启动时从 MCP forgemind://signals 拉一次
  // MCP 返回全部落盘的信号,addSignal 适合追加;这里是一次性覆盖
  // 注意: 不能在 render 体内 inline 写 (s) => setState({...}) 那样
  // 每次 render 都生成新函数,作为 useEffect deps 会**每次 render 都重跑**
  // useEffect,把 loadFactorIC 调 N 次 — 切 symbol 后 next render 又跑
  // → 出现"切 000001 → 调 2 次 / 切回 600519 → 又调 1 次 stale 000001"的串扰。
  const setSignals = useAppStore((s) => s.setSignals);
  const setBackendState = useAppStore((s) => s.setBackendState);
  const currentSymbol = useAppStore((s) => s.currentSymbol);

  useEffect(() => {
    if (!isTauri()) {
      // 浏览器里跑(Next dev / 静态导出):没有后端,如实说明而不是假装正常
      setState("unsupported");
      return;
    }
    let cancelled = false;
    (async () => {
      setState("starting");
      try {
        // Rust 侧会 emit("python-sidecar-ready"),但先主动查一次状态,
        // 避免错过已就绪的情况
        // 关窗/卸载时停掉 sidecar。不接 stop_python_sidecar 的话,
        // Python 进程会变成孤儿并一直占着 data/duckdb/main.db 的写锁 ——
        // 之后用户再跑 `forgemind etl` 就会撞上 storage_locked。
        const stopOnLeave = () => {
          void call("stop_python_sidecar");
        };
        window.addEventListener("beforeunload", stopOnLeave);
        const un = await on("python-sidecar-ready", () => {
          if (!cancelled) setState("ready");
          void refreshPortfolio(setPortfolio, setCash, setPipelineResult, setAgentDecisions, setRiskMetrics);
          void loadCatalog(setFactors, setStrategies, setSymbols);
          void loadSignals(setSignals);
          // 读最新 currentSymbol (避免 stale 闭包: 切 symbol 期间重跑 useEffect
          void loadFactorIC(useAppStore.getState().currentSymbol);
        });
        await call("start_python_sidecar");
        const status = await call<Record<string, unknown>>("get_system_status");
        if (cancelled) return;
        if (status) {
          setState("ready");
          await refreshPortfolio(setPortfolio, setCash, setPipelineResult, setAgentDecisions, setRiskMetrics);
          await loadCatalog(setFactors, setStrategies, setSymbols);
          await loadSignals(setSignals);
          // 后台算所有因子 IC (5-10s, 不 await — 让 UI 先 ready 显示)
          // 读最新 currentSymbol 而非闭包,避免 setCurrentSymbol 之后 useEffect 重跑
          // 仍然传旧值的 stale 闭包问题
          void loadFactorIC(useAppStore.getState().currentSymbol);
        }
        return () => {
          window.removeEventListener("beforeunload", stopOnLeave);
          un();
        };
      } catch (e) {
        if (!cancelled) setState("failed");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setPortfolio, setCash, setPipelineResult, setAgentDecisions, setRiskMetrics, setFactors, setStrategies, setSymbols, setSignals]);

  return state;
}

/**
 * 重新读一次组合、决策与风险指标。
 *
 * 拍板之后要用:决策落库了,面板上还挂着上一次组合 —— 界面看着正常,
 * 数据却是旧的,用户会以为刚才那次批准没生效。
 */
export async function reloadPortfolio(): Promise<void> {
  const s = useAppStore.getState();
  await refreshPortfolio(
    s.setPortfolio,
    s.setCash,
    s.setPipelineResult,
    s.setAgentDecisions,
    s.setRiskMetrics,
  );
}

async function refreshPortfolio(
  setPortfolio: (p: PortfolioPosition[]) => void,
  setCash: (c: number | null) => void,
  setPipelineResult: (r: unknown) => void,
  setAgentDecisions: (d: AgentDecision[]) => void,
  setRiskMetrics: (m: RiskMetrics | null) => void,
) {
  let raw: Record<string, unknown> | null = null;
  try {
    raw = await mcpTool<Record<string, unknown>>("query_portfolio");
  } catch (e) {
    // 工具失败会把原因带回来(后端连不上、工具报错都在里面)。
    // 直接抛出去的话,界面只会是一片空白,看不出发生了什么。
    noteDataError(`取组合数据失败:${e instanceof Error ? e.message : String(e)}`);
    return;
  }
  if (!raw) {
    noteDataError("取不到组合数据:后端没有返回结果");
    return;
  }
  // mcpTool 返 JSON-RPC wrapper {result:{content:[{text}]}}, 解二次 JSON
  const inner = (raw as { result?: { content?: Array<{ text?: string }> } })
                  ?.result?.content?.[0]?.text;
  let snap: Record<string, unknown> = raw as Record<string, unknown>;
  if (inner) {
    try { snap = JSON.parse(inner); }
    catch {
      noteDataError("组合数据不是可解析的 JSON,后端可能报错了");
      return;
    }
  } else if (!(raw as { status?: string }).status) {
    noteDataError("组合数据没有内容,后端可能还没就绪");
    return;
  }
  // 用户会以为那就是自己的账户
  // query_portfolio 的 positions 形状与 store 的 PortfolioPosition 对齐;
  // current_price 不在 MCP 返回里 —— 用最近一次 backtest 落盘时的 last_close
  // 或留 0 让 UI 显示均价(PnL=0),绝不编造。
  const rawPositions = (snap.positions ?? []) as Array<{
    symbol: string; quantity: number; avg_price: number; unrealized_pnl?: number;
  }>;
  const positions: PortfolioPosition[] = rawPositions.map((p) => ({
    symbol: p.symbol,
    quantity: p.quantity,
    avg_price: p.avg_price,
    current_price: p.avg_price,  // UI 用 avg_price 暂代,直到有真实行情喂入
  }));
  setPortfolio(positions);
  // 后端没给现金 = 还没有组合快照,置成"不知道"(null),不要留 0 ——
  // 面板会把 0 渲染成 ¥0,读的人以为这是个空组合。
  setCash(typeof snap.cash === "number" ? snap.cash : null);
  if (snap) setPipelineResult(snap);

  const decisions = (snap.decisions ?? []) as AgentDecision[];
  setAgentDecisions(decisions);

  setRiskMetrics((snap.risk_metrics ?? null) as RiskMetrics | null);
}

/** 从 MCP resource 拉真实的因子与策略清单
 *
 * factor-grid / research-log 从 MCP resource 拉真数据
 * 硬编码日志、strategy-panel 显示硬编码策略。三个面板都在展示编造的内容,
 * 而且 factor-grid 还写死了 "(6 / 166 预览)" —— 真实数量早已是 169。
 */
async function loadCatalog(
  setFactors: (f: FactorMeta[]) => void,
  setStrategies: (s: { name: string; kind: string }[]) => void,
  setSymbols: (symbols: string[]) => void,
) {
  const feats = await readResource<{
    total: number;
    breakdown: Record<string, number>;
    factors: FactorMeta[];
  }>("forgemind://features");
  if (feats?.factors?.length) setFactors(feats.factors);

  const strats = await readResource<{
    count: number;
    strategies: { name: string; kind: string }[];
  }>("forgemind://strategies");
  if (strats?.strategies?.length) setStrategies(strats.strategies);

  // 已 ETL 过的标的清单 —— 桌面 header <select> 用这个派生候选
  // 标的会让 K 线面板说"暂无数据",体验糟。现在每次 ETL 后自动出现
  const syms = await readResource<{
    total: number;
    symbols: string[];
  }>("forgemind://symbols");
  if (syms?.symbols?.length) setSymbols(syms.symbols);
}

/** 批量算所有因子 IC — 给 factor-grid 面板显示真 IC 值

factor-grid 的 IC 字段从 list_factor_ic MCP tool 真算
只返 name + category,不算 IC。现在加 list_factor_ic tool, 启动后后台
算一次,写到 store.factors[].ic,面板直接显示。100 因子约 8s,放到后台
跑,期间面板显示 "IC: 计算中..." 而不是空白。

性能:
- 后端 100 因子 ~8s (真算 IC 需要加载 K 线 + 算 alpha + 算 forward_returns)
- 169 全算会超过 15s, 当前截到 100, 后续可改成并发池 + cache
*/
// 因子 IC 缓存: 同 symbol 切回不重算 (100 因子 ~8s 算期)
// cache 存 (ic_by_name map, 而不是合并后的 factors 列表) — 切换回
// 任何 symbol 都能 re-merge 进 store.factors (后者只有 metadata, 没 ic)
const _factorICByName = new Map<string, Record<string, { ic: number | null; icir: number | null }>>();

export async function loadFactorIC(symbol: string): Promise<void> {
  if (_factorICByName.has(symbol)) {
    mergeFactorICIntoStore(_factorICByName.get(symbol)!);
    useAppStore.getState().setFactorIcState("ready");
    return;
  }
  let raw: Record<string, unknown> | null = null;
  useAppStore.getState().setFactorIcState("loading");
  try {
    raw = await mcpTool<Record<string, unknown>>(
      "list_factor_ic", { symbol, window_days: 5 },
    );
  } catch (e) {
    noteDataError(`取因子 IC 失败:${e instanceof Error ? e.message : String(e)}`);
    useAppStore.getState().setFactorIcState("failed");
    return;
  }
  // mcpTool 返 JSON-RPC wrapper {result:{content:[{text}]}}, 解二次 JSON
  const inner = (raw as { result?: { content?: Array<{ text?: string }> } })
                  ?.result?.content?.[0]?.text;
  let r: {
    status: string;
    factors?: Array<{
      name: string;
      ic: number | null;
      icir: number | null;
      status: string;
    }>;
  };
  if (!raw) {
    // 工具返回空时不能再往下取 status —— raw 是 null,取属性会抛异常,
    // 异常一路冒出去,界面就只剩空白,连"取不到"都说不出来。
    noteDataError("取不到因子 IC 数据,后端没有返回结果");
    useAppStore.getState().setFactorIcState("failed");
    return;
  }
  if (inner) {
    try { r = JSON.parse(inner); }
    catch {
      noteDataError("因子 IC 数据不是可解析的 JSON,后端可能报错了");
      useAppStore.getState().setFactorIcState("failed");
      return;
    }
  } else if ((raw as { status?: string }).status) {
    r = raw as typeof r;
  } else {
    noteDataError("取不到因子 IC 数据,后端没有返回结果");
    useAppStore.getState().setFactorIcState("failed");
    return;
  }
  if (!r?.factors?.length) {
    useAppStore.getState().setFactorIcState("ready");
    return;
  }
  // cache 按 name 索引, 切 symbol 复用
  const byName: Record<string, { ic: number | null; icir: number | null }> = {};
  for (const f of r.factors) {
    byName[f.name] = { ic: f.ic, icir: f.icir };
  }
  _factorICByName.set(symbol, byName);
  mergeFactorICIntoStore(byName);
  useAppStore.getState().setFactorIcState("ready");
}

function mergeFactorICIntoStore(byName: Record<string, { ic: number | null; icir: number | null }>): void {
  useAppStore.setState((state) => ({
    factors: state.factors.map((f) => {
      const found = byName[f.name];
      if (!found) return f;
      return { ...f, ic: found.ic ?? undefined, icir: found.icir ?? undefined };
    }),
  }));
}

// 拉真信号落盘历史 (forgemind://signals MCP resource)
// 这个 helper 拉回 store.signals。
// 注意:MCP 返回 JSON 字符串包了一层 "..." (因为 _signal_catalog 返回 str),
// readResource 已经处理了二次 JSON 解析
export async function loadSignals(
  setSignals: (s: Signal[]) => void,
): Promise<void> {
  const resp = await readResource<{
    total: number;
    signals: Array<{
      signal_id: string;
      symbol: string;
      side: "BUY" | "SELL" | "HOLD";
      confidence: number;
      rationale: string;
      emitted_at: string;
      source: string;
    }>;
  }>("forgemind://signals");
  if (!resp?.signals) return;
  // MCP 落盘格式 → store Signal 格式 (compat: timestamp 用 emitted_at)
  const mapped: Signal[] = resp.signals.map((s) => ({
    signal_id: s.signal_id,
    symbol: s.symbol,
    side: s.side,
    confidence: s.confidence,
    rationale: s.rationale,
    timestamp: s.emitted_at,
    emitted_at: s.emitted_at,
  }));
  setSignals(mapped);
}

// readResource 由 lib/tauri.ts 提供,走 Rust 的 read_mcp_resource command。
// 早先这里调的是一个并不存在的 MCP 工具 "__read_resource__"。

/** 跑一次真实 pipeline(Rust command) */
export async function runPipeline(symbols: string[], start: string, end: string) {
  const setRunning = useAppStore.getState().setPipelineRunning;
  const setResult = useAppStore.getState().setPipelineResult;
  setRunning(true);
  try {
    const r = await call<unknown>("run_pipeline", { symbols, start, end });
    setResult(r);
    return r;
  } finally {
    setRunning(false);
  }
}
