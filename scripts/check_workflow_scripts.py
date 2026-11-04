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


def check_script_exists(
    label: str, run: str, workdir: str | None, repo_root: Path
) -> tuple[list[str], int]:
    """run 里调用的仓库脚本,必须真的存在于那个作业的工作目录下。

    作业可以指定 working-directory,也可以用 defaults.run.working-directory
    统一指定。脚本路径写对了、文件却不在那个目录下时,流水线会在这里
    失败 —— 而且是在跑了一堆别的之后才失败,不容易看出是路径问题。

    工作目录一律相对**被检查的那个仓根**解析,不相对进程的当前目录。
    相对当前目录的话,同一份工作流在本地跑和在流水线里跑会得出不同结论
    (流水线把源码 checkout 到别的目录,本地没有),检查就成了看运气 ——
    本地永远说"查不到",就永远查不到。

    返回 (问题列表, 没查的条数)。工作目录本身不在时无从判断脚本在不在 ——
    这时只记"没查",不报"缺失"。把"查不到"当成"没有",会让检查恒红,
    而红的原因与工作流本身无关,反倒把真问题淹了。
    """
    problems: list[str] = []
    skipped = 0
    # python scripts/xxx.py 或 python3 scripts/xxx.py
    matches = list(re.finditer(r"\bpython3?\s+(?:-[^\s]+\s+)*([\w./-]+\.py)\b", run))
    if not matches:
        return problems, skipped
    base = (repo_root / workdir) if workdir else repo_root
    if not base.is_dir():
        # 工作目录本身不在,脚本在不在没法验证
        return problems, len(matches)
    repo_base = repo_root.resolve()
    for match in matches:
        rel = match.group(1)
        if rel.startswith("/"):
            continue
        # 相对工作目录解析,包括 "../scripts/xxx.py" 这种写法 —— 基准目录
        # 是知道的,没有理由不核对。解析完还要确认落点仍在被检查的仓里,
        # 跑出仓外的路径不归这道检查管。
        target = (base / rel).resolve()
        if repo_base not in target.parents and target != repo_base:
            continue
        if not target.is_file():
            problems.append(f"{label}: 调用的脚本 {rel} 在工作目录 {base} 下不存在")
    return problems, skipped


def check_job_graph(path: Path, data: dict, repo_root: Path) -> list[str]:
    """作业之间的引用必须指向真实存在的东西。

    needs 指向一个不存在的作业,或者用了 ./ 开头却不在仓里的本地 action,
    GitHub 会把整个工作流判为无效 —— 那个工作流一个作业都不会跑,而
    失败信息只出现在工作流页面上。仓库里一切正常,只是那条流水线从来
    没跑过,这种失败最难被发现。

    作业依赖成环同样无效。
    """
    problems: list[str] = []
    jobs = data.get("jobs") or {}
    if not isinstance(jobs, dict):
        return problems

    for name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        needs = job.get("needs")
        if needs is None:
            continue
        wanted = [needs] if isinstance(needs, str) else list(needs or [])
        for dep in wanted:
            if dep not in jobs:
                problems.append(f"{path.name}: 作业 {name} 依赖的作业 {dep} 不存在")
        # 复用工作流调用(作业级 uses)不需要 runs-on
        if not job.get("runs-on") and not job.get("uses"):
            problems.append(f"{path.name}: 作业 {name} 既没有 runs-on 也没有 uses")

    # 本地 action:./ 开头指的就是仓里的目录,它必须真的在
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        refs = []
        job_uses = job.get("uses")
        if isinstance(job_uses, str):
            refs.append(job_uses)
        for step in job.get("steps") or []:
            if isinstance(step, dict) and isinstance(step.get("uses"), str):
                refs.append(step["uses"])
        for ref in refs:
            if not ref.startswith("./"):
                continue
            target = (repo_root / ref[2:]).resolve()
            if not target.is_dir():
                problems.append(f"{path.name}: 引用的本地 action {ref} 不存在")
            elif not (target / "action.yml").is_file() and not (target / "action.yaml").is_file():
                problems.append(f"{path.name}: 本地 action {ref} 里没有 action.yml")

    # 作业里只要有 run 步骤,就说明它要在工作区里读写东西 —— 那它必须
    # 先把仓库检出出来。少了这一步,作业会在一个空工作区里跑,报出来
    # 的却是"某个文件读不到",与真实原因无关。
    for name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        steps = [s for s in (job.get("steps") or []) if isinstance(s, dict)]
        if not steps:
            continue
        if not any("run" in s for s in steps):
            # 纯 action 组成的作业不碰工作区,不必检出
            continue
        if not any("actions/checkout" in str(s.get("uses", "")) for s in steps):
            problems.append(f"{path.name}: 作业 {name} 有 run 步骤却没有检出仓库")

    # 作业依赖成环
    state: dict[str, int] = {}

    def visit(name: str, trail: list[str]) -> None:
        if state.get(name) == 1:
            problems.append(f"{path.name}: 作业依赖成环({' → '.join(trail + [name])})")
            return
        if state.get(name) == 2:
            return
        state[name] = 1
        job = jobs.get(name)
        if isinstance(job, dict):
            needs = job.get("needs")
            wanted = [needs] if isinstance(needs, str) else list(needs or [])
            for dep in wanted:
                if dep in jobs:
                    visit(dep, trail + [name])
        state[name] = 2

    for name in jobs:
        visit(name, [])
    return problems


