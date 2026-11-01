# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""确认工作区里的代码就是本次提交的内容。

流水线跑的是哪一份代码,需要能被流水线自己回答。代码与提交对不上时,
失败信息会指向旧版本的文件,只看报错很难察觉,常常要反复比对行号才
能发现。这里直接核对提交号与关键文件的内容标记。
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

# 关键文件与它们应当包含的内容标记。标记取自这些文件里不太可能重复的
# 片段,用来确认拿到的确实是当前提交的内容。
PROBES: dict[str, str] = {
    "tests/test_underlying_memory_page.py": "assert log",
    "tests/test_underlying_git_history.py": "stash",
    "forgemind/core/config/settings.py": "min_length=32",
}


def head_commit() -> str:
    """返回当前提交号。"""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=60
    )
    return result.stdout.strip()


def main() -> int:
    """核对提交号与关键文件内容,返回进程退出码。"""
    head = head_commit()
    if not head:
        print("取不到当前提交号", file=sys.stderr)
        return 1
    print(f"checkout HEAD: {head}")

    for rel, marker in PROBES.items():
        path = pathlib.Path(rel)
        if not path.exists():
            print(f"缺失文件: {rel}", file=sys.stderr)
            return 1
        text = path.read_text(encoding="utf-8")
        if marker not in text:
            print(f"{rel} 里找不到 {marker!r},工作区与预期不一致", file=sys.stderr)
            return 1
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        print(f"  {rel}: {digest}")

    print("工作区与本次提交一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
