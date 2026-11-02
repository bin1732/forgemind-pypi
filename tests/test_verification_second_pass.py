# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""第二层验证:用**不同的方法**复核第一层已覆盖的功能

为什么要这一层:同一个测试跑两遍不等于验证两次 —— 它只会以同样方式
以同样盲点通过。这里刻意换一条验证路径:

  第一层 (tests/test_*.py)      第二层 (本文件)
  ------------------------     ------------------------------------
  直接调用函数返回值            经 CLI / HTTP / stdio 端到端
  断言数值                     断言用户看得见的输出文本
  构造对象                     走真实入口 + 真实协议
  验证"算得对"                验证"用得顺、说得清"

真实已修复的坑证明这层不可省:
  * Sortino 公式错了 15%  —— 第一层没断言,第二层对拍 empyrical 才发现
  * 未平仓持仓报 Trades: 0 —— 单测全绿,CLI 一跑就自相矛盾
  * OTLP 导出微秒而非纳秒 —— 没有任何测试碰过时间单位
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

from _path_setup import child_env, prefer_source_tree  # noqa: E402

prefer_source_tree()


def _child_env(**extra):
    """子进程环境:按统一策略摆好导入路径。

    默认把源码树放在最前,否则子进程 import 的是 venv 里已安装的旧副本,
    拿它的输出来跟源码断言比对,会得出"版本号不一致"之类的假结论。
    "验装出来的那份"那一档反过来 —— 子进程也该 import 到装好的发行包。
    """
    return child_env(**extra)


def run_cli(*args, timeout=120):
    """经 console_scripts 入口跑,而不是直接调函数"""
    out = subprocess.run(
        [sys.executable, "-m", "forgemind.cli", *args],
        capture_output=True, text=True, timeout=timeout, cwd="/tmp",
        env=_child_env(),
    )
    return out.returncode, (out.stdout or "") + (out.stderr or "")


class TestCliOutputIsCleanAndTruthful:
    """第二层:CLI 输出必须干净、且与内部数字一致"""

    def test_info_reports_real_version(self):
        import forgemind

        rc, out = run_cli("info")
        assert rc == 0, out
        assert forgemind.__version__ in out, "info 未显示真实版本号"

    def test_no_json_log_noise_on_stdout(self):
        """日志必须走 stderr;stdout 只留用户输出

        :structlog 写 stdout,`forgemind agent` 的结果里混进
        十几行 JSON 事件。

        关键:必须显式开 INFO。CLI 默认 WARNING 会把日志全滤掉,
        那样即使 logger 指回 stdout 测试也照样通过 —— 本轮就已修复,
        注入 bug 后测试毫无反应。开了 INFO 才真正检验 stdout 的纯净度。
        """
        import subprocess

        for level in ("info", "INFO"):
            out = subprocess.run(
                [sys.executable, "-m", "forgemind.cli", "backtest",
                 "--start", "2024-01-01", "--end", "2024-06-01"],
                capture_output=True, text=True, timeout=120, cwd="/tmp",
                env=_child_env(FORGEMIND_LOG_LEVEL=level),
            )
            combined = (out.stdout or "") + (out.stderr or "")
            assert out.returncode == 0, combined
            assert "Total Return" in (out.stdout or ""), "stdout 缺少用户结果"
            assert '"event"' not in (out.stdout or ""), (
                f"level={level} 时 stdout 混入了结构化日志")
            assert '"level"' not in (out.stdout or ""), (
                f"level={level} 时 stdout 混入了日志级别字段")
            # 反向确认:日志确实产生了(否则上面的断言是空转)
            assert '"event"' in (out.stderr or ""), (
                f"level={level} 时 stderr 反而没有日志 —— 断言可能空转")

    def test_backtest_reports_consistent_trade_count(self):
        """有非零收益就不能报 0 笔交易

        :只给 entry 不给 exit 时交易完全不进列表,
        报出 "Total Return 50.76% / Trades: 0" 的自相矛盾结果。
        """
        rc, out = run_cli("backtest", "--strategy", "CrossSectionalMomentum",
                          "--start", "2024-01-01", "--end", "2024-12-31")
        assert rc == 0, out
        ret = _num(out, "Total Return:")
        trades = _num(out, "Trades:")
        if abs(ret) > 1e-6:
            assert trades > 0, f"收益 {ret} 非零却报 {trades} 笔交易"

    def test_open_position_forced_close_is_visible_in_trades(self):
        """期末持仓必须计入交易 —— 直接查 _extract_trades 的返回

        :只给 entry 不给 exit 时该笔完全不进 trade 列表,
        CLI 于是报 "Total Return 50.76% / Trades: 0"。第一层只断言了
        CLI 文本,这里再从数据侧确认一次。
        """
        import numpy as np
        import pandas as pd

        from forgemind.core.backtest.engine import SimpleBacktestEngine

        n = 200
        idx = pd.date_range("2024-01-01", periods=n)
        sig = pd.DataFrame({"entries": [False] * 5 + [True] + [False] * (n - 6),
                            "exits": [False] * n}, index=idx)
        close = 100 * np.exp(np.cumsum(np.random.default_rng(1).normal(0.001, 0.01, n)))
        df = pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                           "close": close, "volume": 1_000_000}, index=idx)
        eng = SimpleBacktestEngine(initial_capital=100_000.0)
        eq = eng._simulate_equity(df, sig)
        trades = eng._extract_trades(df, sig, eq)
        ret = float(eq.iloc[-1] / eq.iloc[0] - 1)
        assert len(trades) == 1, f"未平仓持仓未被计入: {trades}"
        assert trades[0].get("forced_close") is True
        assert len(trades) > 0 or abs(ret) < 1e-9

    def test_log_level_env_is_case_insensitive(self):
        """FORGEMIND_LOG_LEVEL=info(小写)不应崩

        :只接受大写字面量,小写直接抛 pydantic ValidationError 堆栈。
        """

        out = subprocess.run(
            [sys.executable, "-m", "forgemind.cli", "info"],
            capture_output=True, text=True, timeout=60, cwd="/tmp",
            env=_child_env(FORGEMIND_LOG_LEVEL="info"),
        )
        assert "ValidationError" not in (out.stderr or ""), "小写 log_level 仍崩溃"
        assert out.returncode == 0

    def test_signal_command_states_no_broker(self):
        rc, out = run_cli("signal")
        assert rc == 0, out
        assert "no broker" in out.lower() or "research-layer" in out.lower()


