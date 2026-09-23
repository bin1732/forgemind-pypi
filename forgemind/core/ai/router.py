# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from enum import Enum
from typing import Optional
from dataclasses import dataclass
import time

from forgemind.core.config.settings import get_settings
from forgemind.core.observability.logging import get_logger

logger = get_logger("forgemind.router")
settings = get_settings()


class ModelTier(str, Enum):
    """模型层级"""
    HAIKU = "haiku"              # 最便宜,简单任务
    SONNET = "sonnet"            # 中等,标准决策
    OPUS = "opus"                # 最贵,深度推理
    LOCAL_VLLM = "local_vllm"    # 本地,无 API cost
    QWEN_MAX = "qwen_max"        # 国内中文强
    HUMAN_REVIEW = "human"       # 人工审批(默认 gating)


@dataclass
class ModelSpec:
    """模型规格"""
    tier: ModelTier
    provider: str       # "openai" / "anthropic" / "local" / "qwen"
    model_name: str     # "gpt-4o-mini" / "claude-sonnet-4" / ...
    cost_per_1k_tokens: float  # USD
    avg_latency_ms: int
    max_context: int
    capability_score: int  # 0-10,任务能力评分


# 6 个 tier 的具体模型(2026-09)
MODELS: dict[ModelTier, ModelSpec] = {
    ModelTier.HAIKU: ModelSpec(
        tier=ModelTier.HAIKU,
        provider="anthropic",
        model_name="claude-haiku-4",
        cost_per_1k_tokens=0.0008,
        avg_latency_ms=500,
        max_context=200000,
        capability_score=6,
    ),
    ModelTier.SONNET: ModelSpec(
        tier=ModelTier.SONNET,
        provider="anthropic",
        model_name="claude-sonnet-4",
        cost_per_1k_tokens=0.003,
        avg_latency_ms=1500,
        max_context=200000,
        capability_score=8,
    ),
    ModelTier.OPUS: ModelSpec(
        tier=ModelTier.OPUS,
        provider="anthropic",
        model_name="claude-opus-4",
        cost_per_1k_tokens=0.015,
        avg_latency_ms=3000,
        max_context=200000,
        capability_score=10,
    ),
    ModelTier.LOCAL_VLLM: ModelSpec(
        tier=ModelTier.LOCAL_VLLM,
        provider="local",
        model_name="Qwen2.5-72B-Instruct-AWQ",
        cost_per_1k_tokens=0.0,  # 0 cost!
        avg_latency_ms=200,
        max_context=32000,
        capability_score=7,
    ),
    ModelTier.QWEN_MAX: ModelSpec(
        tier=ModelTier.QWEN_MAX,
        provider="qwen",
        model_name="qwen3-max",
        cost_per_1k_tokens=0.002,
        avg_latency_ms=1000,
        max_context=128000,
        capability_score=8,
    ),
    ModelTier.HUMAN_REVIEW: ModelSpec(
        tier=ModelTier.HUMAN_REVIEW,
        provider="human",
        model_name="investment_manager",
        cost_per_1k_tokens=0.05,  # 人工时薪
        avg_latency_ms=1800000,  # 30 分钟
        max_context=999999999,
        capability_score=10,
    ),
}


class ModelRouter:
    """
    6-tier Model Router — 根据任务复杂度路由
    """
    
    def __init__(self):
        self.usage_stats = {tier: {"calls": 0, "tokens": 0, "cost": 0.0} for tier in ModelTier}
        self.total_cost = 0.0
    
    def route(
        self,
        task_complexity: int,  # 1-10
        is_critical: bool = False,
        requires_chinese: bool = False,
        is_real_time: bool = False,
    ) -> ModelSpec:
        """
        路由选择模型
        
        Args:
            task_complexity: 1-10(1 = 简单分类, 10 = 深度推理)
            is_critical: 是否关键决策(强制人工)
            requires_chinese: 是否需要中文强(Qwen)
            is_real_time: 是否实时(本地 vLLM 优先)
        """
        # 关键决策永远人工
        if is_critical:
            chosen = MODELS[ModelTier.HUMAN_REVIEW]
        # 中文 + 实时 → Qwen
        elif requires_chinese and is_real_time:
            chosen = MODELS[ModelTier.QWEN_MAX]
        # 实时 + 不复杂 → 本地
        elif is_real_time and task_complexity <= 5:
            chosen = MODELS[ModelTier.LOCAL_VLLM]
        # 中文 → Qwen
        elif requires_chinese:
            chosen = MODELS[ModelTier.QWEN_MAX]
        # 极简任务 → Haiku
        elif task_complexity <= 3:
            chosen = MODELS[ModelTier.HAIKU]
        # 标准 → Sonnet
        elif task_complexity <= 7:
            chosen = MODELS[ModelTier.SONNET]
        # 复杂 → Opus
        else:
            chosen = MODELS[ModelTier.OPUS]
        
        logger.debug(
            "model_routed",
            task_complexity=task_complexity,
            chosen_tier=chosen.tier.value,
            chosen_model=chosen.model_name,
        )
        return chosen
    
    def record_usage(self, tier: ModelTier, tokens: int):
        """记录使用"""
        spec = MODELS[tier]
        cost = (tokens / 1000) * spec.cost_per_1k_tokens
        self.usage_stats[tier]["calls"] += 1
        self.usage_stats[tier]["tokens"] += tokens
        self.usage_stats[tier]["cost"] += cost
        self.total_cost += cost
    
    def get_stats(self) -> dict:
        return {
            "total_cost_usd": round(self.total_cost, 4),
            "by_tier": {
                tier.value: stats for tier, stats in self.usage_stats.items()
            },
        }


# 单例
_router = None


def get_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


# 快速路由 demo
def quick_route_demo():
    """演示:不同任务怎么路由"""
    router = get_router()
    examples = [
        ("信号简单分类", 2, False, False, False),  # Haiku
        ("多因子综合评估", 6, False, False, False),  # Sonnet
        ("PortfolioManager 深度推理", 9, True, False, False),  # Human
        ("中文研报实时解析", 7, False, True, True),  # Qwen
        ("低延迟订单簿特征", 4, False, False, True),  # Local
    ]
    
    print("\n=== Model Router Demo ===")
    for name, complexity, critical, chinese, realtime in examples:
        spec = router.route(
            task_complexity=complexity,
            is_critical=critical,
            requires_chinese=chinese,
            is_real_time=realtime,
        )
        print(f"  {name} → {spec.tier.value} ({spec.model_name}) @ ${spec.cost_per_1k_tokens}/1k")