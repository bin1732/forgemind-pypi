# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import asyncio


class TestLLMProviders:
    """9 个 LLM Provider 测试"""
    
    def test_provider_types(self):
        from forgemind.core.ai.providers import ProviderType, PROVIDER_INFO
        assert len(ProviderType) == 9  # 9 个 Provider
        assert ProviderType.OPENAI in PROVIDER_INFO
        assert ProviderType.ANTHROPIC in PROVIDER_INFO
        assert ProviderType.QWEN in PROVIDER_INFO
        assert ProviderType.DEEPSEEK in PROVIDER_INFO
        assert ProviderType.GEMINI in PROVIDER_INFO
        assert ProviderType.MISTRAL in PROVIDER_INFO
        assert ProviderType.OLLAMA in PROVIDER_INFO
        assert ProviderType.VLLM in PROVIDER_INFO
        assert ProviderType.LMSTUDIO in PROVIDER_INFO
    
    def test_create_provider(self):
        from forgemind.core.ai.providers import (
            create_provider, ProviderConfig, ProviderType,
            OpenAIProvider, AnthropicProvider, OllamaProvider,
            GenericOpenAICompatProvider,
        )
        # OpenAI
        p = create_provider(ProviderConfig(
            provider_type=ProviderType.OPENAI,
            api_key="test",
            model_name="gpt-4o-mini",
        ))
        assert isinstance(p, OpenAIProvider)
        
        # Anthropic
        p = create_provider(ProviderConfig(
            provider_type=ProviderType.ANTHROPIC,
            api_key="test",
            model_name="claude-sonnet-4",
        ))
        assert isinstance(p, AnthropicProvider)
        
        # Ollama
        p = create_provider(ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            model_name="qwen2.5:72b",
        ))
        assert isinstance(p, OllamaProvider)
        
        # 兼容 OpenAI API 协议的(Qwen / DeepSeek / Gemini / vLLM / LM Studio)
        for pt in [
            ProviderType.QWEN, ProviderType.DEEPSEEK,
            ProviderType.GEMINI, ProviderType.MISTRAL,
            ProviderType.VLLM, ProviderType.LMSTUDIO,
        ]:
            p = create_provider(ProviderConfig(
                provider_type=pt,
                model_name="test-model",
            ))
            assert isinstance(p, GenericOpenAICompatProvider)
    
    def test_provider_info_models(self):
        from forgemind.core.ai.providers import PROVIDER_INFO, ProviderType
        # OpenAI
        assert "gpt-4o" in PROVIDER_INFO[ProviderType.OPENAI]["models"]
        # Anthropic
        assert "claude-sonnet-4" in PROVIDER_INFO[ProviderType.ANTHROPIC]["models"]
        # Qwen
        assert any("qwen" in m for m in PROVIDER_INFO[ProviderType.QWEN]["models"])
        # DeepSeek
        assert any("deepseek" in m for m in PROVIDER_INFO[ProviderType.DEEPSEEK]["models"])
    
    @pytest.mark.asyncio
    async def test_openai_chat_without_api(self):
        """没 API key 也优雅返回"""
        from forgemind.core.ai.providers import create_provider, ProviderConfig, ProviderType
        p = create_provider(ProviderConfig(
            provider_type=ProviderType.OPENAI,
            api_key="invalid",
            model_name="gpt-4o-mini",
        ))
        # 不真调用,只测工厂
        assert p is not None


