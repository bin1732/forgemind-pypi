/**
 * PortfolioPanel — 实时组合面板
 * 显示持仓 / 现金 / PnL / 净值曲线 / 风险指标
 *
 * 风险指标(Sharpe / Sortino / Max DD / 胜率)从 useAppStore().riskMetrics 拿,
 * 没有真实回测数据时显示 "—",不填假数字。
 * 组合 PnL / 风险指标从 query_portfolio 真拉
 */
"use client";
import { useAppStore } from "@/lib/store";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";

/** 真值为数字时 format 2 位小数;null / undefined 时显示 "—"(空态) */
function formatRisk(v: number | null | undefined): string {
  return v == null ? "—" : v.toFixed(2);
}

/** 真值为数字时 format 成百分号;null / undefined 时显示 "—" */
function formatPct(v: number | null | undefined): string {
  return v == null ? "—" : `${(v * 100).toFixed(1)}%`;
}

export function PortfolioPanel() {
  const portfolio = useAppStore((s) => s.portfolio);
  const dataError = useAppStore((s) => s.dataError);
  const cash = useAppStore((s) => s.cash);
  const riskMetrics = useAppStore((s) => s.riskMetrics);
  const currentPrices = useAppStore((s) => s.currentPrices);

  // 当前价优先取 KLineChart 写进来的 last close;没拉到时回落 avg_price
  // (没拉到时显式 PnL=0,等 K 线数据流入后变)
  const livePrices = (p: { symbol: string; avg_price: number; quantity: number }) =>
    currentPrices[p.symbol] ?? p.avg_price;

  // 没有组合快照时(cash 为 null)整套金额都算不出来 —— 显示 "—",
  // 不显示 ¥0:"¥0" 看着像"这个组合一分钱没有",实际是"还没有快照"。
  const hasSnapshot = cash != null;
  const totalEquity = hasSnapshot
    ? cash + portfolio.reduce((sum, p) => sum + p.quantity * livePrices(p), 0)
    : null;
  const totalCost = hasSnapshot
    ? cash + portfolio.reduce((sum, p) => sum + p.quantity * p.avg_price, 0)
    : null;
  const pnl = totalEquity != null && totalCost != null ? totalEquity - totalCost : null;
  const pnlPct = totalCost != null && totalCost > 0 ? (pnl ?? 0) / totalCost : null;

  return (
    <div className="space-y-3 p-3">
      <div>
        <h3 className="text-sm font-semibold mb-2">组合概览</h3>
        <div className="space-y-2 rounded-lg border bg-card p-3">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">现金</span>
            <span className="font-mono">{formatCurrency(cash)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">总权益</span>
            <span className="font-mono font-semibold">{formatCurrency(totalEquity)}</span>
          </div>
          <div className="border-t pt-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">PnL</span>
              <span className={cn(
                "font-mono font-bold",
                pnl == null ? "" : pnl >= 0 ? "text-green-600" : "text-red-600"
              )}>
                {pnl == null ? "" : pnl >= 0 ? "+" : ""}{formatCurrency(pnl)}
              </span>
            </div>
            <div className="flex justify-between text-xs mt-1">
              <span></span>
              <span className={cn(
                "font-mono",
                pnl == null ? "" : pnl >= 0 ? "text-green-600" : "text-red-600"
              )}>
                {pnl == null ? "" : pnl >= 0 ? "+" : ""}{formatPercent(pnlPct)}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-2">持仓 ({portfolio.length})</h3>
        <div className="space-y-2">
          {portfolio.map((p) => {
            const livePrice = livePrices(p);
            const unrealized = (livePrice - p.avg_price) * p.quantity;
            const unrealizedPct = p.avg_price > 0
              ? (livePrice - p.avg_price) / p.avg_price
              : 0;
            // K 线还没拉到时,显式标注占位
            const isPlaceholder = !(p.symbol in currentPrices);
            return (
              <div key={p.symbol} className="rounded-lg border bg-card p-2">
                <div className="flex justify-between text-sm font-medium">
                  <span>{p.symbol}</span>
                  <span className="font-mono">{p.quantity} 股</span>
                </div>
                <div className="mt-1 flex justify-between text-xs text-muted-foreground">
                  <span>均价 {formatCurrency(p.avg_price)}</span>
                  <span>
                    现价 {isPlaceholder
                      ? <span className="italic">—(等 K 线)</span>
                      : formatCurrency(livePrice)}
                  </span>
                </div>
                <div className={cn(
                  "mt-1 flex justify-between text-xs font-semibold",
                  unrealized >= 0 ? "text-green-600" : "text-red-600"
                )}>
                  <span>{unrealized >= 0 ? "+" : ""}{formatCurrency(unrealized)}</span>
                  <span>{formatPercent(unrealizedPct)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-2">风险指标</h3>
        <div className="rounded-lg border bg-card p-3 space-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Sharpe</span>
            <span className="font-mono">{formatRisk(riskMetrics?.sharpe)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Sortino</span>
            <span className="font-mono">{formatRisk(riskMetrics?.sortino)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Max DD</span>
            <span
              className={cn(
                "font-mono",
                riskMetrics?.max_drawdown != null && riskMetrics.max_drawdown < 0
                  ? "text-red-600"
                  : ""
              )}
            >
              {formatPct(riskMetrics?.max_drawdown)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">胜率</span>
            <span className="font-mono">{formatPct(riskMetrics?.win_rate)}</span>
          </div>
          {riskMetrics?.strategy && (
            <div className="border-t pt-1 mt-1 text-[10px] text-muted-foreground">
              来自最近一次 forgemind backtest · {riskMetrics.strategy}
              {riskMetrics.symbol ? ` · ${riskMetrics.symbol}` : ""}
            </div>
          )}
          {!riskMetrics && (
            <div className="border-t pt-1 mt-1 text-[10px] text-muted-foreground">
              {dataError ? (
                <span className="text-destructive">
                  取数失败:{dataError} —— 这是取不到数据,不是没有回测结果
                </span>
              ) : (
                <>
                  暂无真实回测:运行{" "}
                  <code className="font-mono">forgemind backtest --symbol &lt;code&gt;</code>{" "}
                  后此处显示真实 Sharpe / Max DD
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}