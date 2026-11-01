# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""API 的每个端点都要带合法参数真调一遍。

只断言"不报错"是不够的:参数错了会得到结构化错误,那正是看起来在
工作的典型形态。这里逐个端点带上合法参数真调,并检查返回体真的有内容。

另有一条覆盖检查:app.routes 里多出来的端点必须补进这张表,否则新
端点会绕过验证 —— 端点越多,漏掉一个越容易。
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

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
