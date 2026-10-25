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
import time
import urllib.error
import urllib.request

WORKFLOW = pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ship.yml"
WANTED = ("call", "list_dir", "remove_path", "purge_dir")


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
    """一个假的 contents API 仓库。

    目录的 sha 由它里面的东西决定 —— 里面的文件删掉了,sha 就变了。
    这正是真仓库的脾气,也是当初那个 bug 的根因:清空之后还拿着旧 sha
    去删目录,只会得到 404。
    """

    def __init__(self) -> None:
        # 路径 -> ("dir" | "file", 内容)
        self.tree: dict[str, tuple[str, str]] = {}
        self.deleted: list[str] = []

    def _sha(self, path: str) -> str:
        prefix = path + "/"
        children = sorted(k for k in self.tree if k.startswith(prefix))
        if children:
            return "sha-dir-" + path + "-" + str(len(children))
        return f"sha-{path}"

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
            if path not in self.tree:
                return 404, {"message": "Not Found"}
            want = (payload or {}).get("sha")
            if want and want != self._sha(path):
                return 409, {"message": "sha mismatch"}
            prefix = path + "/"
            for key in [k for k in self.tree if k.startswith(prefix)]:
                del self.tree[key]
            del self.tree[path]
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
    repo.tree["releases/builds/111"] = ("dir", "")
    repo.tree["releases/builds/111/a.whl"] = ("file", "wheel")
    repo.tree["releases/builds/111/b.tar.gz"] = ("file", "sdist")
    repo.tree["releases/builds/222"] = ("dir", "")
    repo.tree["releases/builds/222/c.whl"] = ("file", "wheel")

    os.environ.setdefault("GITHUB_TOKEN", "fake-token")
    urllib.request.urlopen = make_fake_urlopen(repo)

    # 命名空间只放工作流里那段脚本自己 import 的东西 —— 少一个 import,
    # 这里的测试就会像真跑一样报错。
    namespace: dict[str, object] = {
        "base64": base64,
        "hashlib": hashlib,
        "json": json,
        "pathlib": pathlib,
        "re": re,
        "sys": sys,
        "time": time,
        "urllib": urllib,
        "API": "https://api.github.com/repos/fake/fake",
        "TOKEN": "fake-token",
    }
    exec(compile(source, "ship.yml", "exec"), namespace)  # noqa: S102
    purge_dir = namespace["purge_dir"]

    purge_dir("releases/builds", keep_prefix="releases/builds/222")

    problems: list[str] = []
    if "releases/builds/111" in repo.tree:
        problems.append("旧构建目录没有被删掉")
    if "releases/builds/111/a.whl" in repo.tree:
        problems.append("旧构建目录里的文件没有被删掉")
    if "releases/builds/222/c.whl" not in repo.tree:
        problems.append("保留的构建目录被误删了")

    if problems:
        print("清理逻辑有问题:")
        for item in problems:
            print(" -", item)
        return 1
    print(f"清理逻辑正常: 删了 {len(repo.deleted)} 个路径,保留目录完好")
    return 0


if __name__ == "__main__":
    sys.exit(main())
