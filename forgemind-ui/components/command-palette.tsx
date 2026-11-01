/**
 * CommandPalette — Cmd+K 全局命令面板
 * 对标 OpenBB Workspace / Linear / Raycast
 */
"use client";
import { useEffect, useState } from "react";
import { useAppStore } from "@/lib/store";
import { reloadPortfolio } from "@/lib/backend";
import { mcpTool, call } from "@/lib/tauri";
import { runPipeline } from "@/lib/backend";
import { cn } from "@/lib/utils";

interface Command {
  id: string;
  label: string;
  shortcut?: string;
  category: "pipeline" | "strategy" | "factor" | "ui" | "data";
  action: () => void;
}

/**
 * 解开 MCP 工具返回的 JSON-RPC 包装。
 *
 * mcpTool 拿到的是 {result:{content:[{text}]}},真正的载荷在那段文本里,
 * 还要再解一次 JSON。不解的话读到的字段全是空的 —— 界面上看不出哪里错,
 * 只是"没拿到"。
 */
function unwrapToolPayload<T>(raw: unknown): T {
  const inner = (raw as { result?: { content?: Array<{ text?: string }> } })
    ?.result?.content?.[0]?.text;
  if (!inner) return {} as T;
  try {
    return JSON.parse(inner) as T;
  } catch {
    return {} as T;
  }
}

