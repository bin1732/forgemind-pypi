/**
 * ResearchLog — 研究日志:最近一次多 Agent 决策的完整记录
 *
 * 数据来自 useAppStore().agentDecisions —— 那是 forgemind agent 落盘到
 * DuckDB portfolio_decision 表里的真决策(agent / vote / score /
 * confidence / thesis),由 query_portfolio 读出。
 *
 * 数据源原本是一个空数组常量,面板永远停在空态 —— 研究布局里等于
 * 没有这一块,而界面上看起来像是"后端还没数据"。
 *
 * 没有真决策时如实说"还没有",不编造研究过程。
 */
"use client";
import { useMemo } from "react";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/utils";

interface AgentVote {
  agent: string;
  /** null = 这个 Agent 没能给出票(数据源没接上),不是"持有" */
  vote: "buy" | "sell" | "hold" | null;
  score: number;
  confidence: number | null;
  thesis: string;
}

const VOTE_LABELS: Record<string, string> = {
  buy: "买入",
  sell: "卖出",
  hold: "持有",
  none: "无数据",
};

function normalizeVote(v: string | null | undefined): "buy" | "sell" | "hold" | null {
  if (v === "buy" || v === "sell" || v === "hold") return v;
  return null;
}

export function ResearchLog() {
  const agentDecisions = useAppStore((s) => s.agentDecisions);
  const currentSymbol = useAppStore((s) => s.currentSymbol);

  const votes: AgentVote[] = useMemo(
    () =>
      (agentDecisions ?? []).map((d) => ({
        agent: d.agent,
        vote: normalizeVote(d.vote),
        score: d.score ?? 0,
        confidence: d.confidence ?? null,
        thesis: d.thesis ?? d.evidence ?? "(无详细论据)",
      })),
    [agentDecisions],
  );

  const entry = useMemo(() => {
    if (votes.length === 0) return null;
    const buy = votes.filter((v) => v.vote === "buy").length;
    const sell = votes.filter((v) => v.vote === "sell").length;
    const hold = votes.filter((v) => v.vote === "hold").length;
    // 只数真的有票的 Agent;一个都没投就说"暂无决策",不硬凑一个持有
    const decision: "BUY" | "SELL" | "HOLD" | "NONE" =
      buy + sell + hold === 0
        ? "NONE"
        : buy > sell + hold
          ? "BUY"
          : sell > buy + hold
            ? "SELL"
            : "HOLD";
    // 理由优先用 PM 的结论(它是 orchestrator 的最终票),没有就用置信度最高的那个
    const pm = votes.find((v) => v.agent === "PM");
    const best = [...votes]
      .filter((v) => v.vote !== null)
      .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0))[0];
    const rationale = pm?.thesis || best?.thesis || "(本次决策没有给出理由)";
    return { symbol: currentSymbol, decision, rationale };
  }, [votes, currentSymbol]);

  if (!entry) {
    return (
      <div className="rounded-lg border border-dashed bg-card p-6 text-center">
        <div className="text-sm text-muted-foreground">尚无研究日志</div>
        <div className="mt-1 text-xs text-muted-foreground">
          还没有落盘的多 Agent 决策。先跑一次 forgemind agent --symbol{" "}
          &lt;代码&gt; --cash &lt;金额&gt; --yes,这里会显示那一次决策的完整记录。
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-3 flex items-center justify-between border-b pb-2">
        <div>
          <div className="text-lg font-bold">{entry.symbol}</div>
          <div className="text-xs text-muted-foreground">6 Agent 综合决策记录</div>
        </div>
        <div
          className={cn(
            "rounded px-3 py-1 text-sm font-bold",
            entry.decision === "BUY" && "bg-green-100 text-green-700",
            entry.decision === "SELL" && "bg-red-100 text-red-700",
            entry.decision === "HOLD" && "bg-yellow-100 text-yellow-700",
            entry.decision === "NONE" && "bg-gray-100 text-gray-600"
          )}
        >
          {entry.decision === "NONE" ? "暂无决策" : entry.decision}
        </div>
      </div>

      <div className="space-y-3 text-xs">
        <div>
          <h4 className="font-semibold mb-1">6 Agent 投票</h4>
          <div className="space-y-1">
            {votes.map((v) => (
              <div key={v.agent} className="rounded bg-muted/30 p-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold w-24 shrink-0">{v.agent}</span>
                  <span className="text-muted-foreground">
                    {VOTE_LABELS[v.vote ?? "none"]}
                    {v.confidence !== null && (
                      <span className="ml-2 text-[10px]">
                        置信度 {(v.confidence * 100).toFixed(1)}%
                      </span>
                    )}
                  </span>
                </div>
                <div className="mt-1 text-muted-foreground">{v.thesis}</div>
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
  );
}
