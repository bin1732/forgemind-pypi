#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""命令行的输出不能把内部实现摊给用户。

每个子命令都在一台"全新的机器"上真跑一遍(空的本地库、没有密钥),
然后逐行扫它的输出。规则分两类:

- **stdout 是用户的输出通道**:里面不许出现 SQL 片段、Python 栈回溯、
  异常类型名、本机绝对路径、原始日志 JSON。这些是内部实现,用户读到
  它们只会以为程序坏了 —— 而程序其实没坏,只是"还没拉数据"。
- **stderr 是运维的日志通道**:结构化日志本来就该在那里,不算问题。
  但 SQL、栈回溯、绝对路径仍然不行 —— 那些连运维也用不上。

**内部表名是例外,但要有个条件**:输出里可以提到表(用户要知道自己把
信号落在哪),但那个表名必须在 README 里有交代。说了却没写,就是内部
细节漏出去了。

用法:
    python scripts/check_cli_output_clean.py [仓库根目录]
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 内部实现的四种形态:SQL 片段、栈回溯、异常类型名、本机路径。
# 这四种在哪个通道都不该出现 —— 命令行与接口共用同一份判据,写在
# 一处,免得两处慢慢漂开。
LEAK_PATTERNS: list[tuple[str, str]] = [
    (
        r"(?i)\b(SELECT\s+.+?\s+FROM|information_schema|WHERE\s+\w+\s*=\s*\?|"
        r"ORDER BY\s+\w|LINE \d+:)",
        "SQL 片段",
    ),
    (r"(?i)Traceback \(most recent call last\)", "Python 栈回溯"),
    (
        r"(?i)\b(CatalogException|KeyError|TypeError|ValueError|AttributeError|"
        r"RuntimeError|OSError|FileNotFoundError|ImportError|DuckDBError)\b",
        "异常类型名",
    ),
    # 上面那份是常见异常;这里是兜底:任何"大写开头 + Error/Exception
    # 收尾"的类名都是内部实现。列清单永远列不全 —— 第三方库自己的
    # 异常类(如 AKShareTimeoutError)不在名单里,却一样不该出现在
    # 用户看得到的文字里。
    (r"\b[A-Z][A-Za-z0-9]*(?:Error|Exception)\b", "异常类型名"),
    (r"site-packages|/home/[a-z]|/Users/|[A-Za-z]:\\\\", "本机绝对路径"),
]

# 原始日志 JSON:一行结构化日志混进了用户通道。
#
# 这一条只属于文本通道 —— 接口的响应体是结构化的,"timestamp" 在那里
# 是一个正经字段(信号时间、健康检查时间),单看它不能算漏。接口那边
# 用结构化的判据:find_log_records()。
LOG_JSON_PATTERNS: list[tuple[str, str]] = [
    (r'"event"\s*:|"exc_type"|"exc_msg"|"timestamp"\s*:', "原始日志 JSON"),
]

# 日志记录的键。接口那边用:一个对象里同时出现两个以上这些键,
# 就是一条日志记录混进了响应体。
LOG_RECORD_KEYS = ("event", "level", "timestamp", "exc_type", "exc_msg", "exc_info")

# 用户通道与运维通道分开:同一批特征,两边的严格程度不同。
STRICT_PATTERNS: list[tuple[str, str]] = LEAK_PATTERNS + LOG_JSON_PATTERNS
LOOSE_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)\b(SELECT\s+.+?\s+FROM|information_schema|LINE \d+:)", "SQL 片段"),
    (r"(?i)Traceback \(most recent call last\)", "Python 栈回溯"),
    (r"site-packages|/home/[a-z]|/Users/|[A-Za-z]:\\\\", "本机绝对路径"),
]

# 内部表名:出现在输出里没关系,但必须在 README 里有交代。
TABLE_NAMES = (
    "kline_daily",
    "signal_history",
    "portfolio_decision",
    "portfolio_snapshot",
    "backtest_run",
)

# 要真跑的命令。etl 要联网(装 akshare),mcp 是服务(不会自己退出),
# 都不在这里跑 —— 前者由真实取数的那一档验,后者由 MCP 那一档验。
COMMANDS: list[list[str]] = [
    ["info"],
    ["demo"],
    ["router-demo"],
    ["backtest", "--symbol", "600519", "--start", "2024-01-01", "--end", "2024-06-30"],
    ["pick", "--symbol", "600519"],
    ["signal", "--symbol", "600519"],
    ["agent", "--symbol", "600519", "--yes"],
]

