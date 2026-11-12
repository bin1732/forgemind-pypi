#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""对着真后端把桌面端界面截下来。

沙箱与 CI 里都没有图形桌面,Tauri 的 webview 起不来。界面本身是一个网页,
数据全部来自真后端 —— 所以这条路走得通,而且走的是真数据:真 DuckDB、
真 MCP 工具、真因子 IC、真 Agent 决策。

三步:
  1. 起真的 Python 后端(子进程,带真 DuckDB)
  2. 把导出的静态页用本地 http 伺服起来,Playwright 打开
  3. 注入 Tauri IPC 替身,把 invoke 转发到真后端

替身只替"进程间通信"这一层。命令清单、端点地址、请求体字段、状态字段
全部从 src-tauri/src/lib.rs 的原码里抽出来 —— 手抄一份就会跟真实现分家,
截图看着对、真机却不是那么回事。少实现一个命令直接报错,而不是让界面
安静地少一块数据。

每张截图之前都要先确认面板里是真数据(等到了该出现的文字,且没有
"加载数据…"这类占位),否则宁可报错,也不留下一张看着像证据的空图。

用法:
    python scripts/capture_desktop_evidence.py --out 输出目录
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
UI_DIR = REPO / "forgemind-ui"
RUST = UI_DIR / "src-tauri" / "src" / "lib.rs"
CARGO_TOML = UI_DIR / "src-tauri" / "Cargo.toml"
CARGO_LOCK = UI_DIR / "src-tauri" / "Cargo.lock"
STATIC_OUT = UI_DIR / "out"


class ContractError(RuntimeError):
    """从 Rust 原码里抽不出契约 —— 宁可报错,也不能拿猜出来的地址去连。"""


# ---------------------------------------------------------------- Rust 契约


def _function_bodies(src: str) -> dict[str, str]:
    """取出每个 `#[tauri::command]` 函数的名字与函数体。"""
    bodies: dict[str, str] = {}
    lines = src.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"\s*async fn (\w+)\(", line)
        if not m:
            continue
        # 只认前面紧挨着 #[tauri::command] 的那些
        if i == 0 or "#[tauri::command]" not in lines[i - 1]:
            continue
        name = m.group(1)
        indent = len(line) - len(line.lstrip())
        block = [line]
        j = i + 1
        while j < len(lines):
            cur = lines[j]
            if cur.strip() and (len(cur) - len(cur.lstrip())) <= indent:
                break
            block.append(cur)
            j += 1
        bodies[name] = "\n".join(block)
    return bodies


def _snake_to_camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


def parse_rust() -> dict:
    """把 Rust 侧的契约抽出来:命令、端点、请求体字段、状态字段。"""
    src = RUST.read_text(encoding="utf-8")
    bodies = _function_bodies(src)
    if not bodies:
        raise ContractError(f"{RUST} 里没找到 #[tauri::command] 函数")

    commands: dict[str, dict] = {}
    for name, body in bodies.items():
        urls = re.findall(r'"(http://[0-9.]+:\d+/[^"]+)"', body)
        method = "POST" if ".post(url)" in body else "GET"
        # 请求体字段:从 json!({...}) 里读 "键": 参数名 的对应关系。
        # Tauri 会把 Rust 的 snake_case 参数名以 camelCase 交给前端,
        # 所以前端传进来的键是参数名的 camel 形态。
        fields: dict[str, str] = {}
        m = re.search(r"json!\(\{(.*?)\}\)", body, re.S)
        if m:
            for key, param in re.findall(r'"(\w+)"\s*:\s*(\w+)\s*,?', m.group(1)):
                fields[key] = _snake_to_camel(param)
        err = re.search(r'format!\("([^"]*failed)', body)
        commands[name] = {
            "urls": urls,
            "method": method,
            "fields": fields,
            "error_prefix": err.group(1) if err else "request failed",
        }

    if "get_system_status" not in commands:
        raise ContractError("Rust 里没有 get_system_status 命令")

    # 状态对象的字段:get_system_status 里所有 json!({...}) 的键的并集。
    # 有两个块:后端活着时合并进来的 live 字段,以及最终返回的 out 对象。
    # 失败分支里的 out["status_note"] 之类不算成功路径的字段。
    m = re.search(r"json!\(\{(.*?)\}\)", bodies["get_system_status"], re.S)
    status_keys = re.findall(r'"(\w+)"\s*:', m.group(1)) if m else []
    for extra in re.finditer(r"json!\(\{(.*?)\}\)", bodies["get_system_status"], re.S):
        status_keys += re.findall(r'"(\w+)"\s*:', extra.group(1))
    status_keys = sorted(set(status_keys))
    if not status_keys:
        raise ContractError("抽不出 get_system_status 返回对象的字段")

    # 后端地址:所有端点共用一个 origin,sidecar 就监听在这个端口上
    all_urls = [u for c in commands.values() for u in c["urls"]]
    if not all_urls:
        raise ContractError("Rust 里抽不到后端端点地址")
    origins = {re.match(r"https?://[^/]+", u).group(0) for u in all_urls}
    if len(origins) != 1:
        raise ContractError(f"Rust 里的后端地址不统一: {sorted(origins)}")
    base = origins.pop()

    emit = re.search(r'emit\("([^"]+)"', src)
    event = emit.group(1) if emit else "python-sidecar-ready"

    return {
        "commands": commands,
        "status_keys": status_keys,
        "base": base,
        "event": event,
    }


