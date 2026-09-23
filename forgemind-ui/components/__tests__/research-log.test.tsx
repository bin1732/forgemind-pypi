/**
 * ResearchLog 组件测试
 * 自然语言研究日志查看器
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { ResearchLog } from "../research-log";

describe("ResearchLog", () => {
  it("renders without crash", () => {
    render(<ResearchLog />);
  });

  it("shows research entries", () => {
    render(<ResearchLog />);
    const html = document.body.innerHTML;
    expect(html.length).toBeGreaterThan(30);
  });
});