/**
 * 空态要分清"没有数据"与"取不到数据"
 *
 * 取数失败时如果界面照样写"暂无数据",用户会以为自己没数据,其实是
 * 后端连不上、工具报错了,或者还没跑过 ETL。界面看着正常,问题却没人
 * 发现 —— 这与"接口返回了 JSON 但什么都没做"是同一类。
 *
 * 这里从组件外部注入取数失败的原因,断言界面说出来的是失败,而不是
 * "暂无数据"。
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { useAppStore } from "../../lib/store";
import { AgentDecisionPanel } from "../agent-decision-panel";
import { PortfolioPanel } from "../portfolio-panel";
import { SignalTable } from "../signal-table";

const FAILURE = "后端没有返回结果";

describe("空态分得清没有数据与取不到数据", () => {
  beforeEach(() => {
    useAppStore.setState({
      agentDecisions: [],
      portfolio: [],
      signals: [],
      riskMetrics: null,
      dataError: null,
    });
  });

  it("取数失败时,6 Agent 面板说的是失败而不是暂无", () => {
    useAppStore.setState({ dataError: FAILURE });
    render(<AgentDecisionPanel />);
    expect(screen.getByText(/取数失败/)).toBeTruthy();
    expect(screen.queryByText(/暂无 6 Agent/)).toBeNull();
  });

  it("取数失败时,组合面板说的是失败而不是暂无回测", () => {
    useAppStore.setState({ dataError: FAILURE });
    render(<PortfolioPanel />);
    expect(screen.getByText(/取数失败/)).toBeTruthy();
    expect(screen.queryByText(/暂无真实回测/)).toBeNull();
  });

  it("取数失败时,信号表说的是失败而不是暂无信号", () => {
    useAppStore.setState({ dataError: FAILURE });
    render(<SignalTable />);
    expect(screen.getByText(/取数失败/)).toBeTruthy();
    expect(screen.queryByText(/暂无真实交易信号/)).toBeNull();
  });

  it("确实没有数据时,仍然显示暂无,不说失败", () => {
    useAppStore.setState({ dataError: null });
    render(<SignalTable />);
    expect(screen.getByText(/暂无真实交易信号/)).toBeTruthy();
    expect(screen.queryByText(/取数失败/)).toBeNull();
  });
});
