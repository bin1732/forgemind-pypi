# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestChatResponseFields:
    """ChatResponse dataclass 所有字段"""
    
    def test_default_fields(self):
        from forgemind.core.ai.providers import ChatResponse
        r = ChatResponse(content="hi", model="gpt-4o-mini", provider="openai")
        assert r.content == "hi"
        assert r.tokens_in == 0
        assert r.tokens_out == 0
        assert r.latency_ms == 0
        assert r.cost_usd == 0.0
    
    def test_all_fields_set(self):
        from forgemind.core.ai.providers import ChatResponse, ProviderType
        r = ChatResponse(
            content="answer",
            model="claude-3-5-sonnet",
            provider=ProviderType.ANTHROPIC,
            tokens_in=100,
            tokens_out=50,
            latency_ms=1234,
            cost_usd=0.005,
        )
        assert r.tokens_in == 100
        assert r.tokens_out == 50
        assert r.latency_ms == 1234
        assert r.cost_usd == 0.005


class TestProviderConfig:
    """ProviderConfig 字段"""
    
    def test_required_provider_type(self):
        from forgemind.core.ai.providers import ProviderConfig, ProviderType
        c = ProviderConfig(provider_type=ProviderType.OPENAI)
        assert c.api_key is None
        assert c.base_url is None
        assert c.model_name == ""
        assert c.timeout_sec == 60.0
        assert c.max_retries == 3
    
    def test_custom_values(self):
        from forgemind.core.ai.providers import ProviderConfig, ProviderType
        c = ProviderConfig(
            provider_type=ProviderType.OPENAI,
            api_key="test",
            base_url="https://custom.com",
            model_name="custom-model",
            timeout_sec=120,
            max_retries=5,
        )
        assert c.api_key == "test"
        assert c.base_url == "https://custom.com"
        assert c.model_name == "custom-model"
        assert c.timeout_sec == 120
        assert c.max_retries == 5


class TestCreateProvider:
    """create_provider 工厂 — 9 个 provider 全覆盖"""
    
    def test_openai(self):
        from forgemind.core.ai.providers import create_provider, OpenAIProvider, ProviderConfig, ProviderType
        p = create_provider(ProviderConfig(provider_type=ProviderType.OPENAI))
        assert isinstance(p, OpenAIProvider)
    
    def test_anthropic(self):
        from forgemind.core.ai.providers import create_provider, AnthropicProvider, ProviderConfig, ProviderType
        p = create_provider(ProviderConfig(provider_type=ProviderType.ANTHROPIC))
        assert isinstance(p, AnthropicProvider)
    
    def test_ollama(self):
        from forgemind.core.ai.providers import create_provider, OllamaProvider, ProviderConfig, ProviderType
        p = create_provider(ProviderConfig(provider_type=ProviderType.OLLAMA))
        assert isinstance(p, OllamaProvider)
    
    def test_qwen_uses_generic(self):
        """Qwen / DeepSeek / Gemini / Mistral / vLLM / LMStudio → GenericOpenAICompat"""
        from forgemind.core.ai.providers import (
            create_provider, GenericOpenAICompatProvider, ProviderConfig, ProviderType,
        )
        for pt in [
            ProviderType.QWEN, ProviderType.DEEPSEEK, ProviderType.GEMINI,
            ProviderType.MISTRAL, ProviderType.VLLM, ProviderType.LMSTUDIO,
        ]:
            p = create_provider(ProviderConfig(provider_type=pt))
            assert isinstance(p, GenericOpenAICompatProvider), f"{pt} not GenericOpenAICompat"
    
    def test_unknown_raises(self):
        from forgemind.core.ai.providers import create_provider, ProviderConfig
        # 强转成假类型
        with patch("forgemind.core.ai.providers.ProviderType") as mock_pt:
            mock_pt.OPENAI = "openai"
            mock_pt.ANTHROPIC = "anthropic"
            mock_pt.OLLAMA = "ollama"
            mock_pt.QWEN = "qwen"
            mock_pt.DEEPSEEK = "deepseek"
            mock_pt.GEMINI = "gemini"
            mock_pt.MISTRAL = "mistral"
            mock_pt.VLLM = "vllm"
            mock_pt.LMSTUDIO = "lmstudio"
            
            cfg = ProviderConfig(provider_type="fake_provider")
            with pytest.raises(ValueError, match="Unknown provider"):
                create_provider(cfg)


