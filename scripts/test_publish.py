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


class TestPagesIndexUrl:
    """线上索引地址按仓推导,不写死"""

    def test_public_repo(self):
        assert publish.pages_index_url("bin1732/forgemind-pypi") == (
            "https://bin1732.github.io/forgemind-pypi/pypi/simple/forgemind/"
        )

    def test_mirror_gets_its_own_site(self):
        """同一份脚本换个仓发布,不能还指着上一个仓的站点"""
        assert publish.pages_index_url("bin1732/forgemind") == (
            "https://bin1732.github.io/forgemind/pypi/simple/forgemind/"
        )

    def test_trailing_slash_is_tolerated(self):
        assert publish.pages_index_url("bin1732/forgemind-pypi/") == (
            publish.pages_index_url("bin1732/forgemind-pypi")
        )


class TestIndexHtml:
    """索引声明的校验值必须与文件内容一致。"""

    def test_declared_sha_matches_content(self):
        blob = b"wheel-bytes"
        sha = hashlib.sha256(blob).hexdigest()
        html = publish.index_html(sha, "forgemind-2026.9.3-py3-none-any.whl", "42").decode()
        assert f"#sha256={sha}" in html
        assert "forgemind-2026.9.3-py3-none-any.whl" in html

    def test_points_at_the_release_asset(self):
        """索引指向 Release 资产 —— 用户在 Releases 页面看到的就是这一份

        指向仓库里的构建目录也行,但那是仓库内容的 CDN,网络一抖就装不上
        (实测:装到一半被 TLS 打断)。github.com 上的发布资产更稳。
        """
        html = publish.index_html(
            "a" * 64, "forgemind-2026.9.3.post54-py3-none-any.whl", "42"
        ).decode()
        assert (
            "https://github.com/bin1732/forgemind-pypi/releases/download/continuous/"
            "forgemind-2026.9.3.post54-py3-none-any.whl" in html
        ), html

    def test_asset_name_carries_the_version(self):
        """资产名带版本号 —— 名字不变的资产,CDN 会继续发旧副本"""
        html = publish.index_html(
            "a" * 64, "forgemind-2026.9.3.post54-py3-none-any.whl", "42"
        ).decode()
        assert "post54" in html, html


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


class TestReleaseAssetOrder:
    """Release 资产的更新顺序:先传新的,再删旧的。

    先删后传的话,发布期间这个 Release 上一个资产都没有 —— 用户下载
    任何构件都是 404,正在跑的验证也会在半路上丢掉要下的文件,报出来的
    却是"下载失败"。这两条都不是发布该有的样子。
    """

    @staticmethod
    def _rel(assets):
        return {
            "id": 7,
            "upload_url": "https://uploads.github.com/assets{?name,label}",
            "assets": assets,
        }

    @staticmethod
    def _recorder():
        seq = []

        def call(method, url, data=None, headers=None, retries=4):
            if method == "POST":
                seq.append(("POST", url.split("name=")[-1]))
                return 201, {}
            if method == "DELETE":
                seq.append(("DELETE", url.rsplit("/", 1)[-1]))
                return 204, None
            raise AssertionError(f"未预期的请求: {method} {url}")

        return seq, call

    @staticmethod
    def _tmp_file(name, content=b"x" * 10):
        import tempfile

        d = Path(tempfile.mkdtemp())
        f = d / name
        f.write_bytes(content)
        return f

    def test_old_assets_survive_until_the_new_ones_are_up(self):
        """上一版的资产必须活到新资产全部传完"""
        old = {"name": "forgemind-2026.9.3.post10-linux", "url": "https://api/assets/1"}
        f = self._tmp_file("forgemind-2026.9.3.post11-linux")
        seq, call = self._recorder()
        publish.sync_release_assets(self._rel([old]), [f], "2026.9.3.post11", call)
        kinds = [k for k, _ in seq]
        assert kinds == ["POST", "DELETE"], f"顺序不对: {seq}"
        assert seq[0][0] == "POST", "新资产必须先传上去"
        assert seq[-1][1] == "1", "最后删的是上一版的资产"

    def test_same_name_is_deleted_before_upload(self):
        """重发同一个构建时,同名的先删 —— Releases API 不允许同名共存"""
        same = {"name": "forgemind-2026.9.3.post11-linux", "url": "https://api/assets/9"}
        f = self._tmp_file("forgemind-2026.9.3.post11-linux")
        seq, call = self._recorder()
        publish.sync_release_assets(self._rel([same]), [f], "2026.9.3.post11", call)
        kinds = [k for k, _ in seq]
        assert kinds == ["DELETE", "POST"], f"顺序不对: {seq}"

    def test_wait_returns_when_every_asset_is_downloadable(self):
        """资产都能下时,等待立刻返回"""
        assert publish.wait_assets_downloadable(["a", "b"], timeout=5, check=lambda n: True)

    def test_wait_gives_up_at_the_deadline(self):
        """下不到的资产到时限就放弃,并说清楚是哪些"""
        calls = []

        def never(name):
            calls.append(name)
            return False

        ok = publish.wait_assets_downloadable(["a"], timeout=0, check=never)
        assert ok is False
        assert calls == ["a"]

    def test_asset_name_carries_the_publish_version(self):
        """资产名必须带上这次的版本号"""
        f = self._tmp_file("forgemind-linux")
        assert publish.asset_name(f, "2026.9.3.post11") == "forgemind-2026.9.3.post11-linux"


