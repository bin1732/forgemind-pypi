/**
 * FactorGrid — 166 因子网格展示
 * 显示因子库 + IC 排名
 * 对标 Qlib / RD-Agent 的因子面板
 */
"use client";
import { useState } from "react";
import { cn } from "@/lib/utils";

interface FactorMeta {
  name: string;
  category: "kbar" | "price" | "ma" | "rstd" | "rsi" | "kdj" | "macd" | "boll" | "returns" | "mom" | "alpha101" | "barra";
  ic: number;
}

const SAMPLE_FACTORS: FactorMeta[] = [
  { name: "KMID", category: "kbar", ic: 0.024 },
  { name: "KLEN", category: "kbar", ic: -0.003 },
  { name: "KUP", category: "kbar", ic: 0.012 },
  { name: "KLOW", category: "kbar", ic: -0.008 },
  { name: "CLOSE_MINMAX_5", category: "price", ic: -0.044 },
  { name: "VOLUME_RATIO_5", category: "price", ic: -0.020 },
  { name: "VOLUME_RATIO_20", category: "price", ic: -0.015 },
  { name: "PRICE_VOLUME_CORR_20", category: "price", ic: 0.018 },
  { name: "ROC_3_30", category: "ma", ic: 0.005 },
  { name: "ROC_5_60", category: "ma", ic: 0.003 },
  { name: "MA_SPREAD_10_30", category: "ma", ic: 0.001 },
  { name: "RSTD_20", category: "rstd", ic: -0.012 },
  { name: "RET_STD_20", category: "rstd", ic: -0.018 },
  { name: "RANGE_STD_20", category: "rstd", ic: -0.006 },
  { name: "RSI", category: "rsi", ic: 0.009 },
  { name: "KDJ_K", category: "kdj", ic: 0.011 },
  { name: "KDJ_J", category: "kdj", ic: 0.014 },
  { name: "MACD_DIF", category: "macd", ic: 0.022 },
  { name: "MACD_HIST", category: "macd", ic: 0.019 },
  { name: "BOLL_POS", category: "boll", ic: -0.008 },
  { name: "LOG_RETURN_20", category: "returns", ic: 0.025 },
  { name: "LOG_RETURN_60", category: "returns", ic: 0.029 },
  { name: "MOM_20", category: "mom", ic: 0.020 },
  { name: "MOM_60", category: "mom", ic: 0.026 },
  { name: "ALPHA001", category: "alpha101", ic: 0.018 },
  { name: "ALPHA006", category: "alpha101", ic: 0.006 },
  { name: "ALPHA033", category: "alpha101", ic: -0.011 },
  { name: "ALPHA101", category: "alpha101", ic: 0.014 },
  { name: "BARRA_SIZE", category: "barra", ic: -0.025 },
  { name: "BARRA_BETA", category: "barra", ic: 0.008 },
  { name: "BARRA_MOMENTUM", category: "barra", ic: 0.027 },
  { name: "BARRA_RESIDUAL_VOL", category: "barra", ic: -0.018 },
];

const CATEGORY_COLORS: Record<string, string> = {
  kbar: "bg-blue-100 text-blue-700",
  price: "bg-cyan-100 text-cyan-700",
  ma: "bg-purple-100 text-purple-700",
  rstd: "bg-pink-100 text-pink-700",
  rsi: "bg-orange-100 text-orange-700",
  kdj: "bg-amber-100 text-amber-700",
  macd: "bg-lime-100 text-lime-700",
  boll: "bg-emerald-100 text-emerald-700",
  returns: "bg-teal-100 text-teal-700",
  mom: "bg-green-100 text-green-700",
  alpha101: "bg-rose-100 text-rose-700",
  barra: "bg-slate-100 text-slate-700",
};

const CATEGORY_LABELS: Record<string, string> = {
  kbar: "KBAR",
  price: "量价",
  ma: "均线",
  rstd: "波动",
  rsi: "RSI",
  kdj: "KDJ",
  macd: "MACD",
  boll: "BOLL",
  returns: "收益",
  mom: "动量",
  alpha101: "Alpha101",
  barra: "Barra",
};

export function FactorGrid() {
  const [filter, setFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"ic" | "name">("ic");

  const filtered = filter === "all"
    ? SAMPLE_FACTORS
    : SAMPLE_FACTORS.filter((f) => f.category === filter);

  const sorted = sortBy === "ic"
    ? [...filtered].sort((a, b) => Math.abs(b.ic) - Math.abs(a.ic))
    : [...filtered].sort((a, b) => a.name.localeCompare(b.name));

  const categories = Array.from(new Set(SAMPLE_FACTORS.map((f) => f.category)));

  return (
    <div className="space-y-3 rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">
          因子库 <span className="text-muted-foreground font-normal">({SAMPLE_FACTORS.length} / 166 预览)</span>
        </h3>
        <div className="flex gap-1 text-[10px]">
          <button
            onClick={() => setSortBy("ic")}
            className={cn(
              "rounded px-2 py-1",
              sortBy === "ic" ? "bg-primary text-primary-foreground" : "bg-muted"
            )}
          >
            按 |IC|
          </button>
          <button
            onClick={() => setSortBy("name")}
            className={cn(
              "rounded px-2 py-1",
              sortBy === "name" ? "bg-primary text-primary-foreground" : "bg-muted"
            )}
          >
            按名称
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1">
        <button
          onClick={() => setFilter("all")}
          className={cn(
            "rounded px-2 py-1 text-[10px]",
            filter === "all" ? "bg-primary text-primary-foreground" : "bg-muted"
          )}
        >
          全部 ({SAMPLE_FACTORS.length})
        </button>
        {categories.map((cat) => {
          const count = SAMPLE_FACTORS.filter((f) => f.category === cat).length;
          return (
            <button
              key={cat}
              onClick={() => setFilter(cat)}
              className={cn(
                "rounded px-2 py-1 text-[10px]",
                filter === cat
                  ? CATEGORY_COLORS[cat]
                  : "bg-muted text-muted-foreground"
              )}
            >
              {CATEGORY_LABELS[cat]} ({count})
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-2 gap-1 md:grid-cols-4">
        {sorted.map((f) => (
          <div
            key={f.name}
            className={cn(
              "rounded border p-2 text-xs",
              Math.abs(f.ic) >= 0.02 ? "border-green-300 bg-green-50" :
              Math.abs(f.ic) >= 0.01 ? "border-yellow-300 bg-yellow-50" :
              "border-gray-200 bg-muted/30"
            )}
          >
            <div className="flex items-center justify-between">
              <span className="font-mono font-semibold truncate">{f.name}</span>
              <span className={cn(
                "rounded px-1 text-[9px]",
                CATEGORY_COLORS[f.category]
              )}>
                {CATEGORY_LABELS[f.category]}
              </span>
            </div>
            <div className="mt-1 flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground">IC</span>
              <span className={cn(
                "font-mono font-semibold",
                f.ic > 0 ? "text-green-600" : "text-red-600"
              )}>
                {f.ic > 0 ? "+" : ""}{f.ic.toFixed(4)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}