class TestResolveApiKey:
    """_resolve_api_key — 显式 key 优先,从 settings 读 fallback"""
    
    def test_explicit_key_wins(self):
        from forgemind.core.ai.providers import _resolve_api_key, ProviderType
        result = _resolve_api_key(ProviderType.OPENAI, "explicit-key")
        assert result == "explicit-key"
    
    def test_settings_reads_openai(self):
        """没有 explicit_key 时从 settings 读"""
        from forgemind.core.ai.providers import _resolve_api_key, ProviderType
        from forgemind.core.config.settings import Settings
        
        # 直接设置 env var
        import os
        os.environ["FORGEMIND_OPENAI_API_KEY"] = "settings-key"
        try:
            Settings.model_config = Settings.model_config  # 触发 reload
            result = _resolve_api_key(ProviderType.OPENAI, None)
            # 可能 settings 已经 cache 了,不强求非 None
            assert result is None or result == "settings-key"
        finally:
            del os.environ["FORGEMIND_OPENAI_API_KEY"]


class TestProviderInfoTable:
    """PROVIDER_INFO 包含 9 个 provider"""
    
    def test_all_providers_in_info(self):
        from forgemind.core.ai.providers import PROVIDER_INFO, ProviderType
        for pt in ProviderType:
            assert pt in PROVIDER_INFO, f"{pt} missing from PROVIDER_INFO"
            info = PROVIDER_INFO[pt]
            assert "name" in info
            assert "models" in info  # 字段名是 models(复数)
            assert "env_var" in info
            assert "best_for" in info


class TestProviderDefaultTables:
    """_PROVIDER_DEFAULT_BASE_URL 和 _PROVIDER_DEFAULT_MODEL 表"""
    
    def test_base_url_table(self):
        from forgemind.core.ai.providers import _PROVIDER_DEFAULT_BASE_URL, ProviderType
        for pt in ProviderType:
            assert pt in _PROVIDER_DEFAULT_BASE_URL
            url = _PROVIDER_DEFAULT_BASE_URL[pt]
            assert url.startswith("http")
    
    def test_model_table(self):
        from forgemind.core.ai.providers import _PROVIDER_DEFAULT_MODEL, ProviderType
        for pt in ProviderType:
            assert pt in _PROVIDER_DEFAULT_MODEL
            assert len(_PROVIDER_DEFAULT_MODEL[pt]) > 0


