"""Test the new API validation (date, periods)"""
import pytest
from fastapi.testclient import TestClient
from forgemind.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_backtest_rejects_bad_date(client):
    """/api/v1/backtest/run — bad date format → 422 not 500"""
    r = client.post("/api/v1/backtest/run", json={
        "symbol": "600519.SH",
        "start_date": "invalid",
        "end_date": "2024-06-30",
        "fast_period": 5,
        "slow_period": 20,
        "initial_capital": 100_000.0,
    })
    assert r.status_code == 422
    assert "日期格式错误" in r.text


def test_backtest_rejects_end_before_start(client):
    """/api/v1/backtest/run — end < start → 422"""
    r = client.post("/api/v1/backtest/run", json={
        "symbol": "600519.SH",
        "start_date": "2024-12-31",
        "end_date": "2024-01-01",
        "fast_period": 5,
        "slow_period": 20,
        "initial_capital": 100_000.0,
    })
    assert r.status_code == 422
    assert "必须晚于" in r.text


def test_backtest_rejects_slow_le_fast(client):
    """/api/v1/backtest/run — slow <= fast → 422"""
    r = client.post("/api/v1/backtest/run", json={
        "symbol": "600519.SH",
        "start_date": "2024-01-01",
        "end_date": "2024-06-30",
        "fast_period": 20,
        "slow_period": 5,
        "initial_capital": 100_000.0,
    })
    assert r.status_code == 422
    assert "slow_period" in r.text


def test_services_health_doesnt_leak_secrets(client):
    """/api/v1/health/services — must not leak IPs/passwords"""
    r = client.get("/api/v1/health/services")
    assert r.status_code == 200
    data = r.json()
    for service, status in data.items():
        # Status should be a category, not a raw error message
        assert status in ("ok", "unreachable", "error", "auth_failed", "timeout", "driver_missing"), \
            f"{service} leaks raw error: {status}"
        # No IP addresses, no passwords
        assert "::" not in status and "127." not in status and "localhost" not in status
        assert "password" not in status.lower()