class TestIndexMustActuallySwitch:
    """线上索引没切过去,这次发布就不算完成。

    索引是由 Pages 部署发布的:部署一失败,CDN 上还是旧索引,用户
    pip 到的就是上一个版本。构件传上去了、清单也写了,唯独用户真正
    用的那个入口没换 —— 这种情况报成功,是让一次没生效的发布看起来
    像成功了。

    不用 pytest:这个脚本自带极简运行器,那个作业的环境里没有 pytest。
    """

    def _run_publish(self, live_name):
        """跑一次发布,线上索引指向由 live_name 决定。返回退出码。"""
        import tempfile
        from unittest import mock

        with tempfile.TemporaryDirectory(prefix="forgemind-publish-test-") as tmp:
            artifacts = Path(tmp) / "artifacts"
            artifacts.mkdir(parents=True, exist_ok=True)
            (artifacts / "forgemind-1.0-py3-none-any.whl").write_bytes(b"x" * 1000)

            argv = [
                "publish.py",
                "--build-id",
                "42",
                "--source-commit",
                "abc123",
                "--publish-version",
                "1.0",
                "--artifacts",
                str(artifacts),
                # 线上索引按仓推导 ⇒ 测试里得给一个仓;索引地址本身被
                # mock 掉了,不会真的去访问。
                "--repo",
                "bin1732/forgemind-pypi",
            ]
            clock = {"n": 0}

            class _Clock:
                @staticmethod
                def time():
                    # 每次前进一秒:等待窗口是 600 秒,于是循环跑满 600 次
                    # 自然结束 —— 既不会真的睡十分钟,也不会无限转。
                    clock["n"] += 1
                    return 1000.0 + clock["n"]

                @staticmethod
                def sleep(_seconds):
                    return None

            def fake_call(method, url, data=None, headers=None, retries=4):
                # Release 那一步要的是一个完整的 release 对象(带 id 与
                # upload_url)。假实现给得比真实现薄,真代码就会在拿不到
                # id 的地方炸 —— 那是假实现的漏洞,不是真代码的。
                if method == "GET" and "/releases/tags/continuous" in url:
                    return 200, {
                        "id": 7,
                        "upload_url": "https://uploads/x?{?name,label}",
                        "assets": [],
                    }
                return 200, {"object": {"sha": "sha-base"}}

            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(publish, "live_index_filename", new=live_name),
                mock.patch.object(publish, "wait_assets_downloadable", return_value=True),
                mock.patch.object(
                    publish,
                    "sync_release_assets",
                    return_value=(["a.whl"], {"a.whl": 1}),
                ),
                mock.patch.object(publish, "git_write", return_value=(201, "commit-sha")),
                mock.patch.object(publish, "collect_tree", return_value={}),
                mock.patch.object(publish, "call", side_effect=fake_call),
                mock.patch.object(publish.time, "time", _Clock.time),
                mock.patch.object(publish.time, "sleep", _Clock.sleep),
            ):
                return publish.main()

    def test_publish_fails_when_the_index_does_not_switch(self):
        """索引一直指着旧版本 → 这次发布要失败"""
        rc = self._run_publish(lambda timeout=30, index_url=None: "forgemind-0.9-py3-none-any.whl")
        assert rc == 1, "线上索引没切过去,发布却报成功了"

    def test_publish_succeeds_when_the_index_switches(self):
        """索引切过去了 → 发布照常成功"""
        rc = self._run_publish(lambda timeout=30, index_url=None: "forgemind-1.0-py3-none-any.whl")
        assert rc == 0, "索引切过去了,发布却失败了"


