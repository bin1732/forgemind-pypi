#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""接口的响应不能把内部实现摊给调用方。

**为什么这一层要单独守**:命令行与 MCP 各有一份输出判据,接口这条通道
原来没有 —— 于是接口的错误响应里出现过异常类名、本机路径、整条 SQL,
没人发现。第三方调用方拿到 "CatalogException: IO Error: Could not write
file /home/xxx/main.db" 会得出两个错结论:服务坏了,以及换个参数重试
就行。它不会想到"这台机器上的本地库被占着"。

所以每个端点都要**带合法参数真打一遍**(不是"有没有返回",是"返回的
内容对不对"),然后逐条扫:

- 响应里不许有:异常类型名、SQL 片段、Python 栈回溯、本机绝对路径。
- 库被另一个进程占着时,读库的端点必须说"读不到/占用",**不许**说
  "没有数据" —— 说成后者,调用方会去拉数据,而拉数据同样连不上那个库。
- 错误响应必须有能读的说明,不能只有一个状态码。

用法:
    python scripts/check_api_output_clean.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_cli_output_clean as leak  # noqa: E402
import check_mcp_output_clean as mcp  # noqa: E402

#: "读不到"的说法。库被占着时,响应里得出现其中之一。
UNREADABLE_MARKERS = ("读不到", "占用", "暂时用不了", "不可用")

#: "没有数据"的说法。这些词在**库被占着**时出现就是错的 —— 连都没
#: 连上,不知道有没有,说成"没有"会把人引到一条同样跑不通的路上。
MISSING_MARKERS = ("没有 K 线", "无数据", "库里没有", "没有该标的", "没有组合快照")

#: 内部实现不许出现在响应里的形态(与命令行、MCP 的判据同源)。
FORBIDDEN = ("异常类名", "SQL 片段", "Python 栈回溯", "本机绝对路径")


#: 每个端点打两次:一次正常的,一次会出错的。
#:
#: "会出错"那一档才是关键 —— 成功的响应里当然没有内部实现,而失败
#: 路径才是最容易漏的地方:处理里 catch 住异常,把 str(exc) 塞进
#: detail,一句 "CatalogException: ..." 就出去了。
API_PROBES: tuple[tuple[str, str, dict, str], ...] = (
    ("GET", "/health", {}, "健康检查"),
    ("GET", "/api/v1/info", {}, "版本与配置"),
    ("GET", "/api/v1/features", {}, "因子清单"),
    ("GET", "/api/v1/features/search", {"params": {"query": "momentum"}}, "因子搜索"),
    ("GET", "/api/v1/health/services", {}, "各服务连通状态"),
    ("GET", "/api/v1/portfolio", {}, "组合快照"),
    ("GET", "/mcp", {}, "MCP 描述"),
    ("GET", "/mcp/tools/list", {}, "工具清单"),
    ("GET", "/mcp/resources/list", {}, "资源清单"),
    ("GET", "/mcp/prompts/list", {}, "提示词清单"),
    (
        "POST",
        "/api/v1/backtest/run",
        {"json": {"start_date": "bad", "end_date": "2024-06-01"}},
        "回测参数非法",
    ),
    (
        "POST",
        "/api/v1/backtest/run",
        {
            "json": {
                "start_date": "2024-01-01",
                "end_date": "2024-06-01",
                "fast_period": 50,
                "slow_period": 10,
            }
        },
        "回测快慢线颠倒",
    ),
    ("POST", "/api/v1/agent/decide", {"json": {"symbol": "600519.SH"}}, "决策缺账户状态"),
    ("POST", "/api/v1/agent/decide", {"json": {"symbol": "", "cash": 1000}}, "决策标的不合法"),
    ("POST", "/api/v1/agent/decide", {"json": {"symbol": "600519.SH", "cash": -1}}, "决策现金为负"),
    ("POST", "/api/v1/agent/thread-does-not-exist/approve", {"json": {}}, "审批不存在的决策"),
    ("POST", "/api/v1/agent/thread-does-not-exist/reject", {"json": {}}, "驳回不存在的决策"),
    (
        "POST",
        "/mcp/tools/call",
        {"json": {"name": "no_such_tool", "arguments": {}}},
        "调不存在的工具",
    ),
    ("POST", "/mcp/tools/call", {"json": {"name": "get_kline", "arguments": {}}}, "工具参数缺失"),
    ("POST", "/mcp/resources/read", {"json": {"uri": "forgemind://nope"}}, "读不存在的资源"),
    ("POST", "/api/pipeline/run", {"json": {"symbols": "not-a-list"}}, "流水线参数非法"),
)

#: 读库的端点:库被占着时,这些必须说"读不到"。
READ_DB_PATHS = ("/api/v1/portfolio", "/api/v1/features")


def _client():
    """一个真客户端(进程内 TestClient,不占端口)。"""
    from fastapi.testclient import TestClient

    from forgemind.api.main import app

    return TestClient(app)


def _headers(path: str) -> dict:
    """本机专用端点要带桌面端那个头(定义只有一处,在 API 模块里)。"""
    from forgemind.api.main import MCP_CLIENT_HEADER, MCP_CLIENT_VALUE

    if any(path.startswith(p) for p in ("/mcp", "/api/pipeline")):
        return {MCP_CLIENT_HEADER: MCP_CLIENT_VALUE}
    return {}


def _text_of(response) -> str:
    try:
        return response.text
    except Exception:  # noqa: BLE001
        return ""


def check_responses(client, readme: str) -> list[str]:
    """逐个端点真打一遍,扫响应里的内部实现。"""
    problems: list[str] = []
    for method, path, kwargs, label in API_PROBES:
        try:
            response = client.request(method, path, headers=_headers(path), **kwargs)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"[{label}] {method} {path}: 调用本身失败 —— {type(exc).__name__}")
            continue
        text = _text_of(response)
        if not text.strip():
            problems.append(f"[{label}] {method} {path}: 没有返回内容")
            continue
        for kind, segment in leak._scan(text, leak.COMPILED_LEAKS):
            if kind in FORBIDDEN:
                problems.append(f"[{label}] {method} {path}: 响应里有{kind}: ...{segment}...")
        problems.extend(leak.check_table_names(text, readme))
        # 错误响应必须带能读的说明 —— 只有状态码等于没回话
        if response.status_code >= 400:
            if not _has_explanation(response):
                problems.append(
                    f"[{label}] {method} {path}: 错误响应里没有说明 —— "
                    f"只有状态码 {response.status_code},调用方不知道发生了什么"
                )
    return problems


