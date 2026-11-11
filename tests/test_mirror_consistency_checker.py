# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""镜像一致性检查器:两边分家了必须报出来。

镜像最危险的地方在于"看起来还是镜像":一边改了、另一边没同步,于是
那个词还在,内容已经不同了。靠人记得同步靠不住。

这里用合成的上游树与临时的本地仓,把四种情形各钉一个方向:
完全一致 / 上游有本地没有 / 内容不同 / 本仓多出不在名单里的文件。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_mirror_consistency as mirror  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


def _make_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    for name, content in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "x")
    return repo


def _upstream(files: dict[str, str], sha: str = "abc") -> tuple[str, dict[str, str]]:
    return sha, files


def _run(
    monkeypatch,
    repo: Path,
    upstream: dict[str, str],
    allow_prefix=(),
    allow_file=(),
    include_build_artifacts=False,
):
    import argparse

    monkeypatch.setattr(mirror, "upstream_tree", lambda repo_, ref: _upstream(upstream))
    argv = ["check_mirror_consistency.py", "--upstream", "o/r", "--repo", str(repo)]
    # 没有值时别把这个选项放进去 —— argparse 会说"缺个参数"就退出
    for pfx in allow_prefix:
        argv += ["--allow-prefix", pfx]
    for f in allow_file:
        argv += ["--allow-file", f]
    if include_build_artifacts:
        argv += ["--include-build-artifacts"]
    monkeypatch.setattr(sys, "argv", argv)
    return mirror.main()


def _blob_of(repo: Path, name: str) -> str:
    return _git(repo, "rev-parse", f"HEAD:{name}").strip()


class TestMirrorConsistency:
    def test_identical_passes(self, tmp_path, monkeypatch, capsys):
        repo = _make_repo(tmp_path, {"a.py": "x\n", "b/c.txt": "y\n"})
        up = {"a.py": _blob_of(repo, "a.py"), "b/c.txt": _blob_of(repo, "b/c.txt")}
        assert _run(monkeypatch, repo, up) == 0, capsys.readouterr().out
        assert "逐文件一致" in capsys.readouterr().out

    def test_missing_file_is_reported(self, tmp_path, monkeypatch, capsys):
        repo = _make_repo(tmp_path, {"a.py": "x\n"})
        up = {"a.py": _blob_of(repo, "a.py"), "b.py": "0" * 40}
        assert _run(monkeypatch, repo, up) == 1
        assert "缺" in capsys.readouterr().out

    def test_different_content_is_reported(self, tmp_path, monkeypatch, capsys):
        repo = _make_repo(tmp_path, {"a.py": "x\n"})
        up = {"a.py": "0" * 40}
        assert _run(monkeypatch, repo, up) == 1
        out = capsys.readouterr().out
        assert "内容不同" in out, out

    def test_extra_file_not_allowed_is_reported(self, tmp_path, monkeypatch, capsys):
        repo = _make_repo(tmp_path, {"a.py": "x\n", "docs/audit.md": "d\n"})
        up = {"a.py": _blob_of(repo, "a.py")}
        assert _run(monkeypatch, repo, up) == 1
        assert "上游没有" in capsys.readouterr().out

    def test_extra_file_allowed_passes(self, tmp_path, monkeypatch, capsys):
        repo = _make_repo(tmp_path, {"a.py": "x\n", "docs/audit.md": "d\n"})
        up = {"a.py": _blob_of(repo, "a.py")}
        assert _run(monkeypatch, repo, up, allow_prefix=["docs/"]) == 0
        assert "逐文件一致" in capsys.readouterr().out

    # 发布产物这一类:公开仓每发一次版就落两个提交(发布、清理),动的
    # 是产物不是源码。拿产物逐文件比,镜像仓这边永远对不上,而源码其实
    # 一模一样 —— 那是假红,而且是最坏的一种:报出来的话看着像源码分家。
    def test_build_artifacts_are_ignored_by_default(self, tmp_path, monkeypatch, capsys):
        repo = _make_repo(tmp_path, {"a.py": "x\n"})
        up = {
            "a.py": _blob_of(repo, "a.py"),
            # 上游有、本仓没有(上游刚清理掉)
            "releases/builds/42/forgemind-x.whl": "0" * 40,
            "pypi/simple/forgemind/index.html": "1" * 40,
        }
        assert _run(monkeypatch, repo, up) == 0, capsys.readouterr().out
        out = capsys.readouterr().out
        assert "逐文件一致" in out, out
        # 忽略了多少个要写清楚 —— 不然"一致"这两个字看着像什么都没比
        assert "不参与比对的 2 个" in out, out

    def test_extra_build_artifact_in_local_is_ignored(self, tmp_path, monkeypatch, capsys):
        # 反方向:本仓还留着上游已经清掉的产物
        repo = _make_repo(tmp_path, {"a.py": "x\n", "releases/builds/42/x.whl": "w\n"})
        up = {"a.py": _blob_of(repo, "a.py")}
        assert _run(monkeypatch, repo, up) == 0, capsys.readouterr().out
        assert "上游没有" not in capsys.readouterr().out

    def test_build_artifacts_can_be_compared_on_demand(self, tmp_path, monkeypatch, capsys):
        # 真要比的时候也有路走:显式说一声,产物就回到比对范围里
        repo = _make_repo(tmp_path, {"a.py": "x\n"})
        up = {"a.py": _blob_of(repo, "a.py"), "releases/builds/42/x.whl": "0" * 40}
        assert _run(monkeypatch, repo, up, include_build_artifacts=True) == 1
        assert "缺" in capsys.readouterr().out


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
