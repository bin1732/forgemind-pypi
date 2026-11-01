# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _FakeDelta:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.delta = _FakeDelta(content)


class _FakeChunk:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, contents):
        self._contents = contents

    async def create(self, **kwargs):
        async def _chunks():
            for content in self._contents:
                yield _FakeChunk(content)
        return _chunks()


class _FakeChat:
    def __init__(self, contents):
        self.completions = _FakeCompletions(contents)


class _FakeOpenAIClient:
    """只实现流式调用所需的最小接口"""

    def __init__(self, contents):
        self.chat = _FakeChat(contents)


class TestStreamChat:
    """stream_chat 5 个 provider 都应能跑(真发或降级)"""

    @pytest.mark.asyncio
    async def test_openai_stream_raises_when_not_installed(self):
        """openai 未装时必须抛错,不能 yield 占位字符串

        yield 的是 "[OpenAI not installed]" —— 调用方把它当模型增量
        输出拼进结果,拿到一份看起来正常、实则毫无内容的文本。
        """
        from forgemind.core.ai.providers import (
            ChatMessage,
            OpenAIProvider,
            ProviderConfig,
            ProviderType,
            ProviderUnavailableError,
        )
        # ProviderUnavailableError 必须在 patch __import__ **之前**导入:
        # patch 期间任何 import 都会抛 ImportError
        with patch.dict("sys.modules", {"openai": None}):
            with patch("builtins.__import__", side_effect=ImportError("openai not installed")):
                p = OpenAIProvider(ProviderConfig(
                    provider_type=ProviderType.OPENAI,
                    api_key="fake",
                    model_name="gpt-4o-mini",
                ))
                with pytest.raises(ProviderUnavailableError):
                    async for _ in p.stream_chat(
                            [ChatMessage(role="user", content="hi")]):
                        pass

    @pytest.mark.asyncio
    async def test_anthropic_stream_raises_when_not_installed(self):
        """anthropic 未装时必须抛错,不能 yield 占位字符串"""
        from forgemind.core.ai.providers import (
            AnthropicProvider,
            ChatMessage,
            ProviderConfig,
            ProviderType,
        )
        with patch.dict("sys.modules", {"anthropic": None}):
            p = AnthropicProvider(ProviderConfig(
                provider_type=ProviderType.ANTHROPIC,
                api_key="fake",
                model_name="claude-3-5-sonnet-latest",
            ))
            from forgemind.core.ai.providers import ProviderUnavailableError
            with pytest.raises(ProviderUnavailableError):
                async for _ in p.stream_chat(
                        [ChatMessage(role="user", content="hi")]):
                    pass

    @pytest.mark.asyncio
    async def test_qwen_stream(self):
        """Qwen stream — GenericOpenAICompatProvider 走 OpenAI 兼容协议"""
        # openai 是可选依赖:没装就跳过,而不是硬失败
        pytest.importorskip("openai", reason="OpenAI 兼容协议需要 openai SDK")
        from forgemind.core.ai.providers import (
            ChatMessage,
            GenericOpenAICompatProvider,
            ProviderConfig,
            ProviderType,
        )
        p = GenericOpenAICompatProvider(ProviderConfig(
            provider_type=ProviderType.QWEN,
            api_key="fake",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model_name="qwen-plus",
        ))
        captured = {}

        def _fake_client(**kwargs):
            captured.update(kwargs)
            return _FakeOpenAIClient(["你好", ",世界"])

        with patch("openai.AsyncOpenAI", side_effect=_fake_client):
            chunks = [
                c async for c in
                p.stream_chat([ChatMessage(role="user", content="hi")])
            ]

        assert chunks == ["你好", ",世界"]
        # 兼容协议的关键:base_url 与 model 必须按配置传下去
        assert captured["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        assert captured["api_key"] == "fake"

    @pytest.mark.asyncio
    async def test_ollama_stream(self):
        """Ollama 本地 stream — 用 mock 模拟"""
        from forgemind.core.ai.providers import (
            ChatMessage,
            OllamaProvider,
            ProviderConfig,
            ProviderType,
        )
        p = OllamaProvider(ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            base_url="http://localhost:11434",
            model_name="qwen2.5:7b",
        ))

        async def _lines():
            for line in (
                '{"message": {"content": "Hello"}}',
                '{"message": {"content": " World"}}',
                '{"done": true}',
            ):
                yield line

        # 模拟 Ollama /api/chat 流式响应
        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_response = MagicMock()
            mock_response.aiter_lines = MagicMock(return_value=_lines())
            mock_stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_stream.return_value.__aexit__ = AsyncMock(return_value=None)

            chunks = [
                c async for c in
                p.stream_chat([ChatMessage(role="user", content="hi")])
            ]

        assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_abstract_stream_chat_in_base(self):
        """BaseProvider.stream_chat 是 abstractmethod"""

        from forgemind.core.ai.providers import BaseProvider
        # 验证 stream_chat 是 abstract
        assert hasattr(BaseProvider, "stream_chat")
        # 验证 abstract 装饰
        method = BaseProvider.stream_chat
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_all_providers_implement_stream_chat(self):
        """5 个 Provider 都应实现 stream_chat"""
        from forgemind.core.ai.providers import (
            AnthropicProvider,
            BaseProvider,
            GenericOpenAICompatProvider,
            OllamaProvider,
            OpenAIProvider,
        )
        for cls in [OpenAIProvider, AnthropicProvider, OllamaProvider, GenericOpenAICompatProvider]:
            assert "stream_chat" in cls.__dict__, f"{cls.__name__} 缺 stream_chat"
            # 验证 override 了 BaseProvider 的 abstractmethod
            assert cls.stream_chat is not BaseProvider.stream_chat


class TestStreamChatStreaming:
    """stream_chat 的增量输出 — 用假客户端覆盖,不依赖网络与真实凭据"""

    @pytest.mark.asyncio
    async def test_stream_chat_returns_async_iter(self):
        """stream_chat 应返回 AsyncIterator,并逐块吐出增量内容"""
        import inspect

        # openai 是可选依赖:没装就跳过,而不是硬失败
        pytest.importorskip("openai", reason="OpenAI 兼容协议需要 openai SDK")
        from forgemind.core.ai.providers import (
            ChatMessage,
            OpenAIProvider,
            ProviderConfig,
            ProviderType,
        )
        p = OpenAIProvider(ProviderConfig(
            provider_type=ProviderType.OPENAI,
            api_key="fake",
            model_name="gpt-4o-mini",
        ))
        with patch("openai.AsyncOpenAI", return_value=_FakeOpenAIClient(["forge", "mind"])):
            gen = p.stream_chat([ChatMessage(role="user", content="hi")])
            # 验证是 async generator
            assert inspect.isasyncgen(gen)
            chunks = [chunk async for chunk in gen]
        assert chunks == ["forge", "mind"]
