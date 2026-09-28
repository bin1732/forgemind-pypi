# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""回归测试:禁止 MCP 工具返回编造数据

本文件锁死 2026-09 审计发现的真实缺陷:
  1. query_portfolio 永远返回一份写死的 持仓/现金/权益
  2. trace_feature_usage 对任何因子返回同一份写死的关联
  3. check_ic_decay 用 np.random.default_rng(42) 编造 IC/ICIR
  4. 策略层的 MaxSharpe / RiskParity 是没有 generate_signal 的空壳
  5. 扩展策略无法从 CLI 访问
"""

import asyncio
import json

import pytest

from forgemind.core.strategies.extended_library import list_strategies
from forgemind.mcp.server import ForgeMindMCPServer


def _call(server, name, args):
    async def _run():
        return await asyncio.wait_for(
            server.handle_request({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": name, "arguments": args},
            }),
            timeout=60,
        )
    return asyncio.run(_run())


def _text(resp):
    return resp["result"]["content"][0]["text"]


def _payload(resp):
    return json.loads(_text(resp))


@pytest.fixture
def server():
    return ForgeMindMCPServer()


class TestNoFabricatedPortfolio:
    def test_empty_when_no_snapshot(self, server, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        out = _payload(_call(server, "query_portfolio", {}))
        # 没有快照时必须如实为空,不得出现写死的数字
        assert out["status"] == "empty"
        assert out["positions"] == []
        assert out["cash"] is None
        assert out["total_equity"] is None

    def test_no_magic_numbers(self, server, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        blob = _text(_call(server, "query_portfolio", {}))
        # 曾经写死的这三个值不得再出现
        for magic in ("80000", "200000", "1500.0", "600519.SH"):
            assert magic not in blob, f"query_portfolio 又在返回编造数据: {magic}"

    def test_reads_real_snapshot(self, server, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from forgemind.core.agents.portfolio_context import (
            PortfolioContext,
            PortfolioPosition,
        )
        from forgemind.core.data.storage import save_portfolio_snapshot

        ctx = PortfolioContext(
            cash=123456.0,
            total_equity=654321.0,
            positions=[PortfolioPosition(symbol="000001.SZ", quantity=77, avg_price=12.5)],
        )
        save_portfolio_snapshot(ctx)

        out = _payload(_call(server, "query_portfolio", {}))
        assert out["status"] == "ok"
        assert out["cash"] == pytest.approx(123456.0)
        assert out["total_equity"] == pytest.approx(654321.0)
        assert len(out["positions"]) == 1
        assert out["positions"][0]["symbol"] == "000001.SZ"
        assert out["positions"][0]["quantity"] == pytest.approx(77)


class TestNoFabricatedUsage:
    def test_trace_returns_real_refs_only(self, server):
        out = _payload(_call(server, "trace_feature_usage", {"feature_id": "KMID"}))
        # 曾经的写死清单
        assert out["models"] != ["LightGBMModel", "XGBoostModel"]
        assert out["strategies"] != [
            "StockPickerAgent", "MomentumStrategy", "MeanReversionStrategy"
        ]
        assert "note" in out

    def test_trace_unknown_factor_lists_candidates(self, server):
        out = _payload(_call(server, "trace_feature_usage", {"feature_id": "nope_xyz"}))
        assert "error" in out
        assert out["available_count"] > 0
        assert out["sample_available"]


class TestNoFabricatedIC:
    def test_never_returns_seeded_fake_ic(self, server, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        first = _payload(_call(server, "check_ic_decay", {"feature_name": "KMID"}))
        second = _payload(_call(server, "check_ic_decay", {"feature_name": "KMID"}))
        # 无数据时必须报错,不能返回种子 42 的固定假数
        assert "error" in first, "无数据时返回了 IC 数值,这是编造"
        assert "ic_mean" not in first
        assert first.get("status") in {"failed", "no_data"}
        assert first == second

    def test_forbidden_magic_icir(self, server, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        blob = _text(_call(server, "check_ic_decay", {"feature_name": "KMID"}))
        # rng(42) 生成的固定值
        assert "3.29" not in blob
        assert "estimated_no_data" not in blob


class TestFactorNameResolution:
    def test_loose_match(self, server):
        out = _payload(_call(server, "get_feature", {"name": "kmid"}))
        assert out["feature_name"] == "KMID"

    def test_feat_prefix_stripped(self, server):
        out = _payload(_call(server, "get_feature", {"name": "feat-KMID"}))
        assert out["feature_name"] == "KMID"

    def test_unknown_lists_candidates(self, server):
        out = _payload(_call(server, "get_feature", {"name": "momentum_5"}))
        assert "error" in out
        assert out["available_count"] > 0
        assert out["sample_available"]


class TestErrorMessagesDoNotLeakInternals:
    def test_missing_args_hide_method_names(self, server):
        resp = asyncio.run(
            server.handle_request({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "get_feature", "arguments": {}},
            })
        )
        msg = resp["error"]["message"]
        assert "_tool_get_feature" not in msg
        assert "ForgeMindMCPServer" not in msg
        assert resp["error"]["code"] == -32602


class TestExtendedStrategiesAreComplete:
    def test_every_extended_strategy_has_generate_signal(self):
        for name, cls in list_strategies().items():
            assert "generate_signal" in vars(cls), f"{name} 是空壳,缺 generate_signal"

    def test_portfolio_strategies_not_shells(self):
        for name in ("MaxSharpe", "RiskParity"):
            assert "generate_signal" in vars(list_strategies()[name])

    def test_max_sharpe_weights_sum_to_one(self):
        import numpy as np
        import pandas as pd

        from forgemind.core.strategies.extended_library import MaxSharpe

        rng = np.random.default_rng(0)
        dates = pd.date_range("2024-01-01", periods=300)
        df = pd.DataFrame({
            "date": np.repeat(dates, 3),
            "symbol": ["A", "B", "C"] * 300,
            "close": 100 + np.cumsum(rng.normal(0, 1, 900)),
        })
        w = MaxSharpe(lookback=60).compute_weights(df)
        sums = w.sum(axis=1).dropna()
        active = sums[sums > 1e-9]
        assert len(active) > 0, "MaxSharpe 从未产生任何权重"
        assert np.allclose(active.to_numpy(), 1.0, atol=1e-6), "权重没有归一化到 1"


class TestStrategyAdapter:
    def test_adapter_converts_series_to_entries_exits(self):
        import numpy as np
        import pandas as pd

        from forgemind.core.strategies.adapter import build_extended_strategy

        strat = build_extended_strategy("TimeSeriesMomentum")
        idx = pd.date_range("2024-01-01", periods=200)
        rng = np.random.default_rng(1)
        close = 100 + np.cumsum(rng.normal(0, 1, 200))
        df = pd.DataFrame({
            "date": idx, "symbol": "X", "close": close,
            "open": close, "high": close + 1, "low": close - 1,
            "volume": 1_000_000.0,
        })
        sig = strat.generate_signals(df)
        assert "entries" in sig.columns
        assert "exits" in sig.columns
        assert sig["entries"].dtype == bool
        assert len(sig) == len(df)
