/**
 * SignalTable — 信号表格
 * 显示 end_to_end 流水线输出的交易信号
 * 对标 OpenBB Workspace / TradingAgents Dashboard
 */
"use client";
import { Signal, useAppStore } from "@/lib/store";
import { cn, formatPercent } from "@/lib/utils";

export interface SignalTableProps {
  /** 可选 — 显式传入 signals(测试 / 嵌入用);不传则从 store 读。
   *
   * 用 store 里的 Signal 类型,别在这里再抄一份:抄的那份会缺字段
   * (source 就是这么丢的)—— 界面于是分不出"模型给的结论"与"手动
   * 记的一条"。 */
  signals?: Signal[];
}

/** 信号来源的显示名。分不出来源,用户就分不出"系统给的结论"与
 *  "手动记的一条"。 */
const SOURCE_LABELS: Record<string, string> = {
  mcp_output_signal: "模型分析",
  forgemind_signal_cli: "命令行示例",
};

export function SignalTable(props: SignalTableProps = {}) {
  const storeSignals = useAppStore((s) => s.signals);
  const dataError = useAppStore((s) => s.dataError);
  const signals = props.signals ?? storeSignals;

  if (signals.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-4">
        <h3 className="text-sm font-semibold mb-2">交易信号</h3>
        <div className="rounded border border-dashed bg-muted/30 p-6 text-center text-xs text-muted-foreground">
          {dataError ? (
            <>
              <span className="text-destructive">取数失败:{dataError}</span>
              <div className="mt-2 text-[10px]">
                这是取不到数据,不是没有数据。确认后端已启动
                <code className="font-mono">forgemind api</code>后再试。
              </div>
            </>
          ) : (
            <>
              暂无真实交易信号
              <div className="mt-2 text-[10px]">
                跑端到端流水线(⌘K → 运行端到端流水线)生成 PipelineResult.signals,
                <br />
                或在终端:<code className="font-mono">forgemind signal --symbol &lt;code&gt;</code>
              </div>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card">
      <div className="border-b px-4 py-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">交易信号 ({signals.length})</h3>
        <div className="text-xs text-muted-foreground">
          按置信度排序
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="border-b bg-muted/50">
            <tr>
              <th className="px-3 py-2 text-left">代码</th>
              <th className="px-3 py-2 text-left">方向</th>
              <th className="px-3 py-2 text-right">置信度</th>
              <th className="px-3 py-2 text-left">理由</th>
              <th className="px-3 py-2 text-left">时间</th>
            </tr>
          </thead>
          <tbody>
            {signals.map((s) => (
              <tr key={s.signal_id} className="border-b hover:bg-accent/30">
                <td className="px-3 py-2 font-mono font-semibold">{s.symbol}</td>
                <td className="px-3 py-2">
                  <span className={cn(
                    "rounded px-2 py-0.5 text-[10px] font-bold",
                    s.side === "BUY" && "bg-green-100 text-green-700",
                    s.side === "SELL" && "bg-red-100 text-red-700",
                    s.side === "HOLD" && "bg-yellow-100 text-yellow-700"
                  )}>
                    {s.side}
                  </span>
                </td>
                <td className="px-3 py-2 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <div className="h-1.5 w-16 rounded-full bg-muted overflow-hidden">
                      <div
                        className={cn(
                          "h-full",
                          s.confidence >= 0.7 ? "bg-green-500" :
                          s.confidence >= 0.5 ? "bg-yellow-500" : "bg-red-500"
                        )}
                        style={{ width: `${s.confidence * 100}%` }}
                      />
                    </div>
                    <span className="font-mono text-[10px] w-10">
                      {formatPercent(s.confidence, 0)}
                    </span>
                  </div>
                </td>
                <td className="px-3 py-2 text-muted-foreground max-w-xs truncate">
                  {s.rationale}
                  {s.source && (
                    <span className="ml-1 text-[10px] text-muted-foreground/80">
                      [{SOURCE_LABELS[s.source] ?? s.source}]
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-muted-foreground text-[10px]">
                  {new Date(s.timestamp).toLocaleString("zh-CN", { hour12: false })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}