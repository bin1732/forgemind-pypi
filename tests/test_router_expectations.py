# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""路由 demo 里的预期结果必须由测试守住

`quick_route_demo` 的 examples 上挂着 `# Haiku` / `# Sonnet` / `# Human`
这样的注释 —— 它们是**对路由结果的预测**,写在注释里就不会有人维护。
路由优先级一改,注释就变成假话,而 demo 照常打印真实结果,没人发现。

这里把它们变成断言:改了路由而不同步预期,测试就红。
"""

import pytest


class TestDemoPredictionsHold:
    # (任务名, 复杂度, 关键决策, 中文, 实时, 期望 tier)
    CASES = [
        ("信号简单分类", 2, False, False, False, "haiku"),
        ("多因子综合评估", 6, False, False, False, "sonnet"),
        ("PortfolioManager 深度推理", 9, True, False, False, "human"),
        ("中文研报实时解析", 7, False, True, True, "qwen_max"),
        ("低延迟订单簿特征", 4, False, False, True, "local_vllm"),
    ]

    @pytest.mark.parametrize("name,complexity,critical,zh,rt,expected", CASES)
    def test_routes_as_documented(self, name, complexity, critical, zh, rt,
                                  expected):
        from forgemind.core.ai.router import get_router

        spec = get_router().route(task_complexity=complexity, is_critical=critical,
                                  requires_chinese=zh, is_real_time=rt)
        assert spec.tier.value == expected, (
            f"{name}: 期望路由到 {expected},实际 {spec.tier.value}。"
            "若路由优先级确有改动,请同步 quick_route_demo 的注释与本表。")

    def test_demo_examples_match_this_table(self):
        """demo 里的 examples 与本测试表必须一致,否则注释又在说别的话"""
        import inspect

        from forgemind.core.ai.router import quick_route_demo

        src = inspect.getsource(quick_route_demo)
        for name, _, _, _, _, expected in self.CASES:
            assert name in src, f"demo 里没有 {name} 用例"
            # 注释里应当挂着对应的 tier 名
            line = next(l for l in src.splitlines() if f'"{name}"' in l)
            # 注释是人类可读写法(HAIKU / Qwen / Local),tier 值不同名
            # (haiku / qwen_max / local_vllm) —— 用别名对照
            aliases = {
                "haiku": "haiku", "sonnet": "sonnet", "human": "human",
                "qwen_max": "qwen", "local_vllm": "local",
            }
            assert aliases[expected] in line.lower(), (
                f"{name} 的注释未标出期望 tier({expected}): {line.strip()}")


class TestPricingIsLabelledAsASnapshot:
    """价格是快照,不是现价 —— 输出里必须带日期"""

    def test_snapshot_date_exists(self):
        from forgemind.core.ai.router import PRICING_SNAPSHOT

        assert PRICING_SNAPSHOT and len(PRICING_SNAPSHOT) == 7  # YYYY-MM

    def test_demo_prints_the_snapshot_date(self, capsys):
        from forgemind.core.ai.router import PRICING_SNAPSHOT, quick_route_demo

        quick_route_demo()
        out = capsys.readouterr().out
        assert PRICING_SNAPSHOT in out, (
            "价格是快照,输出里必须带日期,否则用户会当现价估算成本")

    def test_every_model_has_a_cost(self):
        """成本缺失会让 cost 汇总静默变成 0"""
        from forgemind.core.ai.router import MODELS

        for tier, spec in MODELS.items():
            assert spec.cost_per_1k_tokens is not None, f"{tier} 缺成本"
            assert spec.cost_per_1k_tokens >= 0, tier
