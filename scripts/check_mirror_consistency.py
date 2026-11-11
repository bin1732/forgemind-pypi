#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""检查本仓是否与上游仓库逐文件一致。

一个仓库做镜像(同一个项目的两份拷贝)时,最容易出的事是**两份悄悄分家**:
一边改了、另一边没同步,于是"镜像"这个词还在,内容已经不同了。靠人记得
同步,靠不住。

这个检查把两边按内容比:
- 上游每个文件,本仓都要有,而且**内容一模一样**(比的是 git 的 blob
  校验值,不是文件名)。
- 本仓多出来的文件,必须在允许名单里(内部审计文档这类只属于本仓的
  内容)。
- 发布产物(``releases/`` 与 ``pypi/``)默认不参与比对 —— 公开仓每次
  发布都动它们,而源码没动。默认名单写在检查器里,靠调用方记得传参
  迟早会漏一次,漏了那次就是一次"看起来像源码分家"的假红。
- 顺带报出比的是上游的哪个提交 —— 出了分歧能立刻知道该同步哪一版。

用法:
    python scripts/check_mirror_consistency.py --upstream owner/repo [--ref main]
                                                  [--allow-prefix docs/]
                                                  [--allow-file scripts/x.py]

不需要凭据:上游是公开仓时匿名就能读。设了 GITHUB_TOKEN 就用它(提高限额)。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

API = "https://api.github.com"

# 默认不参与比对的路径:发布流程的产物。
#
# 公开仓每发一次版就往 main 上落两个提交(发布、清理),落的是构建产物
# 与索引 —— 它们每次都变,而源码一个字没变。拿它们逐文件比,镜像仓这边
# 永远对不上,而源码其实一模一样。
#
# 这份名单写在检查器里,而不是靠调用方记得传参:靠人记得传,迟早有一次
# 忘,那一次就是一次假红 —— 而且是那种最坏的假红:报出来的话看着像
# "源码分家了",会让人去查根本不存在的分家。
DEFAULT_IGNORE_PREFIXES = ("releases/", "pypi/")


def _fetch(url: str) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "mirror-check"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def upstream_tree(repo: str, ref: str) -> tuple[str, dict[str, str]]:
    """取上游某个提交下的全部文件:路径 → blob sha。返回 (提交, 映射)。"""
    commit = _fetch(f"{API}/repos/{repo}/commits/{ref}")
    sha = commit["sha"]
    tree = _fetch(f"{API}/repos/{repo}/git/trees/{sha}?recursive=1")
    files: dict[str, str] = {}
    for entry in tree.get("tree", []):
        if entry.get("type") != "blob":
            continue
        files[entry["path"]] = entry["sha"]
    return sha, files


def local_files(repo_root: Path) -> dict[str, str]:
    """本仓受版本控制的文件:路径 → blob sha。"""
    out = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-s"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    files: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split(maxsplit=3)
        if len(parts) < 4:
            continue
        mode, sha, path = parts[0], parts[1], parts[3]
        if mode == "160000":  # 子模块
            continue
        files[path] = sha
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description="核对本仓与上游仓库是否逐文件一致")
    ap.add_argument("--upstream", required=True, help="上游仓库,owner/repo")
    ap.add_argument("--ref", default="main", help="上游的分支或提交(默认 main)")
    ap.add_argument(
        "--allow-prefix", action="append", default=[], help="允许本仓多出来的路径前缀(可重复)"
    )
    ap.add_argument(
        "--allow-file", action="append", default=[], help="允许本仓多出来的单个文件(可重复)"
    )
    ap.add_argument(
        "--ignore-prefix",
        action="append",
        default=[],
        help="不参与比对的路径前缀(可重复,可叠加在默认名单上)。构建产物"
        "用它 —— 公开仓每发一次版就落两个提交(发布、清理),拿 main 逐文件"
        "比,镜像仓这边永远对不上,而源码其实一模一样",
    )
    ap.add_argument(
        "--include-build-artifacts",
        action="store_true",
        help="把发布产物(默认忽略的 releases/ 与 pypi/)也算进比对",
    )
    ap.add_argument("--repo", default=".", help="本仓目录(默认当前目录)")
    args = ap.parse_args()

    ignore_prefixes = list(DEFAULT_IGNORE_PREFIXES) if not args.include_build_artifacts else []
    ignore_prefixes += args.ignore_prefix

    repo_root = Path(args.repo).resolve()
    try:
        sha, up = upstream_tree(args.upstream, args.ref)
    except Exception as exc:  # noqa: BLE001 — 取不到上游就说清,别静默
        print(f"取不到上游 {args.upstream}@{args.ref}: {exc}", file=sys.stderr)
        return 2

    local = local_files(repo_root)

    def ignored(path: str) -> bool:
        return any(path.startswith(p) for p in ignore_prefixes)

    def allowed(path: str) -> bool:
        return path in args.allow_file or any(path.startswith(p) for p in args.allow_prefix)

    missing = sorted(p for p in up if p not in local and not ignored(p))
    differing = sorted(p for p in up if p in local and local[p] != up[p] and not ignored(p))
    extra = sorted(p for p in local if p not in up and not allowed(p) and not ignored(p))

    if missing or differing or extra:
        print(f"本仓与上游 {args.upstream}@{sha[:12]} 不一致:")
        if missing:
            print(f"  缺 {len(missing)} 个文件(上游有、本仓没有):")
            for p in missing[:20]:
                print(f"    - {p}")
            if len(missing) > 20:
                print(f"    … 还有 {len(missing) - 20} 个")
        if differing:
            print(f"  {len(differing)} 个文件内容不同:")
            for p in differing[:20]:
                print(f"    - {p}")
            if len(differing) > 20:
                print(f"    … 还有 {len(differing) - 20} 个")
        if extra:
            print(f"  {len(extra)} 个文件上游没有(不在允许名单里):")
            for p in extra[:20]:
                print(f"    - {p}")
            if len(extra) > 20:
                print(f"    … 还有 {len(extra) - 20} 个")
        return 1

    print(
        f"本仓与上游 {args.upstream}@{sha[:12]} 逐文件一致"
        f"({len(local)} 个受版本控制的文件;允许名单外的额外文件 0 个;"
        f"不参与比对的 {sum(1 for p in set(up) | set(local) if ignored(p))} 个,"
        f"忽略前缀 {', '.join(ignore_prefixes) or '无'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
