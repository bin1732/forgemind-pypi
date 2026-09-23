/**
 * ResearchLog — 自然语言研究日志查看器
 * 显示 6-Agent 综合决策 + 自然语言解释
 * 对标 QuantConnect / RD-Agent 的研究日志
 */
"use client";
import { useState } from "react";
import { cn } from "@/lib/utils";

interface LogEntry {
  timestamp: string;
  symbol: string;
  decision: "BUY" | "SELL" | "HOLD";
  agentVotes: Record<string, string>;
  factors: Record<string, number>;
  rationale: string;
}

const SAMPLE_LOGS: LogEntry[] = [
  {
    timestamp: "2026-09-19 14:15:32",
    symbol: "600519.SH",
    decision: "BUY",
    agentVotes: {
      Fundamentals: "买入(4/5):PE 28 < 行业 35,ROE 18%",
      Technical: "持有(3/5):MACD 金叉但 RSI 67 接近超买",
      News: "买入(5/5):新品发布获正面反馈",
      Bull: "买入(4/5):对标全球仍有上行空间",
      Bear: "持有(2/5):短期涨幅过大",
      PM: "买入(4/5):综合共识,建议仓位 30%",
    },
    factors: {
      "KMID": 0.024,
      "GAP": -0.030,
      "ROC_3_50": -0.011,
      "RSI": 67.0,
      "MACD_DIF": 0.15,
    },
    rationale:
      "5/6 Agent 共识买入。基本面 4/5 + 新闻 5/5 + 多头 4/5,综合置信度 78%。" +
      "建议仓位 30%,止损 -8%,止盈 +15%。",
  },
  {
    timestamp: "2026-09-19 14:10:18",
    symbol: "000001.SZ",
    decision: "HOLD",
    agentVotes: {
      Fundamentals: "持有(3/5):银行估值偏低但增长乏力",
      Technical: "卖出(2/5):跌破 60 日均线",
      News: "持有(3/5):无重大新闻",
      Bull: "持有(3/5):分红率较高但弹性不足",
      Bear: "卖出(4/5):地产风险传导",
      PM: "持有(3/5):观望",
    },
    factors: {
      "ROC_3_50": -0.022,
      "CLOSE_MINMAX_5": -0.058,
    },
    rationale:
      "Agent 观点分化,综合中性。建议继续持有现有仓位,不增不减。",
  },
];

export function ResearchLog() {
  const [selectedIdx, setSelectedIdx] = useState(0);
  const entry = SAMPLE_LOGS[selectedIdx];

  return (
    <div className="grid grid-cols-[240px_1fr] gap-4">
      <div className="space-y-2">
        <h3 className="text-sm font-semibold">研究日志</h3>
        <div className="space-y-1">
          {SAMPLE_LOGS.map((log, idx) => (
            <button
              key={idx}
              onClick={() => setSelectedIdx(idx)}
              className={cn(
                "w-full rounded border p-2 text-left text-xs transition-colors",
                idx === selectedIdx
                  ? "border-primary bg-accent"
                  : "hover:bg-accent/50"
              )}
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold">{log.symbol}</span>
                <span className={cn(
                  "rounded px-1 text-[10px] font-bold",
                  log.decision === "BUY" && "bg-green-100 text-green-700",
                  log.decision === "SELL" && "bg-red-100 text-red-700",
                  log.decision === "HOLD" && "bg-yellow-100 text-yellow-700"
                )}>
                  {log.decision}
                </span>
              </div>
              <div className="mt-1 text-[10px] text-muted-foreground">
                {log.timestamp}
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-lg border bg-card p-4">
        <div className="mb-3 flex items-center justify-between border-b pb-2">
          <div>
            <div className="text-lg font-bold">{entry.symbol}</div>
            <div className="text-xs text-muted-foreground">{entry.timestamp}</div>
          </div>
          <div className={cn(
            "rounded px-3 py-1 text-sm font-bold",
            entry.decision === "BUY" && "bg-green-100 text-green-700",
            entry.decision === "SELL" && "bg-red-100 text-red-700",
            entry.decision === "HOLD" && "bg-yellow-100 text-yellow-700"
          )}>
            {entry.decision}
          </div>
        </div>

        <div className="space-y-3 text-xs">
          <div>
            <h4 className="font-semibold mb-1">6 Agent 投票</h4>
            <div className="space-y-1">
              {Object.entries(entry.agentVotes).map(([agent, vote]) => (
                <div key={agent} className="flex gap-2 rounded bg-muted/30 p-2">
                  <span className="font-semibold w-24 shrink-0">{agent}</span>
                  <span className="text-muted-foreground">{vote}</span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h4 className="font-semibold mb-1">关键因子</h4>
            <div className="grid grid-cols-3 gap-1">
              {Object.entries(entry.factors).map(([k, v]) => (
                <div key={k} className="rounded bg-muted/30 px-2 py-1 font-mono">
                  <span className="text-muted-foreground">{k}:</span>{" "}
                  <span className="font-semibold">{v.toFixed(3)}</span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h4 className="font-semibold mb-1">决策理由</h4>
            <p className="rounded bg-muted/30 p-3 leading-relaxed text-muted-foreground">
              {entry.rationale}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}