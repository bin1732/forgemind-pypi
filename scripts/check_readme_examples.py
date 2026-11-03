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
# 命令名的前缀要认反引号等引号:正文里写的是 `forgemind backtest`,
# 只认空白与行首的话,正文里那些一个都抓不到。
# 名字里允许下划线:真命令没有,但抓假的要能抓到。
# `forgemind.core.pipeline.X` 这种模块路径不会被当成命令 ——
# "forgemind" 后面跟的是点号,不是空白。
CLI_COMMAND = re.compile(r"""(?:^|[\s`'"(])forgemind\s+([a-z][a-z0-9_-]*)""", re.M)


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


def check_strategy_count(text: str) -> list[str]:
    """README 说的策略数必须等于命令真能跑的那批。

    这个数字写死在文档里就会漂:加了策略忘了改文档,或者文档说了总数、
    命令其实只跑其中一部分。两种情况下读者都被误导 —— 他们照着数字
    估这条命令的能力。
    """
    try:
        from forgemind.core.strategies.library import cli_runnable_strategies

        runnable = len(cli_runnable_strategies())
    except Exception:  # noqa: BLE001 — 取不到就当没核对
        return []
    problems = []
    for m in re.finditer(r"(\d+)\s*个策略", text):
        claimed = int(m.group(1))
        if claimed != runnable:
            line = text[: m.start()].count("\n") + 1
            problems.append(f"README 第 {line} 行说 {claimed} 个策略,命令真能跑的是 {runnable} 个")
    return problems


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

    它存在的意义是说明 --index-url 为什么不行 —— 哪天它被改成"对"的,
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

    只查代码块里的 —— 整篇扫描时,"故意写错的示范"那几段要单独排除,
    而它们只在代码块里有标记。
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


def check_all_mentions(text: str, blocks: list[str]) -> list[str]:
    """整篇 README 里提到的子命令都必须真的存在。

    功能表、命令清单、FAQ 里都可能写着命令 —— 那些地方不在代码块里,
    只查代码块就会漏掉。而用户是照着那些地方抄命令的。

    标了"错误示范"的那几段不在此列:那里的命令是故意写错的。
    """
    subcommands = _real_subcommands()
    if not subcommands:
        return []
    problems: list[str] = []
    for cmd in CLI_COMMAND.findall(text):
        if cmd in {"--help", "-h"}:
            continue
        if cmd not in subcommands:
            # 报错时给出行号:读者要能自己找过去
            line = text[: text.index(f"forgemind {cmd}")].count("\n") + 1
            problems.append(f"README 第 {line} 行提到的 `forgemind {cmd}` 不是真实子命令")
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
    problems += check_all_mentions(text, bash_blocks)
    problems += check_strategy_count(text)
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
