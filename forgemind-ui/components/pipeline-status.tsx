/**
 * PipelineStatus — 流水线状态条
 * 显示 OTel spans + Prometheus metrics 实时状态
 */
"use client";
import { useEffect, useState } from "react";
import { useAppStore } from "@/lib/store";
import type { BackendState } from "@/lib/backend";
import { call } from "@/lib/tauri";
import { cn } from "@/lib/utils";

const BACKEND_LABEL: Record<BackendState, { text: string; dot: string }> = {
  // 状态从 get_system_status 真拉
  // UI 在声明一个不存在的连接。
  unsupported: { text: "浏览器预览 · 无后端(桌面版才有真实数据)", dot: "bg-muted-foreground" },
  starting: { text: "正在启动 Python sidecar...", dot: "bg-yellow-500 animate-pulse" },
  ready: { text: "已连接 Python sidecar", dot: "bg-green-500" },
  failed: { text: "sidecar 启动失败 — 界面显示的是本地占位数据", dot: "bg-red-500" },
};

export function PipelineStatus({ backendState = "unsupported" }: { backendState?: BackendState }) {
  const pipelineRunning = useAppStore((s) => s.pipelineRunning);
  const factors = useAppStore((s) => s.factors);  // 真实因子数,来自 MCP resource
  const riskMetrics = useAppStore((s) => s.riskMetrics);  // 真实 Sharpe 来自 forgemind backtest
  const activeLayout = useAppStore((s) => s.activeLayout);
  const setActiveLayout = useAppStore((s) => s.setActiveLayout);
  // 拉真 version / duckdb_path,不写死版本号
  const [systemStatus, setSystemStatus] = useState<{ version?: string } | null>(null);
  useEffect(() => {
    void call<{ version?: string }>("get_system_status")
      .then((s) => setSystemStatus(s ?? null))
      .catch(() => undefined);
  }, []);

  return (
    <div className="flex items-center justify-between px-3 py-1 text-[11px]">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          <span className={cn(
            "h-2 w-2 rounded-full",
            pipelineRunning ? "bg-yellow-500 animate-pulse" : BACKEND_LABEL[backendState].dot
          )} />
          <span className="text-muted-foreground">
            {pipelineRunning ? "运行中..." : BACKEND_LABEL[backendState].text}
          </span>
        </div>

        {factors.length > 0 && (
          <div className="text-muted-foreground">·</div>
        )}
        {factors.length > 0 && (
          <div>因子: <b className="text-foreground">{factors.length}</b></div>
        )}
        {riskMetrics && (
          <>
            <div className="text-muted-foreground">·</div>
            <div>Sharpe: <b className="text-foreground">{
              riskMetrics.sharpe == null ? "—" : riskMetrics.sharpe.toFixed(2)
            }</b></div>
            <div className="text-muted-foreground">·</div>
            <div>n_trades: <b className="text-foreground">{riskMetrics.n_trades ?? "—"}</b></div>
          </>
        )}
      </div>

      <div className="flex items-center gap-2">
        <span className="text-muted-foreground">布局:</span>
        {["default", "research", "trading"].map((layout) => (
          <button
            key={layout}
            onClick={() => setActiveLayout(layout as any)}
            className={cn(
              "rounded px-2 py-0.5 text-[10px]",
              activeLayout === layout
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent"
            )}
          >
            {layout}
          </button>
        ))}
        <span className="text-muted-foreground ml-2">
          {systemStatus?.version ? `v${systemStatus.version}` : "v—"} · Tauri 2.x
        </span>
      </div>
    </div>
  );
}