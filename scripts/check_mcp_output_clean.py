#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""MCP 工具的输出不能把内部实现摊给模型。

**为什么这一层要单独守**:MCP 工具的正文是直接回灌给模型的。模型读到
"CatalogException: IO Error: Could not write file /home/xxx/main.db" 会
得出两个错结论:程序坏了,以及该换参数重试。它不会想到"这台机器上的
本地库被占着"。

所以每个工具都要**带合法参数真调一遍**(不是"有没有返回",是"返回的
内容对不对"),然后逐条扫:

- 响应里不许有:异常类型名、SQL 片段、Python 栈回溯、本机绝对路径。
- 库被另一个进程占着时,读库的工具必须说"读不到/占用",**不许**说
  "没有数据" —— 说成后者,模型会去建议用户拉数据,而拉数据同样连不上
  那个库。

用法:
    python scripts/check_mcp_output_clean.py
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_cli_output_clean as leak  # noqa: E402
import mcp_tool_probes as probes  # noqa: E402

#: MCP 除了工具,还有两类原语也直接回灌给模型:prompts 与 resources。
#: 它们以前没人扫 —— 往提示词模板里写一句内部表名,或者让某个
#: resource 返回一段 SQL,都没人发现。
#:
#: prompts 要带**真实参数**:模板里的占位符没被替换的话,渲染出来的
#: 提示词会让模型拿着 "{symbol}" 去调工具。
PROMPT_PROBES: list[tuple[str, dict[str, str]]] = [
    ("stock_analysis", {"symbol": "600519.SH"}),
    ("risk_check", {"symbol": "600519.SH"}),
    ("factor_research", {"feature_name": "KMID"}),
]

#: resources 逐个读一遍。
RESOURCE_URIS: tuple[str, ...] = (
    "forgemind://features",
    "forgemind://strategies",
    "forgemind://symbols",
    "forgemind://signals",
    "forgemind://brokers",
    "forgemind://portfolio",
)

#: "读不到"该有的说法。库被占着时,输出里至少要有一个。
UNREADABLE_MARKERS = ("读不到", "占用", "暂时用不了")

#: "没有数据"的说法。这些词在**库被占着**的时候出现,就是错的。
MISSING_MARKERS = ("没有 K 线", "无数据", "库里没有", "没有该标的")

#: 内部实现不许出现在响应里的形态(与命令行的判据同源)。
FORBIDDEN = ("异常类名", "SQL 片段", "Python 栈回溯", "本机绝对路径")


def _mcp_client(db_path: Path, extra_env: dict[str, str] | None = None):
    """起一个真 MCP server(stdio),返回 (send, read, 进程)。"""
    env = dict(os.environ)
    env["FORGEMIND_DUCKDB_PATH"] = str(db_path)
    env["FORGEMIND_LOG_LEVEL"] = "ERROR"
    env["FORGEMIND_NONINTERACTIVE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO), env.get("PYTHONPATH", "")],
    ).rstrip(os.pathsep)
    env["PYTHONSAFEPATH"] = "1"
    if extra_env:
        env.update(extra_env)

    proc = subprocess.Popen(
        [sys.executable, "-m", "forgemind.cli", "mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
        bufsize=1,
        cwd=str(REPO),
    )
    q: queue.Queue = queue.Queue()

    def pump() -> None:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                q.put(json.loads(line))
            except json.JSONDecodeError:
                pass

    threading.Thread(target=pump, daemon=True).start()

    def send(obj: dict) -> None:
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    def read(timeout: float = 90.0):
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            return None

    send(
        {
            "jsonrpc": "2.0",
            "id": "init",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "check", "version": "1"},
            },
        }
    )
    read()
    return send, read, proc


def _close(proc) -> None:
    try:
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=10)
    except Exception:  # noqa: BLE001
        proc.kill()


def _call(send, read, name: str, args: dict, call_id: str = "call") -> str:
    send(
        {
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        }
    )
    response = read()
    if response is None:
        return ""
    return probes.tool_text(response)