def cargo_versions() -> tuple[str, str]:
    """桌面端版本与 Tauri 版本 —— 前者来自 Cargo.toml,后者来自 Cargo.lock。"""
    cargo = CARGO_TOML.read_text(encoding="utf-8")
    section = re.search(r"^\[package\]\s*$(.*?)(?=^\[|\Z)", cargo, re.M | re.S)
    m = re.search(r'^\s*version\s*=\s*"([^"]+)"', section.group(1), re.M) if section else None
    if not m:
        raise ContractError("Cargo.toml 里读不到 [package].version")
    app_version = m.group(1)

    tauri_version = ""
    if CARGO_LOCK.is_file():
        lock = CARGO_LOCK.read_text(encoding="utf-8")
        tm = re.search(r'^name = "tauri"\nversion = "([^"]+)"', lock, re.M)
        if tm:
            tauri_version = tm.group(1)
    return app_version, tauri_version


# ---------------------------------------------------------------- IPC 替身


def build_shim(contract: dict, app_version: str, tauri_version: str) -> str:
    """生成注入页面的 Tauri IPC 替身。

    严格程度:必须实现 Rust 声明的每一个命令,少一个就报错。
    少实现一个命令不会让界面崩,但会让某块数据永远空着 —— 截图看着
    正常,实际上没验证到任何东西。
    """
    cmds = contract["commands"]
    impl_parts: list[str] = []
    for name, spec in cmds.items():
        if name == "get_system_status":
            continue
        if name in ("start_python_sidecar", "stop_python_sidecar"):
            # 真 Rust 会真的起/停 Python 进程;这里进程由采集脚本管着,
            # 停掉它等于把采集环境拆了。返回成功即可,界面不依赖内容。
            sidecar_msg = f"Python sidecar running on {contract['base']}"
            impl_parts.append(f"  {name}: async () => {json.dumps(sidecar_msg)},")
            continue
        if not spec["urls"]:
            raise ContractError(f"命令 {name} 抽不到端点地址")
        url = spec["urls"][0]
        fields = spec["fields"]
        method = spec["method"]
        # Tauri v2 缺参数会直接报错(命令根本不执行),替身不能偷偷补一个
        # null 上去 —— 后端收到 null 与没收到是两回事(比如 arguments 收到
        # null 会被判 422,而真桌面端是命令直接失败)。缺参数就报错,
        # 这样前端哪天漏传了参数,截图会当场露出来。
        field_pairs = ", ".join(f'["{k}", "{p}"]' for k, p in fields.items())
        body_expr = (
            "(() => { const pairs = [" + field_pairs + "];"
            " const missing = pairs.filter(([, p]) => a[p] === undefined).map(([, p]) => p);"
            " if (missing.length) { throw new Error('invalid args `' + missing.join('`, `')"
            " + '` for command `" + name + "`'); }"
            " const out = {}; for (const [k, p] of pairs) { out[k] = a[p]; }"
            " return JSON.stringify(out); })()"
        )
        impl_parts.append(
            f"""  {name}: async (a) => {{
      const res = await fetch({json.dumps(url)}, {{
        method: {json.dumps(method)},
        headers: {{ "Content-Type": "application/json" }},
        body: {body_expr},
      }});
      const text = await res.text();
      let data = null;
      try {{ data = text ? JSON.parse(text) : null; }} catch (e) {{ data = null; }}
      if (!res.ok) {{
        throw new Error({json.dumps(spec["error_prefix"])} + " (" + res.status + "): " + text);
      }}
      return data;
    }},"""
        )

    status_impl = """  get_system_status: async () => {
    const get = async (url) => {
      const res = await fetch(url);
      if (!res.ok) return null;
      return await res.json();
    };
    const toolsBody = await get(CFG.statusUrls.tools);
    const resourcesBody = await get(CFG.statusUrls.resources);
    const tools = (toolsBody && toolsBody.result && toolsBody.result.tools) || [];
    const resources = (resourcesBody && resourcesBody.result && resourcesBody.result.resources) || [];
    const status = {
      app_version: CFG.appVersion,
      tauri_version: CFG.tauriVersion,
      python_sidecar_running: true,
      mcp_tools: tools.map((t) => t.name),
      mcp_tool_count: tools.length,
      mcp_resource_count: resources.length,
    };
    // 替身给的字段必须与 Rust 写的完全一致。少一个:界面读不到那个值,
    // 截图看着正常,其实没验证到。多一个:替身就在替真实现编字段。
    const got = Object.keys(status).sort();
    const want = CFG.statusKeys.slice().sort();
    if (JSON.stringify(got) !== JSON.stringify(want)) {
      throw new Error(
        "状态字段与 Rust 不一致 —— 替身 " + JSON.stringify(got) + " / Rust " + JSON.stringify(want)
      );
    }
    return status;
  },"""

    cfg = {
        "appVersion": app_version,
        "tauriVersion": tauri_version,
        "statusKeys": contract["status_keys"],
        "statusUrls": {
            "tools": contract["commands"]["get_system_status"]["urls"][0],
            "resources": contract["commands"]["get_system_status"]["urls"][1],
        },
        "event": contract["event"],
    }

    js = f"""
(() => {{
  const CFG = {json.dumps(cfg, ensure_ascii=False)};
  const IMPL = {{
{chr(10).join(impl_parts)}
{status_impl}
  }};

  // 事件:真 Rust 侧 sidecar 就绪时 emit 一次,前端据此刷新数据。
  // 这里把同一个事件补发出去,前端拿到的路径与真桌面端一致。
  const eventHandlers = new Map();
  let seq = 1;

  const shim = {{
    invoke: async (cmd, args) => {{
      if (cmd === "plugin:event|listen") {{
        const id = seq++;
        const list = eventHandlers.get(args.event) || [];
        list.push({{ id, handler: args.handler }});
        eventHandlers.set(args.event, list);
        if (args.event === CFG.event) {{
          setTimeout(() => {{
            list.forEach((h) => {{
              try {{ h.handler({{ event: args.event, id: h.id, payload: null }}); }} catch (e) {{}}
            }});
          }}, 30);
        }}
        return id;
      }}
      if (cmd === "plugin:event|unlisten") {{
        const list = eventHandlers.get(args.event) || [];
        eventHandlers.set(args.event, list.filter((h) => h.id !== args.eventId));
        return null;
      }}
      const fn = IMPL[cmd];
      if (!fn) {{
        throw new Error("IPC 替身没有实现命令: " + cmd);
      }}
      return fn(args || {{}});
    }},
    transformCallback: (cb, once) => {{
      const id = seq++;
      shim.__callbacks = shim.__callbacks || {{}};
      shim.__callbacks[id] = {{ cb, once }};
      return id;
    }},
    __callbacks: {{}},
  }};
  window.__TAURI_INTERNALS__ = shim;
}})();
"""
    return js


