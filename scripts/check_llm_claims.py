#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""README 与界面关于"用了模型"的说法,必须与代码对得上。

**为什么这一层要单独守**:项目里有 9 家 provider 的适配层,读代码的人很
容易以为决策链路已经在用模型。而决策的六个节点目前全是规则 —— 多空
论点由技术面读数按固定条件生成。"决策用了模型"这句话与实际行为不符,
比缺功能更误导人:用户会以为结论里有模型的理解,其实只有指标。

所以判据问的是**代码的事实**,不是文案的感觉:

- 生产代码里没有任何一处调用 provider 适配层 ⇒ README 必须说明"决策
  链路尚未接上模型",界面不许出现"AI 决策"这种说法。
- 生产代码真的接上了模型 ⇒ 那句说明就过时了,判据会要求把它删掉。

于是两边不会各说各话:接上了模型,说明自动作废;还没接上,说明不能删。

用法:
    python scripts/check_llm_claims.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: 生产代码里出现这些,就说明真的在调模型适配层。
PROVIDER_CALL_PATTERNS = (
    re.compile(r"\bcreate_provider\b"),
    re.compile(r"\bfrom\s+forgemind\.core\.ai\.providers\s+import\b"),
    re.compile(r"\bfrom\s+forgemind\.core\.ai\s+import\b[^\n]*providers"),
)

#: README 里"还没接上模型"这句话的记号。接上之后这句就作废了。
NOT_CONNECTED_MARK = "尚未接上模型"

#: 界面上不该出现的说法:那一步其实不调模型。
UI_CLAIM_PATTERNS = (
    re.compile(r"AI\s*决策"),
    re.compile(r"AI\s*智能"),
)

#: 界面源码目录(排除测试与构建产物)。
UI_DIRS = ("forgemind-ui/components", "forgemind-ui/lib", "forgemind-ui/app")
UI_SKIP = ("__tests__", "__mocks__", "node_modules", ".next", "out")


def production_calls_providers() -> list[str]:
    """生产代码里有没有真的调 provider 适配层 —— 返回命中的位置。"""
    hits: list[str] = []
    for path in sorted((REPO / "forgemind").rglob("*.py")):
        rel = path.relative_to(REPO)
        if rel.parts[:3] == ("forgemind", "core", "ai"):
            continue  # 适配层自己不算
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for rx in PROVIDER_CALL_PATTERNS:
            for m in rx.finditer(text):
                line = text[: m.start()].count("\n") + 1
                hits.append(f"{rel}:{line}")
                break
    return hits


def ui_claim_hits() -> list[str]:
    """界面上"AI 决策"这类说法的位置。"""
    hits: list[str] = []
    for sub in UI_DIRS:
        base = REPO / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.tsx")) + sorted(base.rglob("*.ts")):
            if any(part in UI_SKIP for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for rx in UI_CLAIM_PATTERNS:
                for m in rx.finditer(text):
                    line = text[: m.start()].count("\n") + 1
                    hits.append(f"{path.relative_to(REPO)}:{line}")
                    break
    return hits


def evaluate(readme_text: str, prod_hits: list[str], ui_hits: list[str]) -> list[str]:
    """核对文档与界面的说法 —— 单独抽出来,好让测试用合成数据双向验。

    规则本身要能验:该报的报、不该报的不报,不能靠真跑一遍来证明。
    """
    problems: list[str] = []
    mentions_not_connected = NOT_CONNECTED_MARK in readme_text

    if not prod_hits:
        # 生产代码没调模型 ⇒ 文档必须说实话
        if not mentions_not_connected:
            problems.append(
                "生产代码里没有任何一处调用模型适配层,但 README 没有说明"
                f"「{NOT_CONNECTED_MARK}」—— 读者会以为决策用了模型"
            )
        for hit in ui_hits:
            problems.append(
                f"{hit}: 界面上写着「AI 决策」,而这一步不调模型 —— 换个说法(决策 / 多 Agent 决策)"
            )
    else:
        # 生产代码真的调了 ⇒ 那句说明过时了
        if mentions_not_connected:
            problems.append(
                f"生产代码已经在调模型适配层({', '.join(prod_hits[:3])}),"
                f"README 里「{NOT_CONNECTED_MARK}」这句过时了 —— 删掉它"
            )
    return problems


def main() -> int:
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    hits = production_calls_providers()
    problems = evaluate(readme, hits, ui_claim_hits())

    if problems:
        print(f"关于「用了模型」的说法与代码对不上({len(problems)} 处):")
        for item in problems:
            print(" -", item)
        return 1

    if hits:
        print(f"模型接入了生产链路({', '.join(hits[:3])}),文档与界面的说法一致")
    else:
        print(f"模型还没接进生产链路,README 与界面都如实说明了(「{NOT_CONNECTED_MARK}」)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
