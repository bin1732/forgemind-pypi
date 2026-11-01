# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""MCP 对外契约的回归测试。

覆盖四件容易悄悄坏掉的事:

- prompts/list 不声明参数,客户端就不知道该给提示词传什么,
  拿到的提示词里留着没替换的 {symbol}
- run_backtest 明明本地有落盘行情,却只跑随机游走 —— 引擎和指标
  都是真算的,输入却是造的,调用方会把结论当真
- 声明"确定性"的合成行情,换个进程就不一样
- 失败走了错误的通道 —— 工具执行失败必须标 isError 回灌给模型,
  抛成协议错误的话模型看不到原因,对话就断在那儿了

每个工具都带合法参数真调一遍,只返回 JSON 不算通过。
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _parse_like_javascript(text: str):
    """按 JavaScript 的 JSON.parse 规则解析。

    Python 的 json.loads 容忍 NaN / Infinity,JavaScript 不容忍。
    工具结果里带着 NaN 的话,桌面端整段解析失败 —— 界面上写"取数失败",
    而数据其实是好的。只用 json.loads 验,这种错永远测不出来。
    """
    def _reject(constant: str):
        raise ValueError(f"JSON.parse 不接受 {constant}")

    return json.loads(text, parse_constant=_reject)

# 每个工具的合法参数(取自 tools/list 声明的 required)
TOOL_CALLS = [
    ("search_features", {"query": "momentum"}),
    ("get_feature", {"name": "kmid"}),
    ("trace_feature_usage", {"feature_id": "KMID"}),
    ("run_backtest", {"strategy": "ma_cross", "symbol": "600519",
                      "start": "2024-01-01", "end": "2024-06-30"}),
    ("output_signal", {"symbol": "600519.SH", "side": "buy",
                       "confidence": 0.8, "rationale": "契约测试"}),
    ("check_ic_decay", {"feature_name": "kmid", "window_days": 30}),
    ("list_factor_ic", {"symbol": "600519", "window_days": 5}),
    ("get_kline", {"symbol": "600519", "limit": 5}),
    ("query_portfolio", {}),
    ("stock_pick", {"universe": ["600519", "000001"], "top_n": 2}),
    # 人工审批链路:准备阶段停下 → 用 thread_id 拍板
    ("agent_decide", {"symbol": "600519.SH", "cash": 100000,
                      "total_equity": 200000,
                      "positions": [{"symbol": "600519.SH", "quantity": 100,
                                     "avg_price": 1500}]}),
    ("agent_approve", {"thread_id": "contract-test", "approved": True}),
]

TOOL_CALLS_BY_NAME = dict(TOOL_CALLS)

RESOURCE_URIS = [
    "forgemind://features", "forgemind://strategies", "forgemind://symbols",
    "forgemind://signals", "forgemind://brokers", "forgemind://portfolio",
]


def _server():
    sys.path.insert(0, str(REPO))
    from forgemind.mcp.server import ForgeMindMCPServer
    return ForgeMindMCPServer()


def _legal_args(name: str, args: dict) -> dict:
    """补上必须是真值的参数。

    agent_approve 的 thread_id 必须是**真**的 —— 拿假的去调,工具会报
    "找不到待审批的决策",返回的是错误文本而不是 JSON,那测的就不是这个
    工具的正常输出了。先跑一次 agent_decide 拿真 thread_id。
    """
    if name != "agent_approve":
        return args
    import asyncio as _asyncio
    import json as _json

    srv = _server()
    resp = _asyncio.run(_call(srv, "agent_decide", TOOL_CALLS_BY_NAME["agent_decide"]))
    thread_id = _json.loads(_tool_text(resp)).get("thread_id", "")
    assert thread_id, "agent_decide 没给出 thread_id"
    return {**args, "thread_id": thread_id}


async def _call(srv, name, args):
    resp = await srv.handle_request({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": args},
    })
    return resp


def _tool_text(resp):
    assert "error" not in resp, f"调用报错: {resp.get('error')}"
    content = resp["result"]["content"]
    assert content, "没有返回内容"
    return content[0]["text"]


