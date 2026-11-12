# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""API 的每个端点都要带合法参数真调一遍。

只断言"不报错"是不够的:参数错了会得到结构化错误,那正是看起来在
工作的典型形态。这里逐个端点带上合法参数真调,并检查返回体真的有内容。

另有一条覆盖检查:app.routes 里多出来的端点必须补进这张表,否则新
端点会绕过验证 —— 端点越多,漏掉一个越容易。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_cli_output_clean as clean  # noqa: E402
from forgemind.api.main import app

# (方法, 路径, 查询参数, 请求体)
ENDPOINTS = [
    ("GET", "/health", None, None),
    ("GET", "/api/v1/info", None, None),
    ("GET", "/api/v1/features", None, None),
    ("GET", "/api/v1/features/search", {"query": "momentum"}, None),
    ("GET", "/api/v1/health/services", None, None),
    ("GET", "/mcp", None, None),
    ("GET", "/mcp/tools/list", None, None),
    ("GET", "/mcp/resources/list", None, None),
    ("GET", "/mcp/prompts/list", None, None),
    ("POST", "/mcp/tools/call", None,
     {"name": "get_feature", "arguments": {"name": "kmid"}}),
    ("POST", "/mcp/resources/read", None, {"uri": "forgemind://features"}),
    ("POST", "/api/v1/backtest/run", None,
     {"symbol": "600519.SH", "start_date": "2024-01-01",
      "end_date": "2024-06-30"}),
    ("POST", "/api/pipeline/run", None,
     {"symbols": ["600519"], "start": "2024-01-01", "end": "2024-03-31"}),
]

# 审批类端点要真实的 thread_id,单独验
APPROVAL_ENDPOINTS = [
    ("POST", "/api/v1/agent/{thread_id}/approve"),
    ("POST", "/api/v1/agent/{thread_id}/reject"),
]

# 非法输入:错误路径是最容易漏内部实现的地方。
# (方法, 路径, 请求体或查询参数)
BAD_REQUESTS = [
    ("POST", "/api/v1/backtest/run", {"symbol": "600519.SH", "start_date": "bad",
                                      "end_date": "2024-06-01"}),
    ("POST", "/api/v1/backtest/run", {"symbol": "600519.SH", "start_date": "2024-06-01",
                                      "end_date": "2024-01-01"}),
    ("POST", "/api/v1/backtest/run", {}),
    ("POST", "/api/v1/backtest/run", {"symbol": 12345}),
    ("POST", "/api/pipeline/run", {"symbols": "not-a-list", "start": "2024-01-01",
                                   "end": "2024-03-31"}),
    ("POST", "/api/pipeline/run", {}),
    ("POST", "/mcp/tools/call", {}),
    ("POST", "/mcp/tools/call", {"name": "no_such_tool", "arguments": {}}),
    ("POST", "/mcp/resources/read", {}),
    ("POST", "/api/v1/agent/decide", {"symbol": "600519", "cash": "not-a-number",
                                      "total_equity": 1, "positions": []}),
]

# 决策端点要跑真实的决策图,单独验
DECIDE_ENDPOINT = ("POST", "/api/v1/agent/decide")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _routes() -> set[tuple[str, str]]:
    out = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            out.add((method, route.path))
    return out


