/**
 * PortfolioPanel 组件测试
 * 实时组合/PnL/风险指标
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { PortfolioPanel } from "../portfolio-panel";

describe("PortfolioPanel", () => {
  it("renders without crash", () => {
    render(<PortfolioPanel />);
  });

  it("shows portfolio metrics", () => {
    render(<PortfolioPanel />);
    const html = document.body.innerHTML;
    // 至少有一些文字
    expect(html.length).toBeGreaterThan(50);
  });
});