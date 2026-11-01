# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""回归测试:禁止 MCP 工具返回编造数据

本文件锁死 2026-09 审计发现的真实缺陷:
  1. query_portfolio 永远返回一份硬编码的 持仓/现金/权益
  2. trace_feature_usage 对任何因子返回同一份硬编码的关联
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
        # 没有快照时必须如实为空,不得出现硬编码的数字
        assert out["status"] == "empty"
        assert out["positions"] == []
        assert out["cash"] is None
        assert out["total_equity"] is None

    def test_no_magic_numbers(self, server, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        blob = _text(_call(server, "query_portfolio", {}))
        # 这三个值不得硬编码出现
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
        # 硬编码值清单
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


class TestPortfolioStrategiesOnMultiSymbolData:
    """回归:组合策略在真实多标的长表上必须真的换仓

    :_weights_to_row_signal 缺失,MaxSharpe/RiskParity 返回的是
    日期索引的 Series,调用方 reindex 到行索引后全变 NaN → 信号恒为 0。
    单标的回测看不出来,只有多标的横截面数据才暴露。
    """

    @staticmethod
    def _multi_symbol_df(n_symbols=10, n_days=300, seed=7):
        import numpy as np
        import pandas as pd

        rng = np.random.default_rng(seed)
        rows = []
        for i in range(n_symbols):
            drift = rng.normal(0.0004, 0.001)
            close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.015, n_days)))
            for d, c in zip(pd.date_range("2024-01-01", periods=n_days), close):
                rows.append({
                    "date": d, "symbol": f"S{i:03d}", "close": c,
                    "open": c, "high": c * 1.01, "low": c * 0.99, "volume": 1e6,
                })
        return pd.DataFrame(rows)

    @pytest.mark.parametrize("name", ["MaxSharpe", "RiskParity"])
    def test_signal_length_matches_input_rows(self, name):
        df = self._multi_symbol_df()
        from forgemind.core.strategies.extended_library import list_strategies

        sig = list_strategies()[name](lookback=60).generate_signal(df)
        assert len(sig) == len(df), f"{name} 信号长度 {len(sig)} != 输入 {len(df)}"

    @pytest.mark.parametrize("name", ["MaxSharpe", "RiskParity"])
    def test_actually_switches_positions(self, name):
        df = self._multi_symbol_df()
        from forgemind.core.strategies.extended_library import list_strategies

        sig = list_strategies()[name](lookback=60).generate_signal(df)
        assert sig.sum() > 0, f"{name} 在真实多标的上从未给出任何信号"
        assert sig.nunique() > 1, f"{name} 信号恒定,没有换仓"

    @pytest.mark.parametrize("name", ["MaxSharpe", "RiskParity"])
    def test_adapter_produces_entries_and_exits(self, name):
        from forgemind.core.strategies.adapter import build_extended_strategy

        df = self._multi_symbol_df()
        sig = build_extended_strategy(name, lookback=60).generate_signals(df)
        assert sig["entries"].sum() > 0
        assert len(sig) == len(df)


class TestWindowsConsoleEncoding:
    """回归:Windows 控制台默认 GBK,打印中文/emoji 会 UnicodeEncodeError

    真实故障:Windows 上 `forgemind signal` 直接崩,中文用户装完即不可用。
    只有在真正的 Windows runner 上跑二进制才会暴露。
    """

    def test_cli_forces_utf8_stdio(self):
        import io
        import sys

        from forgemind import cli

        # 模拟 Windows 控制台:charmap 编码 + 不支持 reconfigure 的旧流
        class LegacyStream(io.StringIO):
            encoding = "cp936"

            def reconfigure(self, **kwargs):
                raise ValueError("不支持 reconfigure")

        old_out, old_err = sys.stdout, sys.stderr
        fake = LegacyStream()
        sys.stdout = fake
        sys.stderr = LegacyStream()
        try:
            cli._force_utf8_stdio()  # 不应抛异常
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    def test_helper_is_idempotent(self):
        from forgemind import cli

        cli._force_utf8_stdio()
        cli._force_utf8_stdio()  # 重复调用不应炸

    def test_mcp_main_declares_same_guard(self):
        import inspect

        from forgemind.mcp import server as mcp_server

        src = inspect.getsource(mcp_server.main)
        assert "reconfigure" in src, "MCP 入口缺少 UTF-8 保护,Windows 上会崩"


