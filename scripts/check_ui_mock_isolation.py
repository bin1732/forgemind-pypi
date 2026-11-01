# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对界面里的 mock 只活在测试里,不会混进真实界面。

界面目录里放着 __mocks__ 时,最容易出的岔子是:某天有人图省事,在
next.config.js 里加了别名,或者某个组件直接 import 了 mock —— 于是真机
界面上出现的是编造的数据,而测试全绿,看不出来。

这个检查只认一条规矩:__mocks__ 只能出现在测试配置和测试文件里。
构建配置或业务源码提到它,都算违规。

判定不靠文件名猜测,而是看有没有人提到 __mocks__ 这个目录本身 ——
jest 配置里的引用一定带着这个路径,绕不开。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SOURCE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
SKIP_DIRS = {"node_modules", ".next", "out", "dist", "build", ".git"}
# 只有这些文件可以提到 __mocks__
TEST_CONFIG_PREFIXES = ("jest.config", "jest.setup")


def _allowed(path: Path) -> bool:
    """测试配置与测试文件可以引用 mock。"""
    if any(path.name.startswith(prefix) for prefix in TEST_CONFIG_PREFIXES):
        return True
    if "__tests__" in path.parts:
        return True
    return ".test." in path.name or ".spec." in path.name


def _source_files(ui_root: Path) -> list[Path]:
    files = []
    for path in sorted(ui_root.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_EXT:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if "__mocks__" in path.parts:
            continue
        files.append(path)
    return files


def check(ui_root: Path) -> list[str]:
    """返回违规描述列表,空列表表示没问题。"""
    problems: list[str] = []
    mock_dirs = [
        p
        for p in ui_root.rglob("__mocks__")
        if p.is_dir() and not any(s in SKIP_DIRS for s in p.parts)
    ]
    if not mock_dirs:
        return problems

    for src in _source_files(ui_root):
        if _allowed(src):
            continue
        try:
            text = src.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "__mocks__" not in text:
            continue
        rel = src.relative_to(ui_root)
        problems.append(f"{rel} 引用了 __mocks__ —— mock 只应出现在测试里")
    return problems


def count_mock_files(ui_root: Path) -> int:
    total = 0
    for d in ui_root.rglob("__mocks__"):
        if not d.is_dir() or any(s in SKIP_DIRS for s in d.parts):
            continue
        total += sum(1 for f in d.iterdir() if f.is_file())
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="核对界面 mock 只用于测试")
    parser.add_argument("ui", type=Path, help="界面源码目录")
    args = parser.parse_args()

    root = args.ui.resolve()
    if not root.is_dir():
        print(f"找不到目录: {root}", file=sys.stderr)
        return 2

    problems = check(root)
    if problems:
        print(f"界面 mock 越界了,共 {len(problems)} 处:")
        for item in problems:
            print(" -", item)
        return 1

    print(f"界面 mock 只在测试里生效,没有混进真实构建({count_mock_files(root)} 个 mock 文件)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