# ---------------------------------------------------------------- 运行环境


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_http(url: str, timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(1.0)
    return False


def start_backend(python_exe: str, port: int, log_path: pathlib.Path) -> subprocess.Popen:
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = str(REPO) + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    log = log_path.open("w", encoding="utf-8")
    return subprocess.Popen(
        [
            python_exe,
            "-m",
            "uvicorn",
            "forgemind.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(REPO),
        stdout=log,
        stderr=subprocess.STDOUT,
        env=env,
    )


def start_static_server(out_dir: pathlib.Path, port: int) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "http.server",
            str(port),
            "--bind",
            "127.0.0.1",
            "--directory",
            str(out_dir),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def pick_backend_python(explicit: str | None) -> str:
    """挑一个能起后端的解释器 —— 必须真的有 fastapi 与 uvicorn。"""
    candidates = [explicit] if explicit else []
    candidates += [sys.executable, "/workspace/testenv/bin/python3", "python3"]
    for cand in candidates:
        if not cand:
            continue
        exe = shutil.which(cand) or (cand if pathlib.Path(cand).is_file() else None)
        if not exe:
            continue
        probe = subprocess.run(
            [exe, "-c", "import fastapi, uvicorn, duckdb"],
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            return exe
    raise SystemExit(
        "找不到能起后端的 Python(需要 fastapi / uvicorn / duckdb)。\n"
        "用 --backend-python 指定一个装齐了这三个包的解释器。"
    )


# ---------------------------------------------------------------- 采集


def capture(args: argparse.Namespace) -> int:
    contract = parse_rust()
    app_version, tauri_version = cargo_versions()
    shim = build_shim(contract, app_version, tauri_version)

    out_dir = pathlib.Path(args.out).resolve()
    repo_resolved = REPO.resolve()
    if repo_resolved in out_dir.parents:
        raise SystemExit(
            f"输出目录 {out_dir} 在仓库 {repo_resolved} 里面 —— 截图不进版本库,"
            "仓库必须保持干净。请换一个仓库外的目录。"
        )
    out_dir.mkdir(parents=True, exist_ok=True)

    if not STATIC_OUT.is_dir() or not (STATIC_OUT / "index.html").is_file():
        raise SystemExit(
            f"没有找到导出的静态页 {STATIC_OUT / 'index.html'}。\n"
            "先构建:forgemind-ui 目录下 npx next build"
        )

    base = contract["base"]
    m = re.match(r"http://([0-9.]+):(\d+)", base)
    if not m:
        raise SystemExit(f"抽不出后端地址:{base}")
    port = int(m.group(2))

    python_exe = pick_backend_python(args.backend_python)
    backend_log = out_dir / "backend.log"
    backend = start_backend(python_exe, port, backend_log)
    static_port = free_port()
    static = start_static_server(STATIC_OUT, static_port)

    problems: list[str] = []
    shots: list[dict] = []
    try:
        if not wait_http(f"{base}/health", timeout=120):
            raise SystemExit(
                f"后端没在 {base} 起来,日志见 {backend_log}\n"
                + backend_log.read_text(encoding="utf-8", errors="ignore")[-2000:]
            )
        shots = _run_browser(args, out_dir, shim, static_port, app_version, problems)
    finally:
        for proc in (static, backend):
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()

    manifest = {
        "app_version": app_version,
        "tauri_version": tauri_version,
        "source_commit": _git_commit(),
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "backend": base,
        "shots": shots,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if problems:
        print("采集过程中发现问题:")
        for p in problems:
            print(" -", p)
        return 1
    print(f"采集完成:{len(shots)} 张截图,清单见 {out_dir / 'manifest.json'}")
    return 0


def _git_commit() -> str:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _run_browser(
    args: argparse.Namespace,
    out_dir: pathlib.Path,
    shim: str,
    static_port: int,
    app_version: str,
    problems: list[str],
) -> list[dict]:
    from playwright.sync_api import sync_playwright

    url = f"http://127.0.0.1:{static_port}/"
    shots: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(
            viewport={"width": 1680, "height": 1050},
            device_scale_factor=2,
        )
        console: list[str] = []
        page.on("console", lambda msg: console.append(f"{msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: console.append(f"pageerror: {err}"))
        page.add_init_script(shim)
        page.goto(url, wait_until="domcontentloaded")

        # 版本徽章:get_system_status 走通了才会显示真版本
        try:
            page.wait_for_selector(f"text=v{app_version}", timeout=60_000)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"页面上没等到版本徽章 v{app_version}: {exc}")
            _dump_console(console, problems)
            browser.close()
            return shots

        # 逐个面板确认是真数据:该有的文字在,且没有占位文案
        def expect_any_text(texts: list[str], what: str, timeout: int = 45_000) -> bool:
            """几个候选里等到任意一个就算数。

            盯的是**语义**不是某一句文案:界面改个措辞,证据不该跟着
            失效 —— 上一次就是这么变成"永远差一个面板"的(界面把
            "6 Agent 投票" 改成 "6 Agent 综合",采集脚本仍在等旧文案,
            每次都报同一个问题,而面板其实好好的)。
            """
            for text in texts:
                try:
                    page.wait_for_selector(f"text={text}", timeout=timeout)
                    return True
                except Exception:  # noqa: BLE001
                    continue
            problems.append(f"等不到{what}:{' / '.join(texts)}")
            return False

        def expect_agent_panel(timeout: int = 45_000) -> bool:
            """决策相关的面板要渲染出来。

            盯的是**语义**不是某一句文案:界面改个措辞,证据不该跟着
            失效 —— 上一次就是这么变成"永远差一个面板"的(界面把
            "6 Agent 投票" 改成 "6 Agent 综合",采集脚本仍在等旧文案,
            每次都报同一个问题,而面板其实好好的)。
            """
            return expect_any_text(
                ["多 Agent 决策", "6 Agent 综合决策记录", "暂无 6 Agent 真实决策"],
                "决策面板",
                timeout=timeout,
            )

        def expect_agent_votes(timeout: int = 45_000) -> bool:
            """决策面板要显示真投票,不是空状态。

            判据是"空状态那句不在了":有票时面板列的是 6 个 Agent 的
            论据,没票时写"暂无 6 Agent 真实决策"。盯后者在不在,比盯
            某一句文案稳(界面的措辞会变)。
            """
            try:
                page.wait_for_selector("text=多 Agent 决策", timeout=timeout)
            except Exception:  # noqa: BLE001
                problems.append("等不到决策面板")
                return False
            if page.locator("text=暂无 6 Agent 真实决策").count() > 0:
                problems.append(
                    "决策面板还是空状态 —— 审批没有落库,或者界面没读到落库的决策"
                )
                return False
            return True

        def expect_text(text: str, timeout: int = 45_000) -> bool:
            try:
                page.wait_for_selector(f"text={text}", timeout=timeout)
                return True
            except Exception:  # noqa: BLE001
                problems.append(f"等不到面板文字:{text}")
                return False

        def assert_no_placeholder() -> None:
            """面板里不该留着"加载中"这类占位。

            等它消失再判定 —— 数据是异步到的,截图那一刻还在加载,
            不该算成问题;但等了很久还在,就是真有问题。
            """
            for bad in ("加载数据...", "暂无数据"):
                try:
                    page.wait_for_selector(f"text={bad}", state="detached", timeout=25_000)
                except Exception:  # noqa: BLE001
                    problems.append(f"页面上还留着占位文案:{bad}")

        def snap(name: str, description: str, locator=None) -> None:
            path = out_dir / f"{name}.png"
            if locator is not None:
                locator.screenshot(path=str(path))
            else:
                page.screenshot(path=str(path), full_page=True)
            shots.append({"name": name, "description": description, "file": path.name})
            print(f"  {name}.png —— {description}")

        # 1. 默认工作区
        expect_text("组合概览")
        expect_text("交易信号")
        assert_no_placeholder()
        snap("01-workspace-default", "默认工作区:K线 + Agent 决策 + 交易信号 + 组合概览")

        # 2. 面板特写
        panels = page.locator("section > div > *")
        if panels.count() >= 3:
            snap("02-kline", "K线面板(600519.SH 真日线)", panels.nth(0))
            snap("03-agent-decision", "多 Agent 决策面板(真投票)", panels.nth(1))
            snap("04-signal-table", "交易信号表(真落盘信号)", panels.nth(2))
        else:
            problems.append(f"中间栏面板数量不对:{panels.count()}")

        sides = page.locator("aside")
        if sides.count() >= 2:
            snap("05-strategy-panel", "策略库(真策略清单)", sides.nth(0))
            snap("06-portfolio-panel", "组合概览(真持仓与风险指标)", sides.nth(1))
        else:
            problems.append(f"侧栏数量不对:{sides.count()}")

        # 3. 研究布局:⌘K → 切换到研究布局
        page.keyboard.press("Meta+k")
        page.wait_for_timeout(600)
        if page.locator("text=切换到研究布局").count() == 0:
            page.keyboard.press("Control+k")
            page.wait_for_timeout(600)
        if page.locator("text=切换到研究布局").count() == 0:
            problems.append("命令面板打不开,切不了布局")
        else:
            page.locator("text=切换到研究布局").first.click()
            page.wait_for_timeout(1500)
            expect_text("IC")
            expect_agent_panel()
            assert_no_placeholder()
            snap("07-workspace-research", "研究布局:因子库 + 研究日志 + 组合概览")
            # 因子库有 169 行,研究日志在它下面 —— 中间栏是可滚动的,
            # 整页截图拍不到它,单独给一张特写
            research_panels = page.locator("section > div > *")
            if research_panels.count() >= 2:
                snap(
                    "07b-research-log", "研究日志面板(后端落盘的真决策记录)", research_panels.nth(1)
                )
            else:
                problems.append(f"研究布局的面板数量不对:{research_panels.count()}")

        # 4. 交易布局
        page.keyboard.press("Meta+k")
        page.wait_for_timeout(600)
        if page.locator("text=切换到交易布局").count() == 0:
            page.keyboard.press("Control+k")
            page.wait_for_timeout(600)
        if page.locator("text=切换到交易布局").count() > 0:
            page.locator("text=切换到交易布局").first.click()
            page.wait_for_timeout(1500)
            expect_text("K 线")
            assert_no_placeholder()
            snap("08-workspace-trading", "交易布局:K线 + 交易信号 + 策略库")
        else:
            problems.append("切不到交易布局")

        # 5. 命令面板
        page.keyboard.press("Meta+k")
        page.wait_for_timeout(600)
        if page.locator("text=切换到研究布局").count() == 0:
            page.keyboard.press("Control+k")
            page.wait_for_timeout(600)
        if page.locator("text=切换到研究布局").count() > 0:
            snap("09-command-palette", "命令面板(真实命令清单)")

        # 6. 桌面端真点一遍人工审批:决策准备 → 拍板 → 落库 → 面板刷新
        #    这条链路一直只有单测与协议层调用覆盖着,界面上的那条路没点过。
        dialogs: list[str] = []

        def on_dialog(dialog) -> None:  # noqa: ANN001
            dialogs.append(dialog.message)
            dialog.accept()

        page.on("dialog", on_dialog)

        def open_palette() -> bool:
            """把命令面板打开。已经开着就别再按快捷键 —— 那会把它关掉。"""
            if page.locator("input[type=text]").count() > 0:
                return True
            for key in ("Control+k", "Meta+k"):
                page.keyboard.press(key)
                page.wait_for_timeout(700)
                if page.locator("input[type=text]").count() > 0:
                    return True
            return False

        def run_palette_command(query: str) -> str:
            """在命令面板里搜一条命令并回车执行,返回它弹出的提示文本。"""
            if not open_palette():
                problems.append(f"命令面板打不开,执行不了:{query}")
                return ""
            box = page.locator("input[type=text]").first
            box.fill(query)
            page.wait_for_timeout(500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(3000)
            return dialogs[-1] if dialogs else ""

        prepared = run_palette_command("AI 决策准备")
        if "停在人工审批前" not in prepared:
            problems.append(f"桌面的 AI 决策准备没走通: {prepared[:120]}")
        approved = run_palette_command("批准刚才的 AI 决策")
        if "已落库" not in approved:
            problems.append(f"桌面的审批没有落库: {approved[:120]}")
        else:
            # 回到默认布局再拍 —— 决策面板在那边。这张图的名字写着
            # "决策已拍板并落库",图里却拍的是交易布局、没有决策,证据就
            # 名不副实:看图的人看不出审批到底发生了什么。
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            # 布局会被记住(上一轮停在交易布局),回到默认布局 —— 决策面板
            # 只在默认布局里,停在交易布局就拍不到它。
            default_button = page.get_by_role("button", name="default")
            if default_button.count() > 0:
                default_button.first.click()
                page.wait_for_timeout(1500)
            # 这一张要的是**真投票**:空状态说明决策还没落库,
            # 不能拿它当"已拍板"的证据。
            expect_agent_votes()
            snap("10-desktop-agent-approved", "桌面端真点一遍人工审批:决策已拍板并落库")

        _dump_console(console, problems)
        browser.close()
    return shots


def _dump_console(console: list[str], problems: list[str]) -> None:
    errors = [c for c in console if c.startswith("error") or c.startswith("pageerror")]
    for err in errors[:10]:
        problems.append(f"页面报错:{err[:200]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="对着真后端采集桌面端界面截图")
    parser.add_argument("--out", required=True, help="输出目录(必须在仓库之外)")
    parser.add_argument("--backend-python", default=None, help="起后端用的 Python 解释器")
    args = parser.parse_args()
    return capture(args)


if __name__ == "__main__":
    sys.exit(main())