class TestMCPStdioTransport:
    """回归:MCP stdio 传输必须真的能跑,且 stdout 只能是 JSON-RPC

    :
      1. `python -m forgemind.mcp.server` 只打印一段横幅就退出(0.5s),
         根本不读 stdin —— 对外宣传的 MCP 能力实际不可用
      2. structlog 日志与横幅都写 stdout,真实客户端第一包就
         json.decoder.JSONDecodeError: Extra data
    """

    @staticmethod
    def _rpc(reqs):
        """起子进程,按行发 JSON-RPC,返回 (stdout 行, stderr, 退出码)"""
        import json
        import os
        import subprocess
        import sys

        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(sys.path)
        payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in reqs)
        proc = subprocess.run(
            [sys.executable, "-m", "forgemind.mcp.server"],
            input=payload, capture_output=True, text=True, timeout=90, env=env,
        )
        return proc

    def test_stdio_responds_and_survives_multiple_calls(self):
        proc = self._rpc([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 2, "method": "resources/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "search_features", "arguments": {"query": "momentum"}}},
        ])
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        assert len(lines) == 3, f"期望 3 条 JSON-RPC 响应,得到 {len(lines)}: {lines[:2]}"
        import json
        r1 = json.loads(lines[0])
        # 不硬编码数量:与注册表比对,新增工具(get_kline)后仍成立
        from forgemind.mcp.server import ForgeMindMCPServer

        assert len(r1["result"]["tools"]) == len(ForgeMindMCPServer().tools)
        r2 = json.loads(lines[1])
        # 不硬编码:与 server 自身 resource 数同步,新增 resource 后仍成立
        assert len(r2["result"]["resources"]) == len(ForgeMindMCPServer().resources)
        r3 = json.loads(lines[2])
        assert "result" in r3

    def test_stdout_is_pure_jsonrpc(self):
        """stdout 上出现任何非 JSON 行都会让真实客户端解析失败"""
        import json

        proc = self._rpc([{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}])
        for ln in proc.stdout.splitlines():
            if not ln.strip():
                continue
            try:
                json.loads(ln)
            except json.JSONDecodeError as exc:
                pytest.fail(f"stdout 被非 JSON 内容污染: {ln[:120]!r} ({exc})")

    def test_banner_goes_to_stderr(self):
        proc = self._rpc([{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}])
        assert "stdio" in proc.stderr.lower(), "启动横幅应写 stderr"
        assert "stdio" not in proc.stdout.lower(), "横幅不得出现在 stdout"

    def test_invalid_json_returns_parse_error(self):
        import json
        import os
        import subprocess
        import sys

        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(sys.path)
        proc = subprocess.run(
            [sys.executable, "-m", "forgemind.mcp.server"],
            input="{not json}\n", capture_output=True, text=True, timeout=60, env=env,
        )
        resp = json.loads(proc.stdout.strip().splitlines()[0])
        assert resp["error"]["code"] == -32700

    def test_notification_gets_no_response(self):
        import json

        proc = self._rpc([
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 9, "method": "tools/list"},
        ])
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        assert len(lines) == 1, f"notification 不应产生响应,实际 {len(lines)} 条"
        assert json.loads(lines[0])["id"] == 9


class TestModelsPackageIsLazy:
    """回归:models 包必须是惰性导入

    :__init__ eager import lightgbm_model / xgboost_model,
    导致任何一次 models 导入都拉起 lightgbm+sklearn+xgboost(已验证 ~4.5s),
    而模块 docstring 声称 "light-weight imports by default" —— 与实际不符。
    """

    def test_importing_package_does_not_pull_heavy_deps(self):
        import subprocess
        import sys

        code = (
            "import sys; import forgemind.core.models; "
            "heavy=[m for m in ('lightgbm','sklearn','xgboost','torch') "
            "if m in sys.modules]; "
            "print(','.join(heavy) if heavy else 'NONE')"
        )
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
        )
        loaded = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else "ERR"
        assert loaded == "NONE", f"仅仅 import 包就拉起了重依赖: {loaded}"

    def test_attribute_still_resolves_lazily(self):
        from forgemind.core.models import LightGBMModel

        assert LightGBMModel is not None

    def test_unknown_attribute_raises(self):
        import forgemind.core.models as m

        with pytest.raises(AttributeError):
            _ = m.NoSuchModel

    def test_dir_lists_public_api(self):
        import forgemind.core.models as m

        d = dir(m)
        assert "LightGBMModel" in d
        assert "TransformerModel" in d
