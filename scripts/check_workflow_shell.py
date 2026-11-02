#!/usr/bin/env python3
# Copyright (c) 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""检查 workflow:凡是用到 bash 专有语法的 step,必须声明 shell: bash

Windows runner 默认是 PowerShell,不认 set -euo pipefail / [[ ]] / PIPESTATUS
这类语法。显式声明 shell 让同一份脚本在各类 runner 上行为一致。

    python scripts/check_workflow_shell.py
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def check_workflow_shell(repo_root: pathlib.Path) -> list[str]:
    """找出用了 bash 语法却没声明 shell 的 step。"""
    bad: list[str] = []
    workflows = sorted((repo_root / ".github/workflows").glob("*.yml"))
    for wf in workflows:
        text = wf.read_text(encoding="utf-8")
        # 按 step 切块
        for m in re.finditer(
            r"^      - (name|uses):.*?(?=^      - (?:name|uses):|\Z)", text, re.S | re.M
        ):
            blk = m.group(0)
            if "run: |" not in blk:
                continue
            # bash 专有语法
            uses_bash = bool(
                re.search(
                    r"set -euo pipefail|\[\[|PIPESTATUS|shopt -s|\$\(\(|&>/dev/null|timeout \d+ ",
                    blk,
                )
            )
            has_shell = "shell: bash" in blk
            if uses_bash and not has_shell:
                name = re.search(r"name: (.+)", blk)
                bad.append(f"{wf.name} / {name.group(1) if name else '?'}")
    return bad


def main(repo_root: pathlib.Path | None = None) -> int:
    root = (repo_root or REPO_ROOT).resolve()
    workflows = sorted((root / ".github/workflows").glob("*.yml"))
    # 一个 workflow 都没找到就报通过,是假绿 —— 那说明路径不对,不是没问题。
    if not workflows:
        print(f"没找到任何 workflow(找的是 {root / '.github/workflows'})", file=sys.stderr)
        return 1
    bad = check_workflow_shell(root)
    print(f"检查 {len(workflows)} 个 workflow")
    if bad:
        print("以下 step 用了 bash 语法但没声明 shell: bash:")
        for b in bad:
            print("  ✗", b)
        return 1
    print("✓ 全部 bash 步骤都已声明 shell: bash")
    return 0


if __name__ == "__main__":
    sys.exit(main())