def _seed_klines(db_path: Path, symbols=("600519", "000001"), days: int = 40) -> None:
    """按 ETL 的建表路径落一份 K 线,让工具能真的跑出结果。"""
    from datetime import date, timedelta

    from forgemind.core.data.storage import DuckDBStorage

    env_backup = os.environ.get("FORGEMIND_DUCKDB_PATH")
    os.environ["FORGEMIND_DUCKDB_PATH"] = str(db_path)
    try:
        with DuckDBStorage() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS kline_daily ("
                "date DATE, symbol VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, "
                "close DOUBLE, volume BIGINT, provider VARCHAR, "
                "PRIMARY KEY (date, symbol))"
            )
            rows = []
            for si, sym in enumerate(symbols):
                for i in range(days):
                    d = date(2024, 1, 2) + timedelta(days=i)
                    if d.weekday() >= 5:
                        continue
                    close = 100.0 * (1 + 0.002 * (si + 1)) ** i
                    rows.append(
                        (
                            d,
                            sym,
                            close * 0.998,
                            close * 1.005,
                            close * 0.995,
                            round(close, 4),
                            1_000_000,
                            "probe",
                        )
                    )
            for row in rows:
                db.execute(
                    "INSERT INTO kline_daily (date, symbol, open, high, low, close, "
                    "volume, provider) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    list(row),
                )
    finally:
        if env_backup is None:
            os.environ.pop("FORGEMIND_DUCKDB_PATH", None)
        else:
            os.environ["FORGEMIND_DUCKDB_PATH"] = env_backup


def _lock_holder(db_path: Path):
    """起一个真进程占着这个库文件。"""
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import duckdb, sys, time\n"
                "con = duckdb.connect(sys.argv[1])\n"
                "print('held', flush=True)\n"
                "time.sleep(600)\n"
            ),
            str(db_path),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    proc.stdout.readline()
    return proc


def _scan_problems(label: str, text: str, readme: str) -> list[str]:
    """一段正文里有没有内部实现。返回问题清单(空 = 干净)。"""
    problems: list[str] = []
    for kind, segment in leak._scan(text, leak.COMPILED_LEAKS):
        problems.append(f"{label}: 输出里有{kind}: ...{segment}...")
    # 内部表名:说了就要在 README 里有交代
    for item in leak.check_table_names(text, readme):
        problems.append(f"{label}: 输出里{item}")
    return problems


def check_prompts_and_resources(send, read, readme: str) -> list[str]:
    """prompts 与 resources 也直接回灌给模型,一样要扫。"""
    problems: list[str] = []
    for name, args in PROMPT_PROBES:
        send(
            {
                "jsonrpc": "2.0",
                "id": f"prompt-{name}",
                "method": "prompts/get",
                "params": {"name": name, "arguments": args},
            }
        )
        response = read()
        if response is None:
            problems.append(f"[prompts] {name}: 没有返回内容")
            continue
        if "error" in response:
            problems.append(f"[prompts] {name}: 调用报错 —— {response['error'].get('message')}")
            continue
        messages = (response.get("result") or {}).get("messages") or []
        text = " ".join(str(m.get("content", {}).get("text", "")) for m in messages)
        if not text:
            problems.append(f"[prompts] {name}: 渲染出来的提示词是空的")
            continue
        problems.extend(_scan_problems(f"prompts/{name}", text, readme))

    for uri in RESOURCE_URIS:
        send(
            {
                "jsonrpc": "2.0",
                "id": f"res-{uri}",
                "method": "resources/read",
                "params": {"uri": uri},
            }
        )
        response = read()
        if response is None:
            problems.append(f"[resources] {uri}: 没有返回内容")
            continue
        if "error" in response:
            problems.append(f"[resources] {uri}: 读取报错 —— {response['error'].get('message')}")
            continue
        contents = (response.get("result") or {}).get("contents") or []
        text = " ".join(str(c.get("text", "")) for c in contents)
        if not text:
            problems.append(f"[resources] {uri}: 没有内容")
            continue
        problems.extend(_scan_problems(f"resources/{uri}", text, readme))
    return problems


