#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""每个检查器都要真的被流水线调用,否则它只是一段没人跑的代码。

检查脚本写成、放着、没人调用 —— 看起来门禁齐了,实际上一道都没生效。
这个脚本把两仓的检查器与工作流对照一遍,列出没人调用的那些。

跨仓引用要算进来:私人仓的检查器由公开仓的镜像工作流调用,路径写成
src/scripts/xxx.py。
"""

import argparse
import pathlib
import re
import sys

# 不需要进流水线的脚本,以及理由。这些是一次性工具或本地用的,
# 它们不是门禁,接进流水线反而是噪声。
NOT_A_GATE = {
    "clean_wording.py": "一次性清措辞的工具,用完即弃",
    "feature_inventory.py": "本地盘点用的工具,不是门禁",
    "list_coverage_files.py": "本地查覆盖率文件用的工具,不是门禁",
    "dispatch.py": "手动触发流水线的工具,不是门禁",
    "research_demo.py": "给使用者跑的研究示例,不是门禁",
    "audit_release.py": "本地汇总自检;各项检查在流水线里各自跑",
    "verify3.py": "三视角验证的本地入口,流水线里由 verify.yml 覆盖",
    "verify_three_angles.py": "同上",
}

# 脚本名出现在工作流里就算被调用
CALL_PATTERNS = (
    r"scripts/{name}",
    r"\b{name}\b",
)


def _called(scripts: list[pathlib.Path], workflows_text: str) -> set[str]:
    """返回被流水线调用到的脚本名。"""
    called: set[str] = set()
    for script in scripts:
        name = script.name
        for pattern in CALL_PATTERNS:
            if re.search(pattern.format(name=re.escape(name)), workflows_text):
                called.add(name)
                break
    return called


def main() -> int:
    parser = argparse.ArgumentParser(description="核对检查器都接进了流水线")
    parser.add_argument(
        "--public", type=pathlib.Path, default=pathlib.Path("."), help="公开仓根目录"
    )
    parser.add_argument(
        "--private", type=pathlib.Path, default=None, help="私人仓源码目录(镜像里的 src/)"
    )
    args = parser.parse_args()

    public = args.public.resolve()
    private = args.private.resolve() if args.private else None

    workflow_texts = []
    for workflow in sorted((public / ".github/workflows").glob("*.yml")):
        workflow_texts.append(workflow.read_text(encoding="utf-8"))
    if private and (private / ".github/workflows").is_dir():
        for workflow in sorted((private / ".github/workflows").glob("*.yml")):
            workflow_texts.append(workflow.read_text(encoding="utf-8"))
    workflows_text = "\n".join(workflow_texts)

    problems: list[str] = []
    for root, label in ((public, "公开仓"), (private, "私人仓")):
        if root is None or not (root / "scripts").is_dir():
            continue
        scripts = sorted((root / "scripts").glob("*.py"))
        called = _called(scripts, workflows_text)
        for script in scripts:
            name = script.name
            if name.startswith("_"):
                continue
            if name in called:
                continue
            if name in NOT_A_GATE:
                continue
            problems.append(f"{label} 的 {name} 没有被任何流水线调用")

    if problems:
        print("有检查器没接进流水线:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("每个检查器都被流水线调用了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
