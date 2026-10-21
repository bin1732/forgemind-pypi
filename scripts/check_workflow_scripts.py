# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""检查工作流里的内联脚本写法。

内联脚本有两类容易出错的地方:

- 文档分隔符的终止符带缩进时,shell 认不出来,脚本会被吞到文件末尾,
  python 那边报缩进错误
- 写进引号标量的多行脚本,读取时换行会折叠成空格,脚本里的注释行
  会把后面的命令一起注释掉,命令实际没有执行

这个检查按解析后的内容判断,不按文件里的原始缩进判断。带缩进的终止符
与折行的引号标量都会被指出来。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

HEREDOC_START = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")


def check_run(name: str, run: str) -> list[str]:
    """返回单个 run 脚本里的问题列表。"""
    problems: list[str] = []
    lines = run.splitlines()

    for index, line in enumerate(lines):
        match = HEREDOC_START.search(line)
        if not match:
            continue
        tag = match.group(1)
        for offset in range(index + 1, len(lines)):
            if lines[offset].strip() != tag:
                continue
            if lines[offset] != lines[offset].lstrip():
                problems.append(
                    f"{name}: 文档分隔符 {tag} 的终止符带缩进,shell 认不出来"
                )
            break
        else:
            problems.append(f"{name}: 文档分隔符 {tag} 没有终止符")

    if "\n" in run and not run.endswith("\n"):
        problems.append(f"{name}: 多行脚本末尾没有换行")

    return problems


def main() -> int:
    """检查工作流目录,返回进程退出码。"""
    root = Path(__file__).resolve().parent.parent / ".github" / "workflows"
    if not root.is_dir():
        print(f"找不到工作流目录: {root}", file=sys.stderr)
        return 1

    problems: list[str] = []
    for path in sorted(root.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            problems.append(f"{path.name}: 内容不是映射")
            continue
        for job_name, job in (data.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                run = step.get("run")
                if not isinstance(run, str) or not run.strip():
                    continue
                label = f"{path.name}:{job_name}:{step.get('name', step.get('uses', '?'))}"
                problems.extend(check_run(label, run))

    if problems:
        print("工作流脚本写法有问题:")
        for item in problems:
            print(" -", item)
        return 1

    print("工作流脚本写法检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
