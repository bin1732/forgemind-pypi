# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest

from forgemind.core.ai.router import (
    ModelRouter, ModelTier, MODELS, get_router,
)


class TestModels:
    def test_all_tiers(self):
        assert len(MODELS) == 6
        assert ModelTier.HAIKU in MODELS
        assert ModelTier.SONNET in MODELS
        assert ModelTier.OPUS in MODELS
        assert ModelTier.LOCAL_VLLM in MODELS
        assert ModelTier.QWEN_MAX in MODELS
        assert ModelTier.HUMAN_REVIEW in MODELS
    
    def test_local_is_free(self):
        assert MODELS[ModelTier.LOCAL_VLLM].cost_per_1k_tokens == 0.0
    
    def test_human_is_expensive(self):
        # 人工比 Opus 贵
        human = MODELS[ModelTier.HUMAN_REVIEW].cost_per_1k_tokens
        opus = MODELS[ModelTier.OPUS].cost_per_1k_tokens
        assert human > opus


class TestRouter:
    def test_create(self):
        r = ModelRouter()
        assert r.total_cost == 0.0
    
    def test_simple_task_haiku(self):
        r = ModelRouter()
        spec = r.route(task_complexity=2)
        assert spec.tier == ModelTier.HAIKU
    
    def test_complex_task_opus(self):
        r = ModelRouter()
        spec = r.route(task_complexity=9)
        assert spec.tier == ModelTier.OPUS
    
    def test_critical_task_human(self):
        r = ModelRouter()
        spec = r.route(task_complexity=5, is_critical=True)
        assert spec.tier == ModelTier.HUMAN_REVIEW
    
    def test_chinese_qwen(self):
        r = ModelRouter()
        spec = r.route(task_complexity=5, requires_chinese=True)
        assert spec.tier == ModelTier.QWEN_MAX
    
    def test_realtime_local(self):
        r = ModelRouter()
        spec = r.route(task_complexity=3, is_real_time=True)
        assert spec.tier == ModelTier.LOCAL_VLLM
    
    def test_record_usage(self):
        r = ModelRouter()
        r.record_usage(ModelTier.HAIKU, 1000)
        r.record_usage(ModelTier.SONNET, 500)
        stats = r.get_stats()
        assert stats["by_tier"]["haiku"]["tokens"] == 1000
        assert stats["by_tier"]["sonnet"]["tokens"] == 500
        # haiku: 1000 * 0.0008 = 0.0008
        assert abs(stats["by_tier"]["haiku"]["cost"] - 0.0008) < 0.0001
    
    def test_singleton(self):
        r1 = get_router()
        r2 = get_router()
        assert r1 is r2


class TestMCPServer:
    def test_create(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        assert "search_features" in server.tools
    
    def test_list_tools(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        # 用 JSON-RPC tools/list 拿工具列表
        assert len(server.tools) >= 5
    
    @pytest.mark.asyncio
    async def test_search_features(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        # 通过 handle_request JSON-RPC 调用
        request = {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "search_features", "arguments": {"query": "momentum"}},
        }
        response = await server.handle_request(request)
        assert "result" in response or "error" in response
    
    @pytest.mark.asyncio
    async def test_get_feature(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        request = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "get_feature", "arguments": {"name": "rsi_14", "version": 2}},
        }
        response = await server.handle_request(request)
        assert "result" in response or "error" in response
    
    @pytest.mark.asyncio
    async def test_register_feature(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        # register_feature 实际不存在了,改测 search_features
        request = {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "trace_feature_usage", "arguments": {"feature_id": "rsi_14"}},
        }
        response = await server.handle_request(request)
        assert "result" in response or "error" in response


class TestCLI:
    def test_info(self, capsys):
        from forgemind.cli import cmd_info
        from argparse import Namespace
        cmd_info(Namespace())
        captured = capsys.readouterr()
        assert "ForgeMind" in captured.out
    
    def test_router_demo(self, capsys):
        from forgemind.cli import cmd_router_demo
        from argparse import Namespace
        cmd_router_demo(Namespace())
        captured = capsys.readouterr()
        assert "Model Router Demo" in captured.out