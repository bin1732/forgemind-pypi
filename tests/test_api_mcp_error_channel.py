# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""MCP 失败在两条通道上,HTTP 适配层要把它们分开。

MCP 规范把失败分成两类:调用本身不合法(未知工具、参数非法)走 JSON-RPC
错误;工具跑起来但工作失败走 result 里的 isError 标记。前者要回 4xx,
后者在协议层是"成功的响应",但这一层是给桌面端 sidecar 用的 HTTP 适配,
那边靠状态码判断成败 —— 不翻译的话,失败会被当成正常结果显示出来。

这里两条都验一遍。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from forgemind.api import main as api_main
from forgemind.api.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _failing_server():
    """一个会失败的 MCP 服务:工具跑起来就抛异常。"""
    from forgemind.mcp.server import ForgeMindMCPServer

    srv = ForgeMindMCPServer()

    async def _boom(**kwargs):
        raise RuntimeError("上游行情接口超时")

    srv.handlers["tool/get_feature"] = _boom
    return srv


class TestMcpErrorChannelOverHttp:
    def test_execution_failure_becomes_a_server_error(self, client, monkeypatch):
        monkeypatch.setattr(api_main, "_get_mcp_server", _failing_server)
        r = client.post("/mcp/tools/call", json={
            "name": "get_feature", "arguments": {"name": "kmid"}})
        assert r.status_code == 500, r.text
        body = r.json()
        assert body["result"]["isError"] is True, body
        text = body["result"]["content"][0]["text"]
        assert "上游行情接口超时" in text, body

    def test_unknown_tool_becomes_a_client_error(self, client):
        r = client.post("/mcp/tools/call", json={
            "name": "no_such_tool", "arguments": {}})
        assert r.status_code == 400, r.text
        assert r.json()["error"]["code"] == -32601, r.text

    def test_invalid_arguments_become_a_client_error(self, client):
        r = client.post("/mcp/tools/call", json={
            "name": "get_feature", "arguments": {"wrong": "x"}})
        assert r.status_code == 400, r.text
        assert r.json()["error"]["code"] == -32602, r.text

    def test_non_object_arguments_are_rejected_before_dispatch(self, client):
        """arguments 不是对象时,请求模型就拦下了(422),压根到不了工具"""
        r = client.post("/mcp/tools/call", json={
            "name": "get_feature", "arguments": ["not", "an", "object"]})
        assert r.status_code == 422, r.text
        assert "arguments" in r.text, r.text
