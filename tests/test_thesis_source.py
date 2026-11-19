# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""论点的来源必须说清楚,而且模型只能负责措辞。

**不许把规则生成的论点说成模型生成的。** 没配置模型、调用失败、模型
返回空话,一律回落规则,并标明来源。读的人据此知道这句话是谁说的。

**模型只负责措辞,事实仍由规则给。** 论据里的每一个数都来自技术面读
数,模型没碰过它们 —— 所以模型编不出数来。

这些用例用**假的 provider**(不联网),所以判据不依赖网络。
"""

from __future__ import annotations

import asyncio

from forgemind.core.agents.portfolio_context import bear_node, bull_node


class _FakeProvider:
    """一个假的 provider —— 回固定的话,或者按需要失败。"""

    def __init__(self, reply: str = "", fail: bool = False):
        self.reply = reply
        self.fail = fail
        self.calls: list[list] = []

    async def chat(self, messages, temperature=0.7, max_tokens=4096):
        self.calls.append(list(messages))
        if self.fail:
            raise RuntimeError("provider 不可用")
        return type("R", (), {"content": self.reply})()


STATE = {
    "symbol": "600519.SH",
    "technical_analysis": {
        "status": "ok",
        "n_bars": 60,
        "last_date": "2024-02-09",
        "last_close": 120.0,
        "ma5": 121.0,
        "ma20": 118.0,
        "ma60": 115.0,
        "ma_cross": "golden",
        "rsi": 55.0,
        "macd_hist": 0.3,
        "signal": "buy",
        "confidence": 0.6,
    },
}


def _state() -> dict:
    return {
        "symbol": STATE["symbol"],
        "technical_analysis": dict(STATE["technical_analysis"]),
        "fundamentals_analysis": {"status": "unavailable"},
        "news_analysis": {"status": "unavailable"},
    }


class TestThesisSourceIsHonest:
    def test_without_a_model_it_is_a_rule(self, monkeypatch):
        """没配模型 ⇒ 规则生成,并说明为什么。"""
        from forgemind.core.agents import portfolio_context as pc

        async def _none():
            return None

        monkeypatch.setattr(pc, "_decision_provider", _none)
        bull = asyncio.run(bull_node(_state()))["bull_case"]
        assert bull["thesis_source"] == "rule", bull
        assert bull["thesis_source_reason"], bull

    def test_a_model_that_works_is_marked_as_model(self, monkeypatch):
        from forgemind.core.agents import portfolio_context as pc

        fake = _FakeProvider(reply="均线金叉且量能配合,短线偏多但需盯住 MA20 支撑。")

        async def _fake_provider():
            return fake

        monkeypatch.setattr(pc, "_decision_provider", _fake_provider)
        bull = asyncio.run(bull_node(_state()))["bull_case"]
        assert bull["thesis_source"] == "model", bull
        assert "均线金叉" in bull["thesis"], bull
        assert fake.calls, "模型没被调用"

    def test_a_failing_model_falls_back_to_the_rule(self, monkeypatch):
        """模型这一路没走通 ⇒ 用规则的措辞,并说清失败原因。"""
        from forgemind.core.agents import portfolio_context as pc

        async def _fake_provider():
            return _FakeProvider(fail=True)

        monkeypatch.setattr(pc, "_decision_provider", _fake_provider)
        bear = asyncio.run(bear_node(_state()))["bear_case"]
        assert bear["thesis_source"] == "rule", bear
        assert "失败" in (bear["thesis_source_reason"] or ""), bear

    def test_an_empty_reply_falls_back_to_the_rule(self, monkeypatch):
        from forgemind.core.agents import portfolio_context as pc

        async def _fake_provider():
            return _FakeProvider(reply="  ")

        monkeypatch.setattr(pc, "_decision_provider", _fake_provider)
        bull = asyncio.run(bull_node(_state()))["bull_case"]
        assert bull["thesis_source"] == "rule", bull

    def test_the_facts_stay_with_the_rules(self, monkeypatch):
        """模型只改措辞,证据里的数一个都不许变。"""
        from forgemind.core.agents import portfolio_context as pc

        fake = _FakeProvider(reply="这是一句由模型写的、看起来很有说服力的论据。")

        async def _fake_provider():
            return fake

        monkeypatch.setattr(pc, "_decision_provider", _fake_provider)
        bull = asyncio.run(bull_node(_state()))["bull_case"]
        assert bull["thesis_source"] == "model", bull
        # 证据仍然是规则算出来的读数
        assert bull["evidence"], bull
        assert any("MA5" in e or "MA20" in e for e in bull["evidence"]), bull

    def test_the_model_does_not_get_to_invent_numbers(self, monkeypatch):
        """给模型的输入里只有真实读数,没有让它编数字的余地。"""
        from forgemind.core.agents import portfolio_context as pc

        fake = _FakeProvider(reply="看起来很有说服力的论据。")

        async def _fake_provider():
            return fake

        monkeypatch.setattr(pc, "_decision_provider", _fake_provider)
        asyncio.run(bull_node(_state()))
        prompt = fake.calls[0][-1].content
        assert "MA5" in prompt or "MA20" in prompt, prompt
        assert "120" in prompt or "118" in prompt, prompt