class TestReleaseBody:
    """发布说明:每次发布都重写,构件清单是真的,不给假数字。

    原来只在**创建** Release 时写一次正文,之后每次发布都不管它 ——
    页面上永远停着创建时那一版:写着最初的版本号、最初的构件清单。
    """

    def test_body_lists_the_uploaded_assets(self):
        """正文里的构件清单是这次真传上去的那些"""
        body = publish._release_body(
            "1.0",
            ["forgemind-1.0-py3-none-any.whl", "forgemind-1.0-linux"],
        )
        assert "forgemind-1.0-py3-none-any.whl" in body
        assert "forgemind-1.0-linux" in body

    def test_body_has_no_backtest_claims(self):
        """正文不给回测数字 —— 那取决于标的与区间,写上去就是一句谎话"""
        body = publish._release_body("1.0", ["forgemind-1.0-py3-none-any.whl"])
        assert "Total Return" not in body
        assert "%" not in body, "发布说明里不该出现回测数字"

    def test_install_url_has_no_trailing_project_name(self):
        """索引地址后面不能再带 /forgemind/ —— pip 会拼两次,得到 404"""
        body = publish._release_body("1.0", [])
        assert "/pypi/simple/ forgemind" in body
        assert "/pypi/simple/forgemind/" not in body

    def test_body_is_rewritten_on_every_publish(self):
        """Release 已经存在时,发布仍要重写正文"""
        import tempfile
        from unittest import mock

        with tempfile.TemporaryDirectory(prefix="forgemind-body-test-") as tmp:
            artifacts = Path(tmp) / "artifacts"
            artifacts.mkdir(parents=True, exist_ok=True)
            (artifacts / "forgemind-1.0-py3-none-any.whl").write_bytes(b"x" * 1000)

            argv = [
                "publish.py",
                "--build-id",
                "42",
                "--source-commit",
                "abc123",
                "--publish-version",
                "1.0",
                "--artifacts",
                str(artifacts),
                "--repo",
                "bin1732/forgemind-pypi",
            ]
            calls: list[tuple[str, str, dict | None]] = []

            def fake_call(method, url, data=None, headers=None, retries=4):
                calls.append((method, url, data))
                if method == "GET" and "/releases/tags/continuous" in url:
                    return 200, {"id": 7, "upload_url": "https://uploads/x?{?name,label}", "assets": []}
                return 200, {"object": {"sha": "sha-base"}}

            class _Clock:
                @staticmethod
                def time():
                    return 1000.0

                @staticmethod
                def sleep(_seconds):
                    return None

            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(publish, "live_index_filename", return_value="forgemind-1.0-py3-none-any.whl"),
                mock.patch.object(publish, "wait_assets_downloadable", return_value=True),
                mock.patch.object(
                    publish,
                    "sync_release_assets",
                    return_value=(["forgemind-1.0-py3-none-any.whl"], {"forgemind-1.0-py3-none-any.whl": 1}),
                ),
                mock.patch.object(publish, "git_write", return_value=(201, "commit-sha")),
                mock.patch.object(publish, "collect_tree", return_value={}),
                mock.patch.object(publish, "call", side_effect=fake_call),
                mock.patch.object(publish.time, "time", _Clock.time),
                mock.patch.object(publish.time, "sleep", _Clock.sleep),
            ):
                rc = publish.main()
            assert rc == 0, "发布失败了"
            patches = [c for c in calls if c[0] == "PATCH"]
            assert patches, "发布没有重写 Release 正文 —— 页面上留着的仍是旧的说明"
            body = (patches[0][2] or {}).get("body", "")
            assert "forgemind-1.0-py3-none-any.whl" in body, body
            assert "1.0" in body


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
