/**
 * FactorGrid 组件测试
 * 166 因子按类别显示
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { FactorGrid } from "../factor-grid";

describe("FactorGrid", () => {
  it("renders without crash", () => {
    render(<FactorGrid />);
  });

  it("shows category labels", () => {
    render(<FactorGrid />);
    // 应有类别标签(alpha158 / alpha101 / barra 等)
    const html = document.body.innerHTML;
    expect(html).toMatch(/alpha|barra|因子/i);
  });
});