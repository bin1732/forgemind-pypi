#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对流水线用的 runner 镜像标签有没有被平台移除或即将移除。

GitHub 托管的 runner 镜像是有寿命的。标签一旦被移除,写着用它的作业
不会"跑失败"—— 它永远排不上 runner,流水线就停在那里,而失败信息里
看不出是标签的问题。macOS 14 家族就是这么从 2026-11-02 起消失的。

这个检查把两仓所有工作流里的 runner 标签过一遍:

  * 已经移除的标签 → 直接失败。用了它,那条作业永远排不上 runner。
  * 已进入退役流程(brownout 窗口开始)的标签 → 直接失败。此时平台会
    故意让用它的作业间歇性失败,验证信号已经被污染了。
  * 有退役日期但还没到的标签 → 只提示,不拦人。留出迁移窗口。

判据表写在下面,每条都带出处与核对日期。平台改期时这张表会过期,
所以表里记着"核对于"—— 过期超过一年就提醒复核,而不是让人以为
它永远正确。

出处:
  * macOS 14 家族(2026-11-02 移除、10 月的 brownout 窗口):
    https://github.blog/changelog/2026-10-01-github-actions-macos-14-runner-image-retirement
    https://github.com/actions/runner-images/issues/13518
  * macOS 13(2025-12-04 移除):
    https://github.blog/changelog/2025-09-19-github-actions-macos-13-runner-image-is-closing-down
  * macos-15-intel(可用到 2027 年 8 月,之后 x86_64 不再支持):
    https://github.com/actions/runner-images/issues/13045
  * macOS 12 与更早的镜像、Ubuntu 18.04/20.04、Windows Server 2019:
    均为对应镜像的退役公告,见各项说明。
  * Ubuntu 22.04(2027-03-23 起 brownout,2027-04-17 移除):
    https://github.com/actions/runner-images/issues/14254

