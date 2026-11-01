#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""算这次发布要用的版本号。

同一个版本号、内容却变了,pip 是不会升级的:已装过的机器再执行同一条
安装命令,pip 看到"这个版本已经满足"就不重新下载 —— 用户永远拿不到后来
发布的构建。实测过。

所以每次发布给一个新的 post 号:

    2026.9.3 → 2026.9.3.post1 → 2026.9.3.post2 → ...

PEP 440 的 post 发布不是预发布(pip 默认就装 ✓),且严格大于同名的基础
版本 ✓ —— 于是 pip 认得出"这是更新的" ✓。`.devN` 不行:那是预发布,pip
默认不装 ✗。

基础版本来自源码声明(维护者决定什么时候抬大版本 ✓);post 序号从上一次
发布的版本号接续 ✓ —— 基础版本一旦变了,序号重新从 1 开始 ✓。

用法:
    python scripts/publish_version.py --base 2026.9.3 --previous 2026.9.3.post1
"""

from __future__ import annotations

import argparse
import re
import sys

# Windows 的控制台默认编码装不下中文,print 里的中文会直接抛
# UnicodeEncodeError —— 作业在打印这一步就挂了,前面的活全白干。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# PEP 440 的 post 号:基础版本 + .post + 数字
_POST = re.compile(r"^(?P<base>.+)\.post(?P<n>\d+)$")


def split_post(version: str) -> tuple[str, int]:
    """把 "2026.9.3.post2" 拆成 ("2026.9.3", 2)。不是 post 版就返回 (版本, 0)。"""
    match = _POST.match((version or "").strip())
    if not match:
        return (version or "").strip(), 0
    return match.group("base"), int(match.group("n"))


def next_version(base: str, previous: str | None) -> str:
    """下一次发布要用的版本号。

    base 是源码声明的版本(维护者抬大版本时变 ✓);previous 是上一次发布
    用过的版本号(第一次发布时为空 ✓)。
    """
    base = (base or "").strip()
    if not base:
        raise ValueError("基础版本不能为空")
    prev_base, prev_n = split_post(previous or "")
    if prev_base == base:
        n = prev_n + 1
    else:
        # 基础版本变了(维护者抬了大版本),序号从头开始
        n = 1
    return f"{base}.post{n}"


def main() -> int:
    parser = argparse.ArgumentParser(description="算这次发布要用的版本号")
    parser.add_argument("--base", required=True, help="源码声明的版本")
    parser.add_argument("--previous", default="", help="上一次发布用过的版本号")
    args = parser.parse_args()
    try:
        version = next_version(args.base, args.previous)
    except ValueError as exc:
        print(f"算不出版本号: {exc}", file=sys.stderr)
        return 2
    print(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
