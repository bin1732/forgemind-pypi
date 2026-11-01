# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum

from forgemind.core.observability.logging import get_logger

logger = get_logger("forgemind.providers")


class ProviderType(str, Enum):  # noqa: UP042
    """9 个 Provider"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    MISTRAL = "mistral"
    OLLAMA = "ollama"  # 本地
    VLLM = "vllm"  # 本地(高吞吐)
    LMSTUDIO = "lmstudio"  # 本地(桌面)


@dataclass
class ProviderConfig:
    """Provider 配置"""

    provider_type: ProviderType
    api_key: str | None = None
    base_url: str | None = None
    model_name: str = ""
    timeout_sec: float = 60.0
    max_retries: int = 3


@dataclass
class ChatMessage:
    """聊天消息"""

    role: str  # "system" / "user" / "assistant"
    content: str


class ProviderUnavailableError(RuntimeError):
    """依赖的 SDK 未安装 / provider 不可用"""


@dataclass
class ChatResponse:
    """聊天响应

    **error 字段不可省**:失败路径(SDK 未装、鉴权失败、限流、
    网络不通)一律带 `error` 并将 `is_ok` 设为 False,便于机器判定,
    避免错误信息被当作模型推理继续被下游消费。
    """

    content: str
    model: str
    provider: ProviderType
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    #: 非空即表示这次没有拿到真实模型输出
    error: str | None = None

    @property
    def is_ok(self) -> bool:
        return self.error is None


class BaseProvider(ABC):
    """Provider 基类"""

    def __init__(self, config: ProviderConfig):
        self.config = config

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        """同步 chat"""
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """流式 chat"""
        pass


class OpenAIProvider(BaseProvider):
    """OpenAI(gpt-4o / gpt-4o-mini / o1)"""

    async def chat(self, messages, temperature=0.7, max_tokens=4096):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return ChatResponse(
                content="[OpenAI not installed]",
                model=self.config.model_name,
                provider=ProviderType.OPENAI,
                error="缺少 openai 包:pip install 'forgemind[llm]'",
            )

        client = AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url or "https://api.openai.com/v1",
        )

        import time

        start = time.time()

        try:
            response = await client.chat.completions.create(
                model=self.config.model_name or "gpt-4o-mini",
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            return ChatResponse(
                content=content,
                model=self.config.model_name,
                provider=ProviderType.OPENAI,
                tokens_in=response.usage.prompt_tokens if response.usage else 0,
                tokens_out=response.usage.completion_tokens if response.usage else 0,
                latency_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            logger.error("openai_chat_failed", error=str(e))
            return ChatResponse(
                content=f"[OpenAI Error: {e}]",
                model=self.config.model_name,
                provider=ProviderType.OPENAI,
                error=f"{type(e).__name__}: {e}",
            )

    async def stream_chat(self, messages, temperature=0.7, max_tokens=4096):
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.config.api_key)
            stream = await client.chat.completions.create(
                model=self.config.model_name or "gpt-4o-mini",
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except ImportError as exc:
            raise ProviderUnavailableError(
                "OpenAI SDK 未安装:pip install 'forgemind[llm]'"
            ) from exc


class AnthropicProvider(BaseProvider):
    """Anthropic(claude-4 / claude-haiku-4 / claude-sonnet-4 / claude-opus-4)"""

    async def chat(self, messages, temperature=0.7, max_tokens=4096):
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            return ChatResponse(
                content="[Anthropic not installed]",
                model=self.config.model_name,
                provider=ProviderType.ANTHROPIC,
                error="缺少 anthropic 包:pip install 'forgemind[llm]'",
            )

        client = AsyncAnthropic(api_key=self.config.api_key)

        # 分离 system
        system = ""
        chat_msgs = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                chat_msgs.append({"role": m.role, "content": m.content})

        import time

        start = time.time()

        try:
            response = await client.messages.create(
                model=self.config.model_name or "claude-sonnet-4-20250514",
                system=system,
                messages=chat_msgs,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.content[0].text if response.content else ""
            return ChatResponse(
                content=content,
                model=self.config.model_name,
                provider=ProviderType.ANTHROPIC,
                tokens_in=response.usage.input_tokens if response.usage else 0,
                tokens_out=response.usage.output_tokens if response.usage else 0,
                latency_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            logger.error("anthropic_chat_failed", error=str(e))
            return ChatResponse(
                content=f"[Anthropic Error: {e}]",
                model=self.config.model_name,
                provider=ProviderType.ANTHROPIC,
                error=f"{type(e).__name__}: {e}",
            )

    async def stream_chat(self, messages, temperature=0.7, max_tokens=4096):
        try:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=self.config.api_key)
            system = ""
            chat_msgs = []
            for m in messages:
                if m.role == "system":
                    system = m.content
                else:
                    chat_msgs.append({"role": m.role, "content": m.content})

            async with client.messages.stream(
                model=self.config.model_name or "claude-sonnet-4-20250514",
                system=system,
                messages=chat_msgs,
                temperature=temperature,
                max_tokens=max_tokens,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except ImportError as exc:
            raise ProviderUnavailableError(
                "Anthropic SDK 未安装:pip install 'forgemind[llm]'"
            ) from exc


class OllamaProvider(BaseProvider):
    """Ollama 本地(0 元,完全本地)"""

    async def chat(self, messages, temperature=0.7, max_tokens=4096):
        try:
            import httpx
        except ImportError:
            return ChatResponse(
                content="[Ollama needs httpx: pip install httpx]",
                model=self.config.model_name,
                provider=ProviderType.OLLAMA,
                error="缺少 httpx:pip install httpx",
            )
        import time

        start = time.time()
        base_url = self.config.base_url or "http://localhost:11434"

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_sec) as client:
                response = await client.post(
                    f"{base_url}/api/chat",
                    json={
                        "model": self.config.model_name or "qwen2.5:72b",
                        "messages": [{"role": m.role, "content": m.content} for m in messages],
                        "stream": False,
                        "options": {"temperature": temperature, "num_predict": max_tokens},
                    },
                )
                data = response.json()
                content = data.get("message", {}).get("content", "")
                return ChatResponse(
                    content=content,
                    model=self.config.model_name,
                    provider=ProviderType.OLLAMA,
                    tokens_in=data.get("prompt_eval_count", 0),
                    tokens_out=data.get("eval_count", 0),
                    latency_ms=int((time.time() - start) * 1000),
                    cost_usd=0.0,  # 本地 0 元
                )
        except Exception as e:
            logger.error("ollama_chat_failed", error=str(e))
            return ChatResponse(
                content=f"[Ollama Error: {e}. 确认 Ollama 已启动: ollama serve]",
                model=self.config.model_name,
                provider=ProviderType.OLLAMA,
                error=f"{type(e).__name__}: {e}",
            )

    async def stream_chat(self, messages, temperature=0.7, max_tokens=4096):
        try:
            import httpx
        except ImportError as exc:
            raise ProviderUnavailableError("httpx 未安装:pip install httpx") from exc
        base_url = self.config.base_url or "http://localhost:11434"
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_sec) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/api/chat",
                    json={
                        "model": self.config.model_name or "qwen2.5:72b",
                        "messages": [{"role": m.role, "content": m.content} for m in messages],
                        "stream": True,
                    },
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            import json

                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
        except Exception as e:
            raise ProviderUnavailableError(f"Ollama 调用失败:{type(e).__name__}: {e}") from e


class GenericOpenAICompatProvider(BaseProvider):
    """兼容 OpenAI API 协议(Qwen / DeepSeek / Gemini / Mistral / vLLM / LM Studio)

    这些 provider 都用 OpenAI 兼容协议
    """

    async def chat(self, messages, temperature=0.7, max_tokens=4096):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return ChatResponse(
                content="[openai package not installed]",
                model=self.config.model_name,
                provider=self.config.provider_type,
                error="缺少 openai 包:pip install 'forgemind[llm]'",
            )

        if not self.config.base_url:
            # 默认 URL
            defaults = {
                ProviderType.QWEN: "https://dashscope.aliyuncs.com/compatible-mode/v1",
                ProviderType.DEEPSEEK: "https://api.deepseek.com/v1",
                ProviderType.GEMINI: "https://generativelanguage.googleapis.com/v1beta/openai/",
                ProviderType.MISTRAL: "https://api.mistral.ai/v1",
                ProviderType.VLLM: "http://localhost:8000/v1",
                ProviderType.LMSTUDIO: "http://localhost:1234/v1",
            }
            self.config.base_url = defaults.get(self.config.provider_type, "")

        client = AsyncOpenAI(
            api_key=self.config.api_key or "EMPTY",
            base_url=self.config.base_url,
        )

        import time

        start = time.time()

        try:
            response = await client.chat.completions.create(
                model=self.config.model_name,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            return ChatResponse(
                content=content,
                model=self.config.model_name,
                provider=self.config.provider_type,
                tokens_in=response.usage.prompt_tokens if response.usage else 0,
                tokens_out=response.usage.completion_tokens if response.usage else 0,
                latency_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            logger.error(f"{self.config.provider_type.value}_chat_failed", error=str(e))
            return ChatResponse(
                content=f"[{self.config.provider_type.value} Error: {e}]",
                model=self.config.model_name,
                provider=self.config.provider_type,
                error=f"{type(e).__name__}: {e}",
            )

    async def stream_chat(self, messages, temperature=0.7, max_tokens=4096):
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=self.config.api_key or "EMPTY", base_url=self.config.base_url
            )
            stream = await client.chat.completions.create(
                model=self.config.model_name,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except ImportError as exc:
            raise ProviderUnavailableError("openai 包未安装:pip install 'forgemind[llm]'") from exc


def create_provider(config: ProviderConfig) -> BaseProvider:
    """按 provider_type 创建 provider

    未显式给出 api_key 时自动从 PROVIDER_INFO 声明的环境变量读 ——
    否则直接 `create_provider(ProviderConfig(...))` 这条最常见的用法会拿到
    api_key=None,报出来的是 SDK 的鉴权错误,而不是"请设置 XXX_API_KEY"。
    """
    """工厂 — 按 ProviderType 创建对应 provider"""
    if config.api_key is None:
        # 未显式给 key 时按 PROVIDER_INFO 声明的 env_var 兜底。
        # 否则最常见的 `create_provider(ProviderConfig(...))` 拿到的
        # api_key 是 None,报出来的是 SDK 的鉴权错误而不是
        # "请设置 DEEPSEEK_API_KEY" —— 用户无从知道要设哪个变量。
        resolved = _resolve_api_key(config.provider_type, None)
        if resolved:
            config.api_key = resolved
    if config.provider_type == ProviderType.OPENAI:
        return OpenAIProvider(config)
    elif config.provider_type == ProviderType.ANTHROPIC:
        return AnthropicProvider(config)
    elif config.provider_type == ProviderType.OLLAMA:
        return OllamaProvider(config)
    elif config.provider_type in (
        ProviderType.QWEN,
        ProviderType.DEEPSEEK,
        ProviderType.GEMINI,
        ProviderType.MISTRAL,
        ProviderType.VLLM,
        ProviderType.LMSTUDIO,
    ):
        return GenericOpenAICompatProvider(config)
    else:
        raise ValueError(f"Unknown provider: {config.provider_type}")


# Provider 默认 base_url 表(从 settings 读,允许 env 覆盖)
_PROVIDER_DEFAULT_BASE_URL = {
    ProviderType.OPENAI: "https://api.openai.com/v1",
    ProviderType.ANTHROPIC: "https://api.anthropic.com",
    ProviderType.QWEN: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ProviderType.DEEPSEEK: "https://api.deepseek.com/v1",
    ProviderType.GEMINI: "https://generativelanguage.googleapis.com/v1beta",
    ProviderType.MISTRAL: "https://api.mistral.ai/v1",
    ProviderType.OLLAMA: "http://localhost:11434/v1",
    ProviderType.VLLM: "http://localhost:8000/v1",
    ProviderType.LMSTUDIO: "http://localhost:1234/v1",
}

# Provider 默认 model
_PROVIDER_DEFAULT_MODEL = {
    ProviderType.OPENAI: "gpt-4o-mini",
    ProviderType.ANTHROPIC: "claude-3-5-sonnet-latest",
    ProviderType.QWEN: "qwen-plus",
    ProviderType.DEEPSEEK: "deepseek-chat",
    ProviderType.GEMINI: "gemini-1.5-pro",
    ProviderType.MISTRAL: "mistral-large-latest",
    ProviderType.OLLAMA: "qwen2.5:7b",
    ProviderType.VLLM: "Qwen/Qwen2.5-7B-Instruct",
    ProviderType.LMSTUDIO: "qwen2.5-7b",
}


def _resolve_api_key(provider_type: ProviderType, explicit_key: str | None) -> str | None:
    """解析 API Key — 优先用 explicit, 否则从 settings / env 读"""
    if explicit_key:
        return explicit_key

    # 从环境变量读 —— 变量名直接取自 PROVIDER_INFO,作为环境变量名唯一定义点。
    import os as _os

    info = PROVIDER_INFO.get(provider_type) or {}
    env_var = info.get("env_var")
    if env_var:
        val = _os.environ.get(env_var)
        if val:
            return val
        # 环境变量没有,退回 settings(它读的是同一个变量)
        from forgemind.core.config.settings import get_settings

        attr = env_var.lower()
        return getattr(get_settings(), attr, None) or None
    return None


# 便利函数 — 按名字选 provider
async def quick_chat(
    provider: str,
    model: str = "",
    prompt: str = "",
    api_key: str | None = None,
    base_url: str | None = None,
    system: str | None = None,
) -> ChatResponse:
    """
    快速对话 — 自动从 env / settings 读 API key

    provider: openai/anthropic/qwen/deepseek/gemini/mistral/ollama/vllm/lmstudio
    model: 不传时用 provider 默认 model
    prompt: 用户提示
    api_key: 不传时从 env FORGEMIND_<PROVIDER>_API_KEY 读
    base_url: 不传时用 provider 默认
    system: 系统提示(可选)
    """
    ptype = ProviderType(provider)

    resolved_model = model or _PROVIDER_DEFAULT_MODEL.get(ptype, "gpt-4o-mini")
    resolved_key = _resolve_api_key(ptype, api_key)
    resolved_url = base_url or _PROVIDER_DEFAULT_BASE_URL.get(ptype)

    config = ProviderConfig(
        provider_type=ptype,
        api_key=resolved_key,
        base_url=resolved_url,
        model_name=resolved_model,
    )
    p = create_provider(config)

    messages = []
    if system:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=prompt))

    return await p.chat(messages)


# Provider 信息
PROVIDER_INFO = {
    ProviderType.OPENAI: {
        "name": "OpenAI",
        "env_var": "OPENAI_API_KEY",
        "models": ["gpt-4o", "gpt-4o-mini", "o1-preview", "o1-mini"],
        "best_for": "通用",
    },
    ProviderType.ANTHROPIC: {
        "name": "Anthropic",
        "env_var": "ANTHROPIC_API_KEY",
        "models": ["claude-opus-4", "claude-sonnet-4", "claude-haiku-4"],
        "best_for": "深度推理 + 长上下文",
    },
    ProviderType.QWEN: {
        "name": "Qwen",
        "env_var": "QWEN_API_KEY",
        "models": ["qwen3-max", "qwen2.5-72b-instruct", "qwen-long"],
        "best_for": "中文",
    },
    ProviderType.DEEPSEEK: {
        "name": "DeepSeek",
        "env_var": "DEEPSEEK_API_KEY",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "best_for": "推理 + 开源权重",
    },
    ProviderType.GEMINI: {
        "name": "Gemini",
        "env_var": "GEMINI_API_KEY",
        "models": ["gemini-2.0-flash", "gemini-2.5-pro"],
        "best_for": "多模态",
    },
    ProviderType.MISTRAL: {
        "name": "Mistral",
        "env_var": "MISTRAL_API_KEY",
        "models": ["mistral-large-latest", "mistral-small"],
        "best_for": "欧洲",
    },
    ProviderType.OLLAMA: {
        "name": "Ollama",
        "env_var": None,
        "models": ["qwen2.5:72b", "llama3.1:70b", "deepseek-r1:70b"],
        "best_for": "本地 0 元",
    },
    ProviderType.VLLM: {
        "name": "vLLM",
        "env_var": None,
        "models": ["任意 HF 模型"],
        "best_for": "高吞吐本地推理",
    },
    ProviderType.LMSTUDIO: {
        "name": "LM Studio",
        "env_var": None,
        "models": ["任意 GGUF 模型"],
        "best_for": "桌面端本地",
    },
}