用法:
    python scripts/check_runner_labels.py [仓库根目录] [--as-of YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

import yaml

# `runs-on: ${{ matrix.xxx }}` 里取矩阵键名
_MATRIX_REF = re.compile(r"matrix\.([A-Za-z_][A-Za-z0-9_-]*)")

# 平台已经移除的标签。还在用,作业就永远排不上 runner。
GONE: dict[str, str] = {
    "macos-12": "macOS 12 镜像已移除(2024-12)",
    "macos-13": "macOS 13 镜像已移除(2025-12-04)",
    "ubuntu-18.04": "Ubuntu 18.04 镜像已移除(2022-12)",
    "ubuntu-20.04": "Ubuntu 20.04 镜像已移除(2025-04)",
    "windows-2019": "Windows Server 2019 镜像已移除(2025-06)",
}

# 仍在提供、但已进入退役流程的标签。
# 每项是 (开始拦截的日期, 移除日期, 说明)。
#   开始拦截的日期取官方公告里的第一个 brownout 窗口 —— 从那天起,
#   平台会故意让用这个标签的作业间歇性失败,验证信号已经被污染了,
#   不能等到移除那天才当成问题。
#   移除日期到期后,标签彻底消失,作业永远排不上 runner。
# macos-15-intel 官方只说了"可用到 2027 年 8 月",没公布 brownout
# 日程,所以它的开始拦截日期留空 —— 有新公告时再补。
RETIRING: dict[str, tuple[str | None, str, str]] = {
    "macos-14": (
        "2026-10-05",
        "2026-11-02",
        "官方公告:2026-10-05 起进入 brownout 窗口,2026-11-02 移除",
    ),
    "macos-14-large": (
        "2026-10-05",
        "2026-11-02",
        "官方公告:2026-10-05 起进入 brownout 窗口,2026-11-02 移除",
    ),
    "macos-14-xlarge": (
        "2026-10-05",
        "2026-11-02",
        "官方公告:2026-10-05 起进入 brownout 窗口,2026-11-02 移除",
    ),
    "macos-15-intel": (
        None,
        "2027-08-01",
        "官方说法:可用到 2027 年 8 月,之后 x86_64 不再支持",
    ),
    "ubuntu-22.04": (
        "2027-03-23",
        "2027-04-17",
        "官方公告:2027-03-23 起进入 brownout,2027-04-17 移除",
    ),
    "ubuntu-22.04-arm": (
        "2027-03-23",
        "2027-04-17",
        "官方公告:2027-03-23 起进入 brownout,2027-04-17 移除",
    ),
}

# 判据表最后一次对着平台公告核对的日期。平台改期时它会过期。
LAST_VERIFIED = dt.date(2026, 10, 30)

# 浮动标签:平台决定它指向哪个镜像,自己会随平台的迁移日程变动。
# 不拦人(用 -latest 有时就是想要"当前默认"),但要提示 —— 环境在没人
# 通知的情况下换掉,流水线的结果会前后不一致,是最难查的那种故障。
FLOATING_HINT = (
    "这个标签指向哪个镜像由平台决定,会随平台公布的迁移日程变动。"
    "想要确定的环境,就把标签钉到具体版本(ubuntu-26.04 / macos-26 / windows-2025)"
)

# 退役日期临近多少天开始提示(只提示,不拦人)。
WARN_DAYS = 60

# 判据表多久没复核就提醒一次(只提示,不拦人)。
REVERIFY_AFTER_DAYS = 365

# 矩阵里可能承载 runner 标签的键名。
MATRIX_KEYS = ("os", "runs-on", "runner", "label", "image", "runner-label")


def _include_labels(matrix: dict, keys: set[str]) -> list[str]:
    """矩阵 include 条目里的标签。

    include 的每一项常常就是一组 (os, name) —— 同一个键既可能写在
    matrix 的顶层,也可能只写在 include 里,两处都要看。
    """
    found: list[str] = []
    for entry in matrix.get("include") or []:
        if not isinstance(entry, dict):
            continue
        for name, value in entry.items():
            if str(name).lower() in keys and _is_label(value):
                found.append(value)
    return found


def _matrix_labels(job: dict, keys: set[str]) -> list[str]:
    """取出矩阵里可能承载 runner 标签的字符串。"""
    matrix = (job.get("strategy") or {}).get("matrix") or {}
    found: list[str] = []
    for key in keys:
        value = matrix.get(key)
        if _is_label(value):
            found.append(value)
        elif isinstance(value, list):
            found.extend(item for item in value if _is_label(item))
    found.extend(_include_labels(matrix, keys))
    return found


def _is_label(value: object) -> bool:
    """是不是一个具体的标签(排除表达式与容器)。"""
    return isinstance(value, str) and value.strip() != "" and "${{" not in value


def _job_labels(job: dict) -> list[str]:
    """一个作业里用到的所有 runner 标签。"""
    runs_on = job.get("runs-on")
    if isinstance(runs_on, str):
        if "${{" not in runs_on:
            return [runs_on]
        # 键名从表达式里取,而不是猜:`runs-on: ${{ matrix.platform }}`
        # 里的键就叫 platform,只认 os/runner 那几个固定名字会漏掉它。
        # 固定的几个名字也一并留着 —— include 条目里的键名未必与表达式
        # 里那个一致。
        keys = {key.lower() for key in _MATRIX_REF.findall(runs_on)} | set(MATRIX_KEYS)
        if not keys:
            return []
        return _matrix_labels(job, keys)
    if isinstance(runs_on, list):
        return [item for item in runs_on if _is_label(item)]
    return []


def collect(repo: Path) -> list[tuple[str, str]]:
    """返回 (标签, 出处) 列表。出处是 "<工作流>:<作业>"。"""
    workflows = repo / ".github/workflows"
    if not workflows.is_dir():
        return []
    hits: list[tuple[str, str]] = []
    for path in sorted(workflows.glob("*.y*ml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        jobs = data.get("jobs") or {}
        if not isinstance(jobs, dict):
            continue
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            for label in _job_labels(job):
                hits.append((label, f"{path.name}:{job_name}"))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="核对流水线用的 runner 镜像标签")
    parser.add_argument("repo", nargs="?", type=Path, default=Path("."), help="仓库根目录")
    parser.add_argument(
        "--as-of",
        default=None,
        help="按哪一天判定(YYYY-MM-DD),默认今天。用于复现历史判定。",
    )
    args = parser.parse_args()

    repo = args.repo.resolve()
    if args.as_of:
        as_of = dt.date.fromisoformat(args.as_of)
    else:
        as_of = dt.date.today()

    hits = collect(repo)
    problems: list[str] = []
    warnings: list[str] = []

    for label, where in hits:
        if label in GONE:
            problems.append(f"{where}: runner 标签 {label} 已被平台移除 —— {GONE[label]}")
            continue
        entry = RETIRING.get(label)
        if entry is None:
            if "-latest" in label:
                warnings.append(f"{where}: runner 标签 {label} 是浮动标签 —— {FLOATING_HINT}")
            continue
        migrate_by, retire_on, note = entry
        retire_date = dt.date.fromisoformat(retire_on)
        if as_of >= retire_date:
            problems.append(f"{where}: runner 标签 {label} 已于 {retire_on} 退役 —— {note}")
            continue
        if migrate_by and as_of >= dt.date.fromisoformat(migrate_by):
            problems.append(
                f"{where}: runner 标签 {label} 已进入退役流程({migrate_by} 起)—— {note}"
            )
            continue
        days = (retire_date - as_of).days
        if days <= WARN_DAYS:
            warnings.append(
                f"{where}: runner 标签 {label} 将在 {retire_on} 退役(还剩 {days} 天)—— {note}"
            )
        elif migrate_by and (dt.date.fromisoformat(migrate_by) - as_of).days <= WARN_DAYS:
            days = (dt.date.fromisoformat(migrate_by) - as_of).days
            warnings.append(
                f"{where}: runner 标签 {label} 将在 {migrate_by} 进入退役流程"
                f"(还剩 {days} 天)—— {note}"
            )

    stale_days = (as_of - LAST_VERIFIED).days
    if stale_days > REVERIFY_AFTER_DAYS:
        warnings.append(
            f"runner 标签判据表最后一次核对于 {LAST_VERIFIED},距今 {stale_days} 天,"
            " 平台可能已改期,请对照官方公告复核"
        )

    print(f"扫描了 {repo} 的工作流,用到 {len(hits)} 处 runner 标签")
    for warning in warnings:
        print(f"  提示: {warning}", file=sys.stderr)

    if problems:
        print("有 runner 标签已被平台移除:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("没有用到已移除或已到退役日期的 runner 标签")
    return 0


if __name__ == "__main__":
    sys.exit(main())
