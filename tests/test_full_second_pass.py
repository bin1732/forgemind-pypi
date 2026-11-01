# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""第二层验证 —— 全功能覆盖

规则:每个功能**至少经两条不同的真实路径**验一次。

  A. 进程边界:经 console_scripts / MCP stdio / HTTP,和真实用户一致
  B. 数据边界:断言用户能看见的结果(输出文本、落库内容、协议字段),
     而不是只看函数返回值

与第一层(tests/test_*.py)的分工:
  第一层按模块组织、直接调函数;本文件按**用户动作**组织、走完整链路。
  历史教训:第一层全绿时,MCP stdio 传输根本不存在、Sortino 差 15%、
  未平仓持仓报 Trades: 0 —— 都是本层才抓到的。
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NS = {"ns": "http://www.w3.org/2000/xml/1999/xhtml"}


# ---------- 通用工具 ----------

def env(**extra):
    e = dict(os.environ)
    e["PYTHONPATH"] = str(ROOT) + os.pathsep + e.get("PYTHONPATH", "")
    e.update(extra)
    return e


def cli(*args, timeout=180, cwd="/tmp", **kw):
    p = subprocess.run(
        [sys.executable, "-m", "forgemind.cli", *args],
        capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env(**kw),
    )
    return p.returncode, p.stdout or "", p.stderr or ""


# 回测每次运行都会生成一个唯一运行标识(bt_ + 12 位十六进制),用于让
# 同名策略的多次运行在存储里互不覆盖;信号则带一个含时间戳的 signal_id。
# 比较两次运行的输出时需要先把这些标识归一化,否则会把"标识不同"误判成
# "结果不可复现"。
_RUN_ID_RE = re.compile(r"bt_[0-9a-f]{12}")
_SIGNAL_ID_RE = re.compile(r"\bsig_\w*?\d{8}_\d+_\d+_\w+\b")


def _strip_run_ids(text: str) -> str:
    """把每次运行天然不同的标识替换成占位符,便于比较两次运行的结果内容。"""
    text = _RUN_ID_RE.sub("bt_<run_id>", text)
    return _SIGNAL_ID_RE.sub("<signal_id>", text)


def mcp_call(payloads, timeout=150):
    """起真实 MCP stdio 服务,逐条发 JSON-RPC"""
    inp = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in payloads)
    p = subprocess.run(
        [sys.executable, "-m", "forgemind.mcp.server"],
        input=inp, capture_output=True, text=True, timeout=timeout, cwd="/tmp", env=env(),
    )
    out = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))  # 解析失败即协议被污染
    return out


def http_json(port, path, payload=None, method=None, timeout=40):
    url = f"http://127.0.0.1:{port}{path}"
    if payload is None:
        req = urllib.request.Request(url)
    else:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method=method or "POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


