/**
 * 命令面板里的 AI 决策链路
 *
 * 桌面端原来根本没有 agent 入口 —— 人工审批这条核心链路在界面上够不着:
 * API 与 MCP 都有,UI 不调。现在补上两个命令:决策准备(停在审批前)与
 * 拍板(PM 跑完并落库)。
 *
 * 关键性质:**拍板必须先有决策准备**。没有 thread_id 就批准不了,
 * PM 节点也不会跑 —— 人工审批是 gating,不是走过场。
 */
import React from "react";
import { render, screen, act } from "@testing-library/react";

/**
 * MCP 工具返回的真实形状:JSON-RPC wrapper,载荷在 content[0].text 里,
 * 而且那段文本本身还是一份 JSON(工具的返回值被序列化过一次)。
 */
function toolResponse(payload: unknown) {
  return {
    jsonrpc: "2.0",
    id: 1,
    result: { content: [{ type: "text", text: JSON.stringify(payload) }] },
  };
}

const mcpTool = jest.fn();
const alertSpy = jest.fn();

const reloadPortfolio = jest.fn();

jest.mock("@/lib/tauri", () => ({
  call: jest.fn(),
  mcpTool: (...args: unknown[]) => mcpTool(...args),
  readResource: jest.fn(),
  on: jest.fn(),
  isTauri: () => true,
}));

jest.mock("@/lib/backend", () => ({
  reloadPortfolio: () => reloadPortfolio(),
}));

import { CommandPalette } from "../command-palette";
import { useAppStore } from "@/lib/store";

beforeEach(() => {
  mcpTool.mockReset();
  reloadPortfolio.mockReset();
  alertSpy.mockReset();
  global.alert = alertSpy as unknown as typeof alert;
  useAppStore.setState({
    commandPaletteOpen: true,
    pendingAgentDecision: null,
    currentSymbol: "600519.SH",
  });
});

function clickCommand(label: string) {
  const item = screen.getByText(label);
  act(() => {
    item.click();
  });
}

describe("命令面板的 AI 决策链路", () => {
  it("决策准备把 thread_id 存下来,供下一步拍板", async () => {
    mcpTool.mockResolvedValue(
      toolResponse({
        thread_id: "thread-abc",
        bull_thesis: "上穿 MA20",
        bear_thesis: "空头排列",
      }),
    );
    render(<CommandPalette />);
    await act(async () => {
      clickCommand("AI 决策准备(停在人工审批前)");
    });
    expect(mcpTool).toHaveBeenCalledWith("agent_decide", expect.objectContaining({
      symbol: "600519.SH",
    }));
    const pending = useAppStore.getState().pendingAgentDecision;
    expect(pending?.threadId).toBe("thread-abc");
    expect(pending?.bullThesis).toBe("上穿 MA20");
  });

  it("拍板用的是决策准备留下的 thread_id", async () => {
    mcpTool.mockResolvedValue(
      toolResponse({
        status: "APPROVED",
        pm_decision: { direction: "sell", quantity: 96, price: 1444.42 },
        persisted: { snapshot_id: "snap-1", decisions_written: 6, error: null },
      }),
    );
    useAppStore.setState({
      pendingAgentDecision: {
        threadId: "thread-abc",
        symbol: "600519.SH",
        bullThesis: "b",
        bearThesis: "s",
      },
    });
    render(<CommandPalette />);
    await act(async () => {
      clickCommand("批准刚才的 AI 决策(PM 跑完并落库)");
    });
    expect(mcpTool).toHaveBeenCalledWith("agent_approve", expect.objectContaining({
      thread_id: "thread-abc",
      approved: true,
    }));
    // 拍板完就没有待审批的了
    expect(useAppStore.getState().pendingAgentDecision).toBeNull();
  });

  it("拍板落库后面板要刷新 —— 否则组合概览还挂着上一次组合", async () => {
    mcpTool.mockResolvedValue(
      toolResponse({
        status: "APPROVED",
        pm_decision: { direction: "sell", quantity: 96, price: 1444.42 },
        persisted: { snapshot_id: "snap-1", decisions_written: 6, error: null },
      }),
    );
    useAppStore.setState({
      pendingAgentDecision: {
        threadId: "thread-abc",
        symbol: "600519.SH",
        bullThesis: "b",
        bearThesis: "s",
      },
    });
    render(<CommandPalette />);
    await act(async () => {
      clickCommand("批准刚才的 AI 决策(PM 跑完并落库)");
    });
    expect(reloadPortfolio).toHaveBeenCalled();
  });

  it("没有待审批的决策时,拍板不会去调后端", async () => {
    render(<CommandPalette />);
    await act(async () => {
      clickCommand("批准刚才的 AI 决策(PM 跑完并落库)");
    });
    expect(mcpTool).not.toHaveBeenCalled();
    expect(alertSpy).toHaveBeenCalled();
  });

  it("决策准备拿不到 thread_id 时不进入待审批状态", async () => {
    mcpTool.mockResolvedValue(toolResponse({ thread_id: "" }));
    render(<CommandPalette />);
    await act(async () => {
      clickCommand("AI 决策准备(停在人工审批前)");
    });
    expect(useAppStore.getState().pendingAgentDecision).toBeNull();
  });

  it("落库失败要说出来,不假装写成了", async () => {
    mcpTool.mockResolvedValue(
      toolResponse({
        status: "APPROVED",
        pm_decision: { direction: "sell", quantity: 96, price: 1444.42 },
        persisted: { snapshot_id: null, decisions_written: 0, error: "IOException: 库锁住" },
      }),
    );
    useAppStore.setState({
      pendingAgentDecision: {
        threadId: "thread-abc",
        symbol: "600519.SH",
        bullThesis: "b",
        bearThesis: "s",
      },
    });
    render(<CommandPalette />);
    await act(async () => {
      clickCommand("批准刚才的 AI 决策(PM 跑完并落库)");
    });
    const text = alertSpy.mock.calls.map((c) => String(c[0])).join("\n");
    expect(text).toContain("落库失败");
  });
});
