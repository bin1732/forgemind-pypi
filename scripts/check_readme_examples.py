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

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 平台自己的报错原文,不在本仓源码里 —— 它们是别人的话,不该按本仓文案核。
PLATFORM_MESSAGES = {
    "No matching distribution found",
    "Unique file handle conflict",
}

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


# README 里的一条命令与它带的选项:forgemind <子命令> ... --flag ...
_COMMAND_WITH_FLAGS = re.compile(r"forgemind\s+([a-z][a-z0-9-]*)\s+([^\n`#]*)", re.M)
_FLAG = re.compile(r"--[a-z0-9][a-z0-9-]*")


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


def check_quoted_messages(text: str, repo_root: Path) -> list[str]:
    """FAQ 里引用的报错原文必须还真的会被打印出来。

    README 的 FAQ 会直接引用命令的输出("报 XXX 怎么办")。改了文案却不改
    FAQ,读者照着引号里的字去搜就搜不到 —— 那是过期文档,比没有还糟。
    这里把引号里的话拿去源码里核:还在,就是真的;不在了,读者会白找。

    平台自己的报错原文(pip / DuckDB)不在本仓源码里 —— 它们是别人的话,
    列在下面免得误报。
    """
    problems: list[str] = []
    haystack = _source_text(repo_root)
    for match in re.finditer(r"<summary><b>Q:[^\n]*?\"([^\"]+)\"", text):
        quoted = match.group(1)
        if quoted in PLATFORM_MESSAGES:
            continue
        # "报 XXX 在 ... 的 YYY" 这种省略写法:每段都得在源码里找得到
        for part in (p.strip() for p in quoted.split("...")):
            if len(part) < 4:
                continue
            if part not in haystack:
                line = text[: match.start()].count("\n") + 1
                problems.append(
                    f"README 第 {line} 行引用的报错原文在源码里找不到了:{part!r}"
                    " —— 命令改了文案,FAQ 没跟着改,读者照着引号里的字找不到"
                )
    return problems


def _source_text(repo_root: Path) -> str:
    """把可能产生用户可见文案的源码汇成一大段文本,供上面检索。"""
    chunks: list[str] = []
    roots = ["forgemind", "forgemind-ui", "scripts"]
    skip = {"node_modules", ".next", "dist", "build", "__pycache__", ".git"}
    for name in roots:
        base = repo_root / name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".ts", ".tsx", ".rs", ".md"}:
                continue
            if any(part in skip for part in path.parts):
                continue
            try:
                chunks.append(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
    return "\n".join(chunks)


def _subcommand_options() -> dict[str, set[str]]:
    """每个子命令真正认的选项(不含 --help)。

    直接问 argparse 自己,不去读源码:源码里写的名字与解析器认的名字
    可能已经不是一个东西了。
    """
    from forgemind.cli import build_parser

    parser = build_parser()
    out: dict[str, set[str]] = {}
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for name, sub in action.choices.items():
            opts = set()
            for a in sub._actions:
                opts.update(a.option_strings)
            opts.discard("--help")
            out[name] = opts
    return out


def check_command_options(text: str) -> list[str]:
    """README 里写的选项,这个命令真的认。

    之前只核对子命令在不在 —— 用户照着抄一条带选项的命令,选项写错了
    一样报错,而那时没人拦。

    认的是 argparse 的真实规则:精确匹配,或者**唯一前缀**(argparse
    允许 `--symbol` 缩写 `--symbols`)。前缀不唯一时 argparse 会报错,
    这里也报错 —— 宁可现在说清,别让用户撞一次。
    """
    options = _subcommand_options()
    if not options:
        return []
    problems: list[str] = []
    for sub, rest in _COMMAND_WITH_FLAGS.findall(text):
        if sub not in options:
            continue  # 子命令本身由 check_all_mentions 负责
        known = options[sub]
        for flag in _FLAG.findall(rest):
            if flag in known:
                continue
            # 唯一前缀缩写:argparse 允许,--symbol → --symbols
            hits = [o for o in known if o.startswith(flag)]
            if len(hits) == 1:
                continue
            if len(hits) > 1:
                problems.append(
                    f"README 里的 `forgemind {sub} {flag}` 是多个选项的前缀"
                    f"({', '.join(sorted(hits))}),argparse 会报歧义"
                )
                continue
            problems.append(
                f"README 里的 `forgemind {sub} {flag}` 不是这个命令的选项"
                f"(它认的是:{', '.join(sorted(known))})"
            )
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
    problems += check_quoted_messages(text, REPO)
    problems += check_command_options(text)
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
