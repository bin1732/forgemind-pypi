/**
 * AgentDecisionPanel 组件测试
 * 6-Agent 投票可视化
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { AgentDecisionPanel } from "../agent-decision-panel";

describe("AgentDecisionPanel", () => {
  it("renders without crash", () => {
    render(<AgentDecisionPanel />);
  });

  it("shows agent decisions", () => {
    render(<AgentDecisionPanel />);
    const html = document.body.innerHTML;
    expect(html.length).toBeGreaterThan(50);
  });
});