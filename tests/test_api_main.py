# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest


class TestFastAPIApp:
    """覆盖 /health /info /backtest /agent /features /services_health"""
    
    @pytest.fixture
    def client(self):
        """FastAPI TestClient"""
        from fastapi.testclient import TestClient
        from forgemind.api.main import app
        return TestClient(app)
    
    def test_app_loads(self):
        """App 应能加载"""
        from forgemind.api.main import app
        assert app is not None
        assert app.title == "ForgeMind API"
    
    def test_health_endpoint(self, client):
        """/health 应返回 ok"""
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "env" in data
        assert "timestamp" in data
    
    def test_info_endpoint(self, client):
        """/api/v1/info 应返回 app info"""
        r = client.get("/api/v1/info")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "ForgeMind"
        assert "version" in data
    
    def test_backtest_endpoint(self, client):
        """/api/v1/backtest/run 真跑回测"""
        r = client.post(
            "/api/v1/backtest/run",
            json={
                "symbol": "600519.SH",
                "start_date": "2024-01-01",
                "end_date": "2024-06-30",
                "fast_period": 5,
                "slow_period": 20,
                "initial_capital": 100_000.0,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "total_return" in data
        assert "sharpe" in data
        assert "max_drawdown" in data
        assert "win_rate" in data
        assert "n_trades" in data
        assert "params" in data
    
    def test_backtest_validation_error(self, client):
        """/api/v1/backtest/run — fast_period < 2 应 422"""
        r = client.post(
            "/api/v1/backtest/run",
            json={
                "symbol": "X",
                "fast_period": 1,  # < 2 应报错
                "slow_period": 20,
            },
        )
        assert r.status_code == 422
    
    def test_agent_endpoint(self, client):
        """/api/v1/agent/decide 真跑"""
        r = client.post(
            "/api/v1/agent/decide",
            json={
                "symbol": "600519.SH",
                "cash": 80_000.0,
                "total_equity": 100_000.0,
                "positions": [],
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "decision" in data
        assert "confidence" in data
        assert "requires_human_review" in data
        assert "reasoning" in data
    
    def test_features_search(self, client):
        """/api/v1/features/search"""
        r = client.get("/api/v1/features/search?query=momentum&limit=5")
        assert r.status_code == 200
        data = r.json()
        assert data["query"] == "momentum"
        assert "results" in data
        assert len(data["results"]) <= 5
    
    def test_features_search_default_limit(self, client):
        """/api/v1/features/search 不传 limit 用默认 10"""
        r = client.get("/api/v1/features/search?query=rsi")
        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) == 1  # RSI 命中 1 个因子
    
    def test_services_health(self, client):
        """/api/v1/health/services"""
        r = client.get("/api/v1/health/services")
        assert r.status_code == 200
        data = r.json()
        # 各服务都应有一个 key(可能 down)
        assert "clickhouse" in data
        assert "postgresql" in data
        assert "redis" in data
        assert "nats" in data
    
    def test_forgemind_error_handler_exists(self):
        """ForgeMindError handler 应存在"""
        from forgemind.api.main import forgemind_error_handler
        assert forgemind_error_handler is not None
        assert callable(forgemind_error_handler)
    
    def test_forgemind_error_returns_json(self):
        """ForgeMindError handler 应返回 JSONResponse"""
        import asyncio
        from forgemind.api.main import forgemind_error_handler
        from forgemind.core.observability.logging import ConfigError
        from starlette.requests import Request
        
        async def run_test():
            request = Request(scope={"type": "http"})
            err = ConfigError("test error", code="TEST_CODE")
            response = await forgemind_error_handler(request, err)
            return response
        
        response = asyncio.run(run_test())
        assert response.status_code == 500
        # body 解析
        import json
        body = json.loads(response.body)
        # code 字段是 int 1001 (ConfigError 默认 code)
        assert body["code"] == 1001
        assert "ConfigError" in body["error"]
        assert "test error" in body["message"]


class TestAppMetadata:
    def test_app_version(self):
        """App version 应匹配 settings.version"""
        from forgemind.api.main import app
        from forgemind.core.config.settings import get_settings
        assert app.version == get_settings().version
    
    def test_cors_configured(self):
        """CORS middleware 应配置"""
        from forgemind.api.main import app
        # middleware stack 包含 CORSMiddleware
        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_classes