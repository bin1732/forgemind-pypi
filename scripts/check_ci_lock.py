# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""确认流水线装的依赖集合与项目声明的一致。

流水线用 `--no-deps -e .` 安装本项目,等于只装 requirements-ci.txt 里
的包。若锁定文件缺了某个声明过的依赖,对应的代码路径在流水线里根本
不会被执行 —— 用例以"依赖缺失"为由跳过,流水线却显示为绿。

这里核对:项目声明的每个运行时依赖,锁定文件里都要有满足其版本区间的
条目。

只看这一条,是有意的:锁定文件里可以有项目没有直接声明的包 —— 那些是
传递依赖,判断某个包是不是传递依赖需要已解析的依赖环境,而检查脚本会
在没装依赖的作业里跑,那样判出来的结果会随环境变化。判定规则随环境
变化的检查等于没有检查。
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

REPO = Path(__file__).resolve().parent.parent
LOCK = REPO / "requirements-ci.txt"


def load_declared() -> dict[str, Requirement]:
    """项目声明的运行时依赖。"""
    with (REPO / "pyproject.toml").open("rb") as fh:
        project = tomllib.load(fh)["project"]
    declared: dict[str, Requirement] = {}
    for spec in project.get("dependencies", []):
        req = Requirement(spec)
        declared[req.name.lower().replace("_", "-")] = req
    return declared


def load_lock() -> dict[str, str]:
    locked: dict[str, str] = {}
    for line in LOCK.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, version = line.partition("==")
        key = name.strip().lower().replace("_", "-")
        if key in locked:
            raise SystemExit(f"锁定文件里 {key} 出现了两次")
        locked[key] = version.strip()
    return locked


def main() -> int:
    declared = load_declared()
    locked = load_lock()

    problems: list[str] = []

    for name, req in sorted(declared.items()):
        if name not in locked:
            problems.append(
                f"项目声明了 {name}{req.specifier},锁定文件里没有它 —— 流水线里这条依赖不会被安装"
            )
            continue
        version = Version(locked[name])
        if not req.specifier.contains(version, prereleases=True):
            problems.append(f"{name} 锁定 {locked[name]},不满足声明的区间 {req.specifier}")

    if problems:
        print("锁定文件与项目声明不一致:", file=sys.stderr)
        for item in problems:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(f"锁定文件与项目声明一致:声明 {len(declared)} 个运行时依赖,锁定 {len(locked)} 个包")
    return 0


if __name__ == "__main__":
    sys.exit(main())
