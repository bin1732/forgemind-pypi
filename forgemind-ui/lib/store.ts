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

interface Signal {
  signal_id: string;
  symbol: string;
  side: "BUY" | "SELL" | "HOLD";
  confidence: number;
  rationale: string;
  timestamp: string;
}

interface PortfolioPosition {
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price: number;
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
  clearSignals: () => void;

  // 组合
  portfolio: PortfolioPosition[];
  setPortfolio: (p: PortfolioPosition[]) => void;
  cash: number;
  setCash: (c: number) => void;

  // UI
  commandPaletteOpen: boolean;
  setCommandPaletteOpen: (open: boolean) => void;
  activeLayout: "default" | "research" | "trading";
  setActiveLayout: (layout: "default" | "research" | "trading") => void;

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
      clearSignals: () => set({ signals: [] }),

      portfolio: [
        { symbol: "600519.SH", quantity: 100, avg_price: 1500, current_price: 1520 },
      ],
      setPortfolio: (portfolio) => set({ portfolio }),
      cash: 80000,
      setCash: (cash) => set({ cash }),

      commandPaletteOpen: false,
      setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
      activeLayout: "default",
      setActiveLayout: (activeLayout) => set({ activeLayout }),

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