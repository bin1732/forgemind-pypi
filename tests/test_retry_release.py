# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""发布补跑工具:找得到那次运行、叫得动补跑、读得出线上版本。

发布被平台的 macOS 队列卡住时,恢复的入口就是"把这次运行失败的作业重跑
一遍"。这个工具把那条路径做成一条命令,并且**说清楚它动了什么** ——
一个悄悄改状态、只回一句"好了"的脚本,下次没人敢用。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import retry_release as retry  # noqa: E402


class FakeApi:
    """够用的假 GitHub:运行列表、作业列表、补跑、清单。"""

    def __init__(self, runs=None, jobs=None, manifest=None):
        self.runs = runs or []
        self.jobs = jobs or []
        self.manifest = manifest or {}
        self.calls: list[tuple[str, str]] = []
        self.posted: list[tuple[str, dict]] = []

    def request(self, method, url, token, payload=None):
        self.calls.append((method, url))
        if method == "POST":
            self.posted.append((url, payload or {}))
            return {}
        if "workflows/ship.yml/runs" in url:
            return {"workflow_runs": self.runs}
        if "/jobs" in url:
            return {"jobs": self.jobs}
        if "/contents/releases/builds/manifest.json" in url:
            return self.manifest
        return {}


class TestFindFailedRun:
    def test_latest_failure_is_picked(self, monkeypatch):
        api = FakeApi(
            runs=[
                {"id": 1, "conclusion": "success", "head_sha": "a" * 40},
                {"id": 2, "conclusion": "failure", "head_sha": "b" * 40},
                {"id": 3, "conclusion": "success", "head_sha": "c" * 40},
            ]
        )
        monkeypatch.setattr(retry, "request", api.request)
        run = retry.latest_failed_publish_run("o/r", "t")
        assert run["id"] == 2

    def test_no_failure_raises(self, monkeypatch):
        import pytest

        api = FakeApi(runs=[{"id": 1, "conclusion": "success"}])
        monkeypatch.setattr(retry, "request", api.request)
        with pytest.raises(SystemExit) as exc:
            retry.latest_failed_publish_run("o/r", "t")
        assert "没有失败的发布" in str(exc.value)


class TestFailedJobs:
    def test_only_failed_jobs_are_returned(self, monkeypatch):
        api = FakeApi(
            jobs=[
                {"name": "build-wheel", "conclusion": "success"},
                {"name": "build-standalone (macos-26, macos)", "conclusion": "cancelled"},
                {"name": "ship", "conclusion": "failure"},
                {"name": "resolve-source", "conclusion": "success"},
            ]
        )
        monkeypatch.setattr(retry, "request", api.request)
        jobs = retry.failed_jobs("o/r", "t", 42)
        assert [j["name"] for j in jobs] == [
            "build-standalone (macos-26, macos)",
            "ship",
        ]


class TestOnMainHead:
    """补跑只对"还在 main 头上"的那次运行有意义"""

    def test_same_sha_is_on_head(self, monkeypatch):
        api = FakeApi()
        monkeypatch.setattr(retry, "request", api.request)
        # /commits/main 返回的就是这次运行的提交
        monkeypatch.setattr(
            retry,
            "request",
            lambda method, url, token, payload=None: {"sha": "a" * 40},
        )
        assert retry.is_on_main_head("o/r", "t", {"head_sha": "a" * 40}) is True

    def test_different_sha_is_not_on_head(self, monkeypatch):
        monkeypatch.setattr(
            retry,
            "request",
            lambda method, url, token, payload=None: {"sha": "b" * 40},
        )
        assert retry.is_on_main_head("o/r", "t", {"head_sha": "a" * 40}) is False


class TestRerun:
    def test_rerun_posts_to_the_failed_jobs_endpoint(self, monkeypatch):
        api = FakeApi()
        monkeypatch.setattr(retry, "request", api.request)
        retry.rerun_failed("o/r", "t", 42)
        assert api.posted, "补跑没有发出去"
        url, _payload = api.posted[0]
        assert url.endswith("/actions/runs/42/rerun-failed-jobs")


class TestPublishedVersion:
    def test_version_comes_from_the_manifest(self, monkeypatch):
        import urllib.request

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"published_version": "2026.9.3.post65"}).encode()

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())
        assert retry.published_version("o/r", "t") == "2026.9.3.post65"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
