#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""发布物在哪个平台上构建,就要在哪个平台上验证。

用户下载到的 macOS 二进制是在 ship.yml 的 macos-latest 上构建的,
verify-desktop.yml 却拿 macos-14 当发布构建环境 —— 验证用的环境和
发布用的环境不是同一套,于是"验过的"和"用户拿到的"可能不是一回事。

这个检查把仓库里所有带 name/os 矩阵的工作流放在一起比对:同一个平台
名(linux / macos / windows)在各处必须用同一个 runner 标签。平台标签
还会被平台自己退役(见 check_runner_labels.py),两边的标签一旦分叉,
其中一边就会在某天突然不再可用。

用法:
    python scripts/check_release_platform_parity.py [仓库根目录]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def collect(repo: Path) -> list[tuple[str, str, dict[str, str]]]:
    """返回 (工作流, 作业, {平台名: runner 标签}) 列表。"""
    workflows = repo / ".github/workflows"
    if not workflows.is_dir():
        return []
    found: list[tuple[str, str, dict[str, str]]] = []
    for path in sorted(workflows.glob("*.y*ml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        jobs = data.get("jobs") or {}
        if not isinstance(jobs, dict):
            continue
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            matrix = (job.get("strategy") or {}).get("matrix") or {}
            mapping: dict[str, str] = {}
            for entry in matrix.get("include") or []:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                os_label = entry.get("os")
                if not isinstance(name, str) or not isinstance(os_label, str):
                    continue
                if "${{" in os_label:
                    continue
                mapping[name] = os_label
            if mapping:
                found.append((path.name, job_name, mapping))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="核对发布与验证用的平台标签一致")
    parser.add_argument("repo", nargs="?", type=Path, default=Path("."), help="仓库根目录")
    args = parser.parse_args()

    repo = args.repo.resolve()
    matrices = collect(repo)
    if not matrices:
        # 一个都找不到,多半是工作流改了写法、判据已经失效 ——
        # 这种"检查器自己不再检查任何东西"的假绿比没有检查更糟。
        print("没有找到带 name/os 的矩阵,平台一致性判据已失效", file=sys.stderr)
        return 1

    problems: list[str] = []
    labels_by_platform: dict[str, dict[str, str]] = {}
    for workflow, job, mapping in matrices:
        print(f"  {workflow}:{job} -> {mapping}")
        for platform, label in mapping.items():
            labels_by_platform.setdefault(platform, {})[f"{workflow}:{job}"] = label

    for platform, seen in sorted(labels_by_platform.items()):
        distinct = sorted(set(seen.values()))
        if len(distinct) > 1:
            detail = ", ".join(f"{where}={label}" for where, label in sorted(seen.items()))
            problems.append(f"平台 {platform} 在不同工作流里用了不同的 runner 标签: {detail}")

    if problems:
        print("发布与验证用的平台标签不一致:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"共比对 {len(matrices)} 处矩阵,平台标签一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