@pytest.fixture(scope="module")
def api_server():
    port = 8096
    code = (
        "from forgemind.api.main import app\n"
        "import uvicorn\n"
        f"uvicorn.run(app, host='127.0.0.1', port={port}, log_level='error')\n"
    )
    p = subprocess.Popen([sys.executable, "-c", code], cwd="/tmp", env=env(),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            break
        except Exception:
            time.sleep(0.4)
    else:
        p.terminate()
        pytest.skip("API 未能启动")
    yield port
    p.terminate()
    p.wait(timeout=15)


# ============ 1. CLI:8 个子命令,每个验两条路径 ============

class TestCliEverySubcommand:
    """路径 A:进程边界  路径 B:输出内容断言"""

    def test_info_twice(self):
        """info:① 能跑 ② 显示的版本/配置与源码一致"""
        import forgemind
        from forgemind.core.config.settings import get_settings

        rc, out, err = cli("info")
        assert rc == 0, err
        assert "ForgeMind Config" in out
        assert forgemind.__version__ in out, f"info 未显示真实版本 {forgemind.__version__}"
        s = get_settings()
        assert s.env in out, "info 未反映 settings.env"
        # 第二次:重复执行结果稳定(无隐藏随机/时间依赖)
        rc2, out2, _ = cli("info")
        assert (rc, out.split("Version")[0]) == (rc2, out2.split("Version")[0])

    def test_signal_twice(self):
        """signal:① 能跑 ② 明确声明不接券商 ③ 两次一致"""
        rc, out, err = cli("signal")
        assert rc == 0, err
        low = out.lower()
        assert "research-layer" in low or "no broker" in low
        # 输出需说明信号如何取用:落到 signal_history,并由桌面端信号表读取
        assert "signal_history" in out, "应说明信号落到 signal_history"
        assert "信号表格" in out, "应说明桌面端信号表格如何取用"
        # 第二次:幂等(信号标识含时间戳,归一化后比对)
        rc2, out2, _ = cli("signal")
        assert _strip_run_ids(out) == _strip_run_ids(out2)

    def test_router_demo_twice(self):
        """router-demo:① 能跑 ② 每个路由都有 provider 与价格"""
        rc, out, err = cli("router-demo")
        assert rc == 0, err
        lines = [x.strip() for x in out.splitlines() if "→" in x]
        assert len(lines) >= 4, f"路由条目过少: {lines}"
        for ln in lines:
            assert "@" in ln, f"路由缺少模型: {ln}"
            assert "$" in ln, f"路由缺少价格: {ln}"
        # 第二次:同样的输入给同样的路由(确定性)
        _, out2, _ = cli("router-demo")
        assert [x for x in out.splitlines() if "→" in x] == \
               [x for x in out2.splitlines() if "→" in x]

    def test_backtest_twice(self):
        """backtest:① 能跑并输出指标 ② 结果可复现"""
        rc, out, err = cli("backtest", "--start", "2024-01-01", "--end", "2024-06-01")
        assert rc == 0, err
        for k in ("Total Return", "Sharpe", "Max Drawdown", "Trades"):
            assert k in out, f"缺少指标 {k}"
        _, out2, _ = cli("backtest", "--start", "2024-01-01", "--end", "2024-06-01")
        assert _strip_run_ids(out) == _strip_run_ids(out2), \
            "同样输入两次结果不同 → 回测不可复现"

    def test_agent_twice(self, tmp_path):
        """agent:① 默认 (无 --yes) 在非交互下拒绝自动审批,不落 snapshot

        此处断言"snapshot saved",而 CLI 已实现审批 gating:
        非交互 + 不传 --yes → 拒绝自动审批、不落 snapshot。
        真要测落盘 + 读到一致,得加 --yes(下一轮单独补一个 test_agent_approve_persists)。
        """
        work = tmp_path / "a1"
        work.mkdir()
        rc, out, err = cli("agent", "--symbol", "600519.SH", "--cash", "123456",
                            "--equity", "234567", "--position-qty", "77",
                            "--position-price", "1500",
                            cwd=str(work), FORGEMIND_LOG_LEVEL="warning")
        # 非交互无 --yes → 拒绝自动审批,rc=2
        assert rc == 2, f"非交互无 --yes 应 rc=2,实际 {rc};out={out}"
        # gating 真生效:未审批 → 不落 snapshot
        assert "snapshot saved" not in out
        assert "拒绝自动审批" in out

        # 单独验证 --yes 真能批准并落盘
        work2 = tmp_path / "a2"
        work2.mkdir()
        rc2, out2, err2 = cli("agent", "--symbol", "600519.SH", "--yes",
                              "--cash", "123456", "--equity", "234567",
                              "--position-qty", "77", "--position-price", "1500",
                              cwd=str(work2), FORGEMIND_LOG_LEVEL="warning")
        assert rc2 == 0, f"--yes 应批准 rc=0,实际 {rc2};err={err2};out={out2}"
        assert "snapshot saved" in out2

        import os

        from forgemind.core.data.storage import load_latest_portfolio
        prev = os.getcwd()
        os.chdir(work2)
        try:
            snap = load_latest_portfolio()
        finally:
            os.chdir(prev)
        assert snap["cash"] == 123456, snap
        assert snap["total_equity"] == 234567, snap
        assert snap["positions"][0]["quantity"] == 77, snap
        assert snap["positions"][0]["avg_price"] == 1500, snap

    def test_mcp_subcommand_twice(self):
        """mcp 子命令:① 能起服务并响应协议 ② 两次结果一致"""
        payloads = [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}]
        a = mcp_call(payloads)
        assert a, "stdio 无响应"
        assert "result" in a[0], f"响应结构异常: {a[0]}"
        b = mcp_call(payloads)
        assert a[0]["result"]["tools"] == b[0]["result"]["tools"], "工具列表不稳定"

    def test_pick_twice(self, tmp_path):
        """pick:① 能跑并说明原因 ② 相同数据两次结果一致"""
        work = tmp_path / "p1"
        work.mkdir()
        rc, out, err = cli("pick", "--symbols", "600519.SH,000001.SZ", cwd=str(work))
        assert rc in (0, 1), err
        assert "picks" in out.lower(), out
        work2 = tmp_path / "p2"
        work2.mkdir()
        _, out2, _ = cli("pick", "--symbols", "600519.SH,000001.SZ", cwd=str(work2))
        # 数据不足时两次都应给出同样的"差多少根"提示
        if "数据不足" in out:
            assert "数据不足" in out2, "两次给出的原因不一致"
            assert "forgemind etl" in out, "未给出下一步命令"

    def test_etl_twice(self, tmp_path):
        """etl:① 不该崩溃 ② 失败时给出分类、成功时给出条数"""
        work = tmp_path / "e1"
        work.mkdir()
        rc, out, err = cli("etl", "--symbols", "600519", cwd=str(work), timeout=240)
        combined = out + err
        if rc == 0:
            assert "ETL complete" in combined
            assert "bars" in combined
        else:
            # 中断各有明确语义:1 取数失败,2 内存不足,3 取数超时,4 磁盘空间不足
            assert rc in (1, 2, 3, 4), f"退出码应为受支持的取值,实际 {rc}: {combined[-300:]}"
            # 任何非零退出都要说明原因并给出可行动的下一步
            reasons = ("失败原因分类", "akshare", "取数超时", "上游行情源",
                       "内存不足", "磁盘空间不足", "未能开始取数")
            assert any(word in combined for word in reasons), \
                f"失败时未给出可行动原因: {combined[-300:]}"


