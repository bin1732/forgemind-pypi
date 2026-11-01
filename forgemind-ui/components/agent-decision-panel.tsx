/**
 * AgentDecisionPanel — 多 Agent 决策面板
 * 显示 6-Agent(Fundamentals / Technical / News / Bull / Bear / PM)投票 + 最终决策
 * 对标 Vibe-Trading / TradingAgents 的 Agent Chat 面板
 *
 * 6 Agent 的 vote / score / reasoning 全部从 useAppStore().agentDecisions 拿,
 * 没有真实决策时显示空态(去跑一次 `forgemind agent --symbol <code> --cash <N> --yes`)。
 * 6 Agent 决策从 portfolio_decision 真落盘表读
 */
"use client";
import { useAppStore } from "@/lib/store";
import { cn, formatPercent } from "@/lib/utils";

const VOTE_COLORS = {
  buy: "text-green-600 bg-green-50 border-green-200",
  sell: "text-red-600 bg-red-50 border-red-200",
  hold: "text-yellow-600 bg-yellow-50 border-yellow-200",
  none: "text-gray-500 bg-gray-50 border-gray-200",
};

const VOTE_LABELS = {
  buy: "买入",
  sell: "卖出",
  hold: "持有",
  none: "无数据",
};

/**
 * 把后端 vote 字符串归一化。
 *
 * 没有投票与"持有"是两回事:某个 Agent 的数据源没接上时,后端给的 vote
 * 是空的,它的论据也会写明"本项目未接入 XX 数据源"。早先这里把空值一律
 * 归成 hold,于是没数据源的 Agent 也被算进"持有"票数里 —— 票数是假的,
 * 票数一多还会把最终决策带偏(判成 BUY/SELL 还要看票数)。
 */
function normalizeVote(v: string | null | undefined): "buy" | "sell" | "hold" | null {
  if (v === "buy" || v === "sell" || v === "hold") return v;
  return null;
}

