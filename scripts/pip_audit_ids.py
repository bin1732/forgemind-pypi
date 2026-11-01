# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""输出 pip-audit 白名单对应的命令行参数。

白名单的唯一来源是仓库根目录的 pip-audit.toml。流水线把这里的输出
直接拼进 pip-audit 命令行,避免同一份清单在多处维护。

pip-audit 的 --ignore-vuln 每次只接受一个编号,重复传参才会逐个生效,
因此这里输出的是完整的参数片段,而不是逗号分隔的编号列表。
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "pip-audit.toml"


def main() -> int:
    """打印逐个编号的 --ignore-vuln 参数。"""
    if not CONFIG.exists():
        print(f"找不到白名单文件: {CONFIG}", file=sys.stderr)
        return 1

    data = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    ids = data.get("ignore-vuln", [])
    if not isinstance(ids, list) or not ids:
        print("白名单为空或格式不正确", file=sys.stderr)
        return 1

    print(" ".join(f"--ignore-vuln {i}" for i in ids))
    return 0


if __name__ == "__main__":
    sys.exit(main())
