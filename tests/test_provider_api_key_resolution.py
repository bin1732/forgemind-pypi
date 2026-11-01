# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""API key 只能从 PROVIDER_INFO 声明的变量名解析,且所有入口都要生效

发现的两处问题:

1. **两份真相源**。`PROVIDER_INFO[p]["env_var"]` 声明了变量名,
   `_resolve_api_key` 里又手写了一张 `key_map`。当时两边一致,
   但没有任何机制保证它们继续一致 —— 改一处忘另一处,key 就会
   从错误的变量里读,而且不报错。

2. **最常见的用法绕过解析**。`create_provider(ProviderConfig(...))`
   拿到的 `api_key` 恒为 None,报出来的是 SDK 的鉴权错误,
   而不是"请设置 DEEPSEEK_API_KEY" —— 用户无从知道要设哪个变量。
"""

import inspect

import pytest

from forgemind.core.ai.providers import (
    PROVIDER_INFO,
    ProviderConfig,
    ProviderType,
    create_provider,
)


class TestSingleSourceOfTruth:
    def test_no_second_key_map_exists(self):
        """不许再出现第二份 provider→变量名映射"""
        from forgemind.core.ai import providers

        src = inspect.getsource(providers._resolve_api_key)
        # 只查真正的字典字面量(注释里提到 key_map 是允许的,
        # 否则这段说明历史的话自己会把测试搞红)
        import ast
        # 空 {} 是防御性默认值,不算映射表;非空的才是
        mappings = [n for n in ast.walk(ast.parse(src.strip()))
                    if isinstance(n, ast.Dict) and n.keys]
        assert not mappings, (
            "_resolve_api_key 里出现了非空映射表 —— 变量名必须来自 PROVIDER_INFO")
        assert 'PROVIDER_INFO.get(provider_type)' in src

    def test_every_env_var_matches_the_settings_field(self):
        """PROVIDER_INFO 里的 env_var 必须真有对应的 settings 字段"""
        from forgemind.core.config.settings import Settings

        s = Settings()
        for t, info in PROVIDER_INFO.items():
            ev = info.get("env_var")
            if not ev:
                continue
            assert hasattr(s, ev.lower()), (
                f"{t.value} 声明 env_var={ev},但 Settings 没有 {ev.lower()} 字段")

    @pytest.mark.parametrize("t", [t for t in PROVIDER_INFO
                                   if PROVIDER_INFO[t].get("env_var")])
    def test_key_is_read_from_the_declared_variable(self, t, monkeypatch):
        info = PROVIDER_INFO[t]
        ev = info["env_var"]
        monkeypatch.setenv(ev, "sk-from-env")
        cfg = ProviderConfig(provider_type=t, model_name="m")
        create_provider(cfg)
        assert cfg.api_key == "sk-from-env", (
            f"{t.value}: 声明读 {ev},实际读到 {cfg.api_key}")


class TestEveryEntryPointResolvesTheKey:
    @pytest.mark.parametrize("t", [ProviderType.DEEPSEEK, ProviderType.ANTHROPIC,
                                   ProviderType.OPENAI])
    def test_create_provider_fills_missing_key(self, t, monkeypatch):
        ev = PROVIDER_INFO[t]["env_var"]
        monkeypatch.setenv(ev, "sk-env")
        cfg = ProviderConfig(provider_type=t, model_name="m")
        assert cfg.api_key is None, "先确认构造时确实没给"
        create_provider(cfg)
        assert cfg.api_key == "sk-env", "create_provider 没有兜底解析"

    def test_explicit_key_wins(self, monkeypatch):
        monkeypatch.setenv(PROVIDER_INFO[ProviderType.DEEPSEEK]["env_var"], "sk-env")
        cfg = ProviderConfig(provider_type=ProviderType.DEEPSEEK,
                             model_name="m", api_key="sk-explicit")
        create_provider(cfg)
        assert cfg.api_key == "sk-explicit"

    def test_missing_env_stays_none(self, monkeypatch):
        ev = PROVIDER_INFO[ProviderType.QWEN]["env_var"]
        monkeypatch.delenv(ev, raising=False)
        cfg = ProviderConfig(provider_type=ProviderType.QWEN, model_name="m")
        create_provider(cfg)
        assert cfg.api_key is None, "没配 key 时应如实为 None,不能编一个"
