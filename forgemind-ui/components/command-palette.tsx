/**
 * CommandPalette — Cmd+K 全局命令面板
 * 对标 OpenBB Workspace / Linear / Raycast
 */
"use client";
import { useEffect, useState } from "react";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/utils";

interface Command {
  id: string;
  label: string;
  shortcut?: string;
  category: "pipeline" | "strategy" | "factor" | "ui" | "data";
  action: () => void;
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
      action: () => alert("启动端到端流水线..."),
    },
    {
      id: "compute-factors",
      label: "计算全部 166 因子",
      category: "pipeline",
      action: () => alert("计算 Alpha158 + Alpha101 + Barra..."),
    },
    {
      id: "evaluate-ic",
      label: "IC 评估全部因子",
      category: "factor",
      action: () => alert("评估 IC / Rank IC / ICIR..."),
    },
    {
      id: "train-lgbm",
      label: "训练 LightGBM 模型",
      category: "pipeline",
      action: () => alert("训练 LightGBM..."),
    },
    {
      id: "walk-forward",
      label: "Walk-Forward OOS 验证",
      category: "pipeline",
      action: () => alert("Walk-Forward 优化..."),
    },
    {
      id: "monte-carlo",
      label: "Monte Carlo 稳健性测试",
      category: "pipeline",
      action: () => alert("Monte Carlo 模拟..."),
    },
    {
      id: "stock-pick",
      label: "AI 选股",
      category: "pipeline",
      action: () => alert("AI 选股中..."),
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
      label: "从 AKShare 拉取数据",
      category: "data",
      action: () => alert("AKShare ETL..."),
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