COMPILED_STRICT = [(re.compile(p), label) for p, label in STRICT_PATTERNS]
COMPILED_LOOSE = [(re.compile(p), label) for p, label in LOOSE_PATTERNS]
COMPILED_LEAKS = [(re.compile(p), label) for p, label in LEAK_PATTERNS]


def _run(args: list[str], repo_root: Path, timeout: int = 240) -> tuple[int, str, str]:
    """在全新的数据目录里跑一条命令,返回 (退出码, stdout, stderr)。"""
    import os

    workdir = tempfile.mkdtemp(prefix="forgemind_clean_")
    env = dict(os.environ)
    env["FORGEMIND_DATA_DIR"] = str(Path(workdir) / "data")
    env["FORGEMIND_DUCKDB_PATH"] = str(Path(workdir) / "data" / "duckdb" / "main.db")
    env["PYTHONPATH"] = str(repo_root)
    env["PYTHONSAFEPATH"] = "1"
    # 不设 FORGEMIND_LOG_LEVEL —— 走真实用户路径(CLI 自己会把级别设成 WARNING)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "forgemind.cli", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=workdir,
        )
    except subprocess.TimeoutExpired:
        return 124, "", f"(超时 {timeout}s)"
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _scan(text: str, patterns: list[tuple[re.Pattern, str]]) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for rx, label in patterns:
        for m in rx.finditer(text):
            segment = text[max(0, m.start() - 30) : m.end() + 30].replace("\n", " ")
            hits.append((label, segment))
    return hits


def find_log_records(payload: object, _path: str = "$") -> list[str]:
    """响应体里混进来的日志记录。

    结构化判据:一个对象里同时出现两个以上日志键,就是一条日志记录
    混进了响应体。比"文本里有没有某个键"准 —— 接口的正经字段也叫
    timestamp(信号时间、健康检查时间),单看它不算漏。

    命令行那边用文本判据就够了(它的 stdout 上不该出现整条 JSON 日志);
    接口这边是结构化的,用同一件事的两种判据。
    """
    found: list[str] = []
    if isinstance(payload, dict):
        hits = sorted(set(payload) & set(LOG_RECORD_KEYS))
        if len(hits) >= 2:
            found.append(f"{_path} 里有日志字段 {hits}")
        for key, value in payload.items():
            found.extend(find_log_records(value, f"{_path}.{key}"))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            found.extend(find_log_records(value, f"{_path}[{index}]"))
    return found


def check_table_names(text: str, readme: str) -> list[str]:
    """输出里提到内部表名,README 里就得有交代。

    说了却没写,就是内部细节漏出去了;写了,那它就是对用户公开的一Promise。
    """
    problems: list[str] = []
    for table in TABLE_NAMES:
        if table in text and table not in readme:
            problems.append(f"输出里提到了内部表名 {table},而 README 里没有交代")
    return problems


def check_outputs(repo_root: Path, readme: str) -> list[str]:
    """跑一遍所有命令,返回问题清单(空 = 干净)。"""
    problems: list[str] = []
    for args in COMMANDS:
        label = "forgemind " + " ".join(args)
        rc, out, err = _run(args, repo_root)
        for stream, text, patterns in (
            ("stdout", out, COMPILED_STRICT),
            ("stderr", err, COMPILED_LOOSE),
        ):
            for kind, segment in _scan(text, patterns):
                problems.append(f"{label} 的 {stream} 里有{kind}:…{segment}…")
        # 表名:说了就要在 README 里有交代
        for item in check_table_names(out, readme):
            problems.append(f"{label} 的输出里{item}")
    return problems


def main(repo_root: Path | None = None) -> int:
    root = (repo_root or REPO).resolve()
    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8") if readme_path.is_file() else ""
    problems = check_outputs(root, readme)
    if problems:
        print("命令行的输出里有内部实现细节:")
        for item in problems:
            print(" -", item)
        return 1
    print(f"命令行输出干净({len(COMMANDS)} 条命令在全新数据目录里实跑过)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
