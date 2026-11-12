# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""MCP 失败必须走 isError 那条通道,不能装成成功的结果。

MCP 规范把失败分成两条:调用本身不合法(未知工具、参数非法)走 JSON-RPC
错误;**工具跑起来了但工作失败**(因子不存在、策略不存在、取数失败、
参数取值不合法)必须放进 result 并标 isError —— host 才会把它回灌给
模型,模型自己改参数重试。

工具内部有一十几处直接返回 {"error": ...}。以前框架把这种返回一律包成
"成功的结果",失败原因只混在一段 JSON 文本里:协议层看不出失败,host 与
模型都可能把它当成正常数据继续走 —— 失败通道等于没接上。

这里验三件事:
  * 框架层:返回体带 error ⇒ 标 isError;不带 error(比如"没有数据")
    ⇒ 不标 —— "没有数据"是工具正常跑完的回答,标成失败会让模型以为
    工具坏了。
  * 真工具:拿真参数调会失败的那些,确认都落在 isError 上。
  * 真 stdio:起真的子进程、真的按行发 JSON-RPC,确认标志一路传出去。
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "forgemind"))

from forgemind.mcp.server import ForgeMindMCPServer  # noqa: E402


def _server() -> ForgeMindMCPServer:
    return ForgeMindMCPServer()


def _call(srv: ForgeMindMCPServer, name: str, arguments: dict) -> dict:
    return asyncio.run(srv.handle_request({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }))


class TestFrameworkMarksFailures:
    """框架层只判一次:返回体带 error 就是失败"""

    def test_error_key_is_marked_as_failure(self):
        srv = _server()

        async def _failed(**kwargs):
            return {"error": "因子不存在", "available_count": 3}

        srv.handlers["tool/get_feature"] = _failed
        resp = _call(srv, "get_feature", {"name": "x"})
        assert "error" not in resp, resp
        assert resp["result"].get("isError") is True, resp
        assert "因子不存在" in resp["result"]["content"][0]["text"]

    def test_no_data_is_not_a_failure(self):
        """"没有数据"是工具正常跑完的回答,不是工具坏了"""
        srv = _server()

        async def _no_data(**kwargs):
            return {"status": "no_data", "symbol": "600519",
                    "message": "本地没有 600519 的 K 线,先跑 forgemind etl。"}

        srv.handlers["tool/list_factor_ic"] = _no_data
        resp = _call(srv, "list_factor_ic", {})
        assert "error" not in resp, resp
        assert not resp["result"].get("isError"), (
            f"没有数据被当成了失败: {resp}")

    def test_empty_error_value_is_not_a_failure(self):
        srv = _server()

        async def _ok(**kwargs):
            return {"error": "", "status": "ok"}

        srv.handlers["tool/query_portfolio"] = _ok
        resp = _call(srv, "query_portfolio", {})
        assert not resp["result"].get("isError"), resp


class TestRealToolsReportFailures:
    """真工具带上会失败的参数,确认都落在 isError 上"""

    @pytest.mark.parametrize(
        "tool,arguments,fragment",
        [
            ("get_feature", {"name": "压根不存在的因子"}, "not found"),
            ("trace_feature_usage", {"feature_id": "压根不存在的因子"}, "not found"),
            ("run_backtest", {"strategy": "压根不存在的策略", "symbol": "600519",
                              "start": "2024-01-01", "end": "2024-06-30"}, "未知策略"),
            ("output_signal", {"symbol": "600519", "side": "FOO",
                               "confidence": 0.5, "rationale": "探针"}, "side"),
            ("get_kline", {"symbol": ""}, "symbol"),
        ],
    )
    def test_failure_is_flagged_and_readable(self, tool, arguments, fragment):
        srv = _server()
        resp = _call(srv, tool, arguments)
        assert "error" not in resp, (
            f"{tool} 的失败走了协议错误通道,模型看不到原因: {resp.get('error')}")
        result = resp["result"]
        assert result.get("isError") is True, (
            f"{tool} 失败了却没有标 isError,失败被当成正常结果: {result}")
        text = result["content"][0]["text"]
        assert fragment in text, f"{tool} 的失败原因里看不到 {fragment}: {text}"

    def test_no_data_tool_is_not_flagged(self):
        """没有本地行情时,list_factor_ic 报的是"没有数据",不是失败"""
        srv = _server()
        resp = _call(srv, "list_factor_ic", {"symbol": "600519", "window_days": 20})
        assert "error" not in resp, resp
        result = resp["result"]
        payload = json.loads(result["content"][0]["text"])
        if payload.get("status") == "no_data":
            assert not result.get("isError"), (
                f"没有数据被当成失败: {result}")


