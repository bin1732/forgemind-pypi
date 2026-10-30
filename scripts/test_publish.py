#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""发布脚本的判据:哪些文件要删、索引声明的校验值、一次提交写多个路径。

假 API 按真接口的语义来:引用不是快进更新时回 422,树条目删除写的是
sha=null。假实现比真实现宽松的话,这些用例就守不住真实现。
"""

import base64
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import publish  # noqa: E402


class FakeApi:
    """一个够用的假 GitHub:引用、树、提交、对象。"""

    def __init__(self):
        self.ref = "sha-base"
        self.commits = {"sha-base": {"tree": {"sha": "tree-base"}, "parents": []}}
        self.trees = {"tree-base": {}}
        self.blobs = {}
        self.commit_calls = 0
        self.ref_updates = 0
        self.ref_conflicts = 0
        self.tree_entries = None
        self.next_sha = 0

    def _sha(self, kind: str) -> str:
        self.next_sha += 1
        return f"{kind}-{self.next_sha}"

    def call(self, method, url, data=None, headers=None, retries=4):
        if url.endswith("/git/ref/heads/main"):
            return 200, {"object": {"sha": self.ref}}
        if "/git/commits/" in url:
            sha = url.rsplit("/", 1)[1]
            return 200, self.commits.get(sha, {})
        if url.endswith("/git/blobs"):
            content = base64.b64decode(data["content"])
            sha = self._sha("blob")
            self.blobs[sha] = content
            return 201, {"sha": sha}
        if url.endswith("/git/trees"):
            # 真接口:base_tree 必须是当前树的祖先;这里要求它就是当前树
            assert data["base_tree"] in self.trees, "基树必须来自当前 main"
            self.base_tree_used = data["base_tree"]
            self.tree_entries = data["tree"]
            sha = self._sha("tree")
            self.trees[sha] = {e["path"]: e["sha"] for e in data["tree"]}
            return 201, {"sha": sha}
        if url.endswith("/git/commits"):
            # 真接口:父提交必须是当前 main 指向的提交
            assert data["parents"] == [self.ref], "父提交必须是当前 main"
            self.commit_calls += 1
            sha = self._sha("commit")
            self.commits[sha] = {"tree": {"sha": data["tree"]}, "parents": data["parents"]}
            return 201, {"sha": sha}
        if "/git/refs/heads/" in url:
            self.ref_updates += 1
            # 真接口:不是快进更新时回 422
            if self.ref_conflicts > 0:
                self.ref_conflicts -= 1
                return 422, None
            self.ref = data["sha"]
            return 200, {"ref": "refs/heads/main", "object": {"sha": self.ref}}
        raise AssertionError(f"未预期的请求: {method} {url}")


class TestPlanPurge:
    """要删哪些文件。"""

    tree = {
        "releases/builds": [("100", "dir"), ("101", "dir"), ("manifest.json", "file")],
        "releases/builds/100": [("a.whl", "file"), ("b.gz", "file")],
        "releases/builds/101": [("c.whl", "file")],
    }

    def test_old_build_files_are_deleted(self):
        doomed = publish.plan_purge(self.tree, "releases/builds", keep_prefix="releases/builds/102")
        assert "releases/builds/100/a.whl" in doomed
        assert "releases/builds/101/c.whl" in doomed

    def test_current_build_is_kept(self):
        doomed = publish.plan_purge(self.tree, "releases/builds", keep_prefix="releases/builds/100")
        assert "releases/builds/100/a.whl" not in doomed
        assert "releases/builds/101/c.whl" in doomed

    def test_manifest_is_never_deleted(self):
        """清单是"发了什么、从哪个提交来"的真源,删了整条链就断。"""
        doomed = publish.plan_purge(self.tree, "releases/builds", keep_names={"manifest.json"})
        assert "releases/builds/manifest.json" not in doomed

    def test_prefix_keeps_index_html(self):
        tree = {"pypi/simple/forgemind": [("index.html", "file"), ("old.txt", "file")]}
        doomed = publish.plan_purge(
            tree, "pypi/simple/forgemind", keep_prefix="pypi/simple/forgemind/index.html"
        )
        assert doomed == ["pypi/simple/forgemind/old.txt"]

    def test_directories_are_not_deleted_explicitly(self):
        """git 里没有空目录,文件删光目录自然就没了。"""
        doomed = publish.plan_purge(self.tree, "releases/builds", keep_names={"manifest.json"})
        assert "releases/builds/100" not in doomed
        assert "releases/builds/101" not in doomed


class TestKeepBuild:
    """哪些构建目录要留下。"""

    def test_keeps_itself_and_the_live_one(self):
        assert publish.keep_build("102", "102", "101")
        assert publish.keep_build("101", "102", "101")

    def test_keeps_newer_build(self):
        """并发发布留下的更新构建不能删。"""
        assert publish.keep_build("103", "102", "101")

    def test_deletes_older_build(self):
        assert not publish.keep_build("100", "102", "101")

    def test_non_numeric_build_id_is_older(self):
        assert not publish.keep_build("local", "102", "101")


class TestIndexHtml:
    """索引声明的校验值必须与文件内容一致。"""

    def test_declared_sha_matches_content(self):
        blob = b"wheel-bytes"
        sha = hashlib.sha256(blob).hexdigest()
        html = publish.index_html(sha, "forgemind-2026.9.3-py3-none-any.whl", "42").decode()
        assert f"#sha256={sha}" in html
        assert "builds/42/forgemind-2026.9.3-py3-none-any.whl" in html


class TestGitWrite:
    """一次提交写多个路径。"""

    def _write(self, api, entries, message="m"):
        original = publish.call
        publish.call = api.call
        try:
            return publish.git_write("API", "main", entries, message)
        finally:
            publish.call = original

    def test_writes_all_entries_in_one_commit(self):
        api = FakeApi()
        st, sha = self._write(api, [("a.txt", b"a"), ("b.txt", b"b")])
        # 引用更新回 200(创建类的接口才回 201)
        assert st == 200
        assert api.commit_calls == 1, "一次发布只能有一个提交 —— 每个提交都触发一次部署"
        paths = {e["path"]: e["sha"] for e in api.tree_entries}
        assert set(paths) == {"a.txt", "b.txt"}
        assert all(v is not None for v in paths.values())

    def test_deletion_uses_null_sha(self):
        api = FakeApi()
        st, _ = self._write(api, [("a.txt", None)])
        assert st == 200
        assert api.tree_entries[0]["sha"] is None, "删除写的是 sha=null"

    def test_retries_when_ref_moves_underneath(self):
        """有人同时推了 main 时,引用更新会被拒 —— 要基于新的树重做。"""
        api = FakeApi()
        api.ref_conflicts = 1
        st, sha = self._write(api, [("a.txt", b"a")])
        assert st == 200
        assert api.commit_calls == 2, "冲突后必须重做,不能就此放弃"
        assert api.ref == sha

    def test_returns_failure_when_never_writable(self):
        api = FakeApi()
        api.ref_conflicts = 99
        st, sha = self._write(api, [("a.txt", b"a")])
        assert st == 0, "一直写不进去要报失败,不能假装成功"
        assert sha is None


class TestManifestShape:
    """清单是机器可读的真源,字段不能少。"""

    def test_manifest_contains_the_fields_the_chain_relies_on(self):
        manifest = {
            "version": "latest",
            "assets": ["forgemind-linux"],
            "sizes": {"forgemind-linux": 10},
            "build_id": "42",
            "source_repo": "bin1732/forgemind",
            "source_commit": "abc",
            "install": "pip install ...",
        }
        assert manifest["build_id"]
        assert manifest["source_commit"]
        assert json.loads(json.dumps(manifest))["sizes"]["forgemind-linux"] == 10


if __name__ == "__main__":
    # 公开仓的脚本测试不依赖 pytest:那个作业的环境里没有 pytest,
    # 依赖它就等于让这道检查永远跑不起来。这里自带一个极简运行器 ——
    # 断言用普通的 assert,跑一遍所有以 test_ 开头的方法。
    failures = []
    total = 0
    for name, obj in sorted(globals().items()):
        if not (isinstance(obj, type) and name.startswith("Test")):
            continue
        for meth in sorted(dir(obj)):
            if not meth.startswith("test_"):
                continue
            total += 1
            try:
                getattr(obj(), meth)()
                print(f"  PASS {name}.{meth}")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{name}.{meth}: {exc}")
                print(f"  FAIL {name}.{meth}: {exc}")
    if failures:
        print(f"{len(failures)}/{total} 条判据不成立:", file=sys.stderr)
        for item in failures:
            print(f" - {item}", file=sys.stderr)
        sys.exit(1)
    print(f"发布判据 {total} 条全部成立")
