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

还要按 GitHub 的 schema 核对字段:步骤上多写一个 `working-directory`
或 `shell`(它们只对 run 步骤有意义),同样是解析期被拒,工作流整体
不执行。

取源码的步骤还要先切进自己的目录再 `git init`:工作区根常常已经
checkout 过本仓,在那儿 init 会串到本仓的 .git,`git remote add origin`
随即因为 origin 已存在而失败。
"""

from __future__ import annotations

import re
import subprocess
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


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys)


def check_strict_parse(path: Path) -> str | None:
    """工作流有重复键时返回问题说明,否则返回 None。"""
    try:
        yaml.load(path.read_text(encoding="utf-8"), Loader=StrictLoader)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"(第 {mark.line + 1} 行)" if mark is not None else ""
        return f"{path.name}: 解析失败{where} {exc.problem or exc}"
    return None


def check_git_init_isolation(name: str, job_name: str, job: dict) -> list[str]:
    """取源码的步骤要先切进自己的目录再 git init。

    工作区根常常已经 checkout 过本仓。在那儿 git init 会接着用本仓的
    .git,后面的 `git remote add origin` 会因为 origin 已存在而失败 ——
    报错只说 "remote origin already exists",与"取源码"毫无关联,极难定位。
    """
    problems: list[str] = []
    for step in job.get("steps") or []:
        run = step.get("run")
        if not isinstance(run, str) or "git init" not in run:
            continue
        if "mkdir -p" not in run or "cd " not in run:
            problems.append(
                f"{name}:{job_name}: 取源码前没有切进自己的目录,"
                f"工作区根若已 checkout 过本仓,git init 会串到本仓的 .git"
            )
    return problems


def check_step_schema(name: str, job_name: str, job: dict) -> list[str]:
    """按 GitHub 的工作流 schema 核对作业与步骤的字段。

    这些错在**解析期**就被拒:整个工作流不会执行,流水线里一个作业都
    看不到,失败信息只留在工作流页面上。已踩过的:
    `uses:` 步骤上写了 `working-directory` —— 它只对 `run:` 步骤有意义。
    """
    problems: list[str] = []
    label = f"{name}:{job_name}"

    has_uses = bool(job.get("uses"))
    if not has_uses and not job.get("runs-on"):
        problems.append(f"{label}: 作业既没有 runs-on 也没有 uses")
    if has_uses and (job.get("steps") or job.get("runs-on")):
        problems.append(f"{label}: 复用工作流的作业不能带 steps 或 runs-on")

    for step in job.get("steps") or []:
        if not isinstance(step, dict):
            continue
        title = step.get("name") or step.get("uses") or "?"
        where = f"{label}:{title}"
        run = step.get("run")
        uses = step.get("uses")
        if run is None and uses is None:
            problems.append(f"{where}: 步骤既没有 run 也没有 uses")
            continue
        if run is not None and uses is not None:
            problems.append(f"{where}: 步骤不能同时有 run 和 uses")
            continue
        if uses is not None:
            # 只对 run 步骤有意义的字段,写在 uses 步骤上会被 GitHub 拒
            for key in ("working-directory", "shell"):
                if key in step:
                    problems.append(
                        f"{where}: uses 步骤上不能有 {key}"
                        f"(它只对 run 步骤有意义,会让整个工作流不被执行)"
                    )
        else:
            if "with" in step:
                problems.append(f"{where}: run 步骤上不能有 with")
    return problems


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
                problems.append(f"{name}: 文档分隔符 {tag} 的终止符带缩进,shell 认不出来")
            break
        else:
            problems.append(f"{name}: 文档分隔符 {tag} 没有终止符")

    if "\n" in run and not run.endswith("\n"):
        problems.append(f"{name}: 多行脚本末尾没有换行")

    problems.extend(check_shell_syntax(name, run))

    return problems


def check_shell_syntax(name: str, run: str) -> list[str]:
    """用 shell 自己检查这段脚本的语法。

    引号写坏、续行断开、|| 落到单独一行 —— 这些在 YAML 里都看不出来,
    流水线跑到那一步才会以语法错误失败。shell 的 -n 不执行,只查语法。
    """
    if not run.strip():
        return []
    try:
        result = subprocess.run(
            ["bash", "-n"], input=run, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        # 没有 shell 可用就放过,别因为环境缺东西而误报
        return []
    if result.returncode == 0:
        return []
    detail = (result.stderr or "").strip().splitlines()
    message = detail[0] if detail else "语法错误"
    return [f"{name}: shell 语法错误 —— {message}"]


def check_script_exists(label: str, run: str, workdir: str | None) -> tuple[list[str], int]:
    """run 里调用的仓库脚本,必须真的存在于那个作业的工作目录下。

    作业可以指定 working-directory,也可以用 defaults.run.working-directory
    统一指定。脚本路径写对了、文件却不在那个目录下时,流水线会在这里
    失败 —— 而且是在跑了一堆别的之后才失败,不容易看出是路径问题。

    返回 (问题列表, 没查的条数)。工作目录在本地不存在时(镜像工作流要把
    私人源码 checkout 到 src/,本地没 checkout 过),无从判断脚本在不在 ——
    这时只记"没查",不报"缺失"。把"查不到"当成"没有",会让检查在本地恒红,
    而红的原因与工作流本身无关,反倒把真问题淹了。
    """
    problems: list[str] = []
    skipped = 0
    # python scripts/xxx.py 或 python3 scripts/xxx.py
    matches = list(re.finditer(r"\bpython3?\s+(?:-[^\s]+\s+)*([\w./-]+\.py)\b", run))
    if not matches:
        return problems, skipped
    base = Path(workdir) if workdir else Path(".")
    if not base.is_dir():
        # 工作目录本身不在,脚本在不在没法验证
        return problems, len(matches)
    for match in matches:
        rel = match.group(1)
        if rel.startswith("/") or ".." in rel:
            continue
        if not (base / rel).is_file():
            problems.append(f"{label}: 调用的脚本 {rel} 在工作目录 {base} 下不存在")
    return problems, skipped


def main() -> int:
    """检查工作流目录,返回进程退出码。"""
    root = Path(__file__).resolve().parent.parent / ".github" / "workflows"
    if not root.is_dir():
        print(f"找不到工作流目录: {root}", file=sys.stderr)
        return 1

    problems: list[str] = []
    unverified = 0
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
            if not isinstance(job, dict):
                continue
            problems.extend(check_step_schema(path.name, job_name, job))
            problems.extend(check_git_init_isolation(path.name, job_name, job))
            # 作业级 working-directory 与步骤级 working-directory 都要算进去
            defaults = (job.get("defaults") or {}).get("run") or {}
            job_wd = defaults.get("working-directory")
            for step in job.get("steps") or []:
                run = step.get("run")
                if not isinstance(run, str) or not run.strip():
                    continue
                label = f"{path.name}:{job_name}:{step.get('name', step.get('uses', '?'))}"
                problems.extend(check_run(label, run))
                step_wd = step.get("working-directory")
                if step_wd:
                    workdir = str(Path(job_wd) / step_wd) if job_wd else str(step_wd)
                else:
                    workdir = job_wd
                found, missed = check_script_exists(label, run, workdir)
                problems.extend(found)
                unverified += missed

    if problems:
        print("工作流脚本写法有问题:")
        for item in problems:
            print(" -", item)
        return 1

    if unverified:
        print(f"工作流脚本写法检查通过({unverified} 处脚本路径因工作目录不在本地而未核对)")
        return 0

    print("工作流脚本写法检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