def check_publish_trigger_is_branch_limited(path: Path, data: dict) -> list[str]:
    """发布那条工作流的 push 触发必须限定分支。

    有 contents: write 权限的工作流就是发布那条 —— 它会写索引、写清单、
    传构件。少了分支过滤,推到任何分支都会触发它:没审过的代码被推成
    用户下载到的"最新版",索引也跟着指过去,而对外看不出发生过什么。
    """
    problems: list[str] = []
    permissions = data.get("permissions")
    if not isinstance(permissions, dict):
        return problems
    if str(permissions.get("contents", "")).lower() != "write":
        return problems
    on = data.get("on")
    if not isinstance(on, dict):
        on = data.get(True) if isinstance(data.get(True), dict) else {}
    push = on.get("push") if isinstance(on, dict) else None
    if not isinstance(push, dict):
        # 没有 push 触发(只靠 workflow_dispatch / workflow_run)就没事
        return problems
    branches = push.get("branches")
    if not branches:
        problems.append(
            f"{path.name}: 发布工作流的 push 触发必须限定分支 —— "
            "否则推到任何分支都会发布,把没审过的代码推成用户下载的最新版"
        )
    return problems


def collect_concurrency_group(data: dict) -> str | None:
    """取工作流声明的并发组;没声明(或声明了空的)就是没有。"""
    concurrency = data.get("concurrency")
    if not isinstance(concurrency, dict):
        return None
    group = concurrency.get("group")
    if not isinstance(group, str) or not group.strip():
        return None
    return group.strip()


def concurrency_group_prefix(group: str) -> str:
    """并发组里第一个表达式之前的字面前缀。

    前缀是字面量,运行时不会变 —— 所以前缀相同的两组,运行时就有可能
    落到同一个组里(表达式部分不同也可能算出同一个值)。前缀不同则
    一定落在不同的组。
    """
    marker = "${{"
    at = group.find(marker)
    return group if at < 0 else group[:at]


def check_concurrency_groups_are_not_shared(
    groups: list[tuple[str, str]],
) -> list[str]:
    """两个工作流不能共用同一个并发组。

    GitHub 的并发组只保留**一个**排队中的运行:新运行进来时,先到的那个
    排队中的会被取消掉。所以两个工作流共用一组,谁先到谁活下来 —— 每次
    触发必然有一个被取消,对外是随机的结果。

    活证据(2026-11-04,公开仓 bin1732/forgemind-pypi):三个发布后验证
    (verify / verify-live / verify-desktop)共用一个组时,同一批发布里
    verify-live 与 wheel-suite 是 success,verify 与 verify-desktop 是
    cancelled;换一批提交,被取消的换成另外两个。被取消的那些停在
    jobs=0 —— 作业压根没被创建,不是作业跑了失败。当时误判成"macOS
    runner 抢不到",实际每一次拿到 runner 的 macOS 作业都正常跑完了。

    判据分两层:
    - 组字符串完全相同:运行时必然落进同一组,直接报。
    - 字面前缀相同:运行时可能落进同一组(表达式算出同一个值),也报。
    """
    problems: list[str] = []
    by_exact: dict[str, list[str]] = {}
    by_prefix: dict[str, list[tuple[str, str]]] = {}
    for name, group in groups:
        by_exact.setdefault(group, []).append(name)
        by_prefix.setdefault(concurrency_group_prefix(group), []).append((name, group))

    for group, names in by_exact.items():
        if len(names) < 2:
            continue
        who = "、".join(sorted(names))
        problems.append(
            f"{who} 共用同一个并发组({group}) —— "
            "GitHub 的并发组只保留一个排队中的运行,新运行进来会把先到的那个取消掉,"
            "这几个工作流里必然有一个被取消,结果随机"
        )

    for prefix, items in by_prefix.items():
        if len(items) < 2:
            continue
        if len({group for _, group in items}) == 1:
            continue  # 完全相同的那一种已经报过了
        who = "、".join(sorted(name for name, _ in items))
        problems.append(
            f"{who} 的并发组字面前缀相同({prefix}) —— "
            "前缀是字面量,运行时相同就可能落进同一个组,那时候先到的那个会被取消"
        )
    return problems


def main(repo_root: Path | None = None) -> int:
    """检查工作流目录,返回进程退出码。

    repo_root 缺省是本仓的根;指到别的目录就能在临时目录里检查另一棵
    工作流树 —— 没有这个口子,检查器自己的行为就只能靠真仓来验。
    """
    repo_root = (repo_root or Path(__file__).resolve().parent.parent).resolve()
    root = repo_root / ".github" / "workflows"
    if not root.is_dir():
        print(f"找不到工作流目录: {root}", file=sys.stderr)
        return 1

    problems: list[str] = []
    unverified = 0
    concurrency_groups: list[tuple[str, str]] = []
    for path in sorted(root.glob("*.yml")):
        strict_problem = check_strict_parse(path)
        if strict_problem:
            problems.append(strict_problem)
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            problems.append(f"{path.name}: 内容不是映射")
            continue
        group = collect_concurrency_group(data)
        if group is not None:
            concurrency_groups.append((path.name, group))
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
                # 步骤上的 working-directory 是**覆盖**作业默认,不是拼接。
                # 活证据:镜像作业里那步写的是 "working-directory: ." 加
                # "python src/scripts/xxx.py",若把 "." 拼到作业默认 "src"
                # 后面,脚本路径就变成 src/src/scripts/xxx.py,那步在流水线里
                # 根本跑不起来 —— 而它是跑通过的。
                step_wd = step.get("working-directory")
                workdir = str(step_wd) if step_wd else job_wd
                found, missed = check_script_exists(label, run, workdir, repo_root)
                problems.extend(found)
                unverified += missed
        problems.extend(check_job_graph(path, data, repo_root))
        problems.extend(check_publish_trigger_is_branch_limited(path, data))

    problems.extend(check_concurrency_groups_are_not_shared(concurrency_groups))

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
