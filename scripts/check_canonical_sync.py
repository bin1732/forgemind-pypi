# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对公开仓里与私人仓真源同名的脚本,内容必须逐字相同。

公开仓有一部分检查器是从私人仓同步过去的 —— 两边各存一份。改了一边
忘了另一边,两个仓就会给出不同结论,而且没人会发现:本地跑公开仓那份是
通的,流水线跑私人仓那份也是通的,可它们根本不是同一份东西。

真源在私人仓。公开仓这边没有私人源码时(本地没有 src/),无从核对 ——
这时只记"没查",不报"缺失"。把"查不到"当成"没有",会让检查在本地恒红,
而红的原因与工作流本身无关,反倒把真问题淹了。

只比两仓都有的文件。公开仓独有的脚本(发布、对账、用户旅程那些)不在
这个范围内 —— 它们本来就只属于公开仓。
"""

from __future__ import annotations

import sys
from pathlib import Path


def compare(public: Path, canonical: Path) -> tuple[list[str], int]:
    """返回 (不一致的文件, 无从核对的文件数)。"""
    problems: list[str] = []
    unverifiable = 0
    for path in sorted(public.glob("*.py")):
        other = canonical / path.name
        if not other.is_file():
            # 公开仓独有的脚本不在比对范围内
            continue
        if path.read_bytes() == other.read_bytes():
            continue
        problems.append(f"{path.name}: 与私人仓真源不一致")
    if not canonical.is_dir():
        unverifiable = len(list(public.glob("*.py")))
    return problems, unverifiable


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="核对两仓同名的脚本")
    parser.add_argument(
        "--canonical",
        type=Path,
        default=None,
        help="私人仓真源脚本目录(默认是紧挨着公开仓的 src/scripts)",
    )
    args = parser.parse_args()

    public = Path(__file__).resolve().parent
    # 真源默认在**紧挨着**公开仓的那个 src/ 里:镜像作业把私人仓 checkout
    # 到 src/,公开仓 checkout 到 public/,两者同级 —— src/scripts 就是真源。
    # 也可显式指定,免得靠"猜同级目录"。
    canonical = (args.canonical or public.parent / "src" / "scripts").resolve()
    problems, unverifiable = compare(public, canonical)
    if problems:
        print("公开仓的脚本与私人仓真源对不上:")
        for item in problems:
            print(f" - {item}")
        return 1
    if unverifiable:
        print(f"公开仓脚本与真源一致性未核对(没有私人仓源码,{unverifiable} 个文件无从比对)")
        return 0
    print("公开仓的脚本与私人仓真源逐字一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