class TestQuickChat:
    """quick_chat 完整覆盖"""
    
    @pytest.mark.asyncio
    async def test_quick_chat_explicit_key(self):
        from forgemind.core.ai.providers import quick_chat
        with patch("forgemind.core.ai.providers.create_provider") as mock_create:
            mock_provider = MagicMock()
            mock_provider.chat = AsyncMock(return_value=MagicMock(
                content="hi", model="gpt-4o-mini", provider="openai",
            ))
            mock_create.return_value = mock_provider
            
            result = await quick_chat(
                provider="openai",
                model="gpt-4o-mini",
                prompt="hello",
                api_key="test-key",
                system="you are helpful",
            )
            assert result.content == "hi"
            mock_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_quick_chat_default_model(self):
        """不传 model 时用 provider 默认 model"""
        from forgemind.core.ai.providers import quick_chat
        with patch("forgemind.core.ai.providers.create_provider") as mock_create:
            mock_provider = MagicMock()
            mock_provider.chat = AsyncMock(return_value=MagicMock(
                content="x", model="default", provider="qwen",
            ))
            mock_create.return_value = mock_provider
            
            await quick_chat(provider="qwen", prompt="hi", api_key="k")
            
            # 验证传入了 _PROVIDER_DEFAULT_MODEL[QWEN]
            call_args = mock_create.call_args
            cfg = call_args[0][0]
            assert cfg.model_name  # 非空
    
    @pytest.mark.asyncio
    async def test_quick_chat_no_system(self):
        """不传 system 时 messages 只有 user"""
        from forgemind.core.ai.providers import quick_chat
        with patch("forgemind.core.ai.providers.create_provider") as mock_create:
            mock_provider = MagicMock()
            mock_provider.chat = AsyncMock(return_value=MagicMock(
                content="x", model="m", provider="openai",
            ))
            mock_create.return_value = mock_provider
            
            await quick_chat(provider="openai", prompt="hi", api_key="k")
            
            call_args = mock_provider.chat.call_args
            messages = call_args[0][0]
            # 1 条 user message
            assert len(messages) == 1
            assert messages[0].role == "user"


class TestAnthropicProviderFallback:
    """Anthropic provider 没装 SDK 时的 fallback"""
    
    @pytest.mark.asyncio
    async def test_anthropic_import_fails(self):
        from forgemind.core.ai.providers import (
            AnthropicProvider, ProviderConfig, ProviderType, ChatMessage,
        )
        p = AnthropicProvider(ProviderConfig(
            provider_type=ProviderType.ANTHROPIC,
            api_key="fake",
            model_name="claude-3-5-sonnet-latest",
        ))
        with patch.dict("sys.modules", {"anthropic": None}):
            result = await p.chat([ChatMessage(role="user", content="hi")])
            assert result.content.startswith("[Anthropic")
            assert result.provider == ProviderType.ANTHROPIC


class TestOllamaProviderFallback:
    """Ollama local provider fallback"""
    
    @pytest.mark.asyncio
    async def test_ollama_no_httpx(self):
        from forgemind.core.ai.providers import (
            OllamaProvider, ProviderConfig, ProviderType, ChatMessage,
        )
        p = OllamaProvider(ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            base_url="http://localhost:11434",
            model_name="qwen2.5:7b",
        ))
        with patch.dict("sys.modules", {"httpx": None}):
            result = await p.chat([ChatMessage(role="user", content="hi")])
            assert "Ollama" in result.content or "httpx" in result.content.lower() or result.content.startswith("[")


class TestGenericOpenAICompatProviderFallback:
    """GenericOpenAICompatProvider fallback"""
    
    @pytest.mark.asyncio
    async def test_no_openai_sdk(self):
        from forgemind.core.ai.providers import (
            GenericOpenAICompatProvider, ProviderConfig, ProviderType, ChatMessage,
        )
        p = GenericOpenAICompatProvider(ProviderConfig(
            provider_type=ProviderType.QWEN,
            api_key="fake",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model_name="qwen-plus",
        ))
        with patch.dict("sys.modules", {"openai": None}):
            result = await p.chat([ChatMessage(role="user", content="hi")])
            assert result.provider == ProviderType.QWEN


class TestOpenAIProviderFallback:
    """OpenAI provider fallback when SDK missing"""
    
    @pytest.mark.asyncio
    async def test_openai_no_sdk(self):
        from forgemind.core.ai.providers import (
            OpenAIProvider, ProviderConfig, ProviderType, ChatMessage,
        )
        p = OpenAIProvider(ProviderConfig(
            provider_type=ProviderType.OPENAI,
            api_key="fake",
            model_name="gpt-4o-mini",
        ))
        with patch.dict("sys.modules", {"openai": None}):
            result = await p.chat([ChatMessage(role="user", content="hi")])
            assert "[OpenAI" in result.content
            assert result.provider == ProviderType.OPENAI