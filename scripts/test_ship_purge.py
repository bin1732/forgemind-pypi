#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""验证发布流程里"清理旧构建目录"这段逻辑真的能删掉目录。

这里抽的是 ship.yml 里那段脚本的原文,不是抄一份 —— 抄的那份会跟真正
跑的代码分家,验证就成了摆设。抽出来之后只替换最底层的 urlopen,其余
(重试、列目录、算 sha、删)跑的都是工作流里的原码。

当初的岔子:清空目录里的文件之后,目录本身的 sha 变了,而代码还拿着
清空前那个旧 sha 去删目录,于是永远 404。旧构建目录就这么一个个留在
仓库里,而删除失败只被打印出来,发布照样报成功。

    python scripts/test_ship_purge.py
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import re
import sys
import textwrap
import urllib.error
import urllib.request

WORKFLOW = pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ship.yml"
WANTED = ("call", "list_dir", "remove_path", "purge_dir", "purge_builds", "keep_build", "build_num")


def extract_functions(text: str) -> str:
    """从工作流里抽出那几个函数的原文。"""
    chunks: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"(\s*)def (\w+)\(", lines[i])
        if m and m.group(2) in WANTED:
            indent = len(m.group(1))
            block = [lines[i]]
            i += 1
            while i < len(lines):
                line = lines[i]
                if line.strip() and (len(line) - len(line.lstrip())) <= indent:
                    break
                block.append(line)
                i += 1
            chunks.append("\n".join(block))
            continue
        i += 1
    missing = [name for name in WANTED if not any(f"def {name}(" in c for c in chunks)]
    if missing:
        raise SystemExit(f"工作流里找不到这些函数: {missing}")
    # 工作流里的代码带着 YAML 的缩进,取出来要先去掉
    return "\n\n".join(textwrap.dedent(c) for c in chunks)


class FakeRepo:
    """一个假的 contents API 仓库 —— 按真 API 的脾气建模。

    真 API 的几条硬规矩(对着真仓库一条条实测过,不是照文档猜的):
      * 删除必须带 sha,不带回 422 '"sha" wasn't supplied'
      * 删非空目录回 422 '"<path>" is not a file' —— contents API 删不了非空目录
      * sha 对不上(目录被清空后 sha 就变了)回 404 Not Found
      * git 里没有空目录:最后一个文件删掉,那个目录就没了

    早先这个假实现比真实现宽松(不带 sha 也放行),于是"清空之后还拿着
    旧 sha 去删目录"这种错在测试里是绿的,真跑时才炸 —— 而且炸在发布
    流程上。假实现必须比真实现严,不然它守不住任何东西。
    """

    def __init__(self) -> None:
        # 路径 -> ("dir" | "file", 内容)
        self.tree: dict[str, tuple[str, str]] = {}
        self.deleted: list[str] = []

    def _sha(self, path: str) -> str:
        """内容的 sha。目录的 sha 由里面的东西决定 —— 里面的文件删了,sha 就变了。"""
        entry = self.tree.get(path)
        if entry is not None and entry[0] == "file":
            return "sha-file-" + hashlib.sha256(entry[1].encode()).hexdigest()[:12]
        prefix = path.rstrip("/") + "/"
        children = sorted(
            k for k in self.tree if k.startswith(prefix) and "/" not in k[len(prefix) :]
        )
        if not children:
            return "sha-dir-empty-" + path
        digest = hashlib.sha256()
        for child in children:
            digest.update(child.encode())
            digest.update(self._sha(child).encode())
        return "sha-dir-" + digest.hexdigest()[:12]

    def _children(self, path: str) -> list[str]:
        prefix = path.rstrip("/") + "/"
        return sorted(k for k in self.tree if k.startswith(prefix) and "/" not in k[len(prefix) :])

    def _prune_empty_dirs(self, path: str) -> None:
        """删掉一个路径之后,把它上面已经空掉的目录也去掉(git 不存空目录)。"""
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        while parent and parent in self.tree:
            if self._children(parent):
                return
            del self.tree[parent]
            parent = parent.rsplit("/", 1)[0] if "/" in parent else ""

    def listing(self, path: str) -> list[dict]:
        prefix = path.rstrip("/") + "/"
        out = []
        for key in sorted(self.tree):
            if not key.startswith(prefix):
                continue
            rest = key[len(prefix) :]
            if "/" in rest:
                continue
            out.append(
                {
                    "name": rest,
                    "type": self.tree[key][0],
                    "sha": self._sha(key),
                }
            )
        return out

    def handle(self, method: str, path: str, payload: dict | None) -> tuple[int, object]:
        if method == "GET":
            entry = self.tree.get(path)
            if entry is not None and entry[0] == "file":
                return 200, {"type": "file", "sha": self._sha(path), "content": entry[1]}
            listing = self.listing(path)
            if listing:
                return 200, listing
            return 404, {"message": "Not Found"}
        if method == "PUT":
            self.tree[path] = ("file", base64.b64decode(payload["content"]).decode())
            return 200, {}
        if method == "DELETE":
            want = (payload or {}).get("sha")
            if not want:
                # 真 API:不带 sha 直接拒
                return 422, {"message": "Invalid request.\n\n\"sha\" wasn't supplied."}
            entry = self.tree.get(path)
            if entry is None:
                return 404, {"message": "Not Found"}
            if want != self._sha(path):
                # sha 对不上:目录被清空后 sha 就变了
                return 404, {"message": "Not Found"}
            if entry[0] == "dir":
                if self._children(path):
                    # 真 API:contents API 删不了非空目录
                    return 422, {"message": f"{path} is not a file"}
                del self.tree[path]
            else:
                del self.tree[path]
            self._prune_empty_dirs(path)
            self.deleted.append(path)
            return 200, {}
        return 405, {}