def check_tool_outputs(send, read, label: str) -> list[str]:
    """逐个工具带合法参数真调一遍,扫输出里的内部实现。"""
    problems: list[str] = []
    for name, args in probes.TOOL_CALLS:
        try:
            call_args = probes.legal_args(name, args)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{label} {name}: 准备参数失败 —— {type(exc).__name__}")
            continue
        text = _call(send, read, name, call_args, call_id=f"probe-{name}")
        if not text:
            problems.append(f"{label} {name}: 没有返回内容")
            continue
        for kind, segment in leak._scan(text, leak.COMPILED_LEAKS):
            if kind in FORBIDDEN:
                problems.append(f"{label} {name}: 输出里有{kind}: ...{segment}...")
    return problems


def check_locked_output(name: str, text: str) -> list[str]:
    """库被占着时,这个工具的输出合不合规矩。

    单独抽出来,是为了能用**编出来的输出**逐条钉规则 —— 规则没生效
    与场景没造出来,在真跑里长得一模一样。
    """
    problems: list[str] = []
    if not text:
        return [f"[库被占着] {name}: 没有返回内容"]
    if any(marker in text for marker in MISSING_MARKERS):
        problems.append(
            f"[库被占着] {name}: 输出说'没有数据' —— 连都没连上,不知道有没有。"
            f"应当说:{'/'.join(UNREADABLE_MARKERS)}"
        )
    if not any(marker in text for marker in UNREADABLE_MARKERS):
        problems.append(
            f"[库被占着] {name}: 没说要读不到 —— 模型不知道该做什么,"
            f"只会建议用户去拉数据,而拉数据同样连不上那个库"
        )
    for kind, segment in leak._scan(text, leak.COMPILED_LEAKS):
        if kind in FORBIDDEN:
            problems.append(f"[库被占着] {name}: 输出里有{kind}: ...{segment}...")
    return problems


def check_locked_store_says_unreadable(db_path: Path) -> list[str]:
    """库被占着时,读库的工具必须说读不到,不许说没有数据。"""
    problems: list[str] = []
    holder = _lock_holder(db_path)
    send = read = None
    proc = None
    try:
        send, read, proc = _mcp_client(db_path)
        for name, args in probes.TOOL_CALLS:
            if name not in probes.TOOLS_TOUCHING_STORE:
                continue
            text = _call(send, read, name, dict(args), call_id=f"locked-{name}")
            problems.extend(check_locked_output(name, text))
    finally:
        if proc is not None:
            _close(proc)
        holder.terminate()
        try:
            holder.wait(timeout=10)
        except subprocess.TimeoutExpired:
            holder.kill()
    return problems


def main() -> int:
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="forgemind_mcp_probe_") as tmp:
        work = Path(tmp)
        db = work / "duckdb" / "main.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        _seed_klines(db)

        readme = (REPO / "README.md").read_text(encoding="utf-8")
        send, read, proc = _mcp_client(db)
        try:
            problems.extend(check_tool_outputs(send, read, "[逐个工具]"))
            problems.extend(check_prompts_and_resources(send, read, readme))
        finally:
            _close(proc)

        time.sleep(0.3)
        problems.extend(check_locked_store_says_unreadable(db))

    if problems:
        print(f"MCP 工具输出不干净({len(problems)} 处):")
        for item in problems:
            print(" -", item)
        return 1
    print(
        f"MCP 输出干净({len(probes.TOOL_CALLS)} 个工具逐个真调过,"
        f"外加库被占着时 {len(probes.TOOLS_TOUCHING_STORE)} 个读库工具的状态核对,"
        f"以及 {len(PROMPT_PROBES)} 个提示词与 {len(RESOURCE_URIS)} 个资源)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
