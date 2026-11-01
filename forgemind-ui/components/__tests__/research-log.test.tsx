/**
 * ResearchLog 组件测试
 *
 * 研究日志的数据来自 store 里的 agentDecisions —— 那是后端落盘的真决策。
 * 这个面板的数据源原本是一个空数组常量,永远停在空态;现在它必须真的把
 * store 里的决策显示出来,而且一个都没有时说清楚"还没有",不编内容。
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { useAppStore } from "../../lib/store";
import { ResearchLog } from "../research-log";

const DECISIONS = [
  { agent: "Technical", vote: "buy", score: 3.62, confidence: 0.725, thesis: "MA5=1447.57 | MA20=1439.52", evidence: null },
  { agent: "PM", vote: "sell", score: 0, confidence: 0, thesis: "综合 bull=10.00% / bear=5.00%", evidence: null },
  { agent: "Bull", vote: "hold", score: 1.81, confidence: 0.362, thesis: "RSI 53.2 中性区间", evidence: null },
  { agent: "Bear", vote: "hold", score: 1.81, confidence: 0.362, thesis: "中期均线空头排列", evidence: null },
  { agent: "Fundamentals", vote: null, score: 0, confidence: 0, thesis: "unavailable | 未接入基本面数据源", evidence: null },
  { agent: "News", vote: null, score: 0, confidence: 0, thesis: "unavailable | 未接入新闻数据源", evidence: null },
];

describe("ResearchLog", () => {
  beforeEach(() => {
    useAppStore.setState({ agentDecisions: [], currentSymbol: "600519.SH" });
  });

  it("没有决策时如实说没有,并给出怎么才能有", () => {
    render(<ResearchLog />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("尚无研究日志");
    expect(text).toContain("forgemind agent");
  });

  it("把 store 里的真实决策显示出来", () => {
    useAppStore.setState({ agentDecisions: DECISIONS });
    render(<ResearchLog />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("6 Agent 投票");
    expect(text).toContain("600519.SH");
    expect(text).toContain("Technical");
    expect(text).toContain("MA5=1447.57 | MA20=1439.52");
    expect(text).toContain("决策理由");
  });

  it("每个 Agent 的票与论据都照实显示", () => {
    useAppStore.setState({ agentDecisions: DECISIONS });
    render(<ResearchLog />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("买入");
    expect(text).toContain("卖出");
    expect(text).toContain("持有");
    // 没投票的显示"无数据",不是"持有"
    expect(text).toContain("无数据");
    expect(screen.getAllByText("无数据").length).toBe(2);
  });

  it("票数打平时不硬说买或卖", () => {
    useAppStore.setState({
      agentDecisions: [
        { agent: "Technical", vote: "buy", score: 1, confidence: 0.5, thesis: "a", evidence: null },
        { agent: "PM", vote: "sell", score: 1, confidence: 0.5, thesis: "b", evidence: null },
      ],
    });
    render(<ResearchLog />);
    const text = document.body.textContent ?? "";
    expect(text).not.toContain("BUY");
    expect(text).not.toContain("SELL");
  });
});