def _seed_klines(symbols=("600519", "000001"), days=40):
    """按 ETL 的建表路径落一份 K 线。"""
    from forgemind.core.data.storage import DuckDBStorage

    with DuckDBStorage() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS kline_daily (
                date DATE, symbol VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE,
                close DOUBLE, volume BIGINT, provider VARCHAR,
                PRIMARY KEY (date, symbol))""")
        rows = []
        for si, sym in enumerate(symbols):
            for i in range(days):
                d = date(2024, 1, 2) + timedelta(days=i)
                if d.weekday() >= 5:
                    continue
                close = 100.0 * (1 + 0.002 * (si + 1)) ** i
                rows.append((d, sym, close * 0.998, close * 1.005,
                             close * 0.995, round(close, 4), 1_000_000, "test"))
        for row in rows:
            db.execute(
                "INSERT INTO kline_daily (date, symbol, open, high, low, close, "
                "volume, provider) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", list(row))
    return len(rows)


class TestToolContract:
    """每个工具都要能真调,且不编造数据。"""

    @pytest.mark.parametrize("name,args", TOOL_CALLS, ids=[c[0] for c in TOOL_CALLS])
    def test_tool_answers_without_error(self, name, args):
        srv = _server()
        resp = asyncio.run(_call(srv, name, args))
        text = _tool_text(resp)
        assert text.strip(), f"{name} 返回空内容"
        # 编造数据防线:这些词在源码里 0 出现,只可能来自编造的内容
        for marker in ("mock data", "placeholder", "dummy", "fake_",
                       "示例数据"):
            assert marker.lower() not in text.lower(), (
                f"{name} 的返回里出现编造标记 {marker}")

    @pytest.mark.parametrize("name,args", TOOL_CALLS, ids=[c[0] for c in TOOL_CALLS])
    def test_tool_output_is_javascript_parsable_json(self, name, args):
        args = _legal_args(name, args)
        """工具结果必须能被 JavaScript 的 JSON.parse 读懂

        桌面端、浏览器端拿到的都是这段文本。Python 自己读自己写的东西
        永远读得回来,那种验法测不出 NaN 这类非法 JSON。
        """
        srv = _server()
        resp = asyncio.run(_call(srv, name, args))
        text = _tool_text(resp)
        _parse_like_javascript(text)

    def test_every_tool_is_reachable(self):
        srv = _server()
        resp = asyncio.run(srv.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}))
        names = {t["name"] for t in resp["result"]["tools"]}
        assert names == {n for n, _ in TOOL_CALLS}, (
            f"工具清单与测试覆盖不一致: {sorted(names)}")


class TestAgentToolValidation:
    """agent_decide 的输入校验 —— 说不通的组合要挡在门外

    负现金、负权益、空代码照单全收的话,后面算出来的权重与股数全是废数,
    而界面看上去还像个正常决策。口径跟 API 的 AgentRequest 一致。
    """

    @pytest.mark.parametrize(
        "args,reason",
        [
            ({"symbol": ""}, "symbol 不能为空"),
            ({"symbol": "600519.SH", "cash": -1}, "cash 必须大于 0"),
            ({"symbol": "600519.SH", "cash": 100000, "total_equity": -5},
             "total_equity 不能为负"),
            ({"symbol": "600519.SH", "cash": 100000,
              "positions": [{"symbol": "600519.SH", "quantity": -5, "avg_price": 1500}]},
             "持仓数量不能为负"),
            ({"symbol": "600519.SH", "cash": 100000,
              "positions": [{"symbol": "600519.SH", "quantity": 10, "avg_price": -3}]},
             "持仓均价不能为负"),
        ],
    )
    def test_invalid_input_is_rejected(self, args, reason):
        srv = _server()
        resp = asyncio.run(_call(srv, "agent_decide", args))
        result = resp.get("result", {})
        assert result.get("isError"), f"{args} 应当被拒绝,实际返回了结果"
        assert reason in result["content"][0]["text"], result["content"][0]["text"]


class TestResourceContract:
    @pytest.mark.parametrize("uri", RESOURCE_URIS)
    def test_resource_returns_json(self, uri):
        srv = _server()
        resp = asyncio.run(srv.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "resources/read",
            "params": {"uri": uri}}))
        assert "error" not in resp, f"{uri} 读取报错: {resp.get('error')}"
        contents = resp["result"]["contents"]
        assert contents, f"{uri} 没有内容"
        # 必须是 JavaScript 也能读懂的合法 JSON
        _parse_like_javascript(contents[0]["text"])


class TestPromptContract:
    def test_list_declares_template_arguments(self):
        """prompts/list 必须声明参数,客户端才知道要传什么"""
        srv = _server()
        resp = asyncio.run(srv.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "prompts/list", "params": {}}))
        prompts = {p["name"]: p for p in resp["result"]["prompts"]}
        assert set(prompts) == {"stock_analysis", "risk_check", "factor_research"}
        # 声明的参数必须与模板占位符一致
        # (prompts/list 不带 template,模板要从服务端对象取)
        templates = {name: p.template for name, p in srv.prompts.items()}
        for name, p in prompts.items():
            placeholders = sorted(set(re.findall(r"\{(\w+)\}", templates[name])))
            declared = sorted(a["name"] for a in p.get("arguments", []))
            if not placeholders:
                assert declared == [], f"{name} 声明了多余的参数 {declared}"
                continue
            assert declared == placeholders, (
                f"{name} 声明的参数 {declared} 与模板占位符 {placeholders} 不一致")

    def test_arguments_from_template_are_required(self):
        srv = _server()
        resp = asyncio.run(srv.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "prompts/list", "params": {}}))
        for p in resp["result"]["prompts"]:
            for arg in p.get("arguments", []):
                assert arg.get("required") is True, (
                    f"{p['name']}.{arg['name']} 不是必填")
                assert arg.get("description"), (
                    f"{p['name']}.{arg['name']} 没有说明")

    def test_get_renders_declared_arguments(self):
        """按 prompts/list 声明的参数传进去,提示词里不该留占位符"""
        srv = _server()
        resp = asyncio.run(srv.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "prompts/list", "params": {}}))
        for p in resp["result"]["prompts"]:
            args = {a["name"]: "600519" for a in p.get("arguments", [])}
            got = asyncio.run(srv.handle_request({
                "jsonrpc": "2.0", "id": 2, "method": "prompts/get",
                "params": {"name": p["name"], "arguments": args}}))
            assert "error" not in got, got.get("error")
            text = " ".join(m.get("content", {}).get("text", "")
                            for m in got["result"]["messages"])
            leftovers = re.findall(r"\{\w+\}", text)
            assert not leftovers, (
                f"{p['name']} 残留未替换的占位符 {leftovers}")


class TestRunBacktestDataSource:
    """回测必须优先用真数据,并如实标注来源"""

    def test_uses_stored_klines(self):
        n = _seed_klines()
        srv = _server()
        resp = asyncio.run(_call(srv, "run_backtest", {
            "strategy": "ma_cross", "symbol": "600519",
            "start": "2024-01-01", "end": "2024-06-30"}))
        d = json.loads(_tool_text(resp))
        assert d.get("is_real_data") is True, (
            f"本地有 {n} 根 K 线,回测却没走真数据: {d.get('data_source')}")
        assert d.get("data_source") == "duckdb_kline_daily"
        assert d.get("n_bars", 0) > 0, d
        assert "warning" not in d, "走了真数据还挂着降级警告"

    def test_symbol_with_suffix_hits_stored_rows(self):
        """库里存 6 位代码,入参带后缀也要命中"""
        _seed_klines()
        srv = _server()
        resp = asyncio.run(_call(srv, "run_backtest", {
            "strategy": "ma_cross", "symbol": "600519.SH",
            "start": "2024-01-01", "end": "2024-06-30"}))
        d = json.loads(_tool_text(resp))
        assert d.get("is_real_data") is True, (
            f"带后缀的代码没命中落盘数据: {d.get('data_source')}")

    def test_falls_back_to_synthetic_with_warning(self):
        srv = _server()
        resp = asyncio.run(_call(srv, "run_backtest", {
            "strategy": "ma_cross", "symbol": "999999",
            "start": "2024-01-01", "end": "2024-06-30"}))
        d = json.loads(_tool_text(resp))
        assert d.get("is_real_data") is False
        assert d.get("data_source") == "synthetic_random_walk"
        assert d.get("warning"), "降级到合成行情却没有声明"
        assert d.get("n_bars") == 0

    def test_synthetic_path_is_deterministic_across_processes(self):
        """声明"确定性"就要跨进程也一致。字符串 hash 每个进程加盐,不行。"""
        script = (
            "import asyncio, json, sys;"
            f"sys.path.insert(0, {str(REPO)!r});"
            "from forgemind.mcp.server import ForgeMindMCPServer;"
            "srv = ForgeMindMCPServer();"
            "r = asyncio.run(srv.handle_request({'jsonrpc':'2.0','id':1,"
            "'method':'tools/call','params':{'name':'run_backtest','arguments':"
            "{'strategy':'ma_cross','symbol':'600519','start':'2024-01-01',"
            "'end':'2024-06-30'}}}));"
            "print(json.loads(r['result']['content'][0]['text'])['sharpe'])"
        )
        env = {"PYTHONHASHSEED": "random", "PATH": "/usr/bin:/bin",
               "PYTHONPATH": str(REPO)}
        outs = []
        for _ in range(2):
            proc = subprocess.run([sys.executable, "-c", script], capture_output=True,
                                  text=True, timeout=300, env=env, cwd=str(REPO))
            assert proc.returncode == 0, proc.stderr[-400:]
            outs.append(proc.stdout.strip().splitlines()[-1])
        assert outs[0] == outs[1], f"两个进程算出的 sharpe 不一样: {outs}"


class TestErrorChannelContract:
    """MCP 把失败分成两条通道,走错通道模型就自不了纠。

    规范原文:工具跑起来但工作失败(取数失败、无数据、上游报错)必须放进
    result 并标 isError,host 才会把它回灌给模型;只有调用本身不合法
    (未知工具、参数非法)才走 JSON-RPC 错误。
    """

    @staticmethod
    def _failing_server():
        """把一个真工具的 handler 换成会抛异常的,模拟"跑了但失败" """
        srv = _server()

        async def _boom(**kwargs):
            raise RuntimeError("上游行情接口超时")

        srv.handlers["tool/get_feature"] = _boom
        return srv

    def test_execution_failure_is_reported_with_is_error(self):
        srv = self._failing_server()
        resp = asyncio.run(_call(srv, "get_feature", {"name": "kmid"}))
        assert "error" not in resp, (
            f"执行失败走了协议错误通道,模型看不到原因: {resp.get('error')}")
        result = resp["result"]
        assert result.get("isError") is True, result
        text = result["content"][0]["text"]
        assert "get_feature" in text, text
        assert "上游行情接口超时" in text, (
            f"模型看不到失败原因就没法自纠: {text}")

    def test_unknown_tool_is_a_protocol_error(self):
        """调用不合法 → 协议错误通道,客户端改调用"""
        srv = _server()
        resp = asyncio.run(srv.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "no_such_tool", "arguments": {}}}))
        assert resp.get("error", {}).get("code") == -32601, resp

    def test_invalid_arguments_are_a_protocol_error(self):
        srv = _server()
        resp = asyncio.run(srv.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "get_feature", "arguments": {"wrong": "x"}}}))
        assert resp.get("error", {}).get("code") == -32602, resp

    def test_missing_arguments_are_a_protocol_error(self):
        srv = _server()
        resp = asyncio.run(srv.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "get_feature", "arguments": {}}}))
        assert resp.get("error", {}).get("code") == -32602, resp

    def test_non_object_arguments_are_rejected(self):
        srv = _server()
        resp = asyncio.run(srv.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "get_feature", "arguments": ["not", "object"]}}))
        assert resp.get("error", {}).get("code") == -32602, resp

    def test_unknown_resource_uses_the_spec_code(self):
        """资源不存在用规范专用的 -32002;方法本身是存在的"""
        srv = _server()
        resp = asyncio.run(srv.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "resources/read",
            "params": {"uri": "forgemind://does-not-exist"}}))
        assert resp.get("error", {}).get("code") == -32002, resp
