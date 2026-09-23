/**
 * StrategyPanel — 策略列表 + 启动/停止控制
 * 对标 Zipline / QuantConnect 的策略选择面板
 */
"use client";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";

interface Strategy {
  id: string;
  name: string;
  category: "momentum" | "mean_reversion" | "stat_arb" | "ml" | "event" | "portfolio";
  description: string;
  status: "running" | "stopped" | "paused";
  sharpe: number;
  totalReturn: number;
}

const STRATEGIES: Strategy[] = [
  {
    id: "ma_cross",
    name: "双均线交叉",
    category: "momentum",
    description: "5 / 20 日均线金叉买入死叉卖出",
    status: "running",
    sharpe: 1.42,
    totalReturn: 0.18,
  },
  {
    id: "pairs",
    name: "配对交易",
    category: "stat_arb",
    description: "协整对 spread z-score ±2 入场",
    status: "stopped",
    sharpe: 0.87,
    totalReturn: 0.11,
  },
  {
    id: "lgbm_alpha",
    name: "LightGBM ML",
    category: "ml",
    description: "166 因子 + LightGBM 预测 top-K",
    status: "running",
    sharpe: 1.68,
    totalReturn: 0.27,
  },
  {
    id: "risk_parity",
    name: "风险平价组合",
    category: "portfolio",
    description: "每资产贡献相同风险(1/σ 加权)",
    status: "running",
    sharpe: 0.95,
    totalReturn: 0.13,
  },
  {
    id: "momentum_rotation",
    name: "动量轮动",
    category: "momentum",
    description: "20/60/120 日动量加权,top 1/3 配置",
    status: "paused",
    sharpe: 1.21,
    totalReturn: 0.16,
  },
];

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
  const [activeId, setActiveId] = useState<string>("lgbm_alpha");
  const setPipelineRunning = useAppStore((s) => s.setPipelineRunning);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between border-b px-2 py-1">
        <h3 className="text-sm font-semibold">策略库</h3>
        <button
          className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground hover:bg-primary/90"
          onClick={() => setPipelineRunning(true)}
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
              <span>Sharpe: <b className="text-green-600">{s.sharpe.toFixed(2)}</b></span>
              <span>收益: <b className="text-green-600">{(s.totalReturn * 100).toFixed(1)}%</b></span>
            </div>
          </button>
        ))}
      </div>

      <div className="border-t px-2 py-1 text-[10px] text-muted-foreground">
        总计: {STRATEGIES.length} 个策略 · {STRATEGIES.filter((s) => s.status === "running").length} 运行中
      </div>
    </div>
  );
}