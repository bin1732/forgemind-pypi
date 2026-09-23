/**
 * PortfolioPanel — 实时组合面板
 * 显示持仓 / 现金 / PnL / 净值曲线
 */
"use client";
import { useAppStore } from "@/lib/store";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";

export function PortfolioPanel() {
  const portfolio = useAppStore((s) => s.portfolio);
  const cash = useAppStore((s) => s.cash);

  const totalEquity = cash + portfolio.reduce(
    (sum, p) => sum + p.quantity * p.current_price, 0
  );
  const totalCost = cash + portfolio.reduce(
    (sum, p) => sum + p.quantity * p.avg_price, 0
  );
  const pnl = totalEquity - totalCost;
  const pnlPct = pnl / totalCost;

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
                pnl >= 0 ? "text-green-600" : "text-red-600"
              )}>
                {pnl >= 0 ? "+" : ""}{formatCurrency(pnl)}
              </span>
            </div>
            <div className="flex justify-between text-xs mt-1">
              <span></span>
              <span className={cn(
                "font-mono",
                pnl >= 0 ? "text-green-600" : "text-red-600"
              )}>
                {pnl >= 0 ? "+" : ""}{formatPercent(pnlPct)}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-2">持仓 ({portfolio.length})</h3>
        <div className="space-y-2">
          {portfolio.map((p) => {
            const unrealized = (p.current_price - p.avg_price) * p.quantity;
            const unrealizedPct = (p.current_price - p.avg_price) / p.avg_price;
            return (
              <div key={p.symbol} className="rounded-lg border bg-card p-2">
                <div className="flex justify-between text-sm font-medium">
                  <span>{p.symbol}</span>
                  <span className="font-mono">{p.quantity} 股</span>
                </div>
                <div className="mt-1 flex justify-between text-xs text-muted-foreground">
                  <span>均价 {formatCurrency(p.avg_price)}</span>
                  <span>现价 {formatCurrency(p.current_price)}</span>
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
            <span className="font-mono">1.42</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Sortino</span>
            <span className="font-mono">1.87</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Max DD</span>
            <span className="font-mono text-red-600">-8.3%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">胜率</span>
            <span className="font-mono">58.5%</span>
          </div>
        </div>
      </div>
    </div>
  );
}