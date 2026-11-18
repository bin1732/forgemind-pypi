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
    ("POST", "/mcp/tools/call", None, {"name": "get_feature", "arguments": {"name": "kmid"}}),
    ("POST", "/mcp/resources/read", None, {"uri": "forgemind://features"}),
    (
        "POST",
        "/api/v1/backtest/run",
        None,
        {"symbol": "600519.SH", "start_date": "2024-01-01", "end_date": "2024-06-30"},
    ),
    (
        "POST",
        "/api/pipeline/run",
        None,
        {"symbols": ["600519"], "start": "2024-01-01", "end": "2024-03-31"},
    ),
]

# 审批类端点要真实的 thread_id,单独验
APPROVAL_ENDPOINTS = [
    ("POST", "/api/v1/agent/{thread_id}/approve"),
    ("POST", "/api/v1/agent/{thread_id}/reject"),
]

# 非法输入:错误路径是最容易漏内部实现的地方。
# (方法, 路径, 请求体或查询参数)
BAD_REQUESTS = [
    (
        "POST",
        "/api/v1/backtest/run",
        {"symbol": "600519.SH", "start_date": "bad", "end_date": "2024-06-01"},
    ),
    (
        "POST",
        "/api/v1/backtest/run",
        {"symbol": "600519.SH", "start_date": "2024-06-01", "end_date": "2024-01-01"},
    ),
    ("POST", "/api/v1/backtest/run", {}),
    ("POST", "/api/v1/backtest/run", {"symbol": 12345}),
    (
        "POST",
        "/api/pipeline/run",
        {"symbols": "not-a-list", "start": "2024-01-01", "end": "2024-03-31"},
    ),
    ("POST", "/api/pipeline/run", {}),
    ("POST", "/mcp/tools/call", {}),
    ("POST", "/mcp/tools/call", {"name": "no_such_tool", "arguments": {}}),
    ("POST", "/mcp/resources/read", {}),
    (
        "POST",
        "/api/v1/agent/decide",
        {"symbol": "600519", "cash": "not-a-number", "total_equity": 1, "positions": []},
    ),
]

# 决策端点要跑真实的决策图,单独验
DECIDE_ENDPOINT = ("POST", "/api/v1/agent/decide")


#: 桌面端 sidecar 带的自定义头。本机专用端点(/mcp、/api/pipeline)
#: 认这个头 —— 浏览器里的网页发它会触发 CORS 预检,预检被允许来源
#: 列表挡下,于是网页驱动不了用户本机的库。
CLIENT_HEADERS = {"X-ForgeMind-Client": "tauri-sidecar"}


def _headers(path: str) -> dict:
    """本机专用端点要带桌面端那个头。"""
    if any(path.startswith(p) for p in ("/mcp", "/api/pipeline")):
        return dict(CLIENT_HEADERS)
    return {}


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

    @pytest.mark.parametrize(
        "method,path,params,body", ENDPOINTS, ids=[f"{m} {p}" for m, p, _, _ in ENDPOINTS]
    )
    def test_success_response_has_no_internals(self, client, method, path, params, body):
        if method == "GET":
            r = client.get(path, params=params, headers=_headers(path))
        else:
            r = client.post(path, json=body, headers=_headers(path))
        payload = r.json()
        self._assert_clean(method, path, payload, json.dumps(payload, ensure_ascii=False))

    @pytest.mark.parametrize(
        "method,path,body", BAD_REQUESTS, ids=[f"{m} {p}" for m, p, _ in BAD_REQUESTS]
    )
    def test_error_response_has_no_internals(self, client, method, path, body):
        """非法输入必须给 4xx,而且错误响应同样不许漏内部。

        错误路径才是最容易漏的地方:处理里 catch 住异常,把 str(exc)
        塞进 detail,一句 "CatalogException: ..." 就出去了。
        """
        if method == "GET":
            r = client.get(path, params=body, headers=_headers(path))
        else:
            r = client.post(path, json=body, headers=_headers(path))
        assert 400 <= r.status_code < 500, f"{method} {path} -> {r.status_code}: {r.text[:300]}"
        payload = r.json()
        self._assert_clean(method, path, payload, json.dumps(payload, ensure_ascii=False))
        # 错误响应还得说人话:只有状态码没有内容,等于没回话
        assert payload.get("detail") or payload.get("error"), f"{method} {path} 没有说明"


