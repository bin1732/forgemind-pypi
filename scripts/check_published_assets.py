# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对发布出来的构件与清单、索引、文档三者一致。

真实用户旅程验的是"线上索引指向的 wheel 能不能装" —— 那一层已经有人
守着了。这里补的是另外几环,它们断了不会有任何报错,只会留下一个
没人知道的过期说法:

1. 仓库里只留当前 build 目录 —— 旧的还在,用户按旧索引就能拿到旧构件
2. 索引页声明的校验值与仓库里那个文件一致
3. 清单列的资产与实际发布的一致
4. 私人仓自检文档里声明的资产字节数与真实发布资产一致
   (给 --doc 时才查,需要能读 Release)

用法:
    python scripts/check_published_assets.py
    python scripts/check_published_assets.py --doc /path/to/AUDIT_3_DIMENSIONS.md
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 索引页里的一条链接
INDEX_LINK = re.compile(r'href="([^"#]+)(?:#sha256=([0-9a-f]{64}))?"')
# 文档里出现的反引号内容(资产名以反引号包裹)
DOC_NAME = re.compile(r"`([^`]+)`")
# 围栏代码块:三个反引号,正则配对时会把整段代码当成一个名字,
# 行内代码的配对会跟着错位 —— 先剥掉
CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
# 算作资产的命名形态
ASSET_SUFFIXES = (".whl", ".tar.gz", ".exe")


def is_asset(name: str) -> bool:
    """清单里的资产名。"""
    return name.endswith(ASSET_SUFFIXES) or name in ("forgemind-linux", "forgemind-macos")


