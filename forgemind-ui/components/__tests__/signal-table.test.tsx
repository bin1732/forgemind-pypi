/**
 * SignalTable 组件测试
 */
import { render, screen } from "@testing-library/react";
import { SignalTable } from "../signal-table";

describe("SignalTable", () => {
  it("renders empty signal table", () => {
    render(<SignalTable signals={[]} />);
    // 空时应显示 "暂无信号" 提示
    expect(screen.getByText(/暂无信号|empty|no signals/i)).toBeInTheDocument();
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
});