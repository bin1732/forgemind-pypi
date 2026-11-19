/**
 * PortfolioPanel 组件测试
 * 实时组合/PnL/风险指标
 *
 * 重点:总权益用**后端算好的那个数**。界面自己再算一遍用的就是另一套
 * 口径(现价 vs 成本),持仓有浮盈浮亏时两个数不是一个 —— 而用户看到的
 * 与 AI 算仓位用的必须是同一个。
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { useAppStore } from "@/lib/store";
import { PortfolioPanel } from "../portfolio-panel";

describe("PortfolioPanel", () => {
  beforeEach(() => {
    useAppStore.setState({
      portfolio: [],
      cash: null,
      totalEquity: null,
      equityBasis: null,
      riskMetrics: null,
      dataError: null,
    });
  });

  it("renders without crash", () => {
    render(<PortfolioPanel />);
  });

  it("shows portfolio metrics", () => {
    render(<PortfolioPanel />);
    const html = document.body.innerHTML;
    // 至少有一些文字
    expect(html.length).toBeGreaterThan(50);
  });

  it("总权益用后端给的那个数,不是自己算的", () => {
    useAppStore.setState({
      // 持仓按现价算市值是 100 × 2000 = 20 万;后端给的是 18 万
      // (库里最新收盘价与界面手头的现价不同)。
      portfolio: [
        { symbol: "600519.SH", quantity: 100, avg_price: 1500, current_price: 2000 },
      ],
      cash: 0,
      totalEquity: 180000,
      equityBasis: "market",
    });
    render(<PortfolioPanel />);
    const html = document.body.innerHTML;
    expect(html).toContain("180,000");
    expect(html).not.toContain("200,000");
  });

  it("标明权益是按现价还是按成本", () => {
    useAppStore.setState({
      portfolio: [],
      cash: 1000,
      totalEquity: 1000,
      equityBasis: "cost",
    });
    render(<PortfolioPanel />);
    expect(document.body.innerHTML).toContain("按成本");
  });
});
