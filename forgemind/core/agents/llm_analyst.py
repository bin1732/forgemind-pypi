# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""用模型给多空论点**措辞**,事实仍由规则给。

**为什么这么分工**:模型能写得像人,也能编数字。让它参与措辞、不参与
事实,两头的好处都留着 —— 表达更连贯,而论据里的每一个数仍然来自规则
算出的真实读数。没让模型碰过的事实,它编不出来。

**不许把规则生成的论点说成模型生成的。** 没有配置模型、调用失败、模型
返回空话或超时,一律回落规则,并把 `source` 标成 `rule`、把原因写进
`reason`。读的人据此知道这句话是谁说的。

这个模块只负责"有没有模型可用、模型说了什么";事实与降级后的措辞由
调用方组装。
"""

from __future__ import annotations

from typing import Any

#: 模型返回的论点太短就不算论点 —— 短于这个长度多半是空话或报错回显。
MIN_THESIS_LEN = 12

#: 论点的两种来源。
SOURCE_MODEL = "model"
SOURCE_RULE = "rule"

_SYSTEM = """你是一名量化研究员。根据给定的**真实技术面读数**,写一句简短的看多或看空论点。

硬要求:
1. 只能使用给定读数里出现的数字与事实,不要引入任何新的数字、价位或日期。
2. 不要给仓位建议、不要预测涨跌点数。
3. 一句话,不超过 60 个字,中文。
4. 只输出这句话本身,不要解释、不要标题、不要引号。
"""


def build_prompt(symbol: str, kind: str, evidence: list[str], gaps: list[str]) -> str:
    """把真实读数拼成给模型的输入。

    缺哪些维度也一并说明 —— 让模型知道它看到的是全部,而不是部分。
    """
    facts = "\n".join(f"- {e}" for e in evidence) if evidence else "- (没有任何可用读数)"
    missing = "、".join(gaps) if gaps else "无"
    return (
        f"标的:{symbol}\n"
        f"方向:{'看多' if kind == 'bull' else '看空'}\n"
        f"真实读数(只能用这些):\n{facts}\n"
        f"缺失的维度:{missing}\n"
        f"请写一句{'看多' if kind == 'bull' else '看空'}论点。"
    )


async def model_thesis(
    provider: Any,
    symbol: str,
    kind: str,
    evidence: list[str],
    gaps: list[str],
    timeout: float = 30.0,
) -> dict:
    """让模型写一句论点 —— 任何一步不成立就如实说"没成"。

    返回 {"thesis": str | None, "reason": str | None}：
    thesis 为 None 表示模型这一路没走通,调用方该用规则的措辞并标明来源。
    """
    if provider is None:
        return {"thesis": None, "reason": "没有配置模型"}

    from forgemind.core.ai.providers import ChatMessage

    messages = [
        ChatMessage(role="system", content=_SYSTEM),
        ChatMessage(
            role="user",
            content=build_prompt(symbol, kind, evidence, gaps),
        ),
    ]
    try:
        response = await provider.chat(messages, temperature=0.3, max_tokens=200)
    except Exception as exc:  # noqa: BLE001 —— 任何失败都要能回落规则
        return {"thesis": None, "reason": f"模型调用失败({type(exc).__name__})"}
    finally:
        close = getattr(provider, "aclose", None)
        if callable(close):
            try:
                await close()
            except Exception:  # noqa: BLE001
                pass

    content = (getattr(response, "content", "") or "").strip()
    if len(content) < MIN_THESIS_LEN:
        return {"thesis": None, "reason": "模型没有给出可用的论点"}
    # 模型偶尔会带引号或多余的行,去掉再存。
    if len(content) > 300:
        content = content[:300]
    return {"thesis": content.strip("\"'“”"), "reason": None}
