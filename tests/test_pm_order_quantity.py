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
        """目标权重 5%、权益 20 万、股价 1444.42 → 卖 93 股

        当前权重按**市值**算:100 股 × 1444.42 / 20 万 = 72.22%,于是要
        减掉 72.22% - 5% = 67.22% 的权益,除以股价得 93 股。

        (原先用成本价当分子,算出的是 96 股 —— 那个式子把"目标市值"
        与"成本市值"混在一起除以现价,分子分母两个口径。)
        """
        decision = portfolio_manager_node(_state())["pm_decision"]
        assert decision["direction"] == "sell"
        assert decision["quantity"] == int(0.67221 * 200_000 / 1444.42)
        assert decision["quantity"] == 93

    def test_quantity_is_not_the_pe_ratio_away(self):
        """PE 比率(缺省 10)除出来是 14000 股 —— 那是错的"""
        decision = portfolio_manager_node(_state())["pm_decision"]
        assert decision["quantity"] != int(0.70 * 200_000 / 10)

    def test_decision_records_the_price_it_used(self):
        """决策里带着用的股价,看的人能自己核"""
        decision = portfolio_manager_node(_state())["pm_decision"]
        assert decision["price"] == 1444.42

    def test_quantity_follows_target_minus_current_market_value(self):
        """恒等式:下单金额 = 目标市值 - 当前市值,股数 = 下单金额 / 现价

        这才是不依赖口径的那条关系。原先那条"股价减半、股数翻倍"其实
        是成本口径下的巧合:当前权重也跟着价格变,于是股数并不与价格
        成反比。改成市值口径后,分子分母同一口径,这条恒等式才立得住。
        """
        for last_close in (1444.42, 722.21):
            decision = portfolio_manager_node(
                _state(
                    technical_analysis={"status": "ok", "last_close": last_close, "confidence": 0.6}
                )
            )["pm_decision"]
            target_value = decision["final_weight"] * 200_000
            current_value = 100 * last_close
            assert decision["quantity"] == int(abs(target_value - current_value) / last_close), (
                last_close,
                decision,
            )

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
        decision = portfolio_manager_node(_state(technical_analysis={"status": "unavailable"}))[
            "pm_decision"
        ]
        assert decision["price"] == 1500.0
        assert decision["quantity"] == int(0.70 * 200_000 / 1500.0)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
