#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""把这次发布的版本号打到构建用的源码副本上。

源码里声明的版本(四处 ✓)保持不动 —— 那是维护者抬大版本的地方 ✓。
发布时另给一个 post 号 ✓,打在**构建用的那份副本**上 ✓:

    pyproject.toml            → 装出来的包报这个版本
    forgemind/__init__.py     → 独立二进制报这个版本
    src-tauri/Cargo.toml     → 桌面端包的版本
    package.json             → 界面包的版本

四处都要改 ✓,否则版本一致性对账会报不一致 ✓。

用法:
    python scripts/apply_publish_version.py <源码目录> <版本号>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Windows 的控制台默认编码装不下中文,print 里的中文会直接抛
# UnicodeEncodeError —— 作业在打印这一步就挂了,前面的活全白干。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# (相对路径, 替换用的正则, 说明)
TARGETS = (
    ("pyproject.toml", re.compile(r'^version = "(?P<v>[^"]+)"', re.M), "构建配置"),
    ("forgemind/__init__.py", re.compile(r'^__version__ = "(?P<v>[^"]+)"', re.M), "Python 包"),
    ("forgemind-ui/src-tauri/Cargo.toml", re.compile(r'^version = "(?P<v>[^"]+)"', re.M), "桌面端"),
    ("forgemind-ui/package.json", re.compile(r'"version": "(?P<v>[^"]+)"', re.M), "界面"),
)


def apply_version(root: Path, version: str) -> list[str]:
    """把版本号打进源码副本。返回改了哪些文件。"""
    changed: list[str] = []
    for rel, pattern, label in TARGETS:
        path = root / rel
        if not path.is_file():
            raise SystemExit(f"找不到 {label} 的版本声明: {path}")
        text = path.read_text(encoding="utf-8")
        if not pattern.search(text):
            raise SystemExit(f"{rel} 里没找到版本号声明(格式变了?)")
        new_text, count = pattern.subn(
            lambda m: m.group(0).replace(f'"{m.group("v")}"', f'"{version}"'), text, count=1
        )
        if count != 1:
            raise SystemExit(f"{rel} 的版本号替换了 {count} 处,应当只改一处")
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed.append(rel)
    return changed


def main() -> int:
    if len(sys.argv) != 3:
        print("用法: apply_publish_version.py <源码目录> <版本号>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    version = sys.argv[2].strip()
    if not version:
        print("版本号不能为空", file=sys.stderr)
        return 2
    changed = apply_version(root, version)
    print(f"版本号已打成 {version}: {', '.join(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
