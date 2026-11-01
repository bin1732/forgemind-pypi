# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""确认流水线安装的依赖真的可用。

安装日志里的成功提示会随 pip 版本变化,不能作为判据。这里按项目声明
的运行时依赖逐个导入,导入失败即视为依赖不可用。

要检查哪些模块由 pyproject 的声明推导,不手工维护清单 —— 手工清单会
漏,漏掉的正好是那些在流水线里被静默跳过的依赖。
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_dependency_declarations import (  # noqa: E402
    IMPORT_TO_DISTRIBUTION,
    load_declared,
)


def main() -> int:
    """逐个导入关键模块,返回进程退出码。"""
    declared, _ = load_declared()
    # 发行包名 -> 顶层 import 名
    dist_to_module = {dist: module for module, dist in IMPORT_TO_DISTRIBUTION.items()}

    failures: list[str] = []
    checked = 0
    for name in sorted(declared):
        module = dist_to_module.get(name)
        if module is None:
            failures.append(f"{name}: 没有登记对应的顶层模块名,无法检查是否可用")
            continue
        checked += 1
        try:
            importlib.import_module(module)
        except Exception as exc:  # noqa: BLE001 - 任何导入异常都算失败
            failures.append(f"{module} (对应 {name}): {exc}")

    if failures:
        print("缺失或无法导入:")
        for item in failures:
            print(" -", item)
        return 1

    print(f"关键依赖 {checked} 项全部可导入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
