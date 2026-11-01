/**
 * ForgeMind Desktop — 主页面
 * Tauri 2.x + Next.js 15 + React 19
 * 对标 OpenBB Workspace / Claude Desktop / TradingAgents Dashboard
 *
 * 3 种工作区布局:
 * - default: 行情 + Agent 决策 + Portfolio
 * - research: 因子库 + 研究日志 + 信号
 * - trading: K线 + 策略 + 信号表格
 */
"use client";
import { useEffect, useState } from "react";
import { useAppStore } from "@/lib/store";
import { useBackend, loadFactorIC } from "@/lib/backend";
import { call } from "@/lib/tauri";
import { WorkspaceLayout } from "@/components/workspace-layout";
import { KlineChart } from "@/components/kline-chart";
import { StrategyPanel } from "@/components/strategy-panel";
import { AgentDecisionPanel } from "@/components/agent-decision-panel";
import { CommandPalette } from "@/components/command-palette";
import { PortfolioPanel } from "@/components/portfolio-panel";
import { PipelineStatus } from "@/components/pipeline-status";
import { SignalTable } from "@/components/signal-table";
import { ResearchLog } from "@/components/research-log";
import { FactorGrid } from "@/components/factor-grid";

export default function HomePage() {
  const activeLayout = useAppStore((s) => s.activeLayout);
  // 挂载即连后端:启 sidecar → 等就绪 → 拉真实数据。
  // invoke() 接到真后端, 每个面板从 MCP resource 拉真数据
  const backend = useBackend();

  return (
    <main className="min-h-screen bg-background">
      <WorkspaceLayout
        header={<Header />}
        left={<StrategyPanel />}
        center={
          activeLayout === "research" ? (
            <div className="space-y-4 p-4">
              <FactorGrid />
              <ResearchLog />
            </div>
          ) : activeLayout === "trading" ? (
            <div className="space-y-4 p-4">
              <KlineChart />
              <SignalTable />
            </div>
          ) : (
            <div className="space-y-4 p-4">
              <KlineChart />
              <AgentDecisionPanel />
              <SignalTable />
            </div>
          )
        }
        right={
          activeLayout === "research" ? (
            <PortfolioPanel />
          ) : (
            <PortfolioPanel />
          )
        }
        footer={<PipelineStatus backendState={backend} />}
        activeLayout={activeLayout}
      />
      <CommandPalette />
    </main>
  );
}

function Header() {
  const currentSymbol = useAppStore((s) => s.currentSymbol);
  const setCurrentSymbol = useAppStore((s) => s.setCurrentSymbol);
  const symbols = useAppStore((s) => s.symbols);
  const backend = useBackend();  // 拿真 version
  // get_system_status 返回的字段名必须与 Rust 侧写进返回值的一致。
  // Rust 那边写的是 app_version —— 之前这里读 version,两边对不上,
  // 真桌面端的版本号就一直停在 "v—"。改成按后端真有的字段取。
  const [systemStatus, setSystemStatus] = useState<{
    app_version?: string;
    tauri_version?: string;
    python_sidecar_running?: boolean;
  } | null>(null);
  useEffect(() => {
    // 拉一次 get_system_status 拿真 version
    void call<{
      app_version?: string;
      tauri_version?: string;
      python_sidecar_running?: boolean;
    }>("get_system_status")
      .then((s) => setSystemStatus(s))
      .catch(() => undefined);
  }, [backend]);

  return (
    <header className="flex items-center justify-between px-4 py-2">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold">📊 ForgeMind</h1>
        <span className="rounded bg-primary/10 px-2 py-0.5 text-xs">
          {systemStatus?.app_version ? `v${systemStatus.app_version}` : "v—"}
        </span>
        <span className="text-xs text-muted-foreground">GitHub 头部级量化 Agent</span>
      </div>
      <div className="flex items-center gap-2">
        <select
          value={currentSymbol}
          onChange={(e) => {
            const sym = e.target.value;
            setCurrentSymbol(sym);
            void loadFactorIC(sym);
          }}
          className="rounded border bg-background px-2 py-1 text-xs"
        >
          {/* 标的候选从 DuckDB kline_daily 真 ETL 过的 distinct 派生
              来自 forgemind://symbols MCP resource (DuckDB kline_daily 真 ETL 过的 distinct)
              切到一个不在 DuckDB 的会让 K 线面板说 "暂无数据",体验糟。
              fallback 显示当前选中的 + 600519.SH,确保即使 DuckDB 是空的也能选中。 */}
          {Array.from(new Set([
            currentSymbol,
            "600519.SH",
            ...symbols,
          ])).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <button className="rounded border bg-background px-3 py-1 text-xs hover:bg-accent">
          ⌘K 命令
        </button>
      </div>
    </header>
  );
}