/**
 * FactorGrid — 166 因子网格展示
 * 显示因子库 + IC 排名
 * 对标 Qlib / RD-Agent 的因子面板
 */
"use client";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { useAppStore, type FactorMeta } from "@/lib/store";
import { mcpTool } from "@/lib/tauri";


// 数据来自 MCP resource forgemind://features(后端按真实注册表派生)。
// 因子从 forgemind://features 真 resource 拉
// 真实数量早已变成 169,而面板永远显示那 6 条。
const EMPTY: FactorMeta[] = [];


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
  // 选中的因子 (弹窗显示 IC 衰减序列)
  const [selected, setSelected] = useState<string | null>(null);
  // 详情数据
  const [detail, setDetail] = useState<{
    name: string;
    ic: number;
    icir: number;
    horizon: number;
    bars: Array<{ days: number; ic: number }>;
    loading: boolean;
  } | null>(null);

  const factors = useAppStore((s) => s.factors);
  const factorsLoaded = useAppStore((s) => s.factorsLoaded);
  // IC 是现算的,算之前不能显示成"无数据" —— 那是"还没算出来"
  const icState = useAppStore((s) => s.factorIcState);

  // 选中因子 → 拉 IC 详情
  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    setDetail({ name: selected, ic: 0, icir: 0, horizon: 0, bars: [], loading: true });
    (async () => {
      const raw = await mcpTool<Record<string, unknown>>(
        "check_ic_decay", { feature_name: selected, window_days: 20 },
      );
      // mcpTool 返 JSON-RPC wrapper {result:{content:[{text}]}}, 解二次 JSON
      const inner = (raw as { result?: { content?: Array<{ text?: string }> } })
                      ?.result?.content?.[0]?.text;
      let r: {
        status: string;
        feature_name?: string;
        ic_mean?: number;
        icir?: number;
        horizon_days?: number;
        ic_by_horizon?: Record<string, number>;
        n_bars?: number;
        decay?: Record<string, number>;
        message?: string;
      };
      if (inner) {
        try { r = JSON.parse(inner); }
        catch { return; }
      } else if ((raw as { status?: string }).status) {
        r = raw as typeof r;
      } else {
        return;
      }
      if (r.status !== "computed") {
        setDetail({
          name: selected, ic: 0, icir: 0, horizon: 0, bars: [],
          loading: false,
        });
        return;
      }
      const decay = r.decay ?? r.ic_by_horizon ?? {};
      const bars = Object.entries(decay)
        .map(([days, ic]) => ({ days: Number(days), ic: Number(ic) }))
        .sort((a, b) => a.days - b.days);
      const horizon = r.horizon_days ?? (bars.length ? bars[bars.length - 1].days : 20);
      setDetail({
        name: r.feature_name ?? selected,
        ic: r.ic_mean ?? 0,
        icir: r.icir ?? 0,
        horizon,
        bars,
        loading: false,
      });
    })();
  }, [selected]);

  const filtered = filter === "all"
    ? factors
    : factors.filter((f) => f.category === filter);

  const sorted = sortBy === "ic"
    ? [...filtered].sort((a, b) => Math.abs(b.ic ?? 0) - Math.abs(a.ic ?? 0))
    : [...filtered].sort((a, b) => a.name.localeCompare(b.name));

  const categories = Array.from(new Set(factors.map((f) => f.category)));

  return (
    <div className="space-y-3 rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">
          因子库 <span className="text-muted-foreground font-normal">({factors.length} 个)</span>
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
          全部 ({factors.length})
        </button>
        {categories.map((cat) => {
          const count = factors.filter((f) => f.category === cat).length;
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
          <button
            key={f.name}
            type="button"
            onClick={() => setSelected(f.name)}
            className={cn(
              "rounded border p-2 text-left text-xs transition-colors hover:shadow",
              selected === f.name ? "ring-2 ring-primary" : "",
              Math.abs(f.ic ?? 0) >= 0.02 ? "border-green-300 bg-green-50" :
              Math.abs(f.ic ?? 0) >= 0.01 ? "border-yellow-300 bg-yellow-50" :
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
                f.ic === undefined ? "text-muted-foreground" : f.ic > 0 ? "text-green-600" : "text-red-600"
              )}>
                {f.ic === undefined
                  ? (icState === "ready"
                      ? "无数据"
                      : icState === "failed"
                        ? "取不到"
                        : icState === "loading"
                          ? "计算中…"
                          : "…")
                  : `${f.ic > 0 ? "+" : ""}${f.ic.toFixed(4)}`}
              </span>
            </div>
          </button>
        ))}
      </div>

      {/* IC 衰减详情弹窗 */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
             onClick={() => setSelected(null)}>
          <div className="w-[480px] max-w-[90vw] rounded-lg border bg-card p-5 shadow-xl"
               onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold">因子 IC 详情 · {detail?.name ?? selected}</h3>
              <button
                onClick={() => setSelected(null)}
                className="rounded px-2 py-1 text-xs hover:bg-muted"
              >
                关闭
              </button>
            </div>
            {detail?.loading ? (
              <div className="mt-6 text-center text-sm text-muted-foreground">
                正在算 IC 衰减…
              </div>
            ) : !detail ? (
              <div className="mt-6 text-center text-sm text-muted-foreground">
                无数据
              </div>
            ) : (
              <div className="mt-4 space-y-3 text-xs">
                <div className="grid grid-cols-3 gap-2 rounded bg-muted/40 p-3">
                  <div>
                    <div className="text-muted-foreground">IC 均值</div>
                    <div className={cn("font-mono font-semibold",
                      detail.ic > 0 ? "text-green-600" : "text-red-600")}>
                      {detail.ic > 0 ? "+" : ""}{detail.ic.toFixed(4)}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">ICIR</div>
                    <div className={cn("font-mono font-semibold",
                      detail.icir > 0 ? "text-green-600" : "text-red-600")}>
                      {detail.icir > 0 ? "+" : ""}{detail.icir.toFixed(3)}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">窗口</div>
                    <div className="font-mono font-semibold">
                      {detail.horizon} 日
                    </div>
                  </div>
                </div>
                <div>
                  <div className="mb-1 text-muted-foreground">IC 衰减序列 (前瞻天数 → IC)</div>
                  <div className="space-y-1">
                    {detail.bars.map((b) => (
                      <div key={b.days} className="flex items-center gap-2">
                        <span className="w-10 text-right font-mono">{b.days}d</span>
                        <div className="relative h-3 flex-1 rounded bg-muted/30 overflow-hidden">
                          <div
                            className={cn("h-full",
                              b.ic >= 0 ? "bg-green-500" : "bg-red-500")}
                            style={{
                              width: `${Math.min(100, Math.abs(b.ic) / 0.3 * 100)}%`,
                              marginLeft: b.ic < 0 ? "auto" : undefined,
                            }}
                          />
                        </div>
                        <span className={cn("w-14 text-right font-mono",
                          b.ic >= 0 ? "text-green-600" : "text-red-600")}>
                          {b.ic > 0 ? "+" : ""}{b.ic.toFixed(4)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="text-[10px] text-muted-foreground">
                  数据源: DuckDB kline_daily · 计算: alpha158 + 前瞻收益
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
