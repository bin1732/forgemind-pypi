# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""把覆盖率数据文件里的路径统一成文本。

覆盖率数据文件里的路径列有时会存成字节串。报告阶段按文本处理这些路径,
就会因为类型不符而中断,一个覆盖率数字都拿不到。这里在报告之前把
字节串统一解码成文本,让数据文件与报告阶段的预期一致。
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

DATA_FILE = Path(".coverage")


def decode(value: object) -> str | None:
    """把字节串解码成文本,其它类型原样保留。"""
    if isinstance(value, bytes):
        return os.fsdecode(value)
    return None


def main() -> int:
    """规范化覆盖率数据里的路径,返回进程退出码。"""
    if not DATA_FILE.exists():
        print(f"找不到覆盖率数据文件: {DATA_FILE}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DATA_FILE)
    try:
        rows = conn.execute("select id, path from file").fetchall()
        updates = []
        for file_id, path in rows:
            text = decode(path)
            if text is not None:
                updates.append((text, file_id))
        if updates:
            conn.executemany("update file set path = ? where id = ?", updates)
            conn.commit()
    except sqlite3.Error as exc:
        print(f"规范化覆盖率数据失败: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    print(f"已规范化的路径数量: {len(updates)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
