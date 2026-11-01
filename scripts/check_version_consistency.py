# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对版本号的各处声明一致。

版本号写在四个地方:pyproject 的 project.version(构建时用)、
forgemind/__init__.py 的 __version__(运行时用)、桌面端 Cargo.toml 的
[package].version(桌面二进制报的版本)、界面 package.json 的 version。
四个地方只要有一个漏改,装出来的包或桌面包就会报一个和实际不符的版本 ——
用户看到的版本对不上代码,排查起来极难。构建产物里的 METADATA 也一起核对。
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys


def pyproject_version(root: pathlib.Path) -> str | None:
    """读 pyproject 里的 project.version。"""
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', text, re.M)
    return match.group(1) if match else None


def package_version(root: pathlib.Path) -> str | None:
    """读 forgemind/__init__.py 里的 __version__。"""
    path = root / "forgemind" / "__init__.py"
    if not path.is_file():
        return None
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Name)
                and target.id == "__version__"
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                return node.value.value
    return None


def metadata_version(wheel: pathlib.Path) -> str | None:
    """读 wheel 里 METADATA 的 Version 字段。"""
    import zipfile

    with zipfile.ZipFile(wheel) as archive:
        names = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
        if not names:
            return None
        for line in archive.read(names[0]).decode("utf-8").splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    return None


def cargo_version(root: pathlib.Path) -> str | None:
    """读桌面端 Cargo.toml 里 [package] 段的版本。

    桌面二进制报的版本就是它。发布出去的二进制与 Python 包版本必须一致 ——
    两者分家时,用户手里的桌面端与 pip 装的是两份不同的东西。
    只看 [package] 段:依赖段里的 version 是依赖的版本,不是本包的。
    """
    path = root / "forgemind-ui" / "src-tauri" / "Cargo.toml"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    section = re.search(r"^\[package\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    if section is None:
        return None
    match = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', section.group(1), re.M)
    return match.group(1) if match else None


def ui_package_version(root: pathlib.Path) -> str | None:
    """读界面 package.json 里的版本。"""
    path = root / "forgemind-ui" / "package.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("version")
    except json.JSONDecodeError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="核对版本号各处一致")
    parser.add_argument(
        "source",
        type=pathlib.Path,
        nargs="?",
        default=pathlib.Path("."),
        help="源码目录",
    )
    parser.add_argument(
        "--wheel",
        type=pathlib.Path,
        default=None,
        help="可选:一并核对 wheel 里的 METADATA 版本",
    )
    args = parser.parse_args()
    root = args.source.resolve()

    declared = pyproject_version(root)
    runtime = package_version(root)
    desktop = cargo_version(root)
    ui = ui_package_version(root)

    problems = []
    if declared is None:
        problems.append("pyproject.toml 里读不到 project.version")
    if runtime is None:
        problems.append("forgemind/__init__.py 里读不到 __version__")
    if desktop is None:
        problems.append("forgemind-ui/src-tauri/Cargo.toml 里读不到 [package].version")
    if ui is None:
        problems.append("forgemind-ui/package.json 里读不到 version")
    if declared and runtime and declared != runtime:
        problems.append(
            f"版本号两处不一致: pyproject 是 {declared},forgemind/__init__.py 是 {runtime}"
        )
    if declared and desktop and declared != desktop:
        problems.append(
            f"桌面端版本与 Python 包不一致: Cargo.toml 是 {desktop},pyproject 是 {declared}"
        )
    if declared and ui and declared != ui:
        problems.append(
            f"界面包版本与 Python 包不一致: package.json 是 {ui},pyproject 是 {declared}"
        )

    if args.wheel is not None:
        if not args.wheel.is_file():
            problems.append(f"找不到 wheel: {args.wheel}")
        else:
            built = metadata_version(args.wheel)
            if built is None:
                problems.append("wheel 里读不到 METADATA 的 Version")
            elif declared and built != declared:
                problems.append(f"wheel 里的版本是 {built},与 pyproject 的 {declared} 不一致")

    if problems:
        print("版本号声明不一致:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    target = f"(pyproject {declared}"
    if desktop:
        target += f" / Cargo.toml {desktop}"
    if ui:
        target += f" / package.json {ui}"
    if args.wheel is not None:
        target += f" / wheel {metadata_version(args.wheel)}"
    target += ")"
    print(f"版本号声明一致 {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
