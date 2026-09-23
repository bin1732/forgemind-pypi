/**
 * KLineChart 组件测试
 * lightweight-charts 已在 __mocks__/lightweight-charts-mock.js 中 mock
 */
import React from "react";
import { render } from "@testing-library/react";
import { KlineChart } from "../kline-chart";

describe("KLineChart", () => {
  it("renders with default props", () => {
    const { container } = render(<KlineChart />);
    expect(container.querySelector("div")).toBeTruthy();
  });

  it("renders with custom symbol", () => {
    const { container } = render(<KlineChart symbol="000001.SZ" />);
    expect(container.querySelector("div")).toBeTruthy();
  });

  it("renders with custom height", () => {
    const { container } = render(<KlineChart height={600} />);
    expect(container.querySelector("div")).toBeTruthy();
  });
});