class TestFailuresDoNotLeakExceptionNames:
    """失败原因要留给模型,但异常类名是内部实现,不该出现在文字里。

    活证据(2026-11-12):接口的响应里写着"读不到本地行情(CatalogException)"
    —— 读的人看到的是 DuckDB 的异常类名,只会以为程序坏了,而程序没坏,
    只是还没拉数据。

    失败原因本身必须留着(模型要靠它调整参数重试),去掉的只是类名。
    """

    def _assert_no_exception_name(self, text: str, where: str) -> None:
        import re

        hits = re.findall(r"\b[A-Z][A-Za-z0-9]*(?:Error|Exception)\b", text)
        assert not hits, f"{where} 的文字里有异常类名 {hits}: {text[:300]}"

    def test_generic_failure_text_has_no_exception_name(self):
        """工具抛异常时,框架给的那段话不能带类名"""
        srv = _server()

        def _boom(**_arguments):
            raise RuntimeError("内部炸了")

        # 用真的注册口挂上去:只塞 handlers 的话,工具不在清单里,请求
        # 会在参数校验那一步就被拒,压根走不到失败分支 —— 用例看着通过,
        # 实际什么都没验。
        srv._tool("boom", "故意炸的工具", {"type": "object", "properties": {}}, _boom)
        resp = _call(srv, "boom", {})
        assert resp["result"].get("isError") is True, resp
        text = resp["result"]["content"][0]["text"]
        assert "内部炸了" in text, f"失败原因丢了,模型没法据此重试: {text}"
        self._assert_no_exception_name(text, "工具失败")

    @pytest.mark.parametrize(
        "tool,arguments",
        [
            ("get_feature", {"name": "压根不存在的因子"}),
            ("run_backtest", {"strategy": "压根不存在的策略", "symbol": "600519",
                              "start": "2024-01-01", "end": "2024-06-30"}),
            ("get_kline", {"symbol": ""}),
        ],
    )
    def test_tool_failures_have_no_exception_name(self, tool, arguments):
        srv = _server()
        resp = _call(srv, tool, arguments)
        result = resp["result"]
        text = result["content"][0]["text"]
        self._assert_no_exception_name(text, f"{tool} 的失败")


class TestStdioTransportCarriesTheFlag:
    """真 stdio:起子进程、按行发 JSON-RPC,标志要一路传出去"""

    @staticmethod
    def _run_over_stdio(tool: str, arguments: dict) -> dict:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO)
        env["PYTHONSAFEPATH"] = "1"
        env["FORGEMIND_LOG_LEVEL"] = "ERROR"
        proc = subprocess.Popen(
            [sys.executable, "-m", "forgemind.mcp.server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env=env, cwd=str(REPO),
        )
        try:
            proc.stdin.write(json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            }, ensure_ascii=False) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
            assert line, "服务端没有响应"
            return json.loads(line)
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()

    def test_failure_over_stdio_is_flagged(self):
        resp = self._run_over_stdio("get_feature", {"name": "压根不存在的因子"})
        assert "error" not in resp, resp
        assert resp["result"].get("isError") is True, resp
        assert "not found" in resp["result"]["content"][0]["text"]

    def test_stdout_carries_only_json_rpc(self):
        """stdout 上只能有 JSON-RPC 响应 —— 日志混进来客户端就解析不了"""
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO)
        env["PYTHONSAFEPATH"] = "1"
        proc = subprocess.Popen(
            [sys.executable, "-m", "forgemind.mcp.server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env=env, cwd=str(REPO),
        )
        try:
            proc.stdin.write(json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {},
            }) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
            payload = json.loads(line)  # 解析不了就说明 stdout 上混了别的东西
            assert "result" in payload, payload
            assert payload["result"]["tools"], payload
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
