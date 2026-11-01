/**
 * FactorGrid 组件测试
 *
 * 重点:因子 IC 的三种状态必须分得开。
 *
 * IC 是现算的(169 个因子要跑 5-10 秒),算完才写进 store。算之前
 * factors 里的 ic 全是 undefined —— 那不是"这些因子没有 IC",是
 * "还没算出来"。早先只按"目录加载了没有"分两种,于是计算期间整个
 * 因子库显示成一片"无数据",用户会以为真没有。
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { useAppStore } from "../../lib/store";
import { FactorGrid } from "../factor-grid";

const FACTORS = [
  { name: "MA_SPREAD_3_120", category: "alpha158" },
  { name: "ROC_5_10", category: "alpha158" },
];

describe("FactorGrid", () => {
  beforeEach(() => {
    useAppStore.setState({
      factors: FACTORS,
      factorsLoaded: true,
      factorIcState: "idle",
    });
  });

  it("renders without crash", () => {
    render(<FactorGrid />);
  });

  it("shows category labels", () => {
    render(<FactorGrid />);
    const html = document.body.innerHTML;
    expect(html).toMatch(/alpha|barra|因子/i);
  });

  it("IC 还在算的时候不说无数据", () => {
    useAppStore.setState({ factorIcState: "loading" });
    render(<FactorGrid />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("计算中");
    expect(text).not.toContain("无数据");
  });

  it("IC 算完了还没有才叫无数据", () => {
    useAppStore.setState({ factorIcState: "ready" });
    render(<FactorGrid />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("无数据");
    expect(text).not.toContain("计算中");
  });

  it("取不到 IC 与算完了没有是两回事", () => {
    useAppStore.setState({ factorIcState: "failed" });
    render(<FactorGrid />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("取不到");
    expect(text).not.toContain("无数据");
  });

  it("有真实 IC 时显示数值", () => {
    useAppStore.setState({
      factorIcState: "ready",
      factors: [{ name: "ROC_5_10", category: "alpha158", ic: -0.1234 }],
    });
    render(<FactorGrid />);
    expect(document.body.textContent).toContain("-0.1234");
  });
});
