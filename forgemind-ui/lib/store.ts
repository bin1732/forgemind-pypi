/**
 * Zustand 全局状态管理
 * 对标 OpenBB Workspace / TradingAgents Dashboard
 */
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface KlineData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Signal {
  signal_id: string;
  symbol: string;
  side: "BUY" | "SELL" | "HOLD";
  confidence: number;
  rationale: string;
  timestamp: string;
  /** 真落盘时间,DuckDB emitted_at,可显示"5 分钟前"之类 */
  emitted_at?: string;
}

export interface FactorMeta {
  name: string;
  feature_id?: string;
  category: string;
  /** IC 由 check_ic_decay 现算,目录里没有 —— 缺失时面板显示 "—" 而不是 0 */
  ic?: number;
}

export interface PortfolioPosition {
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price: number;
}

/** 单个 Agent 的投票 — 由 forgemind agent 落 portfolio_decision 表派生 */
export interface AgentDecision {
  agent: string;
  vote: "buy" | "sell" | "hold" | string | null;
  score: number | null;
  confidence: number | null;
  thesis: string | null;
  evidence: string | null;
}

/** 最近一次 backtest_run 的真实指标 — 由 forgemind backtest 落盘 */
export interface RiskMetrics {
  run_id: string;
  ran_at: string;
  symbol: string;
  strategy: string;
  total_return: number | null;
  sharpe: number | null;
  sortino: number | null;
  max_drawdown: number | null;
  win_rate: number | null;
  n_trades: number | null;
}

interface AppState {
  // 当前
  currentSymbol: string;
  setCurrentSymbol: (symbol: string) => void;

  // 数据
  klineData: KlineData[];
  setKlineData: (data: KlineData[]) => void;

  // 信号
  signals: Signal[];
  addSignal: (signal: Signal) => void;
  setSignals: (signals: Signal[]) => void;
  clearSignals: () => void;

  // 组合
  portfolio: PortfolioPosition[];
  setPortfolio: (p: PortfolioPosition[]) => void;
  cash: number;
  setCash: (c: number) => void;

  // 6 Agent 决策明细 — 来自 query_portfolio.decisions
  agentDecisions: AgentDecision[];
  setAgentDecisions: (d: AgentDecision[]) => void;

  // 持仓现价缓存 — KLineChart 拉成功后写入,portfolio-panel 用它算未实现 PnL
  currentPrices: Record<string, number>;
  setCurrentPrice: (symbol: string, price: number) => void;

  // 最近一次回测真实风险指标 — 来自 query_portfolio.risk_metrics
  riskMetrics: RiskMetrics | null;
  setRiskMetrics: (m: RiskMetrics | null) => void;

  // 待人工审批的 AI 决策 —— 决策准备跑完停在审批前,拍板后才有 pm_decision。
  // thread_id 是拍板的凭据:没有它就批准不了,PM 节点也不会跑。
  pendingAgentDecision: {
    threadId: string;
    symbol: string;
    bullThesis: string;
    bearThesis: string;
  } | null;
  setPendingAgentDecision: (d: {
    threadId: string;
    symbol: string;
    bullThesis: string;
    bearThesis: string;
  } | null) => void;

  // UI
  commandPaletteOpen: boolean;
  setCommandPaletteOpen: (open: boolean) => void;
  activeLayout: "default" | "research" | "trading";
  setActiveLayout: (layout: "default" | "research" | "trading") => void;

  // 因子目录 —— 由 MCP resource forgemind://features 派生,不是本地常量
  factors: FactorMeta[];
  setFactors: (factors: FactorMeta[]) => void;
  factorsLoaded: boolean;

  // 因子 IC 的计算状态
  //
  // IC 是现算的(169 个因子要跑 5-10 秒),算完才写进 factors。
  // 算之前 factors 里的 ic 全是 undefined —— 那不是"这些因子没有 IC",
  // 是"还没算出来"。没有这个状态,整个因子库会在计算期间显示成一片
  // "无数据",用户会以为真没有。
  factorIcState: "idle" | "loading" | "ready" | "failed";
  setFactorIcState: (state: "idle" | "loading" | "ready" | "failed") => void;

  // 策略清单 —— 由 forgemind://strategies 派生
  strategies: { name: string; kind: string }[];
  setStrategies: (strategies: { name: string; kind: string }[]) => void;

  // 已 ETL 过的标的清单 —— 由 forgemind://symbols 派生(DuckDB kline_daily 真 distinct)
  symbols: string[];
  setSymbols: (symbols: string[]) => void;
  strategiesLoaded: boolean;

  // 后端连接状态
  backendState: "unsupported" | "starting" | "ready" | "failed";
  setBackendState: (s: AppState["backendState"]) => void;

  // 取数失败的原因。空界面有两种:"确实没有数据"与"取不到数据"——
  // 不区分开,用户会以为自己没数据,其实是后端连不上或者工具报错了。
  // 这里记下原因,让界面能如实说出来,而不是一律显示"暂无数据"。
  dataError: string | null;
  setDataError: (message: string | null) => void;

  // Pipeline 状态
  pipelineRunning: boolean;
  setPipelineRunning: (running: boolean) => void;
  pipelineResult: any;
  setPipelineResult: (result: any) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      currentSymbol: "600519.SH",
      setCurrentSymbol: (symbol) => set({ currentSymbol: symbol }),

      klineData: [],
      setKlineData: (data) => set({ klineData: data }),

      signals: [],
      addSignal: (signal) => set((state) => ({ signals: [signal, ...state.signals].slice(0, 100) })),
      setSignals: (signals) => set({ signals }),
      clearSignals: () => set({ signals: [] }),

      portfolio: [],
      setPortfolio: (portfolio) => set({ portfolio }),
      cash: 0,
      setCash: (cash) => set({ cash }),

      agentDecisions: [],
      setAgentDecisions: (agentDecisions) => set({ agentDecisions }),

      currentPrices: {},
      setCurrentPrice: (symbol, price) =>
        set((state) => ({ currentPrices: { ...state.currentPrices, [symbol]: price } })),

      riskMetrics: null,
      setRiskMetrics: (riskMetrics) => set({ riskMetrics }),

      pendingAgentDecision: null,
      setPendingAgentDecision: (pendingAgentDecision) => set({ pendingAgentDecision }),

      commandPaletteOpen: false,
      setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
      activeLayout: "default",
      setActiveLayout: (activeLayout) => set({ activeLayout }),

      factors: [],
      setFactors: (factors) => set({ factors, factorsLoaded: true }),
      factorsLoaded: false,

      factorIcState: "idle",
      setFactorIcState: (factorIcState) => set({ factorIcState }),

      strategies: [],
      setStrategies: (strategies) => set({ strategies, strategiesLoaded: true }),
      strategiesLoaded: false,

      symbols: [],
      setSymbols: (symbols) => set({ symbols }),

      backendState: "unsupported",
      setBackendState: (backendState) => set({ backendState }),
      dataError: null,
      setDataError: (dataError) => set({ dataError }),

      pipelineRunning: false,
      setPipelineRunning: (pipelineRunning) => set({ pipelineRunning }),
      pipelineResult: null,
      setPipelineResult: (pipelineResult) => set({ pipelineResult }),
    }),
    {
      name: "forgemind-store",
      storage: createJSONStorage(() => (typeof window !== "undefined" ? localStorage : (undefined as any))),
    }
  )
);