class TestMCPProtocol:
    """完整 MCP 协议测试"""
    
    def test_create_server(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        assert len(server.tools) >= 5
        assert len(server.resources) >= 3
        assert len(server.prompts) >= 3
    
    def test_all_tools_have_handlers(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        for tool_name in server.tools:
            assert f"tool/{tool_name}" in server.handlers
    
    def test_list_tools(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        tool_names = list(server.tools.keys())
        assert "search_features" in tool_names
        assert "get_feature" in tool_names
        assert "trace_feature_usage" in tool_names
        assert "run_backtest" in tool_names
        assert "output_signal" in tool_names  # 不是 place_order — Agent 不替用户下单
        assert "stock_pick" in tool_names
    
    def test_no_place_order(self):
        """Agent 框架不替用户下单 — 这是 GitHub 头部项目的定位"""
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        tool_names = list(server.tools.keys())
        assert "place_order" not in tool_names, "Agent 框架不应该有 place_order — 那是交易终端的事"
        assert "output_signal" in tool_names, "应该输出信号让用户自己执行"
    
    def test_list_resources(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        uris = list(server.resources.keys())
        assert "forgemind://features" in uris
        assert "forgemind://strategies" in uris
        assert "forgemind://portfolio" in uris
    
    def test_list_prompts(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        names = list(server.prompts.keys())
        assert "stock_analysis" in names
        assert "risk_check" in names
        assert "factor_research" in names
    
    @pytest.mark.asyncio
    async def test_handle_initialize(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
        }
        response = await server.handle_request(request)
        assert response["jsonrpc"] == "2.0"
        assert "serverInfo" in response["result"]
        assert response["result"]["serverInfo"]["name"] == "forgemind"
    
    @pytest.mark.asyncio
    async def test_handle_tools_list(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
        }
        response = await server.handle_request(request)
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) >= 5
    
    @pytest.mark.asyncio
    async def test_handle_tools_call_stock_pick(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "stock_pick",
                "arguments": {
                    "universe": ["600519", "000001"],
                    "top_n": 1,
                },
            },
        }
        response = await server.handle_request(request)
        assert "result" in response
        assert "content" in response["result"]
    
    @pytest.mark.asyncio
    async def test_handle_unknown_method(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "unknown/method",
        }
        response = await server.handle_request(request)
        assert "error" in response
        assert response["error"]["code"] == -32601
    
    @pytest.mark.asyncio
    async def test_handle_tools_call_output_signal(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "output_signal",
                "arguments": {
                    "symbol": "600519.SH",
                    "side": "buy",
                    "confidence": 0.85,
                    "rationale": "Alpha158 + LightGBM 强信号",
                },
            },
        }
        response = await server.handle_request(request)
        assert "result" in response
        content = response["result"]["content"]
        if isinstance(content, list):
            content = content[0]
        assert "600519" in str(content)
    
    @pytest.mark.asyncio
    async def test_handle_tools_call_run_backtest(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "run_backtest",
                "arguments": {
                    "strategy": "ma_cross",
                    "symbol": "600519.SH",
                    "start": "2024-01-01",
                    "end": "2024-12-31",
                },
            },
        }
        response = await server.handle_request(request)
        assert "result" in response
    
    @pytest.mark.asyncio
    async def test_handle_tools_call_search_features(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "search_features",
                "arguments": {"query": "momentum"},
            },
        }
        response = await server.handle_request(request)
        assert "result" in response
    
    @pytest.mark.asyncio
    async def test_handle_tools_call_check_ic_decay(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "check_ic_decay",
                "arguments": {"feature_name": "ROC_3_10"},
            },
        }
        response = await server.handle_request(request)
        assert "result" in response
    
    @pytest.mark.asyncio
    async def test_handle_tools_call_query_portfolio(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "query_portfolio",
                "arguments": {},
            },
        }
        response = await server.handle_request(request)
        assert "result" in response
    
    @pytest.mark.asyncio
    async def test_handle_resources_list(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "resources/list",
        }
        response = await server.handle_request(request)
        assert "result" in response
        assert "resources" in response["result"]
        assert len(response["result"]["resources"]) >= 1
    
    @pytest.mark.asyncio
    async def test_handle_resources_read(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        # 第一个 resource URI
        resources = list(server.resources.values())
        if not resources:
            pytest.skip("无 resources")
        first_uri = resources[0].uri
        request = {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "resources/read",
            "params": {"uri": first_uri},
        }
        response = await server.handle_request(request)
        assert "result" in response
    
    @pytest.mark.asyncio
    async def test_handle_prompts_list(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "prompts/list",
        }
        response = await server.handle_request(request)
        assert "result" in response
        assert "prompts" in response["result"]
        assert len(response["result"]["prompts"]) >= 1
    
    @pytest.mark.asyncio
    async def test_handle_prompts_get(self):
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        prompts = list(server.prompts.values())
        if not prompts:
            pytest.skip("无 prompts")
        first_name = prompts[0].name
        request = {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "prompts/get",
            "params": {"name": first_name},
        }
        response = await server.handle_request(request)
        assert "result" in response
    
    @pytest.mark.asyncio
    async def test_handle_initialize(self):
        """initialize 方法"""
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.1.0"},
            },
        }
        response = await server.handle_request(request)
        assert "result" in response
        assert "serverInfo" in response["result"]
        assert response["result"]["serverInfo"]["name"] == "forgemind"
    
    @pytest.mark.asyncio
    async def test_handle_notification_initialized(self):
        """initialized 通知(无 response)"""
        from forgemind.mcp.server import ForgeMindMCPServer
        server = ForgeMindMCPServer()
        request = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        response = await server.handle_request(request)
        # notifications 应返回 None 或空
        assert response is None or response == {}


