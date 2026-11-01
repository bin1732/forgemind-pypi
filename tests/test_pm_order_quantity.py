# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""PM 节点的下单数量必须按**真股价**算。

当初的岔子:下单数量算成 `目标金额 / PE 比率`(pe_ratio 缺省 10)。
14 万的目标金额除出来是 14000 股 —— 按真股价(约 1500)该卖 90 多股,
**差了一百多倍**。

界面上只看到一个数字,没有测试盯过它,于是这个错一路活到今天。
现在钉住:股数必须等于 目标金额 / 股价。

    python -m pytest tests/test_pm_order_quantity.py -v
"""

from __future__ import annotations

import pytest

from forgemind.core.agents.portfolio_context import portfolio_manager_node


def _state(**over) -> dict:
    state = {
        "symbol": "600519.SH",
        "portfolio": {
            "total_equity": 200_000.0,
            "positions": [
                {"symbol": "600519.SH", "quantity": 100, "avg_price": 1500.0},
            ],
        },
        "bull_case": {"thesis": "上穿 MA20", "target_weight": 0.10},
        "bear_case": {"thesis": "空头排列", "max_weight": 0.05},
        "fundamentals_analysis": {"status": "unavailable", "confidence": 0.0},
        "technical_analysis": {"status": "ok", "last_close": 1444.42, "confidence": 0.6},
        "news_analysis": {"status": "unavailable", "confidence": 0.0},
    }
    state.update(over)
    return state


class TestOrderQuantityFollowsPrice:
    def test_sell_quantity_uses_the_real_price(self):
        """目标权重 5%、当前 75%、权益 20 万、股价 1444.42 → 卖 96 股"""
        decision = portfolio_manager_node(_state())["pm_decision"]
        assert decision["direction"] == "sell"
        assert decision["quantity"] == int(0.70 * 200_000 / 1444.42)
        assert decision["quantity"] == 96

    def test_quantity_is_not_the_pe_ratio_away(self):
        """PE 比率(缺省 10)除出来是 14000 股 —— 那是错的"""
        decision = portfolio_manager_node(_state())["pm_decision"]
        assert decision["quantity"] != int(0.70 * 200_000 / 10)

    def test_decision_records_the_price_it_used(self):
        """决策里带着用的股价,看的人能自己核"""
        decision = portfolio_manager_node(_state())["pm_decision"]
        assert decision["price"] == 1444.42

    def test_quantity_scales_with_the_price(self):
        """股价减半,同一目标金额的股数翻倍(int 截断,差个位)"""
        low = portfolio_manager_node(_state())["pm_decision"]["quantity"]
        high = portfolio_manager_node(
            _state(technical_analysis={"status": "ok", "last_close": 722.21, "confidence": 0.6})
        )["pm_decision"]["quantity"]
        assert abs(high - low * 2) <= 1

    def test_buy_quantity_uses_the_real_price(self):
        """空仓时买:最终权重 5%(bear 的 max_weight 压住)、权益 20 万、股价 1000 → 买 10 股"""
        decision = portfolio_manager_node(
            _state(
                portfolio={"total_equity": 200_000.0, "positions": []},
                technical_analysis={"status": "ok", "last_close": 1000.0, "confidence": 0.6},
            )
        )["pm_decision"]
        assert decision["direction"] == "buy"
        # 最终权重 = min(bull 的 10%, bear 的上限 5%) = 5%
        assert decision["final_weight"] == 0.05
        assert decision["quantity"] == int(0.05 * 200_000 / 1000.0)


class TestNoPriceNoOrder:
    def test_without_a_price_no_quantity_is_given(self):
        """拿不到真价格就不下单 —— 不拿别的东西冒充股价"""
        decision = portfolio_manager_node(
            _state(
                portfolio={"total_equity": 200_000.0, "positions": []},
                technical_analysis={"status": "unavailable"},
            )
        )["pm_decision"]
        assert decision["quantity"] == 0
        assert decision["direction"] == "hold"
        assert decision["no_price_reason"]

    def test_position_average_price_is_used_as_fallback(self):
        """没有技术面时退回持仓均价"""
        decision = portfolio_manager_node(
            _state(technical_analysis={"status": "unavailable"})
        )["pm_decision"]
        assert decision["price"] == 1500.0
        assert decision["quantity"] == int(0.70 * 200_000 / 1500.0)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
