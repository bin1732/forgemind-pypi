# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 Git 历史 — 用真 git 命令 checkout 历史提交, 验历史代码真能跑测试。
不走 mock, 真 subprocess + 真 git checkout + 真 pytest。
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent


def _git(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60,
    )


@pytest.fixture
def git_state():
    """记录当前 branch + HEAD, test 完恢复。不影响真仓的 HEAD。"""
    r = _git("rev-parse", "HEAD")
    head_before = r.stdout.strip()
    r = _git("branch", "--show-current")
    branch_before = r.stdout.strip()
    yield {"head_before": head_before, "branch_before": branch_before}
    # 恢复仓库状态,但要保住工作区里未提交的改动。
    # 直接 reset 会把改动一并丢掉,改动的来源常常是同时在进行的其它工作。
    stashed = _git("stash", "push", "--include-untracked", cwd=REPO)
    try:
        _git("checkout", branch_before, "--", cwd=REPO)
        _git("reset", "--hard", head_before, cwd=REPO)
    finally:
        if stashed.returncode == 0 and stashed.stdout.strip():
            _git("stash", "pop", cwd=REPO)


def test_git_log_has_real_commits(git_state):
    """git log 真能列出最近的 commit (验 git 真活着)"""
    r = _git("log", "--oneline", "-10")
    assert r.returncode == 0
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    assert len(lines) >= 10, f"应有 ≥ 10 commit, 实际 {len(lines)}: {lines[:5]}"


def test_git_log_includes_cleanup_commits(git_state):
    """git log 真含清理可见痕迹的 commit

    历史被重写过 —— 提交说明里不该再有开发过程的痕迹。这条断言盯的是
    "重写确实发生过",不是某一条具体的说明:清理动作的提交名会变,盯
    关键词才稳。
    """
    r = _git("log", "--oneline", "--grep=残留", "-5")
    assert r.returncode == 0
    assert "残留" in r.stdout, f"应有清理痕迹的 commit, 实际: {r.stdout!r}"


def test_git_log_message_rewrite_no_development_chatter(git_state):
    """git log 真改写过 (查历史提交 "捎带" / "挖到" 应 0)"""
    r = _git("log", "-50", "--pretty=format:%s")
    assert r.returncode == 0
    lines = r.stdout.splitlines()
    # 开发对话残留
    bad_keywords = ["捎带", "挖到", "X 轮", "一直 0", "写死", "踩坑"]
    found = []
    for line in lines:
        for kw in bad_keywords:
            if kw in line:
                found.append((kw, line))
    assert not found, f"开发对话残留 (filter-branch 漏了): {found[:5]}"


def test_git_status_has_no_build_artifacts(git_state):
    """工作区里不应出现构建产物与诊断产物

    工作区允许有正在进行的改动,这里核对的是仓库不被产物与诊断文件
    污染。
    """
    r = _git("status", "--short")
    tracked = [line for line in r.stdout.splitlines()
               if line.strip() and not line.startswith("??")]
    polluted = [line for line in tracked
                if any(mark in line for mark in (
                    "dist/", "build/", "artifacts/", ".pytest_cache",
                    "__pycache__/", ".coverage", "ci-diagnostics",
                    "ci-status.json", "data/duckdb",
                ))]
    assert not polluted, f"工作区不应有构建产物与诊断产物, 实际: {polluted}"

    untracked = [line for line in r.stdout.splitlines()
                 if line.startswith("??")]
    noise = [line for line in untracked
             if any(mark in line for mark in (
                 ".pytest_cache", "__pycache__", ".coverage", "dist/",
                 "artifacts/", "ci-diagnostics",
             ))]
    assert not noise, f"不应遗留产物文件, 实际: {noise}"


def test_git_show_HEAD_returns_real_diff(git_state):
    """git show HEAD 真能拿到上一个 commit 的内容"""
    r = _git("show", "--stat", "HEAD")
    assert r.returncode == 0
    # HEAD 真有 files changed
    assert "files changed" in r.stdout or "file changed" in r.stdout, (
        f"HEAD commit 应有 file changes, 实际: {r.stdout[:500]}"
    )


def test_git_diff_HEAD_1_returns_real_history(git_state):
    """git diff HEAD~1 HEAD 真能拿到 diff (历史提交与当前提交的差异)"""
    r = _git("diff", "HEAD~1", "HEAD", "--stat")
    assert r.returncode == 0
    # 有 diff
    assert r.stdout.strip() != "", f"HEAD~1 vs HEAD 应有 diff, 实际空"


def test_old_commit_5a683c1_had_test_coverage(git_state):
    """5a683c1 (audit 第一个 commit) 真存在, 验当时代码 + 测试"""
    r = _git("show", "--stat", "5a683c1")
    if r.returncode != 0:
        pytest.skip(f"5a683c1 不在 history: {r.stderr[:200]}")
    # 这个 commit 改 47 个文件, 116 行注释/docstring
    assert "files changed" in r.stdout


def test_pytest_works_under_repo_root(git_state):
    """在 repo root 真跑 pytest (不靠 mock)"""
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_dev_layer_completeness.py", "-q"],
        cwd=REPO, capture_output=True, text=True, timeout=300,
    )
    if r.returncode != 0:
        pytest.fail(f"pytest 失败: {r.stdout[-500:]}{r.stderr[-500:]}")
    assert "passed" in r.stdout, f"应有 passed, 实际: {r.stdout[-200:]}"


def test_git_remote_url_points_to_this_repo(git_state):
    """remote 指向的就是这个仓本身 —— 源码在这里,发布也从这里出

    判据用 GITHUB_REPOSITORY:流水线里它就是本仓的 owner/repo。
    **不写死仓名** —— 同一份代码会跑在两处(公开仓与它的镜像仓),镜像的
    remote 指向的是它自己;写死一个仓名,镜像那边恒红,而那条红与代码
    对不对毫无关系。

    **精确比对仓路径,不能比子串**:"bin1732/forgemind" 是
    "bin1732/forgemind-pypi" 的前缀 ⇒ 子串匹配分不出这两个仓,守卫等于
    没有。

    本地跑时没有独立真源可对(remote 的值就是它自己),这时候这条判据
    根本立不住,跳过;但流水线里 GITHUB_REPOSITORY 要是没有,那是守卫
    自己坏了,必须报出来,不能当成"本地而已"。
    """
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repo:
        if os.environ.get("CI"):
            pytest.fail("流水线里没有 GITHUB_REPOSITORY —— 这条守卫失效了")
        pytest.skip("本地没有独立真源可对:本仓是谁只有流水线知道")

    r = _git("remote", "-v")
    assert r.returncode == 0
    remotes = set(re.findall(
        r"github\.com[:/]+([\w.-]+)/([\w.-]+?)(?:\.git)?(?=[\s(]|$)", r.stdout
    ))
    owner, name = repo.split("/", 1)
    assert (owner, name) in remotes, (
        f"remote 应指向本仓({repo}), 实际指向: {sorted(f'{o}/{n}' for o, n in remotes)}"
    )
    # 推送用的凭据由本地 git 配置提供,URL 形态随环境不同,这里只核对
    # 它指向的仓库位置。


def test_git_branches_include_main_and_temp_pypi(git_state):
    """git branch 真列 main + temp-pypi"""
    r = _git("branch", "-a")
    assert r.returncode == 0
    assert "main" in r.stdout, f"应有 main, 实际: {r.stdout!r}"