class TestResponseHasNoInternals:
    """响应体不许把内部实现摊给用户。

    命令行那条通道有 `scripts/check_cli_output_clean.py` 守着;接口这一侧
    原本没有 —— 十六个端点里只有一条被流水线扫过内部实现,其余端点的
    响应体没人看:里面有 SQL 片段、栈回溯、异常类型名、本机路径,都不会
    有人发现。

    判据从命令行那套脚本里导入,不在这里另写一份 —— 写了就会漂。
    """

    def _assert_clean(self, method: str, path: str, payload, text: str) -> None:
        for label, segment in clean._scan(text, clean.COMPILED_LEAKS):
            pytest.fail(f"{method} {path} 的响应里有{label}: ...{segment}...")
        records = clean.find_log_records(payload)
        assert not records, f"{method} {path} 的响应里有日志记录: {records}"

    @pytest.mark.parametrize("method,path,params,body", ENDPOINTS,
                             ids=[f"{m} {p}" for m, p, _, _ in ENDPOINTS])
    def test_success_response_has_no_internals(self, client, method, path, params, body):
        if method == "GET":
            r = client.get(path, params=params)
        else:
            r = client.post(path, json=body)
        payload = r.json()
        self._assert_clean(method, path, payload, json.dumps(payload, ensure_ascii=False))

    @pytest.mark.parametrize("method,path,body", BAD_REQUESTS,
                             ids=[f"{m} {p}" for m, p, _ in BAD_REQUESTS])
    def test_error_response_has_no_internals(self, client, method, path, body):
        """非法输入必须给 4xx,而且错误响应同样不许漏内部。

        错误路径才是最容易漏的地方:处理里 catch 住异常,把 str(exc)
        塞进 detail,一句 "CatalogException: ..." 就出去了。
        """
        if method == "GET":
            r = client.get(path, params=body)
        else:
            r = client.post(path, json=body)
        assert 400 <= r.status_code < 500, (
            f"{method} {path} -> {r.status_code}: {r.text[:300]}")
        payload = r.json()
        self._assert_clean(method, path, payload, json.dumps(payload, ensure_ascii=False))
        # 错误响应还得说人话:只有状态码没有内容,等于没回话
        assert payload.get("detail") or payload.get("error"), f"{method} {path} 没有说明"


class TestEndpointSweep:
    @pytest.mark.parametrize("method,path,params,body", ENDPOINTS,
                             ids=[f"{m} {p}" for m, p, _, _ in ENDPOINTS])
    def test_endpoint_answers_with_content(self, client, method, path, params, body):
        if method == "GET":
            r = client.get(path, params=params)
        else:
            r = client.post(path, json=body)
        assert r.status_code < 500, (
            f"{method} {path} -> {r.status_code}: {r.text[:400]}")
        payload = r.json()
        assert payload, f"{method} {path} 返回了空体"

    @pytest.mark.parametrize("method,path", APPROVAL_ENDPOINTS,
                             ids=[f"{m} {p}" for m, p in APPROVAL_ENDPOINTS])
    def test_approval_endpoints_report_missing_thread_cleanly(self, client, method, path):
        """不存在的 thread_id 要给 404,不能是裸 500"""
        real = path.replace("{thread_id}", "no-such-thread")
        r = client.post(real, json={"reviewer": "tester", "notes": "probe"})
        assert r.status_code == 404, f"{method} {real} -> {r.status_code}: {r.text[:300]}"
        assert r.json().get("detail"), r.text

    def test_decide_endpoint_returns_a_structured_answer(self, client):
        """决策端点要么给出 thread_id,要么给结构化错误 —— 不能是裸栈"""
        r = client.post("/api/v1/agent/decide", json={
            "symbol": "600519", "cash": 100000.0, "total_equity": 100000.0,
            "positions": []})
        assert r.status_code < 500, f"-> {r.status_code}: {r.text[:400]}"
        payload = r.json()
        assert payload, "返回了空体"
        if r.status_code == 200:
            assert payload.get("thread_id"), payload
            assert payload.get("status") == "PENDING_HUMAN_REVIEW", payload
        else:
            assert payload.get("detail"), f"错误响应没有 detail: {payload}"

    def test_every_route_is_covered(self):
        """新端点必须补进真调清单,否则它就绕过验证了"""
        covered = {(m, p) for m, p, _, _ in ENDPOINTS}
        covered |= set(APPROVAL_ENDPOINTS)
        covered |= {DECIDE_ENDPOINT}
        missing = _routes() - covered
        assert not missing, f"这些端点没有带合法参数真调过: {sorted(missing)}"
