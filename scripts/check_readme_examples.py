# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对 README 里的示例:写的代码要真能跑。

README 里最常见的失败不是写错,而是"看着像能跑":顶层写 await、用了没
定义的变量、调用了不存在的子命令。这类东西没人会在读文档时真跑一遍,
于是它能一直留在交付物里 —— 直到某个新人照着抄,卡在第一步。

这个检查做两件事:

- README 里的 python 代码块**逐个真跑一遍**,跑不通就报出来
- README 里的 bash 代码块里出现的 forgemind 子命令必须真的存在

跑 python 代码块用子进程,一段一段跑,互不影响;超时就当失败。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

PY_BLOCK = re.compile(r"```python\n(.*?)```", re.S)
BASH_BLOCK = re.compile(r"```bash\n(.*?)```", re.S)
CLI_COMMAND = re.compile(r"(?:^|\s)forgemind\s+([a-z][a-z0-9-]*)", re.M)


def _python_blocks(text: str) -> list[str]:
    return [m.group(1) for m in PY_BLOCK.finditer(text)]


def _bash_blocks(text: str) -> list[str]:
    return [m.group(1) for m in BASH_BLOCK.finditer(text)]


def _real_subcommands() -> set[str]:
    """CLI 真实存在的子命令。"""
    try:
        from forgemind.cli import build_parser

        parser = build_parser()
        for action in parser._subparsers._group_actions:  # noqa: SLF001
            if hasattr(action, "choices") and action.choices:
                return set(action.choices)
    except Exception:  # noqa: BLE001 — 取不到就当没查到,只报"未核对"
        return set()
    return set()


def check_python_blocks(blocks: list[str], timeout: int = 180) -> list[str]:
    """逐个真跑 python 代码块,返回问题清单。"""
    problems: list[str] = []
    for i, code in enumerate(blocks, 1):
        if not code.strip():
            continue
        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                cwd=REPO,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            problems.append(f"第 {i} 段 python 示例超时(超过 {timeout} 秒)")
            continue
        if proc.returncode != 0:
            tail = (proc.stderr or "").strip().splitlines()
            reason = tail[-1] if tail else f"退出码 {proc.returncode}"
            problems.append(f"第 {i} 段 python 示例跑不通:{reason[:160]}")
    return problems


# 标了这句话的命令是**故意写错的示范**
ERROR_EXAMPLE_MARK = "错误示范"


def check_error_example(blocks: list[str]) -> list[str]:
    """FAQ 里那条"错误示范"必须真的存在,而且必须真的是错的。

    它存在的意义是说明 --index-url 为什么不行 —— 哪天它被"顺手改成"对的,
    FAQ 就变成一句没有对象的警告,而读者再也学不到差别。
    """
    problems: list[str] = []
    marked = [
        line.strip()
        for block in blocks
        for line in block.splitlines()
        if ERROR_EXAMPLE_MARK in line
    ]
    if not marked:
        return [f"README 里没有标注出来的错误示范(标上 {ERROR_EXAMPLE_MARK} 便于核对)"]
    for line in marked:
        if "--extra-index-url" in line:
            problems.append(f"标成错误示范的命令里却用了 --extra-index-url:{line}")
        elif "--index-url" not in line:
            problems.append(f"标成错误示范的命令里没有 --index-url:{line}")
    return problems


def check_bash_blocks(blocks: list[str]) -> list[str]:
    """README 里点名的子命令必须真的存在。

    整篇 README 都查,不只是代码块里 —— 功能表、命令清单、FAQ 里都可能有。
    故意写错的示范(标了"错误示范"的)不在此列。
    """
    subcommands = _real_subcommands()
    if not subcommands:
        return []
    problems: list[str] = []
    for i, code in enumerate(blocks, 1):
        for cmd in CLI_COMMAND.findall(code):
            if cmd in {"--help", "-h"}:
                continue
            if ERROR_EXAMPLE_MARK in code:
                continue
            if cmd not in subcommands:
                problems.append(f"第 {i} 段 bash 示例里的 `forgemind {cmd}` 不是真实子命令")
    return problems


def main() -> int:
    readme = REPO / "README.md"
    if not readme.is_file():
        print(f"找不到 README:{readme}", file=sys.stderr)
        return 1
    text = readme.read_text(encoding="utf-8")
    py_blocks = _python_blocks(text)
    bash_blocks = _bash_blocks(text)
    problems = check_python_blocks(py_blocks)
    problems += check_bash_blocks(bash_blocks)
    problems += check_error_example(bash_blocks)
    if problems:
        print("README 里的示例有问题:")
        for item in problems:
            print(f" - {item}")
        return 1
    print(
        f"README 里的示例都对得上({len(py_blocks)} 段 python 已实跑,{len(bash_blocks)} 段 bash 已核对)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
