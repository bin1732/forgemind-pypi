/**
 * SignalTable 组件测试
 */
import { render, screen } from "@testing-library/react";
import { SignalTable } from "../signal-table";

describe("SignalTable", () => {
  it("renders empty signal table", () => {
    render(<SignalTable signals={[]} />);
    // 空时应显示"暂无真实交易信号"提示(改动后文案更明确)
    expect(screen.getByText(/暂无真实交易信号|暂无信号/i)).toBeInTheDocument();
  });

  it("renders signals with confidence bars", () => {
    const signals = [
      { signal_id: "1", symbol: "600519.SH", side: "BUY" as const, confidence: 0.85, rationale: "强买入", timestamp: "2026-09-20T10:00:00" },
      { signal_id: "2", symbol: "000001.SZ", side: "SELL" as const, confidence: 0.72, rationale: "卖出", timestamp: "2026-09-20T10:01:00" },
    ];
    render(<SignalTable signals={signals} />);
    // 应看到股票代码
    expect(screen.getByText("600519.SH")).toBeInTheDocument();
    expect(screen.getByText("000001.SZ")).toBeInTheDocument();
  });

  it("标出信号从哪儿来的 —— 分不出模型结论与手动记的一条", () => {
    const signals = [
      {
        signal_id: "1", symbol: "600519.SH", side: "BUY" as const,
        confidence: 0.85, rationale: "强买入", source: "mcp_output_signal",
        timestamp: "2026-09-20T10:00:00",
      },
      {
        signal_id: "2", symbol: "000001.SZ", side: "SELL" as const,
        confidence: 0.72, rationale: "卖出", source: "forgemind_signal_cli",
        timestamp: "2026-09-20T10:01:00",
      },
    ];
    render(<SignalTable signals={signals} />);
    expect(screen.getByText(/模型分析/)).toBeInTheDocument();
    expect(screen.getByText(/命令行示例/)).toBeInTheDocument();
  });
});