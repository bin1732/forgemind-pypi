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

#: 不对外承诺的作业(附理由)。
#:
#: 发布流水线自己的步骤不算"对构件的检查" —— 它是发布本身。其余每一个
#: 作业都是真检查,README 那张表必须点名,否则读者会以为关卡比实际少。
EXEMPT_JOBS = {
    ("ship.yml", "resolve-source"): "发布流水线自己的准备步骤",
    ("ship.yml", "build-wheel"): "发布流水线自己的构建步骤",
    ("ship.yml", "build-standalone"): "发布流水线自己的构建步骤",
    ("ship.yml", "ship"): "发布动作本身,不是对构件的检查",
}


def missing_from_table(listed: set[tuple[str, str]], workflows_dir: Path) -> list[str]:
    """实际存在的作业里,哪些没在 README 的表里被点名。

    单独抽出来,好让测试用**造出来的**流水线目录双向验:规则本身要能
    验,不能靠"当前这仓碰巧合规"来证明。
    """
    problems: list[str] = []
    if not workflows_dir.is_dir():
        return problems
    for workflow_file in sorted(workflows_dir.glob("*.yml")):
        try:
            data = yaml.safe_load(workflow_file.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            continue
        for key, job in (data.get("jobs") or {}).items():
            name = str((job or {}).get("name") or key)
            if (workflow_file.name, key) in EXEMPT_JOBS:
                continue
            if (workflow_file.name, name) in listed or (workflow_file.name, key) in listed:
                continue
            problems.append(
                f"流水线里有作业没在 README 的表里点名: {workflow_file.name} / {name}"
                f" —— 读者会以为关卡比实际少"
            )
    return problems


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

    # 反向:实际存在的每一个作业都要在那张表里被点名,除非有豁免。
    # 只做正向的话,表漏掉的作业没人发现 —— 而"少说"在承诺型文档里
    # 同样是误导:读者会以为那就是全部。
    listed_names = {(w, j.strip()) for w, j in rows}
    problems.extend(missing_from_table(listed_names, repo / ".github" / "workflows"))

    if problems:
        print(f"{readme.name} 承诺的关卡与实际流水线对不上:")
        for item in problems:
            print(" -", item)
        return 1

    print(
        f"{readme.name} 承诺的 {len(rows)} 道关卡都有对应的流水线作业,"
        f"而流水线里的每个作业都在表里被点名"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