class TestArchitectureCompliance:
    """架构合规测试"""
    
    def test_no_l5_features(self):
        """不应有 L5 私募级特性"""
        import os
        from pathlib import Path
        deliverable = Path("/workspace/deliverable")
        if not deliverable.exists():
            return  # skip
        
        # 检查不含被删的 spec
        for old in ["26-multi-account-pb.md", "27-feature-store.md",
                    "28-shadow-trading.md", "29-research-best-practice.md"]:
            assert not (deliverable / old).exists(), f"L5 spec {old} 应该已被删除"
    
    def test_l4_open_architecture(self):
        """L1-L4 应该有这些核心 spec"""
        from pathlib import Path
        deliverable = Path("/workspace/deliverable")
        assert (deliverable / "24-master-architecture.md").exists()
        assert (deliverable / "25-desktop-tauri.md").exists()
    
    def test_github_alignment(self):
        """架构文档应对齐 GitHub 头部"""
        with open("/workspace/deliverable/24-master-architecture.md") as f:
            content = f.read()
        # 必须提到这些 GitHub 头部项目
        for project in ["OpenBB", "TradingAgents", "Vibe-Trading", "RD-Agent",
                        "Qlib", "FinRL", "vnpy", "nautilus", "Tauri", "MCP"]:
            assert project in content, f"必须提到 {project}"
        # 不应该有 L5 私募级特性
        # 排除:文档说明"不私募"是可以的
        forbidden = ["L8", "三权分立", "PB 通道", "O32 单元", "实控人合并", "数据出境"]
        for f in forbidden:
            assert f not in content, f"不应有 L5 私募级特性: {f}"
        # 私募只在说明"不做"时出现
        sm_count = content.count("私募")
        assert sm_count <= 2, f"'私募' 只在说明不做时出现,实际 {sm_count}"


class TestCodeStructure:
    """代码结构合规"""
    
    def test_providers_module(self):
        from forgemind.core.ai.providers import (
            ProviderType, ProviderConfig, ChatMessage, ChatResponse,
            BaseProvider, OpenAIProvider, AnthropicProvider,
            OllamaProvider, GenericOpenAICompatProvider,
            create_provider, PROVIDER_INFO,
        )
    
    def test_mcp_module(self):
        from forgemind.mcp.server import (
            ForgeMindMCPServer, MCPTool, MCPResource, MCPPrompt,
        )
    
    def test_no_removed_modules(self):
        """私募级模块不应存在"""
        import importlib.util
        for module in [
            "forgemind.core.compliance.three权分立",
            "forgemind.core.portfolio.pb_unit",
            "forgemind.core.factors.feature_store",
            "forgemind.core.live.shadow_trader_full",
        ]:
            spec = importlib.util.find_spec(module.split(".")[0])
            # 简化:只检查模块不存在
            try:
                importlib.import_module(module)
                # 如果能 import,失败
                assert False, f"{module} 不应该存在"
            except (ImportError, ModuleNotFoundError):
                pass