def _num(text: str, label: str) -> float:
    for line in text.splitlines():
        if line.strip().startswith(label):
            v = line.split(label, 1)[1].strip().rstrip("%")
            try:
                return float(v)
            except ValueError:
                return 0.0
    return 0.0


class TestMcpOverRealProtocol:
    """第二层:MCP 必须经真实 JSON-RPC 协议,而非直接调 handler"""

    def test_tools_list_over_stdio(self):
        payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
        proc = subprocess.run(
            [sys.executable, "-m", "forgemind.mcp.server"],
            input=payload, capture_output=True, text=True, timeout=90, cwd="/tmp",
            env=_child_env(),
        )
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        assert lines, "stdio 模式无任何响应"
        first = json.loads(lines[0])  # 解析失败即协议被污染
        tools = first["result"]["tools"]
        names = {t["name"] for t in tools}
        # 硬编码数量会因新增 MCP 工具而失真,须与真实注册表一致。
        # 下限之外的数量须与真实注册表一致。
        from forgemind.core.factors import get_all_factors  # noqa: F401
        from forgemind.mcp.server import ForgeMindMCPServer

        expected = set(ForgeMindMCPServer().tools)
        assert len(names) >= 8, f"工具数不少于 8,实际 {len(names)}: {names}"
        assert names == expected, (
            f"协议暴露的工具与注册表不一致:\n"
            f"  仅协议有: {names - expected}\n  仅注册表有: {expected - names}")
        assert {"query_portfolio", "get_feature", "trace_feature_usage",
                "get_kline"} <= names

    def test_query_portfolio_over_protocol_has_no_fake_data(self):
        payload = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "query_portfolio", "arguments": {}},
        }) + "\n"
        proc = subprocess.run(
            [sys.executable, "-m", "forgemind.mcp.server"],
            input=payload, capture_output=True, text=True, timeout=90, cwd="/tmp",
            env=_child_env(),
        )
        resp = json.loads(proc.stdout.splitlines()[0])
        text = resp["result"]["content"][0]["text"]
        assert "80000" not in text, "返回了硬编码的 cash"
        assert "200000" not in text, "返回了硬编码的 equity"
        data = json.loads(text)
        assert data["status"] in ("ok", "empty"), data

    def test_check_ic_decay_never_invents_numbers(self):
        """无数据时必须报错,不能用 rng(42) 编一个 ICIR=3.3"""
        payload = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "check_ic_decay", "arguments": {"feature_name": "KMID"}},
        }) + "\n"
        proc = subprocess.run(
            [sys.executable, "-m", "forgemind.mcp.server"],
            input=payload, capture_output=True, text=True, timeout=120, cwd="/tmp",
            env=_child_env(),
        )
        resp = json.loads(proc.stdout.splitlines()[0])
        text = resp["result"]["content"][0]["text"]
        assert "3.29" not in text, "仍在返回 rng(42) 生成的固定假 ICIR"
        if "icir" in text:
            # 若给了数值,必须带明确的数据来源标记
            assert "no_data" in text or "failed" in text, f"无标记的 ICIR: {text[:100]}"