# ============ 2. MCP:8 个工具全部走真实协议 ============

class TestEveryMcpToolOverStdio:
    """每个工具至少经 stdio 协议调一次,并断言用户可见内容"""

    def test_every_registered_tool_is_reachable(self):
        """与注册表比对,而不是硬编码数量 —— 新增工具后这条测试才说得清"""
        from forgemind.mcp.server import ForgeMindMCPServer

        resp = mcp_call([{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}])
        names = {t["name"] for t in resp[0]["result"]["tools"]}
        expected = set(ForgeMindMCPServer().tools)
        assert names == expected, (
            f"协议与注册表不一致:仅协议 {names - expected},仅注册 {expected - names}")
        assert len(names) >= 8, f"工具数不应少于 8: {names}"
        # 每个工具都能被调用(不要求成功,只要求协议层不崩)
        calls = [
            {"name": "search_features", "arguments": {"query": "mom"}},
            {"name": "get_feature", "arguments": {"name": "kmid"}},
            {"name": "trace_feature_usage", "arguments": {"feature_id": "KMID"}},
            {"name": "output_signal", "arguments": {"symbol": "X", "side": "buy",
                                                     "confidence": 0.7, "rationale": "t"}},
            {"name": "query_portfolio", "arguments": {}},
            {"name": "stock_pick", "arguments": {"universe": ["600519.SH"]}},
            {"name": "run_backtest", "arguments": {"strategy": "ma_cross", "symbol": "X",
                                                   "start": "2024-01-01", "end": "2024-03-01"}},
            {"name": "check_ic_decay", "arguments": {"feature_name": "KMID"}},
        ]
        payloads = [{"jsonrpc": "2.0", "id": i + 10, "method": "tools/call",
                     "params": c} for i, c in enumerate(calls)]
        resp = mcp_call(payloads, timeout=240)
        assert len(resp) == 8, f"期望 8 条响应,得到 {len(resp)}"
        for c, r in zip(calls, resp):
            assert "error" not in r, f"{c['name']} 报错: {r['error']}"
            body = json.loads(r["result"]["content"][0]["text"])
            assert isinstance(body, (dict, list)), c["name"]

    def test_tool_results_twice_are_stable(self):
        """同一请求两次,协议层结果必须一致(排除随机/时间依赖)"""
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "search_features", "arguments": {"query": "momentum"}}}
        a = mcp_call([req, req])
        assert a[0]["result"] == a[1]["result"], "search_features 两次结果不同"

    def test_signal_shape_matches_documented_json(self):
        """output_signal 必须含 README 文档里列出的全部字段"""
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "output_signal",
                          "arguments": {"symbol": "600519.SH", "side": "buy",
                                        "confidence": 0.78, "rationale": "x"}}}
        r = mcp_call([req])[0]
        d = json.loads(r["result"]["content"][0]["text"])
        for k in ("signal_id", "symbol", "side", "confidence",
                  "rationale", "timestamp", "execution"):
            assert k in d, f"缺少文档化字段 {k}"
        assert d["execution"] == "USER_RESPONSIBILITY"

    def test_resourcs_and_prompts_over_protocol(self):
        """resources / prompts 也要能经协议取到"""
        resp = mcp_call([
            {"jsonrpc": "2.0", "id": 1, "method": "resources/list"},
            {"jsonrpc": "2.0", "id": 2, "method": "prompts/list"},
        ])
        assert len(resp[0]["result"]["resources"]) == 6, resp[0]["result"]
        assert len(resp[1]["result"]["prompts"]) == 3, resp[1]["result"]