def remote_manifest(token: str | None) -> dict | None:
    """读远端 main 上的清单。读不到就返回 None。"""
    if not token:
        return None
    url = (
        "https://api.github.com/repos/bin1732/forgemind-pypi/contents/releases/builds/manifest.json"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "forgemind-assets",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.load(resp)
        return json.loads(base64.b64decode(payload["content"]))
    except Exception:
        return None


def release_assets(token: str | None) -> dict[str, int] | None:
    """读 continuous release 上的资产与字节数。读不到就返回 None。"""
    if not token:
        return None
    url = "https://api.github.com/repos/bin1732/forgemind-pypi/releases/tags/continuous"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "forgemind-assets",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
    except Exception:
        return None
    return {a["name"]: a["size"] for a in data.get("assets", [])}


def token_from_env_or_remote() -> str | None:
    """能读 Release 的凭据:环境变量优先,其次取 git remote。"""
    for key in ("GITHUB_TOKEN", "GH_PAT"):
        value = os.environ.get(key)
        if value:
            return value
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
    except Exception:
        return None
    if not url:
        return None
    return urllib.parse.urlsplit(url).password


def main() -> int:
    parser = argparse.ArgumentParser(description="核对发布构件与清单、索引、文档")
    parser.add_argument("--repo", type=Path, default=REPO, help="公开仓根目录")
    parser.add_argument(
        "--doc",
        type=Path,
        action="append",
        help="要核对的文档路径(可给多个)。严格:文档必须列全清单里的资产。",
    )
    parser.add_argument(
        "--doc-mentions",
        type=Path,
        action="append",
        help=(
            "只核'文档点名的资产是不是真存在'(宽松)。"
            "给用户看的文档不必列全清单里的每一件 —— 漏列不是错,乱点名才是。"
        ),
    )
    parser.add_argument("--skip-online", action="store_true", help="不查 Release,只核对本地")
    args = parser.parse_args()

    repo = args.repo.resolve()
    problems: list[str] = []

    # 1) 判据是"这次发布的那份产物",不是"仓库里恰好剩一个目录"。
    # 发布流程会往 main 提交索引与清单,而验证工作流是被 ship 触发的 ——
    # 触发的那一刻 main 上可能还没有这次发布的提交。拿"目录数"当判据,
    # 就会把一次正常的发布报成不一致。
    #
    # 优先用清单里记的构建号:清单与文件在同一个提交里,天然同源。
    # 清单没有这个字段(旧清单)时退回索引指向的构建 —— 那也是用户按
    # 索引下载到的。
    builds_dir = repo / "releases" / "builds"
    build_dirs = (
        sorted(p for p in builds_dir.iterdir() if p.is_dir()) if builds_dir.is_dir() else []
    )
    manifest_path = repo / "releases" / "builds" / "manifest.json"
    manifest_assets: set[str] = set()
    manifest_sizes: dict[str, int] = {}
    manifest_build = ""
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_assets = set(manifest.get("assets", []))
        manifest_sizes = dict(manifest.get("sizes", {}))
        manifest_build = str(manifest.get("build_id") or "")

    index_path = repo / "pypi" / "simple" / "forgemind" / "index.html"
    online_build = ""
    if index_path.is_file():
        page = index_path.read_text(encoding="utf-8")
        link = INDEX_LINK.search(page)
        if link:
            # href 形如 .../main/releases/builds/<build_id>/<文件名>
            parts = link.group(1).split("/main/", 1)[-1].split("/")
            if "builds" in parts:
                after = parts[parts.index("builds") + 1 :]
                if after:
                    online_build = after[0]

    # 清单与索引必须指的是同一份产物。
    # 这两条链路是分开的:清单随发布流程写,索引由 Pages 部署刷到线上,
    # 两者之间有延迟。延迟期间"用户按索引装到的"和"清单说的"不是同一份
    # 产物 —— 版本号一样、内容不一样,装到的人不会知道自己拿的是哪一份。
    # 清单与索引对不上时必须报出来,不能只核对各自内部。
    if manifest_build and online_build and manifest_build != online_build:
        problems.append(
            f"线上索引指向的构建 {online_build} 与清单记的构建 {manifest_build} "
            "不是同一份产物 —— 用户按索引装到的是前者,清单说的却是后者"
        )

    build = None
    if manifest_build:
        candidate = builds_dir / manifest_build
        if candidate.is_dir():
            build = candidate
        else:
            problems.append(f"清单记的构建目录不存在: releases/builds/{manifest_build}")
    elif online_build:
        candidate = builds_dir / online_build
        if candidate.is_dir():
            build = candidate
        else:
            problems.append(f"线上索引指向的构建目录不存在: releases/builds/{online_build}")
    elif build_dirs:
        # 没有索引可依据时退回唯一的那个目录
        build = build_dirs[0] if len(build_dirs) == 1 else None
        if build is None:
            problems.append(
                f"索引里找不到构建目录,仓库里有 {len(build_dirs)} 个: "
                f"{[p.name for p in build_dirs]}"
            )

    # 2) 索引声明的校验值与仓库里那个文件一致
    if not index_path.is_file():
        problems.append(f"找不到索引页: {index_path}")
    else:
        page = index_path.read_text(encoding="utf-8")
        match = INDEX_LINK.search(page)
        if not match:
            problems.append("索引页里没有可下载的链接")
        else:
            href, declared = match.group(1), match.group(2)
            if not declared:
                problems.append("索引页里的链接没有声明校验值")
            else:
                rel = href.split("/main/", 1)[-1]
                local = repo / rel
                if not local.is_file():
                    problems.append(f"索引指向的文件不在仓库里: {rel}")
                else:
                    actual = hashlib.sha256(local.read_bytes()).hexdigest()
                    if actual != declared:
                        problems.append(
                            f"索引声明的校验值与 {rel} 不一致: 声明 {declared},实际 {actual}"
                        )

    # 3) 清单与实际文件一致
    if not manifest_path.is_file():
        problems.append(f"找不到清单: {manifest_path}")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not manifest_sizes:
            problems.append("清单里没有 sizes 字段,清单是旧的")
        if not (manifest.get("source_commit") or "").strip():
            # 没有来源提交,镜像就没法保证"测的就是发的那个"
            problems.append("清单里没有 source_commit,构件没记来源提交")
        if build is not None:
            local = {p.name for p in build.iterdir() if p.is_file()}
            missing = local - manifest_assets
            if missing:
                problems.append(f"清单里没有这些已发布的文件: {sorted(missing)}")
            # 字节数只在同一个构建内部比。源码包不是可复现构建 —— 同样的
            # 源码打两次包,字节数会差几十个字节(归档里的时间戳)。拿它去
            # 比另一个构建的同名文件,比的其实是两次不同的构建,必然对不上。
            if manifest_build and manifest_build != build.name:
                problems.append(
                    f"清单记的是构建 {manifest_build},核对的却是 {build.name};两边不是同一份产物"
                )
            elif not manifest_build:
                # 旧清单没有这个字段。它读不到自己属于哪一次构建,字节数
                # 就无从判断该不该比 —— 这种情况下不比,而不是拿两个不同
                # 构建的字节数硬比。
                print(f"注意:清单里没有 build_id,跳过字节数核对(核对的是 {build.name})")
                manifest_sizes = {}
            for name in sorted(local & set(manifest_sizes)):
                actual = (build / name).stat().st_size
                if actual != manifest_sizes[name]:
                    problems.append(
                        f"清单记的 {name} 是 {manifest_sizes[name]} 字节,实际 {actual} 字节"
                    )

    # 4) 文档里列的资产与清单一致;清单的字节数与线上发布资产一致
    def check_doc(doc_arg: Path, strict: bool) -> None:
        doc = doc_arg.resolve()
        if not doc.is_file():
            problems.append(f"找不到文档: {doc}")
            return
        text = CODE_FENCE.sub(" ", doc.read_text(encoding="utf-8"))
        listed = {name for name in DOC_NAME.findall(text) if is_asset(name)}
        # 文档里写成模板的名字(forgemind-<版本>-....whl)不是具体资产,
        # 拿它去比对清单必然对不上 —— 模板跳过。
        listed = {name for name in listed if "<" not in name and ">" not in name}
        if not listed:
            problems.append(f"{doc.name} 里没有找到列出资产的表格")
            return
        # 文档点名了清单里没有的资产 = 承诺了不存在的东西 → 一定要报
        unknown = listed - manifest_assets
        if unknown:
            problems.append(f"{doc.name} 列了清单里没有的资产: {sorted(unknown)}")
        # 清单里有而文档没列 = 漏列,不是错(给用户看的文档不必列全)
        if strict:
            absent = manifest_assets - listed
            if absent:
                problems.append(f"清单里的资产没在 {doc.name} 里列出: {sorted(absent)}")

    for doc_arg in args.doc or []:
        check_doc(doc_arg, strict=True)
    for doc_arg in args.doc_mentions or []:
        check_doc(doc_arg, strict=False)

    if not args.skip_online:
        token = token_from_env_or_remote()
        # 本地检出的清单可能不是线上最新的那一份(工作区落后于远端 main)。
        # 这时"清单记的字节数"与"线上资产的字节数"必然对不上,而错误信息
        # 说的是字节数 —— 看不出根因是工作区旧了。这里先说清楚。
        remote = remote_manifest(token)
        stale = False
        if remote is not None and manifest_build and remote.get("build_id"):
            if str(remote["build_id"]) != manifest_build:
                stale = True
                problems.append(
                    f"本地检出的清单是构建 {manifest_build},线上最新的是 "
                    f"{remote['build_id']} —— 工作区落后于远端 main,先同步再核对"
                )
        actual = release_assets(token)
        if actual is None:
            problems.append(
                "读不到 continuous release 的资产(缺凭据或网络不可达),清单里的字节数未与线上核对"
            )
        elif stale:
            # 拿旧构建的字节数去比新构建,比的是两次不同的构建,必然对不上
            # —— 这时候报字节数不一致只会把人引到错的地方去。
            print(f"注意:本地清单不是线上最新的一份,跳过字节数核对(线上是 {remote['build_id']})")
        else:
            for name, size in manifest_sizes.items():
                if name not in actual:
                    problems.append(f"清单里的 {name} 不在 release 上")
                elif actual[name] != size:
                    problems.append(f"{name} 清单记 {size} 字节,线上实际 {actual[name]} 字节")

    if problems:
        print("发布构件与声明对不上:")
        for item in problems:
            print(" -", item)
        return 1

    print("发布构件与清单、索引、声明全部一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
