/**
 * Tauri 桥接层 —— 前端与 Rust/Python 后端之间**唯一**的通道
 *
 * invoke() 走真 Tauri 桥 (Tauri 2.x Rust 端 + Python sidecar)
 * store 初始值是空数组和一份硬编码的假持仓,所以桌面端能构建、能打包、
 * 能签名、能上传 Releases —— 打开全是空的。
 *
 * 这里做两件事:
 *   1. 在浏览器里跑(无 Tauri)时安全降级,不抛异常 —— 保留 `npm run dev` 的开发体验
 *   2. 在 Tauri 里跑时走真实的 #[tauri::command]
 */
import type { InvokeArgs } from "@tauri-apps/api/core";

type InvokeFn = (cmd: string, args?: InvokeArgs) => Promise<unknown>;
type ListenFn = (event: string, handler: (e: { payload: unknown }) => void) => Promise<UnlistenFn>;
type UnlistenFn = () => void;

// 同步检查 Tauri 容器: 只要 window 里有 __TAURI_INTERNALS__ 就视为真。
// Tauri v2 把 invoke 放在 __TAURI_INTERNALS__ 上,@tauri-apps/api 内部也是
// 调这个;但静态导出 / 测试里 dynamic import 不可用,这里直接同步读。
// 用 dynamic import 设 invoke, isTauri() 在 await 完成前一直返回 false,
// 导致 backend.tsx 直接走 "unsupported" 分支,真后端数据无法展示。
function detectTauri(): boolean {
  if (typeof window === "undefined") return false;
  return "__TAURI_INTERNALS__" in window;
}
const isTauriEnv = detectTauri();

async function loadInvoke(): Promise<InvokeFn | null> {
  if (!isTauriEnv) return null;
  const internals = (window as unknown as { __TAURI_INTERNALS__: { invoke: InvokeFn } })
    .__TAURI_INTERNALS__;
  // 优先用 webview 注入的 invoke(开发/桌面端)
  if (internals?.invoke) return internals.invoke;
  // 兜底: dynamic import(运行时 Tauri webview 也可能延迟注册 internals)
  try {
    const core = await import("@tauri-apps/api/core");
    return core.invoke as unknown as InvokeFn;
  } catch {
    return null;
  }
}
async function loadListen(): Promise<ListenFn | null> {
  if (!isTauriEnv) return null;
  try {
    const evt = await import("@tauri-apps/api/event");
    return evt.listen as unknown as ListenFn;
  } catch {
    return null;
  }
}

/** 是否运行在 Tauri 容器里 */
export const isTauri = (): boolean => isTauriEnv;

/**
 * 调用 Rust command。
 * 不在 Tauri 里时返回 `null` 而不是抛异常 —— 浏览器里 `npm run dev`
 * 仍然能看界面,只是没有真实数据。
 */
export async function call<T = unknown>(cmd: string, args?: InvokeArgs): Promise<T | null> {
  const inv = await loadInvoke();
  if (!inv) return null;
  try {
    return (await inv(cmd, args)) as T;
  } catch (e) {
    // 命令失败要看得见:静默 catch 会让"没接上后端"和"后端报错"长得一样
    console.error(`[tauri] ${cmd} 失败:`, e);
    throw e;
  }
}

/** 订阅 Rust 侧 emit 的事件 */
export async function on(event: string, handler: (payload: unknown) => void): Promise<UnlistenFn> {
  const lst = await loadListen();
  if (!lst) return () => undefined;
  return await lst(event, (e) => handler(e.payload));
}

/** 通过 Rust 的 mcp_call_tool 调一个 MCP 工具 */
export async function mcpTool<T = unknown>(
  toolName: string,
  args: Record<string, unknown> = {},
): Promise<T | null> {
  return call<T>("mcp_call_tool", {
    toolName,
    arguments: args,
  });
}

/** 读一个 MCP resource(桌面端走 HTTP,resources 在 stdio 之外原本够不着) */
export async function readResource<T = unknown>(uri: string): Promise<T | null> {
  const r = await call<Record<string, unknown>>("read_mcp_resource", { uri });
  const contents = (r?.result as { contents?: { text?: string }[] } | undefined)?.contents;
  if (contents?.[0]?.text) {
    try {
      return JSON.parse(contents[0].text) as T;
    } catch {
      return null;
    }
  }
  return null;
}