class TestEndpointSweep:
    @pytest.mark.parametrize(
        "method,path,params,body", ENDPOINTS, ids=[f"{m} {p}" for m, p, _, _ in ENDPOINTS]
    )
    def test_endpoint_answers_with_content(self, client, method, path, params, body):
        if method == "GET":
            r = client.get(path, params=params, headers=_headers(path))
        else:
            r = client.post(path, json=body, headers=_headers(path))
        assert r.status_code < 500, f"{method} {path} -> {r.status_code}: {r.text[:400]}"
        payload = r.json()
        assert payload, f"{method} {path} 返回了空体"

    @pytest.mark.parametrize(
        "method,path", APPROVAL_ENDPOINTS, ids=[f"{m} {p}" for m, p in APPROVAL_ENDPOINTS]
    )
    def test_approval_endpoints_report_missing_thread_cleanly(self, client, method, path):
        """不存在的 thread_id 要给 404,不能是裸 500"""
        real = path.replace("{thread_id}", "no-such-thread")
        r = client.post(real, json={"reviewer": "tester", "notes": "probe"})
        assert r.status_code == 404, f"{method} {real} -> {r.status_code}: {r.text[:300]}"
        assert r.json().get("detail"), r.text

    def test_decide_endpoint_returns_a_structured_answer(self, client):
        """决策端点要么给出 thread_id,要么给结构化错误 —— 不能是裸栈"""
        r = client.post(
            "/api/v1/agent/decide",
            json={"symbol": "600519", "cash": 100000.0, "total_equity": 100000.0, "positions": []},
        )
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


class TestResourceFailuresAreNotReportedAsMissingData:
    """库被占着时,接口不能说"还没拉数据",更不能给一组假数字。

    命令行那条通道有 `scripts/check_command_states.py` 守着;接口这一侧
    在这里守。两边说的是同一件事,判据不该只护一边。
    """

    def test_backtest_reports_store_unavailable(self, client, monkeypatch):
        import forgemind.core.data.storage as storage

        def _boom(*args, **kwargs):
            raise storage.LocalStoreLockedError("/tmp/main.db")

        monkeypatch.setattr(storage, "DuckDBStorage", _boom)
        resp = client.post(
            "/api/v1/backtest/run",
            json={
                "symbol": "600519.SH",
                "start_date": "2024-01-01",
                "end_date": "2024-06-30",
            },
        )
        assert resp.status_code == 503, resp.text
        detail = str(resp.json().get("detail", ""))
        assert "占用" in detail or "读不到" in detail, detail
        # 不能说"先跑 etl 拉数据" —— 拉数据同样连不上那个库
        assert "etl" not in detail.lower(), detail
        # 更不能给数字:调用方会拿着那组数字当真
        assert "total_return" not in resp.text, resp.text

    def test_write_failure_is_also_reported_as_resource(self, client, monkeypatch):
        """存储写不进去也是资源类,不是"还没拉数据"。"""
        import forgemind.core.data.storage as storage

        def _boom(*args, **kwargs):
            raise storage.LocalStoreWriteError("/tmp/main.db")

        monkeypatch.setattr(storage, "DuckDBStorage", _boom)
        resp = client.post(
            "/api/v1/backtest/run",
            json={
                "symbol": "600519.SH",
                "start_date": "2024-01-01",
                "end_date": "2024-06-30",
            },
        )
        assert resp.status_code == 503, resp.text
        detail = str(resp.json().get("detail", ""))
        assert "写不进去" in detail or "读不到" in detail, detail
        assert "total_return" not in resp.text, resp.text