export function AgentDecisionPanel() {
  const currentSymbol = useAppStore((s) => s.currentSymbol);
  const agentDecisions = useAppStore((s) => s.agentDecisions);
  const dataError = useAppStore((s) => s.dataError);

  const votes = (agentDecisions ?? []).map((d) => ({
    agent: d.agent,
    vote: normalizeVote(d.vote),
    score: d.score ?? 0,
    confidence: d.confidence ?? null,  // 0-1 真值,forgemind agent 落盘
    reasoning: d.thesis ?? d.evidence ?? "(无详细论据)",
  }));

  // 没拉到决策时:显示空态 + 提示跑 forgemind agent,绝不显示假投票
  if (votes.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-4">
        <div className="mb-2">
          <h3 className="text-sm font-semibold">多 Agent 决策 · {currentSymbol}</h3>
          <p className="text-xs text-muted-foreground">
            6 Agent 综合 · {currentSymbol} · LangGraph 编排
          </p>
        </div>
        <div className="rounded border border-dashed p-4 text-xs text-muted-foreground">
          {dataError ? (
            <>
              <span className="text-destructive">取数失败:{dataError}</span>
              <div className="mt-1">
                这是取不到 6 Agent 决策,不是没有决策。确认后端已启动
                <code className="font-mono">forgemind api</code>后再试。
              </div>
            </>
          ) : (
            <>
              暂无 6 Agent 真实决策。请在终端运行:
              <pre className="mt-2 rounded bg-muted px-2 py-1 font-mono text-[11px]">
                forgemind agent --symbol {currentSymbol} --cash 80000 --yes
              </pre>
              决策落 portfolio_decision 表后,本面板会自动显示真实投票 + 论据。
            </>
          )}
        </div>
      </div>
    );
  }

  // 综合置信度 / 方向优先用 PM 节点的真 confidence / vote
  // (from forgemind agent 落 portfolio_decision 表,confidence 0-1)
  // 真实 confidence 没关系 —— 用户看到的置信度 ≠ 后端真实 confidence
  const pmVote = votes.find((v) => v.agent === "PM");
  const pmConfidence = pmVote?.confidence;
  const finalDecision: "BUY" | "SELL" | "HOLD" | "NONE" = (() => {
    // PM 节点的 vote 优先:它是 orchestrator 的最终票
    if (pmVote?.vote === "buy") return "BUY";
    if (pmVote?.vote === "sell") return "SELL";
    if (pmVote?.vote === "hold") return "HOLD";
    // PM 没数据(例如只 Fundamentals + News unavailable):退回投票数。
    // 只数真的有投票的 Agent —— 没数据源的 Agent 不投任何票。
    const buy = votes.filter((v) => v.vote === "buy").length;
    const sell = votes.filter((v) => v.vote === "sell").length;
    const hold = votes.filter((v) => v.vote === "hold").length;
    if (buy + sell + hold === 0) return "NONE";
    return buy > sell + hold ? "BUY" : sell > buy + hold ? "SELL" : "HOLD";
  })();
  // 真实 confidence:PM.confidence 优先;PM 缺失时退回有投票的 Agent 平均
  // (没数据源的 Agent 不参与平均 —— 它们的 0 是"没有读数",不是"信心为零")
  const voted = votes.filter((v) => v.vote !== null);
  const confidence = pmConfidence != null ? pmConfidence : (
    voted.length > 0
      ? voted.reduce((s, v) => s + (v.confidence ?? 0), 0) / voted.length
      : 0
  );

  // 计数只算真的有投票的 Agent
  const buyCount = votes.filter((v) => v.vote === "buy").length;
  const sellCount = votes.filter((v) => v.vote === "sell").length;
  const holdCount = votes.filter((v) => v.vote === "hold").length;
  const noVoteCount = votes.filter((v) => v.vote === null).length;

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">多 Agent 决策 · {currentSymbol}</h3>
          <p className="text-xs text-muted-foreground">
            6 Agent 综合 · {currentSymbol} · LangGraph 编排
          </p>
        </div>
        <div className="text-right">
          <div
            className={cn(
              "inline-block rounded px-3 py-1 text-sm font-bold",
              finalDecision === "BUY" && "bg-green-100 text-green-700",
              finalDecision === "SELL" && "bg-red-100 text-red-700",
              finalDecision === "HOLD" && "bg-yellow-100 text-yellow-700",
              finalDecision === "NONE" && "bg-gray-100 text-gray-600"
            )}
          >
            {finalDecision === "NONE" ? "暂无决策" : finalDecision}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            置信度 {formatPercent(confidence, 0)}
          </div>
        </div>
      </div>

      {/* 四档都列出来:买入/卖出/持有/无数据。少列一档,看到的票数就
          跟真实票数对不上 —— 6 个 Agent 里没接数据源的那几个到底算不算
          一票,看这张表就知道。 */}
      <div className="grid grid-cols-4 gap-2 mb-3">
        <div className="rounded border bg-green-50 px-2 py-1 text-center text-xs">
          <div className="font-bold text-green-700">{buyCount}</div>
          <div className="text-green-600">买入</div>
        </div>
        <div className="rounded border bg-red-50 px-2 py-1 text-center text-xs">
          <div className="font-bold text-red-700">{sellCount}</div>
          <div className="text-red-600">卖出</div>
        </div>
        <div className="rounded border bg-yellow-50 px-2 py-1 text-center text-xs">
          <div className="font-bold text-yellow-700">{holdCount}</div>
          <div className="text-yellow-600">持有</div>
        </div>
        <div className="rounded border bg-gray-50 px-2 py-1 text-center text-xs">
          <div className="font-bold text-gray-600">{noVoteCount}</div>
          <div className="text-gray-500">无数据</div>
        </div>
      </div>

      <div className="space-y-2">
        {votes.map((vote) => (
          <div
            key={vote.agent}
            className={cn(
              "flex items-start gap-2 rounded border px-3 py-2 text-xs",
              VOTE_COLORS[vote.vote ?? "none"]
            )}
          >
            <div className="font-semibold w-24 shrink-0">{vote.agent}</div>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="font-bold">{VOTE_LABELS[vote.vote ?? "none"]}</span>
                <span>
                  {"★".repeat(Math.round(vote.score))}
                  {"☆".repeat(Math.max(0, 5 - Math.round(vote.score)))}
                </span>
              </div>
              <div className="mt-1 text-gray-600">{vote.reasoning}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}