# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""库级构件必须如实标注"没有入口",不能让调用方以为能用

nl2strategy.py 里四个类(NL2Strategy / AIFactorFactory /
NaturalLanguageResearchLog / RealtimeSentimentFeed)都有完整实现和
通过的测试,但**没有任何生产入口**:CLI、API、MCP 都不暴露,也没有别的
模块 import 它们。

这本身不是 bug —— README 也没承诺这些特性。但它们的文档写得像已交付:

  NL2Strategy      "把用户的自然语言描述翻译成**可执行的**策略代码"
                   —— 返回的 code 从未被任何地方执行,没有加载器
  AIFactorFactory  "3. 写代码 + 跑 IC 评估 4. 选 Top-N 高 IC 因子
                    5. **加入因子库**"
                   —— 只实现了第 1、2 步;factor_lib 收下就没再用过

文档已改为如实描述。这条测试把"无入口"这个事实钉住:哪天有人把它
接进了用户可达的表面,这里会红,提醒同步更新文档。
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "forgemind"
CLASSES = ["NL2Strategy", "AIFactorFactory",
           "NaturalLanguageResearchLog", "RealtimeSentimentFeed"]


def _prod_sources() -> list[Path]:
    out = []
    for p in PKG.rglob("*.py"):
        if "build" in p.parts or "__pycache__" in p.parts:
            continue
        out.append(p)
    return out


@pytest.mark.parametrize("name", CLASSES)
def test_no_production_caller(name):
    hits = []
    for p in _prod_sources():
        if p.name == "nl2strategy.py" or p.name == "__init__.py":
            continue
        if re.search(rf"\b{name}\b", p.read_text(encoding="utf-8")):
            hits.append(p.relative_to(ROOT).as_posix())
    assert not hits, (
        f"{name} 现在有了生产引用 {hits} —— 它已经可达了。"
        "请把文档里的'仅库级构件'改回真实的能力描述,"
        "并考虑把它加进功能清单。")


@pytest.mark.parametrize("name", CLASSES)
def test_not_exposed_by_any_user_surface(name):
    for surface in ("cli.py", "api/main.py", "mcp/server.py"):
        p = PKG / surface
        if p.exists():
            assert name not in p.read_text(encoding="utf-8"), (
                f"{name} 出现在 {surface} 里,已经是用户可达表面")


def test_no_aspirational_claims_left_in_docstrings():
    """文档里不该再出现无法兑现的说法"""
    src = (PKG / "core" / "agents" / "nl2strategy.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name not in CLASSES:
            continue
        doc = ast.get_docstring(node) or ""
        for claim in ("加入因子库", "翻译成可执行的策略代码",
                      "跑 IC 评估", "选 Top-N"):
            if claim in doc:
                # 允许出现在"原来写的是…实际没有…"这类更正说明里,
                # 但必须紧挨着"实际/没有/只是第 1 步"这类限定
                if not re.search(r"(实际|没有|只实现|从未|未实现)", doc):
                    pytest.fail(f"{node.name} 的文档仍声称「{claim}」")
