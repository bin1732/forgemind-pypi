# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对公开仓的镜像工作流把私人仓的门禁检查一条不落地覆盖了。

公开仓承担私人仓的全量验证:私人仓自己的 CI 被账号计费闸门挡住,而公开仓
的作业不消耗付费分钟。要让"公开仓全绿 ⇒ 私人仓全绿"成立,镜像必须完整
 —— 漏掉任何一条检查,这个蕴含关系就不成立,而且没人会察觉。

所以这里以**逻辑命令**为比对单位:

1. 私人仓每条门禁工作流里的每一条命令,都必须在镜像里出现
2. 私人仓里无条件执行的命令,镜像里也必须无条件执行(镜像不得比
   私人仓跑得少)
3. 私人仓的每个工作流要么被镜像,要么在显式排除清单里写明理由 ——
   不许有漏网的,也不许有悄悄排除的

用法:
    python scripts/check_ci_mirror.py --private <私人仓源码目录>
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("需要 pyyaml 才能解析工作流文件", file=sys.stderr)
    raise SystemExit(2)

PUBLIC = Path(__file__).resolve().parent.parent
MIRROR_WORKFLOW = "ci-mirror.yml"

# 私人仓里属于日常门禁的工作流
GATE_WORKFLOWS = {
    "ci-lint.yml": "代码质量",
    "ci-security.yml": "安全扫描",
    "ci-tests.yml": "Python 测试",
    "ci-ui.yml": "UI 测试",
}

# 私人仓里不属于门禁的工作流,以及不镜像的理由
EXCLUDED_WORKFLOWS = {
    "ci-status.yml": "只写运行摘要的汇总作业,continue-on-error,本来就不是门禁",
    "release.yml": "打版本 tag 才触发的发布动作,不在日常门禁范围;发布由公开仓 ship.yml 承担",
}


def normalize(block: str) -> list[str]:
    """把一段 run 脚本拆成归一化后的逻辑命令。

    续行先接成一条,注释行丢掉,内部空白压成单空格 —— 于是"同一件事的两种
    写法"能被认成同一条,镜像里照抄与改写都算覆盖。
    """
    lines: list[str] = []
    pending = ""
    for raw in block.splitlines():
        line = raw.strip()
        if not pending:
            if not line or line.startswith("#"):
                continue
        if line.endswith("\\"):
            pending += line[:-1].strip() + " "
            continue
        lines.append(pending + line)
        pending = ""
    if pending:
        lines.append(pending.strip())
    return [" ".join(l.split()) for l in lines if l.strip()]


def _steps_of(job: dict) -> list[dict]:
    return [s for s in (job.get("steps") or []) if isinstance(s, dict)]


def _always_runs(step: dict) -> bool:
    """这一步是否无条件执行。always() 视同无条件。"""
    cond = str(step.get("if") or "").strip()
    return cond in ("", "always()", "${{ always() }}")


def commands_of(workflow: dict, only_unconditional: bool) -> set[str]:
    """工作流里无条件执行的命令集合。"""
    out: set[str] = set()
    for job in (workflow.get("jobs") or {}).values():
        job_unconditional = _always_runs(job)
        for step in _steps_of(job):
            if "run" not in step:
                continue
            if only_unconditional and not (job_unconditional and _always_runs(step)):
                continue
            out.update(normalize(step["run"]))
    return out


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def check_no_shallow_fetch(workflow: dict) -> list[str]:
    """镜像必须拿到足够深的历史。

    私人仓的 CI 用 checkout 的 fetch-depth: 0,它的 git 历史用例就靠这个
    前提跑通 —— 只剩一个 commit 时,`git log` 与 `git diff HEAD~1` 全部
    失效,那些用例会红,而这种失败看起来像是用例本身坏了。

    depth=1 是最浅的一种,必然不够;更深的深度可以。
    """
    problems: list[str] = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        for step in (job.get("steps") or []):
            run = step.get("run")
            if not isinstance(run, str) or "git fetch" not in run:
                continue
            if re.search(r"--depth[= ]1(?![0-9])", run):
                problems.append(
                    f"{job_name}: 取源码用了 --depth 1(只剩一个提交),"
                    f"私人仓的 git 历史用例会失效")
    return problems


def check_history_depth(workflow: dict) -> list[str]:
    """跑私人仓全量测试的作业必须拿到完整历史。

    私人仓的 git 历史用例要翻到一千多条之前的提交才找得到
    "docs(audit): 终版三维度自检报告" 那一条。浅克隆的历史不够,那些用例会
    红 —— 而这种失败看起来像是用例本身坏了,极难定位。

    其余作业(静态检查、界面检查)不跑那些用例,浅历史够用。
    """
    problems: list[str] = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        runs = [s.get("run") for s in (job.get("steps") or [])
                if isinstance(s.get("run"), str)]
        if not any("pytest tests/" in r for r in runs):
            continue
        # 只跑重并发档的作业不碰 git 历史用例(那个文件不是重并发档),
        # 浅历史对它够用。
        if any("-m heavy" in r for r in runs):
            continue
        for run in runs:
            if "git fetch" in run and re.search(r"--depth[= ]", run):
                problems.append(
                    f"{job_name}: 跑私人仓全量测试的作业取了浅历史,"
                    f"git 历史用例会失效")
                break
    return problems


