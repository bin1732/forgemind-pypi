/**
 * 因子详情的失败要看得见
 *
 * 工具失败时 MCP 会把原因带回来(协议层标了失败,sidecar 转成非 2xx,
 * 这边就抛出)。不接住的话,弹窗会一直停在"正在算 IC 衰减…" ——
 * 看着像还在算,其实早就断了,而且转圈永远不会停。
 *
 * 这里让取数真的失败一次,看原因有没有被显示出来。
 */
import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
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
  { name: "MA_SPREAD_3_120", category: "alpha158" },
  { name: "ROC_5_10", category: "alpha158" },
];

describe("因子 IC 详情取不到时", () => {
  beforeEach(() => {
    mcpTool.mockReset();
    useAppStore.setState({
      factors: FACTORS,
      factorsLoaded: true,
      factorIcState: "idle",
    });
  });

  it("工具抛错时,原因被显示出来,不是一直转圈", async () => {
    mcpTool.mockRejectedValue(new Error("MCP call failed (500): 因子不存在"));
    render(<FactorGrid />);
    await act(async () => {
      fireEvent.click(screen.getByText("MA_SPREAD_3_120"));
    });
    await waitFor(() => {
      expect(screen.getByText(/取 IC 衰减失败/)).toBeTruthy();
    });
    const text = document.body.textContent ?? "";
    expect(text).toContain("因子不存在");
    // 失败之后不能还停在"正在算…"
    expect(text).not.toContain("正在算 IC 衰减");
  });

  it("工具在正文里带回错误时,那个错误也要显示出来", async () => {
    mcpTool.mockResolvedValue({
      result: {
        content: [
          { type: "text", text: JSON.stringify({ error: "Factor 'X' not found." }) },
        ],
      },
    });
    render(<FactorGrid />);
    await act(async () => {
      fireEvent.click(screen.getByText("MA_SPREAD_3_120"));
    });
    await waitFor(() => {
      expect(screen.getByText(/取 IC 衰减失败/)).toBeTruthy();
    });
    expect(document.body.textContent ?? "").toContain("not found");
  });

  it("后端回的不是可解析的 JSON 时,也要说清,而不是空着", async () => {
    mcpTool.mockResolvedValue({
      result: { content: [{ type: "text", text: "这不是 JSON" }] },
    });
    render(<FactorGrid />);
    await act(async () => {
      fireEvent.click(screen.getByText("MA_SPREAD_3_120"));
    });
    await waitFor(() => {
      expect(screen.getByText(/取 IC 衰减失败/)).toBeTruthy();
    });
  });

  it("算得出来的时候照常显示 IC", async () => {
    mcpTool.mockResolvedValue({
      result: {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              status: "computed",
              feature_name: "MA_SPREAD_3_120",
              ic_mean: 0.0312,
              icir: 0.41,
              horizon_days: 20,
              decay: { "5": 0.04, "10": 0.03 },
            }),
          },
        ],
      },
    });
    render(<FactorGrid />);
    await act(async () => {
      fireEvent.click(screen.getByText("MA_SPREAD_3_120"));
    });
    await waitFor(() => {
      expect(screen.getByText("+0.0312")).toBeTruthy();
    });
    expect(document.body.textContent ?? "").not.toContain("取 IC 衰减失败");
  });
});
