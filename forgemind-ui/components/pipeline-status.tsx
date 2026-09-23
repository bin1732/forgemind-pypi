/**
 * PipelineStatus — 流水线状态条
 * 显示 OTel spans + Prometheus metrics 实时状态
 */
"use client";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/utils";

export function PipelineStatus() {
  const pipelineRunning = useAppStore((s) => s.pipelineRunning);
  const result = useAppStore((s) => s.pipelineResult);
  const activeLayout = useAppStore((s) => s.activeLayout);
  const setActiveLayout = useAppStore((s) => s.setActiveLayout);

  return (
    <div className="flex items-center justify-between px-3 py-1 text-[11px]">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          <span className={cn(
            "h-2 w-2 rounded-full",
            pipelineRunning ? "bg-yellow-500 animate-pulse" : "bg-green-500"
          )} />
          <span className="text-muted-foreground">
            {pipelineRunning ? "运行中..." : "已连接 · 6 服务在线"}
          </span>
        </div>

        {result && (
          <>
            <div className="text-muted-foreground">·</div>
            <div>因子: <b className="text-foreground">{result.n_factors_computed}</b></div>
            <div className="text-muted-foreground">·</div>
            <div>Sharpe: <b className="text-foreground">{result.sharpe?.toFixed(2)}</b></div>
            <div className="text-muted-foreground">·</div>
            <div>WFO OOS: <b className="text-foreground">{result.wfo_oos_sharpe?.toFixed(2)}</b></div>
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
        <span className="text-muted-foreground ml-2">v2026.09 · Tauri 2.x</span>
      </div>
    </div>
  );
}