# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""services_health 端点回归测试

覆盖两个曾经的真实故障:
  1. 错误分类时把 except 捕获的真实异常丢掉了,换成新的空 Exception()
  2. nats-py 2.x 的后台重连任务异常逃逸,把整个端点打成 500
"""

import asyncio

from fastapi.testclient import TestClient

from forgemind.api.main import _classify_error, app, services_health


class TestClassifyError:
    """_classify_error 不得泄露任何敏感信息"""

    def test_connection_refused_is_unreachable(self):
        e = ConnectionRefusedError("[Errno 111] Connect call failed ('127.0.0.1', 6379)")
        assert _classify_error(e) == "unreachable"

    def test_driver_missing(self):
        e = ModuleNotFoundError("No module named 'clickhouse_driver'")
        assert _classify_error(e) == "driver_missing"

    def test_auth_failed(self):
        e = RuntimeError("Authentication failed: password rejected")
        assert _classify_error(e) == "auth_failed"

    def test_timeout(self):
        e = TimeoutError("timed out after 2s")
        assert _classify_error(e) == "timeout"

    def test_falls_back_to_generic_error(self):
        e = ValueError("something odd happened")
        assert _classify_error(e) == "error"

    def test_never_contains_original_message(self):
        """分类结果绝不能带原始消息 —— 那里面有 IP/端口/模块名"""
        secret = "[Errno 111] Connect call failed ('10.0.0.5', 5432)"
        result = _classify_error(ConnectionRefusedError(secret))
        assert result not in secret
        for leak in ("10.0.0.5", "5432", "Errno", "Connect"):
            assert leak not in result


class TestServicesHealth:
    async def test_returns_200_when_all_backends_down(self):
        """核心回归:后端全挂时端点仍须 200,而不是 500"""
        result = await services_health()
        assert isinstance(result, dict)
        for status in result.values():
            assert isinstance(status, str)
            assert status in {"ok", "unreachable", "timeout", "auth_failed", "error", "driver_missing"}

    async def test_no_sensitive_data_in_payload(self):
        result = await services_health()
        blob = str(result).lower()
        for leak in ("127.0.0.1", "::1", "0.0.0.0", "password", "traceback", "site-packages"):
            assert leak not in blob, f"泄露敏感信息: {leak}"

    async def test_nats_error_does_not_escape_event_loop(self):
        """核心回归:nats 后台任务异常不得逃逸出 asyncio.run()"""
        task = asyncio.create_task(services_health())
        # 不加错误容忍:逃逸会直接 raise 到这里
        await asyncio.wait_for(task, timeout=30)


class TestServicesHealthEndpoint:
    def test_endpoint_status_code(self):
        with TestClient(app) as client:
            r = client.get("/api/v1/health/services")
            assert r.status_code == 200, r.text
            assert r.json()