class TestLocalOnlyEndpointsRefuseBrowsers:
    """本机专用端点不接受浏览器发来的请求。

    这两个前缀下都是能写库、能跑决策的东西(写信号、跑 agent 决策、
    跑研究流水线)。它们免 API Key 校验 —— 桌面端 sidecar 不带 key ——
    所以另设一道:必须带桌面端那个自定义头。浏览器里的网页发这个头
    会触发 CORS 预检,预检被允许来源列表挡下 ⇒ 网页驱动不了本机的库。
    """

    @pytest.mark.parametrize(
        "method,path,body",
        [
            ("POST", "/mcp/tools/call", {"name": "get_feature", "arguments": {"name": "kmid"}}),
            ("GET", "/mcp/tools/list", None),
            (
                "POST",
                "/api/pipeline/run",
                {"symbols": ["600519"], "start": "2024-01-01", "end": "2024-01-31"},
            ),
        ],
        ids=["tools/call", "tools/list", "pipeline/run"],
    )
    def test_without_the_client_header_it_is_refused(self, client, method, path, body):
        if method == "GET":
            r = client.get(path)
        else:
            r = client.post(path, json=body)
        assert r.status_code == 403, f"{path} 没带桌面端头也放行 -> {r.status_code}: {r.text[:200]}"

    @pytest.mark.parametrize(
        "method,path,body",
        [
            ("POST", "/mcp/tools/call", {"name": "get_feature", "arguments": {"name": "kmid"}}),
            ("GET", "/mcp/tools/list", None),
        ],
        ids=["tools/call", "tools/list"],
    )
    def test_with_the_client_header_it_works(self, client, method, path, body):
        if method == "GET":
            r = client.get(path, headers=CLIENT_HEADERS)
        else:
            r = client.post(path, json=body, headers=CLIENT_HEADERS)
        assert r.status_code != 403, f"{path} 带了对的头还是被拒: {r.text[:200]}"

    def test_cors_is_not_wide_open_by_default(self):
        """默认放开所有来源,等于用户浏览器里任意网页都能调这台机器。

        浏览器直连调试要放开时,设 FORGEMIND_API_CORS_ORIGINS。
        """
        from forgemind.core.config.settings import Settings

        origins = Settings().api_cors_origins
        assert "*" not in origins, f"默认允许所有跨域来源,网页能跨站调本机接口: {origins}"


class TestAuthFailuresAreNotServerErrors:
    """鉴权失败必须真是 401/403,不能是 500。

    API Key 校验与本机端点检查都住在**中间件**里,而中间件在 FastAPI 的
    异常处理器**外面** —— 在那里抛 HTTPException 没人接,请求一路冒到最
    外层,客户端拿到的是 500。客户端于是以为服务坏了,而不是"你没带
    凭证" ⇒ 排查方向直接被带偏。

    这条判据盯的是**返回的状态码**,不盯源码字面量:实现换成别的写法
    (比如注册一个异常处理器)它照样成立。
    """

    def test_missing_api_key_is_401(self, monkeypatch):
        from forgemind.api import main as m

        monkeypatch.setattr(m.settings, "env", "prod")
        monkeypatch.setattr(m.settings, "api_secret_key", "s3cret-for-this-test")
        with TestClient(m.app) as c:
            r = c.get("/api/v1/backtest")
        assert r.status_code == 401, f"没带 API Key 应该是 401,实际 {r.status_code}: {r.text[:200]}"

    def test_wrong_api_key_is_403(self, monkeypatch):
        from forgemind.api import main as m

        monkeypatch.setattr(m.settings, "env", "prod")
        monkeypatch.setattr(m.settings, "api_secret_key", "s3cret-for-this-test")
        with TestClient(m.app) as c:
            r = c.get("/api/v1/backtest", headers={"X-API-Key": "wrong"})
        assert r.status_code == 403, f"API Key 不对应该是 403,实际 {r.status_code}: {r.text[:200]}"