export function CommandPalette() {
  const open = useAppStore((s) => s.commandPaletteOpen);
  const setOpen = useAppStore((s) => s.setCommandPaletteOpen);
  const [query, setQuery] = useState("");
  const [selectedIdx, setSelectedIdx] = useState(0);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        // 用 functional update 拿最新 state,避免闭包陷阱
        setOpen(!open);
      }
      if (e.key === "Escape" && open) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, setOpen]);

  const commands: Command[] = [
    {
      id: "run-pipeline",
      label: "运行端到端流水线",
      shortcut: "⌘R",
      category: "pipeline",
      // 走 MCP /mcp/tools/call name="run_backtest" 或者直接走
      // /api/pipeline/run; 调用 runPipeline (后端真接)
      action: async () => {
        try {
          const symbols = ["600519.SH", "000001.SZ"];
          const r = await call<unknown>("run_pipeline", {
            symbols,
            start: "2026-08-01",
            end: "2026-10-10",
          });
          useAppStore.getState().setPipelineResult(r);
          alert(`Pipeline 完成 · ${JSON.stringify(r).slice(0, 200)}`);
        } catch (e) {
          alert(`Pipeline 失败: ${e}`);
        }
      },
    },
    {
      id: "compute-factors",
      label: "检查所有因子 IC 衰减",
      category: "pipeline",
      // MCP check_ic_decay, 走真后端
      action: async () => {
        try {
          const raw = await mcpTool<Record<string, unknown>>("check_ic_decay", { feature_name: "all" });
          const r = unwrapToolPayload(raw);
          alert(`IC 衰减已检查 · ${JSON.stringify(r).slice(0, 200)}`);
        } catch (e) {
          alert(`check_ic_decay 失败: ${e}`);
        }
      },
    },
    {
      id: "evaluate-ic",
      label: "搜索/评估因子",
      category: "factor",
      // search_features MCP 工具(把"IC 评估"映射成真实接口)
      action: async () => {
        try {
          const raw = await mcpTool<Record<string, unknown>>("search_features", { query: "alpha" });
          const r = unwrapToolPayload(raw);
          alert(`搜索结果 · ${JSON.stringify(r).slice(0, 200)}`);
        } catch (e) {
          alert(`search_features 失败: ${e}`);
        }
      },
    },
    {
      id: "train-lgbm",
      label: "训练 LightGBM 模型(集成到 run-pipeline)",
      category: "pipeline",
      // 训练是 PipelineResult 内部步骤,没有独立 MCP;接 run-pipeline
      // PipelineResult 含 model_path + train_score + val_score, 跑完自动落 store
      action: async () => {
        try {
          await runPipeline(["600519.SH"], "2026-08-01", "2026-10-10");
        } catch (e) {
          console.error("[cmd] train-lgbm 失败:", e);
        }
      },
    },
    {
      id: "walk-forward",
      label: "Walk-Forward OOS 验证(集成到 run-pipeline)",
      category: "pipeline",
      // WFO 是 PipelineResult 的 step 5b;PipelineResult 字段
      // wfo_folds / wfo_avg_score 落 store 即可, 无需弹窗
      action: async () => {
        try {
          await runPipeline(["600519.SH"], "2026-08-01", "2026-10-10");
        } catch (e) {
          console.error("[cmd] walk-forward 失败:", e);
        }
      },
    },
    {
      id: "monte-carlo",
      label: "Monte Carlo 稳健性测试(集成到 run-pipeline)",
      category: "pipeline",
      // Monte Carlo 是 PipelineResult 的 step 5c; 字段
      // monte_carlo_runs / monte_carlo_sharpe_ci 落 store
      action: async () => {
        try {
          await runPipeline(["600519.SH"], "2026-08-01", "2026-10-10");
        } catch (e) {
          console.error("[cmd] monte-carlo 失败:", e);
        }
      },
    },
    {
      id: "stock-pick",
      label: "AI 选股(真 MCP stock_pick)",
      category: "pipeline",
      // 接 MCP stock_pick
      action: async () => {
        try {
          const raw = await mcpTool<Record<string, unknown>>("stock_pick", {
            universe: ["600519", "000001", "601318"],
            top_n: 5,
          });
          const r = unwrapToolPayload(raw);
          alert(`stock_pick 完成 · ${JSON.stringify(r).slice(0, 200)}`);
        } catch (e) {
          alert(`stock_pick 失败: ${e}`);
        }
      },
    },
    {
      id: "agent-decide",
      label: "AI 决策准备(停在人工审批前)",
      category: "pipeline",
      // 走 MCP agent_decide:3-Agent 取证后停在 PM 节点前,不下单。
      // 拍板要用下一步的"批准"命令 —— 人工审批是 gating,不是走过场。
      action: async () => {
        try {
          const symbol = useAppStore.getState().currentSymbol;
          const raw = await mcpTool<Record<string, unknown>>("agent_decide", {
            symbol,
            cash: 100000,
            total_equity: 200000,
            positions: [{ symbol, quantity: 100, avg_price: 1500 }],
          });
          // mcpTool 返的是 JSON-RPC wrapper {result:{content:[{text}]}},
          // 真正的载荷在那段文本里 —— 不解包就读不到 thread_id。
          const r = unwrapToolPayload<{
            thread_id?: string;
            bull_thesis?: string;
            bear_thesis?: string;
          }>(raw);
          const threadId = r?.thread_id ?? "";
          if (!threadId) {
            alert("AI 决策准备没有拿到 thread_id,无法进入审批");
            return;
          }
          useAppStore.getState().setPendingAgentDecision({
            threadId,
            symbol,
            bullThesis: r?.bull_thesis ?? "",
            bearThesis: r?.bear_thesis ?? "",
          });
          alert(
            `${symbol} 决策已准备,停在人工审批前\n` +
              `多: ${r?.bull_thesis ?? ""}\n` +
              `空: ${r?.bear_thesis ?? ""}\n\n` +
              `用"批准刚才的 AI 决策"拍板`,
          );
        } catch (e) {
          alert(`AI 决策准备失败: ${e}`);
        }
      },
    },
    {
      id: "agent-approve",
      label: "批准刚才的 AI 决策(PM 跑完并落库)",
      category: "pipeline",
      // 走 MCP agent_approve:PM 节点跑完,组合快照与 6 条决策明细落库,
      // 面板随后就能读到这次决策。
      action: async () => {
        const pending = useAppStore.getState().pendingAgentDecision;
        if (!pending) {
          alert("还没有待审批的决策 —— 先跑一次 AI 决策准备");
          return;
        }
        try {
          const raw = await mcpTool<Record<string, unknown>>("agent_approve", {
            thread_id: pending.threadId,
            approved: true,
            reviewer: "desktop",
          });
          const r = unwrapToolPayload<{
            status?: string;
            pm_decision?: { direction?: string; quantity?: number; price?: number };
            persisted?: { snapshot_id?: string; decisions_written?: number; error?: string };
          }>(raw);
          useAppStore.getState().setPendingAgentDecision(null);
          const persisted = r?.persisted;
          // 决策刚落库,面板要马上反映出来 —— 否则组合概览还挂着上一次组合,
          // 用户会以为刚才那次批准没生效
          void reloadPortfolio();
          alert(
            `决策已拍板:${r?.pm_decision?.direction ?? "?"} ` +
              `${r?.pm_decision?.quantity ?? 0} 股 @ ${r?.pm_decision?.price ?? 0}\n` +
              (persisted?.error
                ? `落库失败:${persisted.error}`
                : `已落库:快照 ${persisted?.snapshot_id ?? "-"} · ` +
                  `${persisted?.decisions_written ?? 0}/6 条决策`),
          );
        } catch (e) {
          alert(`审批失败: ${e}`);
        }
      },
    },
    {
      id: "switch-research",
      label: "切换到研究布局",
      category: "ui",
      action: () => useAppStore.getState().setActiveLayout("research"),
    },
    {
      id: "switch-trading",
      label: "切换到交易布局",
      category: "ui",
      action: () => useAppStore.getState().setActiveLayout("trading"),
    },
    {
      id: "fetch-akshare",
      label: "从 AKShare 拉取数据(去终端跑 forgemind etl)",
      category: "data",
      // ETL 是长任务且无对应 MCP;桌面只是提示,实际在终端跑
      action: () => {
        const sym = prompt("输入标的代码(如 600519.SH,逗号分隔,留空跳过):") || "600519.SH";
        alert(
          "ETL 在桌面里跑会阻塞 UI,推荐在终端:\n" +
          "forgemind etl --symbols " + sym + " --start 2026-08-01 --end 2026-10-10\n\n" +
          "跑完后 K 线面板会自动反映"
        );
      },
    },
  ];

  const filtered = commands.filter((c) =>
    c.label.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    setSelectedIdx(0);
  }, [query]);

  useEffect(() => {
    const handleNav = (e: KeyboardEvent) => {
      if (!open) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIdx((idx) => Math.min(idx + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIdx((idx) => Math.max(idx - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (filtered[selectedIdx]) {
          filtered[selectedIdx].action();
          setOpen(false);
        }
      }
    };
    window.addEventListener("keydown", handleNav);
    return () => window.removeEventListener("keydown", handleNav);
  }, [open, filtered, selectedIdx, setOpen]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-32"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-lg rounded-lg border bg-card shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b px-4 py-2">
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入命令或搜索..."
            className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>
        <div className="max-h-96 overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              未找到命令
            </div>
          ) : (
            filtered.map((cmd, idx) => (
              <button
                key={cmd.id}
                onClick={() => {
                  cmd.action();
                  setOpen(false);
                }}
                onMouseEnter={() => setSelectedIdx(idx)}
                className={cn(
                  "flex w-full items-center justify-between rounded px-3 py-2 text-left text-sm",
                  idx === selectedIdx ? "bg-accent" : "hover:bg-accent/50"
                )}
              >
                <div>
                  <div className="font-medium">{cmd.label}</div>
                  <div className="text-xs text-muted-foreground">{cmd.category}</div>
                </div>
                {cmd.shortcut && (
                  <span className="rounded border bg-muted px-1.5 py-0.5 text-[10px]">
                    {cmd.shortcut}
                  </span>
                )}
              </button>
            ))
          )}
        </div>
        <div className="border-t px-4 py-2 text-[10px] text-muted-foreground">
          ↑↓ 选择 · ↵ 执行 · Esc 关闭
        </div>
      </div>
    </div>
  );
}