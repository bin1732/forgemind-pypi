/**
 * AgentDecisionPanel 组件测试
 *
 * 重点:没有投票 ≠ "持有"。
 *
 * 某个 Agent 的数据源没接上时(本项目的 Fundamentals / News 就是这样),
 * 后端给的 vote 是空的。早先前端把空值一律归成 hold,于是这两个 Agent
 * 也被算进"持有"票数里 —— 票数是假的,票数一多还会把最终决策带偏。
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { useAppStore } from "../../lib/store";
import { AgentDecisionPanel } from "../agent-decision-panel";

const DECISIONS = [
  { agent: "Technical", vote: "buy", score: 3.62, confidence: 0.725, thesis: "MA5 上穿 MA20", evidence: null },
  { agent: "PM", vote: "sell", score: 0, confidence: 0, thesis: "综合 bull=10%", evidence: null },
  { agent: "Bull", vote: "hold", score: 1.81, confidence: 0.362, thesis: "中性区间", evidence: null },
  { agent: "Bear", vote: "hold", score: 1.81, confidence: 0.362, thesis: "均线空头排列", evidence: null },
  { agent: "Fundamentals", vote: null, score: 0, confidence: 0, thesis: "unavailable | 未接入基本面数据源", evidence: null },
  { agent: "News", vote: null, score: 0, confidence: 0, thesis: "unavailable | 未接入新闻数据源", evidence: null },
];

describe("AgentDecisionPanel", () => {
  /** 取票数磁贴上的数字。磁贴的结构是 <div><div>数字</div><div>标签</div></div> */
  const tileCount = (label: string, cls: string): string => {
    const el = screen.getByText(label, { selector: `div.${cls}` });
    return el.previousElementSibling?.textContent ?? "";
  };

  beforeEach(() => {
    useAppStore.setState({ agentDecisions: [], dataError: null, currentSymbol: "600519.SH" });
  });

  it("renders without crash", () => {
    render(<AgentDecisionPanel />);
  });

  it("shows agent decisions", () => {
    useAppStore.setState({ agentDecisions: DECISIONS });
    render(<AgentDecisionPanel />);
    const html = document.body.innerHTML;
    expect(html.length).toBeGreaterThan(50);
  });

  it("没投票的 Agent 标成无数据,不算成持有", () => {
    useAppStore.setState({ agentDecisions: DECISIONS });
    render(<AgentDecisionPanel />);
    const text = document.body.textContent ?? "";
    // 两个没有数据源的 Agent
    expect(text).toContain("无数据");
    // 持有只有 Bull 与 Bear 两个 —— Fundamentals / News 不算
    expect(tileCount("持有", "text-yellow-600")).toBe("2");
  });

  it("四档票数都列出来,没有数据源的另算一档", () => {
    useAppStore.setState({ agentDecisions: DECISIONS });
    render(<AgentDecisionPanel />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("买入");
    expect(text).toContain("卖出");
    expect(text).toContain("持有");
    expect(text).toContain("无数据");
    // 买入 1(Technical)、卖出 1(PM)、持有 2、无数据 2
    expect(tileCount("买入", "text-green-600")).toBe("1");
    expect(tileCount("卖出", "text-red-600")).toBe("1");
    expect(tileCount("持有", "text-yellow-600")).toBe("2");
    expect(tileCount("无数据", "text-gray-500")).toBe("2");
  });

  it("一个 Agent 都没投票时不硬凑一个决策出来", () => {
    useAppStore.setState({
      agentDecisions: [
        { agent: "Fundamentals", vote: null, score: 0, confidence: 0, thesis: "unavailable", evidence: null },
        { agent: "News", vote: null, score: 0, confidence: 0, thesis: "unavailable", evidence: null },
      ],
    });
    render(<AgentDecisionPanel />);
    expect(document.body.textContent).toContain("暂无决策");
  });
});
