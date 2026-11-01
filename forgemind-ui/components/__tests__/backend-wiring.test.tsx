/**
 * 前端必须真的调用 Tauri command
 *
 * Rust 侧有 5 个 #[tauri::command](start/stop sidecar、
 * run_pipeline、mcp_call_tool、get_system_status),而前端 **一次 invoke()
 * 都没调过** —— app/components/lib 里 grep "invoke" 是 0 命中。
 * 桌面端于是能构建、能打包、能签名、能上传 Releases,打开却是空面板,
 * 状态条还写死显示"已连接 · 6 服务在线"。
 *
 * 这个测试就是防止那种"能构建但不能用"的状态再次出现。
 */
import { readFileSync, readdirSync, statSync } from "fs";
import { join } from "path";

const UI = join(__dirname, "..", "..");

function walk(dir: string, out: string[] = []): string[] {
  for (const f of readdirSync(dir)) {
    if (f === "node_modules" || f === ".next" || f === "out") continue;
    if (f === "__tests__") continue;   // 排除测试自身,否则会扫到本文件里的历史文案
    const p = join(dir, f);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(ts|tsx)$/.test(f)) out.push(p);
  }
  return out;
}

describe("桌面端必须接后端", () => {
  const sources = [...walk(join(UI, "app")), ...walk(join(UI, "components")),
                   ...walk(join(UI, "lib"))];

  it("package.json 声明了 @tauri-apps/api", () => {
    // 没有这个包,前端物理上无法 invoke —— 这正是当初断链的原因
    const pkg = JSON.parse(readFileSync(join(UI, "package.json"), "utf8"));
    expect(pkg.dependencies?.["@tauri-apps/api"]).toBeDefined();
  });

  it("存在 Tauri 桥接层", () => {
    const bridge = readFileSync(join(UI, "lib", "tauri.ts"), "utf8");
    expect(bridge).toMatch(/invoke/);
    // 不在 Tauri 里时安全降级,浏览器里 npm run dev 才不会崩
    expect(bridge).toMatch(/return null/);
  });

  // 剥掉注释再比对:否则源码里"之前这里写死 X"这类说明文字会被当成残留
  const stripComments = (src: string): string =>
    src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");

  it("有代码真的调用 Tauri command", () => {
    const joined = sources.map((f) => stripComments(readFileSync(f, "utf8"))).join("\n");
    const callers = sources.filter((f) => /call<[^>]*>\(|call\(|mcpTool/.test(
      readFileSync(f, "utf8")));
    expect(callers.length).toBeGreaterThan(0);
    // 不能只有桥接层自己,必须有组件/页面在用
    const outsideBridge = callers.filter((f) => !f.endsWith("lib/tauri.ts"));
    expect(outsideBridge.length).toBeGreaterThan(0);
    expect(joined).not.toMatch(/已连接 · \d+ 服务在线/);
  });

  it("主页面真的启用了后端桥接", () => {
    // 光有桥接层不够:app/page.tsx 不调 useBackend() 的话,
    // 侧边栏和状态条照样是死的,而桥接层自己还在调 call() —— 
    // "桥接层存在"不等于"页面在用它"。
    const page = readFileSync(join(UI, "app", "page.tsx"), "utf8");
    expect(page).toMatch(/useBackend\(\)/);
    expect(stripComments(page)).not.toMatch(/as const;\s*$/m);
  });

  it("Rust 侧的 command 都有前端对应调用", () => {
    const rust = readFileSync(join(UI, "src-tauri", "src", "lib.rs"), "utf8");
    const cmds = [...rust.matchAll(/#\[tauri::command\]\s*(?:#\[[^\]]*\]\s*)*async fn (\w+)/g)]
      .map((m) => m[1]);
    expect(cmds.length).toBeGreaterThan(0);
    const ts = sources.map((f) => readFileSync(f, "utf8")).join("\n");
    // stop_python_sidecar 也必须有调用点:sidecar 起了没人停,
    // 关掉应用会留下孤儿 Python 进程占着 DuckDB 锁
    const unused = cmds.filter((c) => !ts.includes(`"${c}"`));
    expect(unused).toEqual([]);
  });
});
