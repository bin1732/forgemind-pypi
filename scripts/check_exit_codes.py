#!/usr/bin/env python3
# Copyright (c) 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对 README 里的退出码表与命令的真实退出码一致。

表是对用户的承诺:看到某个退出码,就知道发生了什么、该做什么。表与实际
行为分家,这张表就只剩误导作用。

真出现过:表里写着"用户中断 = 1",实测是 130;写着"agent 审批拒绝 = 5+",
实测是 2 —— 而 2 那一行写的是"资源类",两个场景挤在同一个码上,读的人
无从判断该做什么。

所以这张表由机器守着:命令真跑一遍,退出码与表对不上就报错。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (说明, 命令, 期望退出码)。期望的码必须出现在 README 的表里。
PROBES: tuple[tuple[str, tuple[str, ...], int], ...] = (
    ("正常完成", ("info",), 0),
    ("正常完成", ("signal",), 0),
    ("argparse 用法错误", ("backtest", "--bogus-flag"), 2),
    ("策略名不存在", ("backtest", "--strategy", "NoSuchStrategyAnywhere"), 2),
    ("这个命令喂不了该策略", ("backtest", "--strategy", "MaxSharpe"), 2),
    (
        "非交互模式未审批",
        (
            "agent",
            "--symbol",
            "600519.SH",
            "--cash",
            "100000",
            "--position-qty",
            "5",
            "--position-price",
            "1600",
        ),
        2,
    ),
)

# 表里该有哪些退出码。
#
# 码集合放在这里,措辞放在 README 里 —— 各管一处,不用把两边的散文抄成
# 两份。130(用户中断)在这里但不在探针里:它是 Python 对未捕获
# KeyboardInterrupt 的标准退出码,不是某个命令自己定的。
EXPECTED_CODES = (0, 1, 2, 3, 4, 130)

_TABLE_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|", re.M)


def documented_codes(readme: Path) -> dict[int, str]:
    """读出 README 表里记的退出码与类别。"""
    text = readme.read_text(encoding="utf-8")
    start = text.find("## 🛑 错误码速查表")
    if start < 0:
        raise SystemExit("README 里找不到错误码速查表")
    end = text.find("\n##", start + 10)
    section = text[start : end if end > 0 else len(text)]
    out: dict[int, str] = {}
    for code, category in _TABLE_ROW.findall(section):
        out[int(code)] = category
    return out


def looks_like_missing_dependency(output: str) -> bool:
    """这段输出是不是"命令没跑起来,环境里缺东西"。

    命令压根没跑起来,与"退出码不对"是两回事:前者是环境的毛病,后者才
    是行为与表分家。混在一起报,会把环境的毛病说成行为不符。
    """
    return "ModuleNotFoundError" in output or "No module named" in output


def run_probe(argv: tuple[str, ...], db_path: Path) -> tuple[int, str]:
    """跑一个命令,返回 (退出码, 失败时的输出)。"""
    env = dict(os.environ)
    env["FORGEMIND_DUCKDB_PATH"] = str(db_path)
    env["FORGEMIND_LOG_LEVEL"] = "ERROR"
    env["FORGEMIND_NONINTERACTIVE"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "forgemind.cli", *argv],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    return result.returncode, (result.stdout + result.stderr)[-400:]


def main() -> int:
    parser = argparse.ArgumentParser(description="核对 README 的退出码表")
    parser.add_argument(
        "readme",
        nargs="?",
        type=Path,
        default=REPO_ROOT / "README.md",
        help="README 路径",
    )
    args = parser.parse_args()

    table = documented_codes(args.readme)
    if not table:
        print("README 的错误码表是空的", file=sys.stderr)
        return 1

    problems: list[str] = []

    # 表里的码集合要与该有的码一致:多一行少一行都不行。
    missing = [c for c in EXPECTED_CODES if c not in table]
    extra = [c for c in table if c not in EXPECTED_CODES]
    for code in missing:
        problems.append(f"表里缺退出码 {code}")
    for code in extra:
        problems.append(f"表里多了退出码 {code}(该有的码是 {list(EXPECTED_CODES)})")

    with tempfile.TemporaryDirectory(prefix="forgemind-exit-codes-") as tmp:
        db = Path(tmp) / "exit_codes.db"
        for label, argv, expected in PROBES:
            actual, output = run_probe(argv, db)
            # 命令压根没跑起来,与"退出码不对"是两回事:前者是环境缺东西,
            # 混在一起报,会把环境的毛病说成行为不符。
            if looks_like_missing_dependency(output):
                problems.append(
                    f"{label}({argv[0]}): 命令没跑起来,环境里缺依赖 —— {output.strip()[-200:]}"
                )
                continue
            if actual != expected:
                problems.append(f"{label}({argv[0]}): 实际退出码 {actual},表里写的是 {expected}")
                continue
            if expected not in table:
                problems.append(f"退出码 {expected}({label})没有出现在 README 的表里")
                continue
            print(f"  ✓ {label}: 退出码 {actual} —— {table.get(expected, '')}")

    if problems:
        print("退出码与 README 的表对不上:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"退出码与 README 的表一致({len(PROBES)} 条)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
