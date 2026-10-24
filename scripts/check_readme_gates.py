# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对 README 承诺的每一道关卡,真有一条作业在跑。

README 的验证表是一份**承诺**:发布出去的构件经过了什么。这里逐条核对
表格里点名的流水线与作业是不是真的还在。

不核的后果很具体:有一条作业被删掉时,表里的承诺还在,读者会以为
那道关卡仍然在跑 —— 而它已经不在了。

用法:
    python scripts/check_readme_gates.py README.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

# 表格行: | 检查 | 内容 | `workflow.yml` / 作业名 |
GATE_ROW = re.compile(
    r"^\|\s*[^|]+?\s*\|\s*[^|]+?\s*\|\s*`([^`]+\.yml)`\s*/\s*([^|`]+?)\s*\|\s*$", re.M
)


def main() -> int:
    parser = argparse.ArgumentParser(description="核对 README 承诺的关卡")
    parser.add_argument("readme", type=Path, help="README 路径")
    args = parser.parse_args()

    readme = args.readme.resolve()
    repo = readme.parent
    text = readme.read_text(encoding="utf-8")
    rows = GATE_ROW.findall(text)
    if not rows:
        print(f"{readme.name} 里没有找到点名流水线与作业的验证表行")
        return 1

    problems: list[str] = []
    for workflow_name, job_name in rows:
        path = repo / ".github" / "workflows" / workflow_name
        if not path.is_file():
            problems.append(f"承诺的流水线不存在: {workflow_name}")
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        names = [
            str((job or {}).get("name") or key) for key, job in (data.get("jobs") or {}).items()
        ]
        if job_name not in names:
            problems.append(
                f"承诺的作业不存在: {workflow_name} / {job_name}(该流水线现有作业: {names})"
            )

    if problems:
        print(f"{readme.name} 承诺的关卡与实际流水线对不上:")
        for item in problems:
            print(" -", item)
        return 1

    print(f"{readme.name} 承诺的 {len(rows)} 道关卡都有对应的流水线作业")
    return 0


if __name__ == "__main__":
    sys.exit(main())
