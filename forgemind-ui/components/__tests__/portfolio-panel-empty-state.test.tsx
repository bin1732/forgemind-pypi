/**
 * PortfolioPanel 的"没有数据"必须显示 "—",不是 0
 *
 * 活证据(2026-11-12):桌面端截图上,还没有组合快照时,组合概览写着
 * "现金 ¥0 / 总权益 ¥0 / PnL +¥0 +0.00%" —— 读的人以为这是个空组合,
 * 实际是"后端还没给快照"。同一块面板里的风险指标(Sharpe / Max DD)在
 * 没数据时写的是 "—",文字风格不一致:一个说"没有",一个说"是零"。
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { PortfolioPanel } from "../portfolio-panel";
import { useAppStore } from "@/lib/store";

describe("PortfolioPanel 现金与权益", () => {
  beforeEach(() => {
    useAppStore.setState({ portfolio: [], cash: null, riskMetrics: null, currentPrices: {} });
  });

  it("没有组合快照时显示 —,不是 ¥0", () => {
    render(<PortfolioPanel />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("现金");
    expect(text).not.toContain("¥0");
    expect(text).not.toContain("+¥0");
  });

  it("有真实快照时显示真数字", () => {
    useAppStore.setState({
      portfolio: [{ symbol: "600519.SH", quantity: 100, avg_price: 1500, current_price: 1500 }],
      cash: 100000,
    });
    render(<PortfolioPanel />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("¥100,000");
    expect(text).toContain("¥250,000");
  });

  it("风险指标那块仍然各显示各的", () => {
    render(<PortfolioPanel />);
    expect(screen.getByText("Sharpe")).toBeTruthy();
    expect(document.body.textContent).toContain("—");
  });
});
