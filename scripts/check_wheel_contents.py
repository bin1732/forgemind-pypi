# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对发布出去的 wheel 与源码对得上。

两件事:

1. **模块一个不少** —— 构建配置漏掉一个子包,用户装上之后 import 就
   报错,而这种错误只在**装出来的构件**上才现形:源码树里那个模块明明
   在,测试也跑得过。
2. **依赖声明一致** —— wheel 的 METADATA 少声明一个依赖,用户装完同样
   缺包;多声明一个则会让 pip 装上用不到的东西。

用法:
    python scripts/check_wheel_contents.py <wheel> <源码目录>
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path


def source_modules(root: Path) -> set[str]:
    """源码树里属于包的 .py(相对包根的路径)。"""
    pkg = root / "forgemind"
    if not pkg.is_dir():
        return set()
    out = set()
    for path in pkg.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        out.add(path.relative_to(pkg).as_posix())
    return out


def wheel_modules(wheel: Path) -> set[str]:
    """wheel 里属于包的 .py(相对包根的路径)。"""
    with zipfile.ZipFile(wheel) as z:
        out = set()
        for name in z.namelist():
            if not name.startswith("forgemind/") or not name.endswith(".py"):
                continue
            out.add(name[len("forgemind/") :])
    return out


def declared_requirements(root: Path) -> set[str]:
    """pyproject 里声明的运行时依赖(名称,不含版本区间)。"""
    import re as _re
    import tomllib

    with (root / "pyproject.toml").open("rb") as fh:
        data = tomllib.load(fh)
    deps = (data.get("project", {}) or {}).get("dependencies", []) or []
    out = set()
    for item in deps:
        name = _re.split(r"[<>=!~;\[]", item, maxsplit=1)[0].strip()
        if name:
            out.add(_re.sub(r"[-_.]+", "-", name).lower())
    return out


def wheel_requirements(wheel: Path) -> set[str]:
    """wheel 的 METADATA 里声明的运行时依赖(名称,不含版本区间与 extra 标记)。"""
    import re as _re

    with zipfile.ZipFile(wheel) as z:
        meta_name = next(n for n in z.namelist() if n.endswith(".dist-info/METADATA"))
        meta = z.read(meta_name).decode("utf-8", "replace")
    out = set()
    for line in meta.splitlines():
        if not line.startswith("Requires-Dist:"):
            continue
        value = line.split(":", 1)[1].strip()
        if ";" in value:  # 带 extra 标记的是可选依赖
            continue
        name = _re.split(r"[<>=!~;\[ ]", value, maxsplit=1)[0].strip()
        if name:
            out.add(_re.sub(r"[-_.]+", "-", name).lower())
    return out


def source_data_files(source: Path) -> set[str]:
    """源码树里包目录下的非 .py 文件。

    这些文件不在包里,源码树里就白放着 —— 装出来的包用到它们时会报
    "文件不存在"。forgemind/data/ 里的真实历史行情就是这样漏掉的:
    它不是 Python 包,按包查找找不到它,数据文件也就没进 wheel。
    """
    root = source / "forgemind"
    if not root.is_dir():
        return set()
    out: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if rel.suffix == ".py" or "__pycache__" in rel.parts:
            continue
        out.add(str(rel).replace("\\", "/"))
    return out


def wheel_data_files(wheel: Path) -> set[str]:
    """wheel 里包目录下的非 .py 文件。"""
    import zipfile

    out: set[str] = set()
    with zipfile.ZipFile(wheel) as zf:
        for name in zf.namelist():
            if not name.startswith("forgemind/"):
                continue
            rel = name[len("forgemind/") :]
            if rel.endswith(".py") or "__pycache__" in rel:
                continue
            out.add(rel)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="核对 wheel 里的模块与源码一致")
    parser.add_argument("wheel", type=Path, help="wheel 路径")
    parser.add_argument("source", type=Path, help="源码目录")
    args = parser.parse_args()

    if not args.wheel.is_file():
        print(f"找不到 wheel: {args.wheel}", file=sys.stderr)
        return 2

    src = source_modules(args.source.resolve())
    whl = wheel_modules(args.wheel.resolve())
    if not src:
        print(f"{args.source} 下没有 forgemind 包目录", file=sys.stderr)
        return 2
    if not whl:
        print(f"{args.wheel} 里没有 forgemind 包内容", file=sys.stderr)
        return 1

    missing = sorted(src - whl)
    extra = sorted(whl - src)

    problems = []
    if missing:
        problems.append(f"wheel 漏装了 {len(missing)} 个模块: {missing[:12]}")
    if extra:
        problems.append(f"wheel 里有源码树没有的 {len(extra)} 个模块: {extra[:12]}")

    # 包内的数据文件也要在 wheel 里
    src_data = source_data_files(args.source.resolve())
    whl_data = wheel_data_files(args.wheel.resolve())
    missing_data = sorted(src_data - whl_data)
    if missing_data:
        problems.append(f"wheel 漏装了 {len(missing_data)} 个包内数据文件: {missing_data[:12]}")

    # 依赖声明也要一致
    declared = declared_requirements(args.source.resolve())
    required = wheel_requirements(args.wheel.resolve())
    if declared:
        lack = sorted(declared - required)
        surplus = sorted(required - declared)
        if lack:
            problems.append(f"wheel 的 METADATA 少声明了 {len(lack)} 个依赖: {lack[:12]}")
        if surplus:
            problems.append(f"wheel 的 METADATA 多声明了 {len(surplus)} 个依赖: {surplus[:12]}")

    if problems:
        print("wheel 的内容与源码对不上:")
        for item in problems:
            print(" -", item)
        return 1

    print(f"wheel 与源码一致:{len(whl)} 个模块、{len(required)} 个依赖声明,一个不少")
    return 0


if __name__ == "__main__":
    sys.exit(main())
