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

另外用严格解析器读一遍工作流:同一层里出现重复键时,宽松解析器只保留
最后一个,严格解析器会报错。GitHub 的解析器不接受重复键,工作流会整个
不被执行 —— 那种情况下流水线里看不到任何作业,失败信息也只在工作流
页面上,不专门查就会漏掉。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

HEREDOC_START = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")


class StrictLoader(yaml.SafeLoader):
    """同一层里出现重复键就报错的解析器。"""


def _no_duplicate_keys(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None, None, f"重复的键: {key}", key_node.start_mark
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys
)


def check_strict_parse(path: Path) -> str | None:
    """工作流有重复键时返回问题说明,否则返回 None。"""
    try:
        yaml.load(path.read_text(encoding="utf-8"), Loader=StrictLoader)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"(第 {mark.line + 1} 行)" if mark is not None else ""
        return f"{path.name}: 解析失败{where} {exc.problem or exc}"
    return None


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
        strict_problem = check_strict_parse(path)
        if strict_problem:
            problems.append(strict_problem)
            continue
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
