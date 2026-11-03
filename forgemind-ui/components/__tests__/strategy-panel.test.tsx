/**
 * StrategyPanel 组件测试
 *
 * 原先这里断言 "双均线交叉" / "LightGBM ML" / "配对交易" 一定出现 ——
 * 那是 5 条硬编码的假策略,连 sharpe / totalReturn 都是编的。
 * 面板不接后端时展示它们,等于对着用户撒谎。
 *
 * 现在改为:没数据就如实显示空态,有数据就渲染真实清单。
 */
import { render, screen } from "@testing-library/react";
import { StrategyPanel } from "../strategy-panel";
import { useAppStore } from "@/lib/store";

describe("StrategyPanel", () => {
  beforeEach(() => {
    useAppStore.setState({ strategies: [], strategiesLoaded: false });
  });

  it("没有后端数据时不展示编造的策略", () => {
    render(<StrategyPanel />);
    for (const fake of ["LightGBM ML", "配对交易", "双均线交叉"]) {
      expect(screen.queryByText(fake)).toBeNull();
    }
  });

  it("如实说明为什么是空的", () => {
    render(<StrategyPanel />);
    expect(screen.getByText(/未加载|尚无|无数据|需要后端/)).toBeInTheDocument();
  });

  it("有真实清单时逐条渲染", () => {
    useAppStore.setState({
      strategies: [
        { name: "ma_cross", kind: "bar" },
        { name: "PairsTrading", kind: "extended" },
      ],
      strategiesLoaded: true,
    });
    render(<StrategyPanel />);
    expect(screen.getByText("ma_cross")).toBeInTheDocument();
    expect(screen.getByText("PairsTrading")).toBeInTheDocument();
  });

  it("命令行跑不了的策略要说清为什么", () => {
    // 后端给的 cli_runnable / unusable_reason 要真被面板说出来 ——
    // 用户挑一个跑不了的策略,面板得告诉他为什么,而不是让他白试一次。
    useAppStore.setState({
      strategies: [
        { name: "ma_cross", kind: "bar", cli_runnable: true },
        {
          name: "MaxSharpe",
          kind: "extended",
          cli_runnable: false,
          unusable_reason: "多标的策略需要多支标的的行情",
        },
      ],
      strategiesLoaded: true,
    });
    render(<StrategyPanel />);
    expect(screen.getByText(/命令行跑不了/)).toBeInTheDocument();
    expect(screen.getByText(/多支标的/)).toBeInTheDocument();
  });

  it("没有编造的 sharpe 数字", () => {
    useAppStore.setState({
      strategies: [{ name: "ma_cross", kind: "bar" }],
      strategiesLoaded: true,
    });
    render(<StrategyPanel />);
    // 真实策略清单里没有 sharpe —— 面板不得凭空造一个出来
    expect(document.body.textContent).not.toMatch(/Sharpe\s*[:：]?\s*\d/);
  });
});
