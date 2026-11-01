# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""LLM 调用失败必须可被调用方机器判定

失败路径曾统一返回结构上与真实回答完全相同的 ChatResponse,
只是把错误信息塞进 content:

    "[OpenAI not installed]"
    "[Anthropic Error: AuthenticationError ...]"
    "[Ollama Error: ... 确认 Ollama 已启动: ollama serve]"

ChatResponse 当时没有任何错误字段,调用方只能靠解析文本判断。这意味着
鉴权失败之后,错误字符串会作为"模型的推理"被下游继续消费,最终产出一份
看起来很正常、实则毫无依据的输出。

stream 路径更糟:yield 出 "[OpenAI not installed]" 这种字符串,调用方把它
当模型增量输出拼进结果里。现在改为抛 ProviderUnavailableError。
"""

import ast
from pathlib import Path

from forgemind.core.ai.providers import (
    PROVIDER_INFO,
    ChatResponse,
    ProviderType,
    ProviderUnavailableError,
    create_provider,
)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "forgemind/core/ai/providers.py"


class TestChatResponseCarriesError:
    def test_ok_response_is_distinguishable(self):
        r = ChatResponse(content="真实回答", model="m",
                         provider=ProviderType.OPENAI)
        assert r.is_ok and r.error is None

    def test_failed_response_is_machine_detectable(self):
        r = ChatResponse(content="[Anthropic Error: x]", model="m",
                         provider=ProviderType.ANTHROPIC,
                         error="AuthenticationError: invalid api key")
        assert not r.is_ok
        assert "AuthenticationError" in r.error

    def test_every_failure_path_sets_error(self):
        """所有 return ChatResponse 的失败分支都必须带 error"""
        tree = ast.parse(SRC.read_text(encoding="utf-8"))
        missing = []
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Return) and isinstance(node.value, ast.Call)):
                continue
            fn = node.value.func
            if not (isinstance(fn, ast.Name) and fn.id == "ChatResponse"):
                continue
            kw = {k.arg for k in node.value.keywords}
            if "error" not in kw:
                lineno = node.lineno
                # 正常回答(没有方括号占位前缀)不算失败路径
                seg = ast.get_source_segment(SRC.read_text(encoding="utf-8"), node) or ""
                if "[" in seg and "not installed" in seg or "Error:" in seg:
                    missing.append(lineno)
        assert not missing, f"这些失败分支没有设置 error,行号: {missing}"


class TestNoFakeTextFromStreams:
    def test_streams_raise_instead_of_yielding_placeholders(self):
        """stream 不能 yield 出像模型输出的占位字符串"""
        src = SRC.read_text(encoding="utf-8")
        tree = ast.parse(src)
        offenders = []
        # 注意:必须找**所有**含 yield 的方法。只匹配名为 "stream" 的函数
        # 会一个都找不到,测试空跑通过 —— 实际方法叫 stream_chat。
        # (这个假绿我自己已修复一次。)
        # AsyncFunctionDef 也要算 —— stream_chat 是 async 生成器,
        # 只匹配 FunctionDef 会一个都找不到(我已修复两次这种假绿)
        generators = [n for n in ast.walk(tree)
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and any(isinstance(s, (ast.Yield, ast.YieldFrom))
                              for s in ast.walk(n))]
        assert generators, "没有找到任何生成器方法,扫描逻辑本身有问题"
        for node in generators:
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Yield):
                    continue
                # 字面量占位文本
                if (isinstance(sub.value, ast.Constant)
                        and isinstance(sub.value.value, str)
                        and sub.value.value.startswith("[")):
                    offenders.append(f"{node.name}:{sub.lineno} → {sub.value.value!r}")
                # f-string 占位文本(形如 f"[Xxx Error: {e}]")
                elif isinstance(sub.value, ast.JoinedStr):
                    txt = "".join(v.value for v in sub.value.values
                                   if isinstance(v, ast.Constant)
                                   and isinstance(v.value, str))
                    if txt.startswith("["):
                        offenders.append(f"{node.name}:{sub.lineno} → f-string {txt!r}")
        assert not offenders, (
            "stream 仍在 yield 占位文本,调用方会当成模型输出:\n  "
            + "\n  ".join(offenders))

    def test_provider_unavailable_is_an_exception(self):
        assert issubclass(ProviderUnavailableError, RuntimeError)


class TestEveryDeclaredProviderIsConstructible:
    """README 声称 9 个 LLM provider,必须每个都真能建出来"""

    def test_all_nine_instantiate(self, monkeypatch):
        for info in PROVIDER_INFO.values():
            if info.get("env_var"):
                monkeypatch.setenv(info["env_var"], "test-key-not-real")
        built = {}
        for t, info in PROVIDER_INFO.items():
            from forgemind.core.ai.providers import ProviderConfig
            cfg = ProviderConfig(provider_type=t,
                                 model_name=(info.get("models") or ["m"])[0],
                                 api_key="test-key-not-real")
            built[t] = create_provider(cfg)
        assert len(built) == 9, f"README 声称 9 个,实际建出 {len(built)} 个"
        for t, p in built.items():
            assert p is not None

    def test_signature_is_the_documented_one(self):
        """ProviderConfig 的字段名要稳定,调用方按名传参"""
        import dataclasses
        fields = [f.name for f in dataclasses.fields(
            __import__("forgemind.core.ai.providers", fromlist=["ProviderConfig"]
                       ).ProviderConfig)]
        assert fields == ["provider_type", "api_key", "base_url", "model_name",
                          "timeout_sec", "max_retries"], fields
