# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""确认构件已经出现在 TestPyPI 上。

读取 TestPyPI 返回的包信息,核对版本号与文件名,并在缺失时以非零
退出码结束,让发布流程立刻失败。
"""

from __future__ import annotations

import json
import sys
import urllib.request

URL = "https://test.pypi.org/pypi/forgemind/json"
TIMEOUT = 30


def main() -> int:
    """拉取包信息并打印结果,返回进程退出码。"""
    try:
        with urllib.request.urlopen(URL, timeout=TIMEOUT) as resp:
            data = json.load(resp)
    except Exception as exc:  # noqa: BLE001 - 网络与解析异常都算失败
        print(f"读取 TestPyPI 信息失败: {exc}", file=sys.stderr)
        return 1

    version = data["info"]["version"]
    files = [item["filename"] for item in data["urls"]]
    if not files:
        print("TestPyPI 上没有构件", file=sys.stderr)
        return 1

    print(f"TestPyPI: forgemind {version}")
    for name in files:
        print(f"   {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
