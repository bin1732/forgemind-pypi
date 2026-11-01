# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真信号落盘 + MCP forgemind://signals resource 全链路
"""
import asyncio
import json
import pytest

from forgemind.core.data.storage import save_signal, load_recent_signals
from forgemind.mcp.server import ForgeMindMCPServer


def test_save_signal_then_load_recent():
    """save_signal → load_recent_signals 真落盘可读回"""
    sid1 = save_signal("sig_test_001", "600519.SH", "BUY", 0.85, "测试 1")
    sid2 = save_signal("sig_test_002", "000001.SZ", "SELL", 0.62, "测试 2")
    assert sid1 == "sig_test_001"
    assert sid2 == "sig_test_002"

    sigs = load_recent_signals(limit=10)
    assert len(sigs) >= 2
    # 最近在前
    symbols = [s["symbol"] for s in sigs]
    assert "000001.SZ" in symbols
    assert "600519.SH" in symbols
    sides = {s["symbol"]: s["side"] for s in sigs}
    assert sides["000001.SZ"] == "SELL"
    assert sides["600519.SH"] == "BUY"
    confs = {s["symbol"]: s["confidence"] for s in sigs}
    assert abs(confs["000001.SZ"] - 0.62) < 1e-9


def test_load_recent_empty_returns_empty_list():
    """空表时 load_recent_signals 返回 [], 不抛错"""
    sigs = load_recent_signals(limit=10)
    assert isinstance(sigs, list)


@pytest.mark.asyncio
async def test_output_signal_mcp_real_persistence():
    """MCP output_signal 工具真落 DuckDB"""
    s = ForgeMindMCPServer()
    # 落 3 个不同 side
    for side, conf in [("BUY", 0.91), ("SELL", 0.45), ("HOLD", 0.50)]:
        r = await s.handle_request({
            "jsonrpc": "2.0", "id": "1", "method": "tools/call",
            "params": {"name": "output_signal", "arguments": {
                "symbol": "600519.SH", "side": side, "confidence": conf,
                "rationale": f"side={side} 测试落盘",
            }}})
        text = json.loads(r["result"]["content"][0]["text"])
        assert text["status"] == "ok"
        assert text["side"] == side
        assert text["signal_id"].startswith("sig_")

    # 读 forgemind://signals resource
    r = await s.handle_request({
        "jsonrpc": "2.0", "id": "2", "method": "resources/read",
        "params": {"uri": "forgemind://signals"},
    })
    text = json.loads(r["result"]["contents"][0]["text"])
    assert text["total"] >= 3
    sides = {x["side"] for x in text["signals"]}
    assert {"BUY", "SELL", "HOLD"} <= sides


@pytest.mark.asyncio
async def test_output_signal_validates_inputs():
    """output_signal 校验 side / confidence, 乱传要拒绝"""
    s = ForgeMindMCPServer()
    # 错 side
    r = await s.handle_request({
        "jsonrpc": "2.0", "id": "1", "method": "tools/call",
        "params": {"name": "output_signal", "arguments": {
            "symbol": "600519.SH", "side": "BUY_NOW", "confidence": 0.5,
            "rationale": "测错 side",
        }}})
    text = json.loads(r["result"]["content"][0]["text"])
    assert text["status"] == "failed"
    assert "BUY" in text["error"]  # 错误提示包含合法选项

    # 超界 confidence
    r = await s.handle_request({
        "jsonrpc": "2.0", "id": "2", "method": "tools/call",
        "params": {"name": "output_signal", "arguments": {
            "symbol": "600519.SH", "side": "BUY", "confidence": 1.5,
            "rationale": "confidence 越界",
        }}})
    text = json.loads(r["result"]["content"][0]["text"])
    assert text["status"] == "failed"
    assert "1" in text["error"]


@pytest.mark.asyncio
async def test_signals_resource_callable_each_read():
    """forgemind://signals resource 每次读都新算(不缓存陈旧值)"""
    s = ForgeMindMCPServer()
    # 第 1 次读 - 0 条
    r1 = await s.handle_request({
        "jsonrpc": "2.0", "id": "1", "method": "resources/read",
        "params": {"uri": "forgemind://signals"},
    })
    t1 = json.loads(r1["result"]["contents"][0]["text"])
    assert t1["total"] == 0

    # 落 1 条
    await s.handle_request({
        "jsonrpc": "2.0", "id": "2", "method": "tools/call",
        "params": {"name": "output_signal", "arguments": {
            "symbol": "600519.SH", "side": "BUY", "confidence": 0.7,
            "rationale": "callable 验证",
        }}})

    # 第 2 次读 - 1 条(必须新算,不是 0)
    r2 = await s.handle_request({
        "jsonrpc": "2.0", "id": "3", "method": "resources/read",
        "params": {"uri": "forgemind://signals"},
    })
    t2 = json.loads(r2["result"]["contents"][0]["text"])
    assert t2["total"] == 1
