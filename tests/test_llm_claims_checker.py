# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""「用了模型」的说法与代码对得上:这条判据自己也得可靠。

它问的是**代码的事实**:生产代码里到底有没有调用 provider 适配层。

- 没有 ⇒ README 必须说明"决策链路尚未接上模型",界面不许出现"AI 决策"。
- 有 ⇒ 那句说明就过时了,判据要求删掉它。

规则本身要能双向验:该报的报、不该报的不报。所以这里用**合成数据**把
两条分支都走一遍 —— 真跑一遍只能证明"当前这仓合规",验不出**哪条规则**
在起作用。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_llm_claims as claims  # noqa: E402


class TestEvaluate:
    def test_not_connected_requires_the_note(self):
        """生产代码没调模型、README 也没说明 ⇒ 要报。"""
        problems = claims.evaluate("这里什么模型都没提", [], [])
        assert problems, "没说明'尚未接上模型'却没有报出来"
        assert any("尚未接上模型" in p for p in problems), problems

    def test_not_connected_with_the_note_passes(self):
        """生产代码没调模型、README 说明了就过。"""
        readme = f"决策链路{claims.NOT_CONNECTED_MARK}。"
        assert claims.evaluate(readme, [], []) == []

    def test_ui_claim_is_reported(self):
        """界面上写着「AI 决策」⇒ 要报。"""
        readme = f"决策链路{claims.NOT_CONNECTED_MARK}。"
        problems = claims.evaluate(readme, [], ["forgemind-ui/lib/store.ts:112"])
        assert problems, "界面上的说法没被报出来"
        assert any("store.ts" in p for p in problems), problems

    def test_connected_makes_the_note_obsolete(self):
        """生产代码真接上了 ⇒ 那句说明过时了,判据要求删。"""
        readme = f"决策链路{claims.NOT_CONNECTED_MARK}。"
        problems = claims.evaluate(readme, ["forgemind/core/agents/x.py:10"], [])
        assert problems, "过时的说明没被报出来"
        assert any("过时" in p for p in problems), problems

    def test_connected_without_the_note_passes(self):
        readme = "决策链路用的是模型。"
        assert claims.evaluate(readme, ["forgemind/core/agents/x.py:10"], []) == []


class TestRealRepo:
    def test_the_checker_passes_on_this_repository(self):
        """判据在本仓上要通过 —— 它自己坏了要说出来。"""
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        problems = claims.evaluate(
            readme, claims.production_calls_providers(), claims.ui_claim_hits()
        )
        assert problems == [], problems

    def test_provider_calls_are_detected_in_production_code(self):
        """生产代码里真的调了 provider ⇒ 要认出来。"""
        hits = claims.production_calls_providers()
        # 当前这仓没有 —— 那正好说明"生产代码没接模型"这件事是真的
        assert hits == [], hits