def _has_explanation(response) -> bool:
    """错误响应里有没有一句人能读的话。"""
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        return bool(response.text.strip())
    if isinstance(body, dict):
        return bool(body.get("detail") or body.get("error") or body.get("message"))
    return bool(body)


def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _serve_api(db_path: Path, port: int) -> subprocess.Popen:
    """起一个真的接口服务(子进程)。

    **必须跨进程**:DuckDB 的文件锁是进程级的 —— 本进程只要打开过那个
    库文件,就一直持有它的锁,于是"库被另一个进程占着"这件事在进程内
    永远造不出来(连接再关也不释放)。在同一进程里用 TestClient 打,端点
    会照常读到"没有快照",判据据此报一个假红。
    """
    env = dict(os.environ)
    env["FORGEMIND_DUCKDB_PATH"] = str(db_path)
    env["FORGEMIND_DATA_DIR"] = str(db_path.parent.parent / "data")
    env["FORGEMIND_LOG_LEVEL"] = "ERROR"
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "forgemind.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "error",
        ],
        cwd=str(REPO),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )


def _wait_ready(base: str, timeout: float = 90.0) -> bool:
    import time
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base + "/health", timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(1)
    return False


def check_locked_says_unreadable(db_path: Path) -> list[str]:
    """库被占着时,读库的端点必须说读不到,不许说"没有数据"。"""
    import urllib.error
    import urllib.request

    problems: list[str] = []
    port = _free_port()
    server = _serve_api(db_path, port)
    base = f"http://127.0.0.1:{port}"
    holder = mcp._lock_holder(db_path)
    try:
        if not _wait_ready(base):
            problems.append("[库被占着] 接口服务没起来,这一档没验到")
            return problems
        if holder.stdout is not None:
            holder.stdout.readline()  # 等它真的握住锁
        for path in READ_DB_PATHS:
            req = urllib.request.Request(base + path, headers=_headers(path))
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    status = r.status
                    text = r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as exc:
                status = exc.code
                text = exc.read().decode("utf-8", "replace")
            if not text.strip():
                problems.append(f"[库被占着] {path}: 没有返回内容")
                continue
            if any(marker in text for marker in MISSING_MARKERS):
                problems.append(
                    f"[库被占着] {path}: 响应说'没有数据' —— 连都没连上,不知道有没有。"
                    f"应当说:{'/'.join(UNREADABLE_MARKERS)}"
                )
            if status < 400:
                continue
            if not any(marker in text for marker in UNREADABLE_MARKERS):
                problems.append(
                    f"[库被占着] {path}: 没说要读不到 —— 调用方不知道该做什么,"
                    f"只会去拉数据,而拉数据同样连不上那个库"
                )
            for kind, segment in leak._scan(text, leak.COMPILED_LEAKS):
                if kind in FORBIDDEN:
                    problems.append(f"[库被占着] {path}: 响应里有{kind}: ...{segment}...")
    finally:
        for proc in (holder, server):
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:  # noqa: BLE001
                proc.kill()
    return problems


