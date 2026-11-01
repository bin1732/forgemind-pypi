/**
 * K 线图必须画真实数据,不能画随机数
 *
 * loadSampleData() 用 Math.random() 生成随机游走 —— 有实体、
 * 上影线、下影线、成交量柱、坐标轴,视觉上和真实 K 线图毫无区别,但每个
 * 用户看到的都是从 100 开始的随机数。注释里还写着"实际应从后端 API 拉"。
 *
 * 改用 MCP get_kline 后,没有数据时如实显示空态。
 */
import { readFileSync } from "fs";
import { join } from "path";

const SRC = readFileSync(join(__dirname, "..", "kline-chart.tsx"), "utf8");
const stripComments = (s: string): string =>
  s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");

describe("KlineChart 的数据来源", () => {
  it("源码里不得有随机数生成", () => {
    expect(stripComments(SRC)).not.toMatch(/Math\.random/);
  });

  it("不再有 loadSampleData", () => {
    expect(SRC).not.toMatch(/function loadSampleData/);
  });

  it("走 MCP get_kline 拿真实 K 线", () => {
    expect(SRC).toMatch(/mcpTool/);
    expect(SRC).toMatch(/"get_kline"/);
  });

  it("无数据时显示空态而不是空图", () => {
    expect(SRC).toMatch(/noData/);
    expect(SRC).toMatch(/forgemind etl/);
  });

  it("不给图表编造默认值", () => {
    // 不能出现"没数据就画点什么"的兜底
    expect(stripComments(SRC)).not.toMatch(/candles:\s*\[\{/);
  });
});
