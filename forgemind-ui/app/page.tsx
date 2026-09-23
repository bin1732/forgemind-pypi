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
import { useAppStore } from "@/lib/store";
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
        footer={<PipelineStatus />}
        activeLayout={activeLayout}
      />
      <CommandPalette />
    </main>
  );
}

function Header() {
  const currentSymbol = useAppStore((s) => s.currentSymbol);
  const setCurrentSymbol = useAppStore((s) => s.setCurrentSymbol);

  return (
    <header className="flex items-center justify-between px-4 py-2">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold">📊 ForgeMind</h1>
        <span className="rounded bg-primary/10 px-2 py-0.5 text-xs">v2026.09</span>
        <span className="text-xs text-muted-foreground">GitHub 头部级量化 Agent</span>
      </div>
      <div className="flex items-center gap-2">
        <select
          value={currentSymbol}
          onChange={(e) => setCurrentSymbol(e.target.value)}
          className="rounded border bg-background px-2 py-1 text-xs"
        >
          <option>600519.SH</option>
          <option>000001.SZ</option>
          <option>000333.SZ</option>
          <option>601318.SH</option>
          <option>300750.SZ</option>
        </select>
        <button className="rounded border bg-background px-3 py-1 text-xs hover:bg-accent">
          ⌘K 命令
        </button>
      </div>
    </header>
  );
}