class TestApiThroughHttp:
    """第二层:API 必须经真实 HTTP,而非 TestClient"""

    @staticmethod
    def _serve(port=8094):
        code = (
            "from forgemind.api.main import app\n"
            "import uvicorn\n"
            f"uvicorn.run(app, host='127.0.0.1', port={port}, log_level='error')\n"
        )
        p = subprocess.Popen([sys.executable, "-c", code], cwd="/tmp", env=_child_env(),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import time
        for _ in range(40):
            try:
                import urllib.request
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
                return p
            except Exception:
                time.sleep(0.5)
        p.terminate()
        pytest.skip("API server 未能启动")

    def test_endpoints_and_validation_over_http(self):
        import urllib.error
        import urllib.request

        port = 8094
        proc = self._serve(port)
        base = f"http://127.0.0.1:{port}"
        try:
            for ep in ("/health", "/api/v1/info", "/mcp/tools/list"):
                with urllib.request.urlopen(base + ep, timeout=30) as r:
                    assert r.status == 200, ep

            for body in ({"start_date": "bad", "end_date": "2024-06-01"},
                         {"start_date": "2024-06-01", "end_date": "2024-01-01"},
                         {"start_date": "2024-01-01", "end_date": "2024-06-01",
                          "fast_period": 50, "slow_period": 10}):
                req = urllib.request.Request(
                    base + "/api/v1/backtest/run",
                    data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json"}, method="POST")
                with pytest.raises(urllib.error.HTTPError) as ei:
                    urllib.request.urlopen(req, timeout=30)
                assert ei.value.code == 422, f"{body} -> {ei.value.code}"

            with urllib.request.urlopen(base + "/api/v1/health/services", timeout=30) as r:
                text = r.read().decode()
            for leak in ("127.0", "::1", "password", "Traceback"):
                assert leak not in text, f"泄露 {leak}"
        finally:
            proc.terminate()
            proc.wait(timeout=15)


class TestNumericCorrectnessSecondPass:
    """第二层:对第一层同样的指标,用**独立参考实现**再对一次"""

    def test_sharpe_matches_manual_formula(self):
        import numpy as np
        import pandas as pd

        from forgemind.core.backtest.engine import SimpleBacktestEngine
        from forgemind.core.strategies.base import MovingAverageCrossStrategy

        g = np.random.default_rng(2024)
        n = 400
        close = 100 * np.exp(np.cumsum(g.normal(0.0006, 0.015, n)))
        df = pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                           "close": close, "volume": 1_000_000},
                          index=pd.date_range("2024-01-01", periods=n))
        strat = MovingAverageCrossStrategy(parameters={"fast_period": 5, "slow_period": 20})
        eng = SimpleBacktestEngine(initial_capital=100_000.0)
        res = eng.run(strat, df)
        eq = eng._simulate_equity(df, strat.generate_signals(df))
        # 注意 ddof:pandas Series.std() 默认 ddof=1,numpy 默认 ddof=0。
        # 引擎用 pandas 口径,这里必须一致,否则会得到看似不一致的假警报。
        r = eq.pct_change().dropna()
        manual = float(r.mean() / r.std() * np.sqrt(252))
        assert res.sharpe == pytest.approx(manual, abs=1e-9)
        manual_dd = float(((eq / eq.cummax()) - 1).min())
        assert res.max_drawdown == pytest.approx(manual_dd, abs=1e-9)

    def test_sortino_second_pass_against_manual(self):
        import numpy as np

        from forgemind.core.backtest.engine import sortino_ratio

        for seed in (5, 55, 555):
            r = np.random.default_rng(seed).normal(0.0005, 0.011, 400)
            manual = float(r.mean() / np.sqrt(np.mean(np.minimum(r, 0.0) ** 2))
                            * np.sqrt(252))
            assert sortino_ratio(r) == pytest.approx(manual, abs=1e-12)
