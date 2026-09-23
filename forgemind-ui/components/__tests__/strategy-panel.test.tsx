/**
 * StrategyPanel 组件测试
 */
import { render, screen } from "@testing-library/react";
import { StrategyPanel } from "../strategy-panel";

describe("StrategyPanel", () => {
  it("renders strategy list", () => {
    render(<StrategyPanel />);
    // 至少 1 个具体策略名字
    expect(screen.getByText("双均线交叉")).toBeInTheDocument();
  });

  it("shows category filters", () => {
    render(<StrategyPanel />);
    // 应该有分类(momentum / mean_reversion / ml 等)
    const buttons = screen.queryAllByRole("button");
    expect(buttons.length).toBeGreaterThan(0);
  });

  it("shows multiple strategies", () => {
    render(<StrategyPanel />);
    expect(screen.getByText("LightGBM ML")).toBeInTheDocument();
    expect(screen.getByText("配对交易")).toBeInTheDocument();
  });
});