def check_rules_against_synthetic_samples() -> list[str]:
    """用编出来的样本双向验规则本身。

    规则没生效与场景没造出来,在真跑里长得一模一样 —— 所以规则本身
    要能单独验:该报的样本必须报出来,干净的样本必须放过。
    """
    problems: list[str] = []

    class _Resp:
        def __init__(self, status_code: int, text: str):
            self.status_code = status_code
            self.text = text

        def json(self):
            import json as _json

            return _json.loads(self.text)

    dirty = _Resp(500, '{"detail": "CatalogException: IO Error: SELECT * FROM main.kline"}')
    hits = [k for k, _ in leak._scan(dirty.text, leak.COMPILED_LEAKS)]
    if not hits:
        problems.append("规则本身失效:含异常类名与 SQL 的样本没被扫出来")

    clean = _Resp(200, '{"status": "ok", "cash": 1000.0, "message": null}')
    if leak._scan(clean.text, leak.COMPILED_LEAKS):
        problems.append("规则本身过严:干净的样本被误报")

    missing = _Resp(503, '{"detail": "库里没有该标的的行情"}')
    if not any(marker in missing.text for marker in MISSING_MARKERS):
        problems.append("规则本身失效:'没有数据'的说法没被识别出来")

    unreadable = _Resp(503, '{"detail": "本地库被另一个进程占着,暂时用不了"}')
    if not any(marker in unreadable.text for marker in UNREADABLE_MARKERS):
        problems.append("规则本身失效:'读不到'的说法没被识别出来")

    return problems


def main() -> int:
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    problems: list[str] = []

    # **数据目录要在一开始就指走**:判据默认会连仓根的 ./data —— 那既是
    # 用户的数据,也会在仓里留下诊断产物;两个判据实例同时跑还会互相
    # 撞 DuckDB 的文件锁。整段判据都在自己的临时目录里跑。
    with tempfile.TemporaryDirectory(prefix="forgemind-api-output-") as tmp:
        db_path = Path(tmp) / "duckdb" / "main.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        os.environ["FORGEMIND_DUCKDB_PATH"] = str(db_path)
        os.environ["FORGEMIND_DATA_DIR"] = str(Path(tmp) / "data")

        client = _client()
        problems.extend(check_responses(client, readme))
        problems.extend(check_rules_against_synthetic_samples())
        problems.extend(check_locked_says_unreadable(db_path))

    if problems:
        print(f"接口响应不干净({len(problems)} 处):")
        for item in problems:
            print(" -", item)
        return 1

    print(
        f"接口响应干净({len(API_PROBES)} 个端点逐个真打过,外加库被占着时 "
        f"{len(READ_DB_PATHS)} 个读库端点的状态核对,以及规则自身的双向验)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