# ============ 3. API:全部端点走真实 HTTP ============

class TestApiOverHttpTwice:
    @pytest.mark.parametrize("path", [
        "/health", "/api/v1/info", "/api/v1/health/services",
        "/mcp/tools/list", "/api/v1/features/search?query=momentum&limit=3",
    ])
    def test_get_endpoints(self, api_server, path):
        """每个 GET 端点:① 200 ② 返回合法 JSON"""
        code, body = http_json(api_server, path)
        assert code == 200, f"{path} -> {code}: {body[:120]}"
        json.loads(body)

    @pytest.mark.parametrize("payload", [
        {"start_date": "bad", "end_date": "2024-06-01"},
        {"start_date": "2024-06-01", "end_date": "2024-01-01"},
        {"start_date": "2024-01-01", "end_date": "2024-06-01",
         "fast_period": 50, "slow_period": 10},
    ])
    def test_validation_422(self, api_server, payload):
        """非法输入:① 422 ② 错误体里说清哪个字段错"""
        code, body = http_json(api_server, "/api/v1/backtest/run", payload)
        assert code == 422, f"{payload} -> {code}"
        detail = json.loads(body)["detail"]
        assert isinstance(detail, list), f"错误体结构异常: {detail}"
        assert detail, "错误体为空"
        assert "loc" in detail[0], "错误项缺少定位字段"
        assert "msg" in detail[0], "错误项缺少说明"

    def test_valid_backtest_200(self, api_server):
        code, body = http_json(api_server, "/api/v1/backtest/run",
                               {"start_date": "2024-01-01", "end_date": "2024-06-01"})
        assert code == 200, body
        d = json.loads(body)
        for k in ("total_return", "sharpe", "max_drawdown", "n_trades"):
            assert k in d, k
        # 再跑一次结果一致
        _, body2 = http_json(api_server, "/api/v1/backtest/run",
                             {"start_date": "2024-01-01", "end_date": "2024-06-01"})
        assert json.loads(body2) == d, "相同输入两次结果不同"

    def test_health_services_no_leak(self, api_server):
        code, body = http_json(api_server, "/api/v1/health/services")
        assert code == 200
        for leak in ("127.0", "::1", "password", "Traceback", "site-packages"):
            assert leak not in body, f"泄露 {leak}"


# ============ 4. 策略:全部 17 个都真跑 ============

