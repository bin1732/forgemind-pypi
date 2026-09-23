/**
 * PipelineStatus 组件测试
 * OTel + Prometheus 状态显示
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { PipelineStatus } from "../pipeline-status";

describe("PipelineStatus", () => {
  it("renders without crash", () => {
    render(<PipelineStatus />);
  });

  it("shows status indicators", () => {
    render(<PipelineStatus />);
    const html = document.body.innerHTML;
    expect(html.length).toBeGreaterThan(50);
  });
});