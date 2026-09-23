/**
 * AgentDecisionPanel — 多 Agent 决策面板
 * 显示 6-Agent(Fundamentals / Technical / News / Bull / Bear / PM)投票 + 最终决策
 * 对标 Vibe-Trading / TradingAgents 的 Agent Chat 面板
 */
"use client";
import { useAppStore } from "@/lib/store";
import { cn, formatPercent } from "@/lib/utils";

interface AgentVote {
  agent: string;
  vote: "buy" | "sell" | "hold";
  score: number; // 0-5
  reasoning: string;
}

const AGENT_VOTES: AgentVote[] = [
  {
    agent: "Fundamentals",
    vote: "buy",
    score: 4,
    reasoning: "PE 28 < 行业 35,ROE 18%,营收增长 22%,估值合理且成长性强",
  },
  {
    agent: "Technical",
    vote: "hold",
    score: 3,
    reasoning: "MACD 金叉但 RSI 67 接近超买,建议等待回调",
  },
  {
    agent: "News",
    vote: "buy",
    score: 5,
    reasoning: "近期发布新品获市场正面反馈,机构调研 12 次",
  },
  {
    agent: "Bull",
    vote: "buy",
    score: 4,
    reasoning: "对标全球同业估值仍有上行空间,白酒龙头溢价合理",
  },
  {
    agent: "Bear",
    vote: "hold",
    score: 2,
    reasoning: "短期涨幅过大,行业政策风险待消化",
  },
  {
    agent: "PM",
    vote: "buy",
    score: 4,
    reasoning: "综合 5/6 Agent 共识:买入,建议仓位 30%",
  },
];

const VOTE_COLORS = {
  buy: "text-green-600 bg-green-50 border-green-200",
  sell: "text-red-600 bg-red-50 border-red-200",
  hold: "text-yellow-600 bg-yellow-50 border-yellow-200",
};

const VOTE_LABELS = {
  buy: "买入",
  sell: "卖出",
  hold: "持有",
};

export function AgentDecisionPanel() {
  const currentSymbol = useAppStore((s) => s.currentSymbol);

  // 计算综合得分
  const buyCount = AGENT_VOTES.filter((v) => v.vote === "buy").length;
  const sellCount = AGENT_VOTES.filter((v) => v.vote === "sell").length;
  const holdCount = AGENT_VOTES.filter((v) => v.vote === "hold").length;
  const avgScore = AGENT_VOTES.reduce((s, v) => s + v.score, 0) / AGENT_VOTES.length;
  const finalDecision: "BUY" | "SELL" | "HOLD" =
    buyCount > sellCount + holdCount
      ? "BUY"
      : sellCount > buyCount + holdCount
      ? "SELL"
      : "HOLD";
  const confidence = Math.min(0.95, 0.5 + avgScore / 10);

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">多 Agent 决策 · {currentSymbol}</h3>
          <p className="text-xs text-muted-foreground">
            6 Agent 综合 · LangGraph 编排
          </p>
        </div>
        <div className="text-right">
          <div
            className={cn(
              "inline-block rounded px-3 py-1 text-sm font-bold",
              finalDecision === "BUY" && "bg-green-100 text-green-700",
              finalDecision === "SELL" && "bg-red-100 text-red-700",
              finalDecision === "HOLD" && "bg-yellow-100 text-yellow-700"
            )}
          >
            {finalDecision}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            置信度 {formatPercent(confidence, 0)}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="rounded border bg-green-50 px-2 py-1 text-center text-xs">
          <div className="font-bold text-green-700">{buyCount}</div>
          <div className="text-green-600">买入</div>
        </div>
        <div className="rounded border bg-yellow-50 px-2 py-1 text-center text-xs">
          <div className="font-bold text-yellow-700">{holdCount}</div>
          <div className="text-yellow-600">持有</div>
        </div>
      </div>

      <div className="space-y-2">
        {AGENT_VOTES.map((vote) => (
          <div
            key={vote.agent}
            className={cn(
              "flex items-start gap-2 rounded border px-3 py-2 text-xs",
              VOTE_COLORS[vote.vote]
            )}
          >
            <div className="font-semibold w-24 shrink-0">{vote.agent}</div>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="font-bold">{VOTE_LABELS[vote.vote]}</span>
                <span>{"★".repeat(vote.score)}{"☆".repeat(5 - vote.score)}</span>
              </div>
              <div className="mt-1 text-gray-600">{vote.reasoning}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}