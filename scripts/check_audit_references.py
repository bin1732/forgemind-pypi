# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对自检文档点名的回归测试都还在。

自检文档里每条结论都点名了对应的回归测试。文档本身不该成为一句
无人核对的声明:测试被删掉或失效,结论就成了过期说法。这个脚本把
文档与测试对上,让"结论仍成立"可以被机器验证。

文档里声明的**数字**(用例数、MCP 能力数量)由
`scripts/check_audit_claims.py` 核对 —— 那要真跑 pytest 采集,必须放在
依赖齐全的作业里。这个脚本不依赖任何第三方包,放在只装了静态检查工具
的作业里也能跑。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 文档里以文件形式点名的测试模块
MODULE_PATTERN = re.compile(r"\btest_[A-Za-z0-9_]{4,}\.py\b")
# 文档里以函数形式点名的测试
FUNCTION_PATTERN = re.compile(r"(?<![.\w])test_[A-Za-z0-9_]{4,}\b")


def collect_referenced(doc: Path) -> tuple[set[str], set[str]]:
    """从文档里取出点名的测试模块与测试函数。"""
    text = doc.read_text(encoding="utf-8")
    modules = {m[:-3] for m in MODULE_PATTERN.findall(text)}
    functions = set(FUNCTION_PATTERN.findall(text))
    functions -= modules
    # 去掉明显的占位或前缀片段
    functions = {f for f in functions if not f.endswith("_")}
    # 文档里可能提到以点开头的文件名或配置项,不是测试函数
    functions = {f for f in functions if not f.startswith(".")}
    return modules, functions


def main() -> int:
    """核对文档点名的测试,返回进程退出码。"""
    parser = argparse.ArgumentParser(description="核对自检文档点名的回归测试")
    parser.add_argument("doc", type=Path, help="自检文档路径")
    parser.add_argument("--tests", default="tests", help="测试目录")
    args = parser.parse_args()

    repo = args.doc.resolve().parent.parent
    tests_dir = repo / args.tests
    if not tests_dir.is_dir():
        print(f"找不到测试目录: {tests_dir}", file=sys.stderr)
        return 2

    modules, functions = collect_referenced(args.doc)
    source = {p.name: p.read_text(encoding="utf-8") for p in tests_dir.glob("*.py")}

    problems = []
    for name in sorted(m for m in modules if not any(m in n for n in source)):
        problems.append(f"文档点名的测试模块不存在: {name}")
    for name in sorted(
        f for f in functions if not any(f"def {f}(" in text for text in source.values())
    ):
        problems.append(f"文档点名的测试函数不存在: {name}")

    if problems:
        print(f"{args.doc.name} 与测试对不上:")
        for item in problems:
            print(" -", item)
        return 1

    print(f"{args.doc.name} 点名的 {len(modules)} 个测试模块与 {len(functions)} 个测试函数全部存在")
    return 0


if __name__ == "__main__":
    sys.exit(main())
