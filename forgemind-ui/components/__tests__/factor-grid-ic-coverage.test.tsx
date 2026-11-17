/**
 * "没有 IC" 有三种,不能都显示成"无数据"
 *
 * 后端一次只算一部分因子(限流),没算到的那部分是"**没算**";算过了但
 * 这批样本上算不出来,是"**算不出**";真没有数据才是"无数据"。
 *
 * 混成一种,用户会以为那些因子真没有 IC。切标的之后更糟:上一个标的
 * 的 IC 会被留在新标的上 —— 那是把一个标的的结论挂到另一个标的上。
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { useAppStore } from "../../lib/store";

const mcpTool = jest.fn();
jest.mock("@/lib/tauri", () => ({
  mcpTool: (...args: unknown[]) => mcpTool(...args),
  call: jest.fn(),
  on: jest.fn(() => () => undefined),
  isTauri: () => true,
  readResource: jest.fn(),
}));

// eslint-disable-next-line @typescript-eslint/no-var-requires
const { FactorGrid } = require("../factor-grid");

const FACTORS = [
  { name: "COMPUTED_ONE", category: "alpha158", ic: 0.03, icComputed: true },
  { name: "COMPUTED_BUT_NO_IC", category: "alpha158", icComputed: true },
  { name: "NOT_COMPUTED", category: "alpha158", icComputed: false },
];

describe("因子 IC 的三种'没有'", () => {
  beforeEach(() => {
    mcpTool.mockReset();
    useAppStore.setState({
      factors: FACTORS,
      factorsLoaded: true,
      factorIcState: "ready",
      factorIcCoverage: null,
    });
  });

  it("后端只算了一部分时,没算到的显示'未计算',并说清算了多少", () => {
    useAppStore.setState({
      factorIcCoverage: { total: 169, computed: 100 },
    });
    render(<FactorGrid />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("未计算");
    // 说明要说清:算了多少、总共多少
    expect(text).toContain("100");
    expect(text).toContain("169");
    // 还要说清**为什么**只算了一部分,以及用户能怎么办
    expect(text).toContain("点开单个因子");
  });

  it("算过了但这批样本上算不出,显示'算不出'而不是'未计算'", () => {
    useAppStore.setState({
      factorIcCoverage: { total: 3, computed: 2 },
    });
    render(<FactorGrid />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("算不出");
    expect(text).not.toContain("无数据");
  });

  it("后端没给覆盖度时,确实没 IC 的仍显示'无数据'", () => {
    useAppStore.setState({
      factors: [{ name: "PLAIN", category: "alpha158" }],
      factorIcCoverage: null,
    });
    render(<FactorGrid />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("无数据");
  });

  it("有 IC 的因子照常显示数值", () => {
    render(<FactorGrid />);
    expect(screen.getByText(/0\.0300/)).toBeTruthy();
  });
});
