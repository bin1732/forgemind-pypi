/**
 * 取数失败时,失败的原因要能到界面上
 *
 * 工具调用失败时 Rust 侧会把原因带回来(后端连不上、工具报错都在里面)。
 * 直接让异常抛出去,界面就只剩一片空白 —— 用户看到的是"没有数据",
 * 实际是"取不到数据",两者需要分清。
 *
 * 这里让取数函数真的失败一次,看原因有没有被记下来。
 */
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
const { loadFactorIC } = require("../../lib/backend");

describe("取数失败的原因要带到界面上", () => {
  beforeEach(() => {
    mcpTool.mockReset();
    useAppStore.setState({ dataError: null, factors: [] });
  });

  it("工具抛错时,原因被记进 dataError", async () => {
    mcpTool.mockRejectedValue(new Error("MCP call failed (500): 后端报错"));
    await loadFactorIC("600519.SH");
    const message = useAppStore.getState().dataError;
    expect(message).toBeTruthy();
    expect(message).toContain("MCP call failed");
  });

  it("工具返回空时,也说清是取不到而不是没有数据", async () => {
    mcpTool.mockResolvedValue(null);
    // 换一个标的:按 symbol 缓存的成功结果会让同一个标的直接命中缓存,
    // 走不到取数这一步。
    await loadFactorIC("000001.SZ");
    const message = useAppStore.getState().dataError;
    expect(message).toBeTruthy();
    expect(message).toContain("取不到");
  });

  it("取数成功时,不留错误信息", async () => {
    mcpTool.mockResolvedValue({
      result: {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              status: "ok",
              factors: [
                { name: "MOMENTUM_20", ic: 0.08, icir: 1.2, status: "ok" },
              ],
            }),
          },
        ],
      },
    });
    await loadFactorIC("600519.SH");
    expect(useAppStore.getState().dataError).toBeNull();
  });
});
