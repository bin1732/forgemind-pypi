/**
 * StrategyPanel — 策略列表 + 启动/停止控制
 * 对标 Zipline / QuantConnect 的策略选择面板
 */
"use client";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { runPipeline } from "@/lib/backend";

interface Strategy {
  id: string;
  name: string;
  category: "momentum" | "mean_reversion" | "stat_arb" | "ml" | "event" | "portfolio";
  description: string;
  status: "running" | "stopped" | "paused";
  /** 策略清单(resource)里没有绩效数字 —— 没有就显示 "—",不编一个 */
  sharpe?: number;
  totalReturn?: number;
}

// 策略从 forgemind://strategies 真 resource 拉
// 真实清单由 MCP resource forgemind://strategies 提供,里面只有名字和类型,
// 没有绩效数字 —— 面板不编,显示 "—"。
//
// 状态一律 "stopped":清单不代表策略正在运行,声称 "running" 同样是编造。


const CATEGORY_COLORS = {
  momentum: "bg-blue-100 text-blue-700",
  mean_reversion: "bg-purple-100 text-purple-700",
  stat_arb: "bg-pink-100 text-pink-700",
  ml: "bg-orange-100 text-orange-700",
  event: "bg-yellow-100 text-yellow-700",
  portfolio: "bg-green-100 text-green-700",
};

const CATEGORY_LABELS = {
  momentum: "动量",
  mean_reversion: "均值回归",
  stat_arb: "统计套利",
  ml: "机器学习",
  event: "事件驱动",
  portfolio: "组合",
};

const STATUS_COLORS = {
  running: "bg-green-500",
  stopped: "bg-gray-400",
  paused: "bg-yellow-500",
};

export function StrategyPanel() {
  const registry = useAppStore((s) => s.strategies);
  const STRATEGIES: Strategy[] = registry.map((r) => ({
    id: r.name,
    name: r.name,
    category: inferCategory(r.name),
    // 命令行喂不了某些策略(多标的、要模型、要行情表里没有的列)。
    // 说清为什么,用户才知道这个策略不是坏了、而是这条命令用不了。
    description:
      r.cli_runnable === false
        ? `命令行跑不了:${r.unusable_reason ?? "原因未说明"}`
        : r.kind === "bar"
          ? "单标的策略"
          : "扩展策略",
    status: "stopped" as const,
  }));
  const [activeId, setActiveId] = useState<string>("lgbm_alpha");
  const setPipelineRunning = useAppStore((s) => s.setPipelineRunning);

  return (
    <div className="space-y-2">
      {STRATEGIES.length === 0 && (
        <div className="rounded border border-dashed p-4 text-center text-xs text-muted-foreground">
          策略清单未加载 —— 需要后端(MCP resource forgemind://strategies)可用
        </div>
      )}
      <div className="flex items-center justify-between border-b px-2 py-1">
        <h3 className="text-sm font-semibold">策略库</h3>
        <button
          className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground hover:bg-primary/90"
          onClick={() => {
            // 调 runPipeline (call 走真后端)
            // pipeline;接上 backend.runPipeline 真启动端到端流水线
            void runPipeline(
              ["600519.SH", "000001.SZ", "601318.SH"],
              "2026-08-01",
              "2026-10-10"
            );
          }}
        >
          + 新建
        </button>
      </div>

      <div className="space-y-1 px-2">
        {STRATEGIES.map((s) => (
          <button
            key={s.id}
            onClick={() => setActiveId(s.id)}
            className={cn(
              "w-full rounded border p-2 text-left text-xs transition-colors hover:bg-accent",
              activeId === s.id && "border-primary bg-accent"
            )}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className={cn("h-2 w-2 rounded-full", STATUS_COLORS[s.status])}
                />
                <span className="font-semibold">{s.name}</span>
              </div>
              <span
                className={cn(
                  "rounded px-1 text-[10px]",
                  CATEGORY_COLORS[s.category]
                )}
              >
                {CATEGORY_LABELS[s.category]}
              </span>
            </div>
            <div className="mt-1 text-[10px] text-muted-foreground">
              {s.description}
            </div>
            <div className="mt-1 flex justify-between text-[10px]">
              <span>Sharpe: <b>{s.sharpe === undefined ? "—" : s.sharpe.toFixed(2)}</b></span>
              <span>收益: <b>{s.totalReturn === undefined ? "—" : `${(s.totalReturn * 100).toFixed(1)}%`}</b></span>
            </div>
          </button>
        ))}
      </div>

      <div className="border-t px-2 py-1 text-[10px] text-muted-foreground">
        {/* 清单 N 个策略 · 未挂载运行 (注册表不等于运行实例),
            那个"0"看着像"想跑就能跑",实际是策略注册表静态快照。诚实化:
            显示"清单 X 个"+"未挂载运行"(更准确)。 */}
        清单 {STRATEGIES.length} 个策略 · 未挂载运行(注册表不等于运行实例)
      </div>
    </div>
  );
}

/** 按名字推断分类 —— 面板的分组需要,注册表里没有这一项 */
function inferCategory(name: string): Strategy["category"] {
  const n = name.toLowerCase();
  if (/momentum|tsmom|rotation/.test(n)) return "momentum";
  if (/reversion|ou|meanrev/.test(n)) return "mean_reversion";
  if (/pairs|stat|arb/.test(n)) return "stat_arb";
  if (/lightgbm|online|learning/.test(n)) return "ml";
  if (/earn|index|news/.test(n)) return "event";
  return "portfolio";
}