def make_fake_urlopen(repo: FakeRepo):
    """造一个假的 urlopen,只认 contents API。"""

    class _Response:
        def __init__(self, payload: object) -> None:
            self._payload = payload
            self.status = 200
            # 真实的 call 会看 content-type,决定把响应体当 JSON 解析还是当原文
            self.headers = {"content-type": "application/json"}

        def read(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(url, data=None, timeout=None, headers=None):
        # 真实的 call 传进来的是 Request 对象,方法和请求体都在它身上
        method = getattr(url, "method", "GET") or "GET"
        payload: dict | None = None
        body = data if data is not None else getattr(url, "data", None)
        if body:
            if isinstance(body, bytes):
                body = body.decode("utf-8")
            payload = json.loads(body)
        full_url = getattr(url, "full_url", str(url))
        path = full_url.split("/contents/", 1)[-1]
        status, body = repo.handle(method, path, payload)
        if status >= 400:
            raise urllib.error.HTTPError(str(url), status, str(body), None, None)  # type: ignore[arg-type]
        return _Response(body)

    return fake_urlopen


def main() -> int:
    text = WORKFLOW.read_text(encoding="utf-8")
    source = extract_functions(text)

    repo = FakeRepo()
    # 四个构建目录 + 一份清单。分别是:更旧的(该删)、线上索引正指向的
    # (不能删)、本次的(不能删)、编号更大的(并发发布留下的,不能删)。
    repo.tree["releases/builds/100"] = ("dir", "")
    repo.tree["releases/builds/100/a.whl"] = ("file", "wheel")
    repo.tree["releases/builds/111"] = ("dir", "")
    repo.tree["releases/builds/111/b.whl"] = ("file", "wheel")
    repo.tree["releases/builds/222"] = ("dir", "")
    repo.tree["releases/builds/222/c.whl"] = ("file", "wheel")
    repo.tree["releases/builds/333"] = ("dir", "")
    repo.tree["releases/builds/333/d.whl"] = ("file", "wheel")
    repo.tree["releases/builds/manifest.json"] = ("file", '{"build_id": "222"}')

    os.environ.setdefault("GITHUB_TOKEN", "fake-token")
    urllib.request.urlopen = make_fake_urlopen(repo)

    # 命名空间只放工作流里那段脚本自己 import 的东西 —— 少一个 import,
    # 这里的测试就会像真跑一样报错。
    #
    # time 换成不睡的:真脚本删失败时会退避重试(3+6+9+12 秒),
    # 测试里没必要真等那么久 —— 该红的地方一样红,只是快。
    class _FastTime:
        @staticmethod
        def sleep(_seconds: float) -> None:
            return None

    namespace: dict[str, object] = {
        "base64": base64,
        "hashlib": hashlib,
        "json": json,
        "pathlib": pathlib,
        "re": re,
        "sys": sys,
        "time": _FastTime,
        "urllib": urllib,
        "API": "https://api.github.com/repos/fake/fake",
        "TOKEN": "fake-token",
    }
    exec(compile(source, "ship.yml", "exec"), namespace)  # noqa: S102
    purge_builds = namespace["purge_builds"]
    build_num = namespace["build_num"]

    # 跑工作流自己的那个函数,而不是在这里重写一份调用点 ——
    # 重写的那份守不住调用点。清单就是在这儿被顺手删掉的:写清单的
    # 同一步骤把它当成旧文件清掉,来源提交绑定那条链就断了。
    build_id, live_id = "222", "111"
    namespace["build_id"] = build_id
    namespace["live_id"] = live_id
    namespace["my_num"] = build_num(build_id)
    purge_builds(build_id, live_id)

    problems: list[str] = []
    if "releases/builds/100" in repo.tree:
        problems.append("更旧的构建目录没有被删掉")
    if "releases/builds/100/a.whl" in repo.tree:
        problems.append("更旧的构建目录里的文件没有被删掉")
    if "releases/builds/111/b.whl" not in repo.tree:
        problems.append("线上索引正指向的构建被误删了")
    if "releases/builds/222/c.whl" not in repo.tree:
        problems.append("本次构建被误删了")
    if "releases/builds/333/d.whl" not in repo.tree:
        problems.append("编号更大的构建被误删了")
    if "releases/builds/manifest.json" not in repo.tree:
        problems.append("清单文件被清理掉了 —— 来源提交绑定会断")

    if problems:
        print("清理逻辑有问题:")
        for item in problems:
            print(" -", item)
        return 1
    print(f"清理逻辑正常: 删了 {len(repo.deleted)} 个路径,该留的都留着")
    return 0


if __name__ == "__main__":
    sys.exit(main())
