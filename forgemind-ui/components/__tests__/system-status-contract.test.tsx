/**
 * 桌面端头部的版本号必须来自后端真有的字段
 *
 * Rust 侧 get_system_status 写进返回值的键是 app_version,前端读的是
 * version —— 字段名对不上,真桌面端的版本号就一直停在 "v—"。当初那批
 * 截图里显示着 v2026.9.3,那是替身给的字段,真 Tauri 根本不会给。
 *
 * 这个测试把两边的字段名钉在一起:前端从状态对象里读的每一个键,
 * 必须在 Rust 真的写进返回值的键里。哪边改了另一边不跟,这里就红。
 */
import { readFileSync } from "fs";
import { join } from "path";

const UI = join(__dirname, "..", "..");
const RUST = join(UI, "src-tauri", "src", "lib.rs");

/** Rust 的 get_system_status 真的会写进返回值的键 */
function rustStatusKeys(): string[] {
  const src = readFileSync(RUST, "utf8");
  const start = src.indexOf("async fn get_system_status");
  expect(start).toBeGreaterThan(-1);
  // 函数体到下一个行首的右花括号为止(内层的花括号都是缩进的)
  const end = src.indexOf("\n}\n", start);
  const body = src.slice(start, end === -1 ? undefined : end);
  const keys = new Set<string>();
  for (const m of body.matchAll(/"([a-z_]+)"\s*:/g)) keys.add(m[1]);
  return [...keys];
}

/** 前端从状态对象里读到的键 */
function uiStatusKeys(): string[] {
  const ui = readFileSync(join(UI, "app", "page.tsx"), "utf8");
  return [...ui.matchAll(/systemStatus\??\.(\w+)/g)].map((m) => m[1]);
}

describe("状态字段的前后端契约", () => {
  it("Rust 的 get_system_status 真的返回 app_version", () => {
    expect(rustStatusKeys()).toContain("app_version");
  });

  it("界面读的每个状态字段,Rust 都真的会返回", () => {
    const rustKeys = new Set(rustStatusKeys());
    const used = [...new Set(uiStatusKeys())];
    expect(used.length).toBeGreaterThan(0);
    for (const key of used) {
      expect({ key, inRust: rustKeys.has(key) }).toEqual({ key, inRust: true });
    }
  });

  it("版本号读的是后端真有的字段,不是自己编的键", () => {
    // 界面里出现 status.version 这种读法就说明又对不上了
    const ui = readFileSync(join(UI, "app", "page.tsx"), "utf8");
    expect(ui).not.toMatch(/systemStatus\??\.version\b/);
    expect(ui).toMatch(/systemStatus\??\.app_version/);
  });
});