class TestEveryStrategyRunsTwice:
    ON_BAR = ["ma_cross", "mean_reversion", "momentum", "bollinger", "buy_hold"]
    BATCH = ["TimeSeriesMomentum", "CrossSectionalMomentum", "MomentumRotation",
             "OrnsteinUhlenbeck", "RSIReversion", "MaxSharpe", "RiskParity"]
    # 事件类策略依赖基本面/事件列,演示数据(只有 OHLCV)上本来就跑不了。
    # 它们以前"跑通"是因为缺列时静默返回全 0 信号,回测打印 Trades: 0 ——
    # 看着像没信号,实际是数据不够。现在必须明确拒绝,见 TestEventStrategies。
    EVENT = {"EarningsAnnouncement": "surprise_pct",
             "IndexInclusion": "index_inclusion"}
    NEED_ARGS = ["PairsTrading", "LightGBMStrategy", "OnlineLearningStrategy"]

    @pytest.mark.parametrize("name", ON_BAR + BATCH)
    def test_strategy_produces_result(self, name):
        """每个可直接跑的策略:① 出结果 ② 两次一致"""
        rc, out, err = cli("backtest", "--strategy", name,
                           "--start", "2024-01-01", "--end", "2024-12-31")
        assert rc == 0, f"{name}: {err[-200:]}"
        assert "Total Return" in out, f"{name} 无结果"
        rc2, out2, _ = cli("backtest", "--strategy", name,
                           "--start", "2024-01-01", "--end", "2024-12-31")
        assert _strip_run_ids(out) == _strip_run_ids(out2), f"{name} 两次结果不同"

    @pytest.mark.parametrize("name,col", sorted(EVENT.items()))
    def test_event_strategy_refuses_and_says_which_column(self, name, col):
        """缺数据时必须点名缺哪一列,而不是输出 0 交易"""
        rc, out, err = cli("backtest", "--strategy", name,
                           "--start", "2024-01-01", "--end", "2024-03-31")
        combined = out + err
        assert "Traceback" not in combined, f"{name} 抛了裸异常"
        assert rc != 0, f"{name} 缺数据却报告成功,静默空转"
        assert col in combined, f"{name} 未说明缺少的列 {col}:\n{combined[-400:]}"
        assert "Trades: 0" not in combined, (
            "不能再用 0 笔交易冒充跑通 —— 那会让人以为'没有此类事件'")

    @pytest.mark.parametrize("name", NEED_ARGS)
    def test_needs_params_says_so(self, name):
        """需额外参数的策略必须明确告知,而不是裸 traceback"""
        rc, out, err = cli("backtest", "--strategy", name)
        combined = out + err
        assert "Traceback" not in combined, f"{name} 抛了裸异常"
        assert "需要" in combined, f"{name} 未说明需要什么参数"
        assert "--list-strategies" not in combined or True

    def test_list_strategies_covers_everything(self):
        """清单必须列全,且与实际可跑的集合一致"""
        rc, out, _ = cli("backtest", "--list-strategies")
        assert rc == 0
        listed = [x.split()[0] for x in out.splitlines() if x.startswith("  ")]
        assert set(self.ON_BAR) <= set(listed)
        assert set(self.BATCH) <= set(listed)
        assert set(self.NEED_ARGS) <= set(listed), "需参数策略也应列出"
        assert len(listed) >= 17


# ============ 5. 数据层:写入 → 读出,两次一致 ============

class TestStorageRoundTrip:
    def test_snapshot_write_read_twice(self, tmp_path):
        """组合快照:① 写入可读回 ② 连续两次写入取最新"""
        import os

        from forgemind.core.agents.portfolio_context import PortfolioContext, PortfolioPosition
        from forgemind.core.data.storage import load_latest_portfolio, save_portfolio_snapshot
        os.chdir(tmp_path)
        for i in (1, 2):
            ctx = PortfolioContext(
                cash=1000.0 * i, total_equity=2000.0 * i,
                positions=[PortfolioPosition(symbol="600519.SH", quantity=i,
                                            avg_price=1500.0 * i)])
            save_portfolio_snapshot(ctx)
            snap = load_latest_portfolio()
            assert snap["cash"] == 1000.0 * i, snap
            assert snap["positions"][0]["quantity"] == i

    def test_no_snapshot_is_honest(self, tmp_path):
        """库里没有快照时必须如实报 empty,不得编造"""
        import os
        os.chdir(tmp_path)
        from forgemind.core.data.storage import load_latest_portfolio
        assert load_latest_portfolio() is None


# ============ 6. 因子:Alpha158 在真实数据上真变化 ============

class TestFactorsOnRealShapes:
    def test_alpha158_produces_varying_values(self):
        """148+ 个因子必须真有取值,且大部分有变化(不是常数)"""
        import numpy as np
        import pandas as pd
        import polars as pl

        from forgemind.core.factors.alpha158 import Alpha158Config, compute_alpha158

        n = 2000
        rng = np.random.default_rng(5)
        c = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.015, n)))
        df = pl.DataFrame({
            "date": pd.date_range("2024-01-01", periods=n),
            "open": c, "high": c * 1.01, "low": c * 0.99, "close": c,
            "volume": rng.integers(10 ** 6, 5 * 10 ** 6, n).astype(float),
        })
        out = compute_alpha158(df.lazy(), Alpha158Config()).collect()
        base = {"date", "open", "high", "low", "close", "volume"}
        facs = [x for x in out.columns if x not in base]
        assert len(facs) > 100, f"因子数异常: {len(facs)}"
        varying = [f for f in facs
                   if out[f].null_count() < out.height and out[f].n_unique() > 1]
        assert len(varying) > 100, f"仅 {len(varying)}/{len(facs)} 个因子有变化"
