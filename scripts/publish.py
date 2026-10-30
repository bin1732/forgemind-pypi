#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""把这次构建发布出去:Release 资产、仓库里的构件、索引与清单。

**一次发布只往 main 上落两个提交**:一个是构件 + 索引 + 清单,一个是清理
旧构建。

为什么不能一个文件一个提交:GitHub Pages 的部署按提交触发,而同一个站点
同时只能有一个部署在进行。一次发布落七八个提交,部署队列就排起来,线上
索引要几十分钟才切过去。这段时间里"用户按索引装到的"和"清单说的"不是
同一份产物 —— 版本号一样、内容不一样,装到的人不会知道自己拿的是哪一份。

所以这里的写入走 git-data API:一次树、一次提交。contents API 做不到 ——
它一个文件一个提交。

用法:
    python scripts/publish.py --build-id <id> --source-commit <sha> \
        [--artifacts artifacts] [--repo bin1732/forgemind-pypi] [--branch main]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import quote

DEFAULT_API = "https://api.github.com/repos/bin1732/forgemind-pypi"
LIVE_INDEX = "https://bin1732.github.io/forgemind-pypi/pypi/simple/forgemind/"


def call(method: str, url: str, data=None, headers=None, retries: int = 4):
    """发一次 API 请求。返回 (状态码, 响应)。"""
    token = os.environ.get("GITHUB_TOKEN", "")
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    if headers:
        h.update(headers)
    body = data if isinstance(data, bytes) else (json.dumps(data).encode() if data else None)
    if isinstance(data, dict):
        h["Content-Type"] = "application/json"
    for i in range(retries):
        req = urllib.request.Request(url, data=body, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                raw = r.read()
                ctype = r.headers.get("content-type", "")
                return r.status, (
                    json.loads(raw) if raw and ctype.startswith("application/json") else raw
                )
        except urllib.error.HTTPError as e:
            if e.code in (404, 422):
                return e.code, None
            time.sleep(2 * (i + 1))
        except Exception:
            time.sleep(2 * (i + 1))
    return 0, None


def git_write(api: str, branch: str, entries, message: str):
    """一次提交写入或删除多个路径。

    entries 是 [(路径, 内容)] 的列表:内容是 bytes 表示写入,None 表示删除。

    返回 (状态码, 提交号)。状态码 0 表示重试后仍失败。
    """
    for attempt in range(4):
        st, ref = call("GET", f"{api}/git/ref/heads/{branch}")
        if st != 200 or not ref:
            time.sleep(3 * (attempt + 1))
            continue
        base_commit = ref["object"]["sha"]
        st, commit = call("GET", f"{api}/git/commits/{base_commit}")
        if st != 200 or not commit:
            time.sleep(3 * (attempt + 1))
            continue
        tree_entries = []
        ok = True
        for path, content in entries:
            if content is None:
                # sha 为 null 即删除这条路径
                tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
                continue
            st, blob = call(
                "POST",
                f"{api}/git/blobs",
                {"content": base64.b64encode(content).decode(), "encoding": "base64"},
            )
            if st not in (200, 201) or not blob:
                ok = False
                break
            tree_entries.append(
                {"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]}
            )
        if not ok:
            time.sleep(3 * (attempt + 1))
            continue
        st, tree = call(
            "POST",
            f"{api}/git/trees",
            {"base_tree": commit["tree"]["sha"], "tree": tree_entries},
        )
        if st not in (200, 201) or not tree:
            time.sleep(3 * (attempt + 1))
            continue
        st, new_commit = call(
            "POST",
            f"{api}/git/commits",
            {"message": message, "tree": tree["sha"], "parents": [base_commit]},
        )
        if st not in (200, 201) or not new_commit:
            time.sleep(3 * (attempt + 1))
            continue
        st, _ = call(
            "PATCH",
            f"{api}/git/refs/heads/{branch}",
            {"sha": new_commit["sha"], "force": False},
        )
        if st in (200, 201):
            return st, new_commit["sha"]
        # 422 说明有人同时推了 main —— 重来一遍,基于新的树重做
        time.sleep(3 * (attempt + 1))
    return 0, None


def index_html(sha256: str, filename: str, build_id: str) -> bytes:
    """索引页。声明的校验值必须与文件内容一致。"""
    return (
        "<!DOCTYPE html>\n<html>\n  <body>\n    <a href=\"https://raw.githubusercontent.com/"
        f"bin1732/forgemind-pypi/main/releases/builds/{build_id}/{filename}#sha256={sha256}\">"
        f"{filename}</a><br/>\n  </body>\n</html>\n"
    ).encode()


def live_build_id(timeout: int = 30) -> str:
    """线上索引当前指向的构建号。取不到就返回空串。"""
    try:
        with urllib.request.urlopen(LIVE_INDEX, timeout=timeout) as r:
            body = r.read().decode("utf-8", "ignore")
    except Exception:
        return ""
    marker = "builds/"
    if marker in body:
        return body.split(marker, 1)[1].split("/", 1)[0]
    return ""


def build_num(name: str) -> int:
    try:
        return int(name)
    except (TypeError, ValueError):
        return -1


def keep_build(name: str, build_id: str, live_id: str) -> bool:
    """这个构建目录要不要留下。"""
    if name == build_id or name == live_id:
        return True
    # 比本次更新的构建:多半是并发发布留下的,不能删
    my_num = build_num(build_id)
    return my_num >= 0 and build_num(name) >= my_num


def plan_purge(
    tree: dict, root: str, keep_prefix="", keep_names=(), keep_predicate=None
) -> list[str]:
    """算出要删的文件路径。

    tree 是 {目录路径: [(名字, 类型)]};只删文件,不删目录 —— git 里没有空
    目录,文件删光目录自然就没了。

    这是纯函数:判据都在这里,测试直接跑它,调用点自己重写一份的测试守不住
    调用点。
    """
    doomed: list[str] = []

    def walk(path: str):
        for name, kind in tree.get(path, []):
            full = f"{path}/{name}" if path else name
            if keep_prefix and full.startswith(keep_prefix):
                continue
            if name in keep_names:
                continue
            if keep_predicate is not None and keep_predicate(name):
                continue
            if kind == "dir":
                walk(full)
            else:
                doomed.append(full)

    walk(root)
    return doomed


def collect_tree(api: str, root: str) -> dict:
    """递归列出目录内容 → {目录路径: [(名字, 类型)]}。"""
    tree: dict[str, list] = {}

    def list_dir(path: str):
        st, data = call("GET", f"{api}/contents/{path}")
        return data if st == 200 and isinstance(data, list) else []

    def walk(path: str):
        entries = list_dir(path)
        tree[path] = [(e.get("name", ""), e.get("type", "")) for e in entries]
        for name, kind in tree[path]:
            if kind == "dir":
                walk(f"{path}/{name}" if path else name)

    walk(root)
    return tree


def main() -> int:
    parser = argparse.ArgumentParser(description="把这次构建发布出去")
    parser.add_argument("--api", default=DEFAULT_API, help="仓库 API 地址")
    parser.add_argument("--branch", default="main", help="写哪个分支")
    parser.add_argument("--build-id", required=True, help="本次构建的编号")
    parser.add_argument("--source-commit", required=True, help="本次构建的来源提交")
    parser.add_argument("--artifacts", default="artifacts", help="构件目录")
    parser.add_argument("--live-index", default=LIVE_INDEX, help="线上索引地址")
    args = parser.parse_args()

    api = args.api
    build_id = args.build_id
    art_dir = pathlib.Path(args.artifacts)

    # 1) Release 资产:先删同名资产再上传(Releases API 不允许覆盖)
    st, rel = call("GET", f"{api}/releases/tags/continuous")
    if st != 200 or not rel:
        st, rel = call(
            "POST",
            f"{api}/releases",
            {
                "tag_name": "continuous",
                "name": "Continuous Builds",
                "body": "Auto-built from private source.",
                "prerelease": True,
            },
        )
    print(f"release id={rel.get('id')}")
    for a in rel.get("assets", []):
        code, _ = call("DELETE", a["url"])
        print(f"  [del {code}] {a['name']}")
        time.sleep(1)

    uploaded: list[str] = []
    asset_sizes: dict[str, int] = {}
    for f in sorted(art_dir.rglob("*")):
        if not f.is_file() or f.name == "manifest.json":
            continue
        name, size = f.name, f.stat().st_size
        # 资产上传必须走 uploads.github.com,不是 api.github.com
        upload_url = rel["upload_url"].replace("{?name,label}", "")
        code, _ = call(
            "POST",
            f"{upload_url}?name={quote(name)}",
            data=f.read_bytes(),
            headers={"Content-Type": "application/octet-stream"},
        )
        print(f"  [asset {code}] {name} ({size // 1024 // 1024}MB)")
        if code in (200, 201):
            uploaded.append(name)
            asset_sizes[name] = size

    # 2) 仓库里的构件 + 索引 + 清单:**一个提交**。
    #
    # 每次构建写到带 build 标识的新路径,再让索引指向它 —— 旧路径仍在,
    # 旧索引仍然有效,切换过程中不会出现 404。
    #
    # 三样东西在同一个提交里落地:索引声明的校验值、它指向的文件、清单记的
    # 字节数,三者天生一致,不会出现"索引指向了还没落地的文件"。
    entries: list[tuple[str, bytes | None]] = []
    wheel_sha = ""
    wheel_name = ""
    for f in sorted(art_dir.rglob("*")):
        if not f.is_file() or f.suffix not in (".whl", ".gz"):
            continue
        blob = f.read_bytes()
        entries.append((f"releases/builds/{build_id}/{f.name}", blob))
        if f.suffix == ".whl":
            wheel_sha = hashlib.sha256(blob).hexdigest()
            wheel_name = f.name
    if not wheel_sha:
        print("没有找到 wheel,索引无从指向", file=sys.stderr)
        return 1
    entries.append(
        ("pypi/simple/forgemind/index.html", index_html(wheel_sha, wheel_name, build_id))
    )

    # 清单写在产物上传之后(它记的是这次上传的字节数),与构件、索引同属
    # 一个提交。
    manifest = {
        "version": "latest",
        "assets": sorted(uploaded),
        "sizes": {k: asset_sizes[k] for k in sorted(asset_sizes)},
        # 记下这次构建的编号。验证工作流要靠它确认"清单说的"与"线上索引
        # 指向的"是同一份产物 —— 两者不是同一份时,清单里的字节数与文件
        # 对不上是必然的,而不是出了错。
        "build_id": build_id,
        "source_repo": "bin1732/forgemind",
        "source_commit": args.source_commit,
        "install": (
            "pip install --extra-index-url "
            "https://bin1732.github.io/forgemind-pypi/pypi/simple/ forgemind"
        ),
    }
    entries.append(("releases/builds/manifest.json", json.dumps(manifest, indent=2).encode()))

    st, commit_sha = git_write(api, args.branch, entries, f"Publish build {build_id}")
    if st not in (200, 201):
        print(f"写构件与索引失败 (status={st})", file=sys.stderr)
        return 1
    print(f"  [ok] 构件 + 索引 + 清单 → {commit_sha[:12]}")

    # 3) 等线上索引指向本次构建,再清理历史构建目录
    # GitHub Pages 部署新索引有延迟:这段时间里线上索引还指着上一个构建。
    # 立刻把上一个构建删掉,用户按线上索引下载就会拿到 404。
    deadline = time.time() + 600
    while time.time() < deadline:
        if live_build_id() == build_id:
            print(f"  线上索引已指向 {build_id}")
            break
        time.sleep(10)
    else:
        print(f"  线上索引未在时限内指向 {build_id},仍按计划清理旧构建")

    # 4) 清理历史构建目录 —— 也是一个提交。
    #
    # 只保留当前 build 目录;更早的 build 目录全部删除,避免仓库随每次
    # 运行无限增长,也避免 simple index 指向的文件被误删。
    #
    # 有四样东西不能删:
    #   本次构建         —— 刚写完的那份
    #   线上索引指向的   —— 删了用户按索引下载就是 404
    #   编号更大的构建   —— 并发发布时别的作业刚写好的
    #   清单文件本身     —— manifest.json 是"发了什么、从哪个提交来"的
    #                        机器可读真源。少了它,验证工作流就找不到这次
    #                        发布的来源提交,整条"测的就是发的"链就断掉。
    live_id = live_build_id()
    print(f"  保留构建目录: 本次 {build_id} / 线上索引指向 {live_id or '(未知)'}")

    keep = {"manifest.json"}
    if live_id:
        keep.add(live_id)
    tree = collect_tree(api, "releases/builds")
    doomed = plan_purge(
        tree,
        "releases/builds",
        keep_prefix=f"releases/builds/{build_id}",
        keep_names=keep,
        keep_predicate=lambda name: keep_build(name, build_id, live_id),
    )
    # 早期流程使用的固定路径,当前流程不再写入,一并清理
    tree2 = collect_tree(api, "releases/source")
    doomed += plan_purge(tree2, "releases/source")
    tree3 = collect_tree(api, "pypi/simple/forgemind")
    doomed += plan_purge(
        tree3,
        "pypi/simple/forgemind",
        keep_prefix="pypi/simple/forgemind/index.html",
    )

    if doomed:
        st, commit_sha = git_write(
            api, args.branch, [(p, None) for p in doomed], f"Remove stale builds ({build_id})"
        )
        if st not in (200, 201):
            # 删除失败不能只打印:旧构件就会留在仓库里,而发布仍然报成功 ——
            # 下一轮对账才发现,那时候线上索引可能已经指向了残留文件。
            print(f"  [rm {st}] 清理旧构建失败", file=sys.stderr)
            return 1
        print(f"  [ok] 清理 {len(doomed)} 个旧文件 → {commit_sha[:12]}")
    else:
        print("  没有需要清理的旧构建")

    return 0


if __name__ == "__main__":
    sys.exit(main())
