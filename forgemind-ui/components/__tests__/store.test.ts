/**
 * Zustand store 单元测试 — 不需要 DOM
 */
import { useAppStore } from "../../lib/store";

describe("Zustand Store", () => {
  beforeEach(() => {
    // 重置 store(每次测试前)
    useAppStore.setState({
      currentSymbol: "600519.SH",
      klineData: [],
      signals: [],
      portfolio: [
        { symbol: "600519.SH", quantity: 100, avg_price: 1500, current_price: 1520 },
      ],
      cash: 80000,
      commandPaletteOpen: false,
      activeLayout: "default",
      pipelineRunning: false,
      pipelineResult: null,
    });
  });

  it("default state — currentSymbol = 600519.SH", () => {
    expect(useAppStore.getState().currentSymbol).toBe("600519.SH");
  });

  it("setCurrentSymbol updates state", () => {
    useAppStore.getState().setCurrentSymbol("000001.SZ");
    expect(useAppStore.getState().currentSymbol).toBe("000001.SZ");
  });

  it("addSignal prepends + caps at 100", () => {
    const { addSignal } = useAppStore.getState();
    for (let i = 0; i < 105; i++) {
      addSignal({
        signal_id: `sig-${i}`,
        symbol: "TEST",
        side: "BUY",
        confidence: 0.8,
        rationale: `reason ${i}`,
        timestamp: new Date().toISOString(),
      });
    }
    expect(useAppStore.getState().signals.length).toBe(100);
    expect(useAppStore.getState().signals[0].signal_id).toBe("sig-104");
  });

  it("clearSignals empties", () => {
    useAppStore.getState().addSignal({
      signal_id: "x",
      symbol: "X",
      side: "BUY",
      confidence: 0.5,
      rationale: "test",
      timestamp: "2026-01-01",
    });
    expect(useAppStore.getState().signals.length).toBe(1);
    useAppStore.getState().clearSignals();
    expect(useAppStore.getState().signals.length).toBe(0);
  });

  it("setActiveLayout switches", () => {
    useAppStore.getState().setActiveLayout("research");
    expect(useAppStore.getState().activeLayout).toBe("research");
    useAppStore.getState().setActiveLayout("trading");
    expect(useAppStore.getState().activeLayout).toBe("trading");
  });

  it("setCash updates cash", () => {
    useAppStore.getState().setCash(150000);
    expect(useAppStore.getState().cash).toBe(150000);
  });

  it("setPortfolio replaces portfolio", () => {
    const newPortfolio = [
      { symbol: "A.SH", quantity: 50, avg_price: 100, current_price: 110 },
    ];
    useAppStore.getState().setPortfolio(newPortfolio);
    expect(useAppStore.getState().portfolio).toEqual(newPortfolio);
  });

  it("commandPaletteOpen toggles", () => {
    expect(useAppStore.getState().commandPaletteOpen).toBe(false);
    useAppStore.getState().setCommandPaletteOpen(true);
    expect(useAppStore.getState().commandPaletteOpen).toBe(true);
  });

  it("pipelineRunning / pipelineResult", () => {
    useAppStore.getState().setPipelineRunning(true);
    expect(useAppStore.getState().pipelineRunning).toBe(true);
    
    useAppStore.getState().setPipelineResult({ sharpe: 1.5 });
    expect(useAppStore.getState().pipelineResult).toEqual({ sharpe: 1.5 });
  });
});