def _installs_deps(commands: set[str]) -> bool:
    """这个作业是否装了项目的依赖。"""
    return any("requirements-ci.txt" in c and c.startswith("pip install")
               for c in commands)


def _job_commands(job: dict) -> set[str]:
    out: set[str] = set()
    for step in (job.get("steps") or []):
        run = step.get("run")
        if isinstance(run, str):
            out.update(normalize(run))
    return out


def check_dep_placement(private_workflows: dict, mirror_workflows: dict) -> list[str]:
    """私人仓里"装了依赖"的作业中的检查,镜像里也必须落在装了依赖的作业里。

    有两类检查会真的导入项目(因子库、pytest 采集),它们在没装依赖的
    作业里只会报 "No module named 'numpy'"。光比对命令覆盖查不出这个 ——
    命令在镜像里出现了,但落在了错误的作业里。
    """
    problems: list[str] = []
    mirror_jobs = [(name, _job_commands(job)) for name, job
                   in mirror_workflows.get("jobs", {}).items()]
    for wf_name, wf in private_workflows.items():
        for pj_name, pj in (wf.get("jobs") or {}).items():
            pcmds = _job_commands(pj)
            if not _installs_deps(pcmds):
                continue
            checks = {c for c in pcmds
                      if not c.startswith("pip install")
                      and "requirements-ci.txt" not in c}
            for cmd in sorted(checks):
                if not any(cmd in mcmds for _, mcmds in mirror_jobs):
                    continue
                if not any(cmd in mcmds and _installs_deps(mcmds)
                           for _, mcmds in mirror_jobs):
                    problems.append(
                        f"{wf_name}:{pj_name} 的检查在镜像里没有落在装了依赖的"
                        f"作业中: {cmd[:90]}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="核对镜像工作流覆盖了私人仓的门禁")
    parser.add_argument("--private", type=Path, required=True,
                        help="私人仓源码根目录")
    parser.add_argument("--public", type=Path, default=PUBLIC,
                        help="公开仓根目录")
    args = parser.parse_args()

    private_dir = args.private.resolve()
    public_dir = args.public.resolve()
    private_wf_dir = private_dir / ".github" / "workflows"
    public_wf_dir = public_dir / ".github" / "workflows"

    if not private_wf_dir.is_dir():
        print(f"找不到私人仓工作流目录: {private_wf_dir}", file=sys.stderr)
        return 2
    mirror_path = public_wf_dir / MIRROR_WORKFLOW
    if not mirror_path.is_file():
        print(f"找不到镜像工作流: {mirror_path}", file=sys.stderr)
        return 2

    mirror = load(mirror_path)
    mirror_all = commands_of(mirror, only_unconditional=False)
    mirror_uncond = commands_of(mirror, only_unconditional=True)

    problems: list[str] = []
    print(f"镜像工作流: {MIRROR_WORKFLOW}")
    print("=" * 78)

    for name, label in GATE_WORKFLOWS.items():
        path = private_wf_dir / name
        if not path.is_file():
            problems.append(f"私人仓少了工作流 {name}(镜像清单里写着它)")
            continue
        wf = load(path)
        all_cmds = commands_of(wf, only_unconditional=False)
        uncond = commands_of(wf, only_unconditional=True)

        missing = sorted(c for c in all_cmds if c not in mirror_all)
        missing_uncond = sorted(c for c in uncond if c not in mirror_uncond)

        covered = len(all_cmds) - len(missing)
        mark = "完整" if not missing else "有缺口"
        print(f"  {name:<18} {label:<8} {covered:>3}/{len(all_cmds):<3} 条命令  {mark}")
        for cmd in missing:
            problems.append(f"{name} 有命令没被镜像: {cmd}")
        for cmd in missing_uncond:
            problems.append(
                f"{name} 有无条件命令在镜像里被条件跳过了: {cmd}")

    # 私人仓的工作流不许有漏网的
    for path in sorted(private_wf_dir.glob("*.yml")):
        if path.name in GATE_WORKFLOWS or path.name in EXCLUDED_WORKFLOWS:
            continue
        problems.append(
            f"私人仓的工作流 {path.name} 既没被镜像,也没在排除清单里写明理由")

    # 镜像自己的硬性要求
    problems.extend(check_no_shallow_fetch(mirror))
    problems.extend(check_history_depth(mirror))
    # 装了依赖的作业里的检查,镜像里也得落在装了依赖的作业里
    private_wfs = {name: load(private_wf_dir / name) for name in GATE_WORKFLOWS}
    problems.extend(check_dep_placement(private_wfs, mirror))

    print("=" * 78)
    print("不镜像的工作流(附理由):")
    for name, reason in EXCLUDED_WORKFLOWS.items():
        print(f"  {name:<18} {reason}")

    if problems:
        print("\n镜像不完整:")
        for item in problems:
            print(" -", item)
        return 1

    print("\n镜像完整:私人仓门禁里的每一条命令都在镜像里,且无条件命令没有被条件跳过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
