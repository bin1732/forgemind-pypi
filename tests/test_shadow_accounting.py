# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""影子盘的资金核算必须两侧对称

只有卖出分支扣手续费,买入侧的手续费直接蒸发。
1000 股 @10 买、@12 卖、双边各 1bp 佣金:

    应有  毛利 2000 − 买费 10 − 卖费 12 = 1978
    实报  1988                      ← 缺口恰好是买入手续费

高频交易下这个缺口持续累积,而"总盈亏"看起来完全正常。
另外 current_capital 只是"初始资金 + 净已实现盈亏",**不随未平仓
头寸的浮动盈亏变化** —— 把它当总资产报出去会在持仓期间严重低估账户。
"""

import asyncio
from datetime import datetime
from uuid import uuid4

import pytest

from forgemind.core.events.types import MarketTickEvent, SignalEvent
from forgemind.core.live.shadow import ShadowTrader


def _tick(bid: float, ask: float) -> MarketTickEvent:
    return MarketTickEvent(
        event_id=uuid4(), event_type="MARKET_TICK", timestamp=datetime.now(),
        session_id=uuid4(), symbol="600519.SH", bid=bid, ask=ask,
        last=ask, volume=1000)


def _sig(direction: str) -> SignalEvent:
    return SignalEvent(
        event_id=uuid4(), event_type="SIGNAL", timestamp=datetime.now(),
        session_id=uuid4(), symbol="600519.SH", direction=direction,
        strength=10, confidence=0.8)


class _DummyStrategy:
    async def on_bar(self, bar):  # noqa: D102
        return None


def _trader(commission_bps=10, slippage_bps=0) -> ShadowTrader:
    tr = ShadowTrader(_DummyStrategy(), lambda s: None, initial_capital=100_000.0)
    tr.matching.fill_ratio = 1.0
    tr.matching.commission_bps = commission_bps
    tr.matching.slippage_bps = slippage_bps
    return tr


class TestCommissionIsSymmetric:
    def test_round_trip_net_pnl_matches_hand_computed(self):
        tr = _trader()
        asyncio.run(tr._execute_signal(_sig("buy"), _tick(10.0, 10.0)))
        asyncio.run(tr._execute_signal(_sig("sell"), _tick(12.0, 12.0)))

        buy_comm = 1000 * 10.0 * 10 / 10_000
        sell_comm = 1000 * 12.0 * 10 / 10_000
        expected = (12.0 - 10.0) * 1000 - buy_comm - sell_comm
        assert tr.total_pnl == pytest.approx(expected, abs=1e-6), (
            f"净盈亏 {tr.total_pnl:.4f} != 应有 {expected:.4f} —— 有一侧佣金没记账")
        assert tr.total_commission == pytest.approx(buy_comm + sell_comm)

    def test_buy_alone_deducts_commission_from_capital(self):
        """只买不卖也要扣 —— 否则持仓期的现金是虚的"""
        tr = _trader()
        asyncio.run(tr._execute_signal(_sig("buy"), _tick(10.0, 10.0)))
        assert tr.current_capital == pytest.approx(100_000.0 - 10.0)
        assert tr.total_pnl < 0, "买入手续费应体现为当期负盈亏"

    def test_zero_commission_still_works(self):
        tr = _trader(commission_bps=0)
        asyncio.run(tr._execute_signal(_sig("buy"), _tick(10.0, 10.0)))
        asyncio.run(tr._execute_signal(_sig("sell"), _tick(12.0, 12.0)))
        assert tr.total_pnl == pytest.approx(2000.0)
        assert tr.total_commission == 0


class TestAverageCostAccounting:
    def test_averages_in_additional_buys(self):
        tr = _trader(commission_bps=0)
        asyncio.run(tr._execute_signal(_sig("buy"), _tick(10.0, 10.0)))  # 1000 @10
        tr.matching.fill_ratio = 1.0
        sig = _sig("buy")
        sig.strength = 20
        asyncio.run(tr._execute_signal(sig, _tick(20.0, 20.0)))         # 2000 @20
        pos = tr.positions["600519.SH"]
        assert pos["qty"] == 3000
        assert pos["avg_price"] == pytest.approx((1000 * 10 + 2000 * 20) / 3000)

    def test_sell_always_closes_the_whole_position(self):
        """sell 分支是 order_qty = -position["qty"],即只支持全平

        这不是 bug 而是设计:影子盘不做部分减仓。测试如实反映这一点,
        免得后来者以为存在部分卖出路径而去测试不存在的东西。
        """
        tr = _trader(commission_bps=0)
        asyncio.run(tr._execute_signal(_sig("buy"), _tick(10.0, 10.0)))
        sig = _sig("buy")
        sig.strength = 20
        asyncio.run(tr._execute_signal(sig, _tick(20.0, 20.0)))
        assert tr.positions["600519.SH"]["qty"] == 3000
        asyncio.run(tr._execute_signal(_sig("sell"), _tick(12.0, 12.0)))
        pos = tr.positions["600519.SH"]
        assert pos["qty"] == 0
        assert pos["avg_price"] == 0.0, "清仓后成本价应归零"
        # 均价法验证:(1000*10 + 2000*20)/3000 = 16.667,卖出 12 应亏 4667
        assert tr.total_pnl == pytest.approx((12.0 - 50 / 3) * 3000)


class TestEquityIsMarkedToMarket:
    def test_equity_includes_unrealised_pnl(self):
        """current_capital 不含浮盈;总资产必须用盯市口径"""
        tr = _trader(commission_bps=0)
        asyncio.run(tr._execute_signal(_sig("buy"), _tick(10.0, 10.0)))
        # 持仓 1000 股,成本 10,现价 13 → 浮盈 3000
        eq = tr.mark_to_market_equity({"600519.SH": 13.0})
        assert eq == pytest.approx(100_000.0 + 3000.0)
        # current_capital 此时不含这 3000 —— 这正是必须盯市的原因
        assert tr.current_capital == pytest.approx(100_000.0)

    def test_equity_equals_capital_when_flat(self):
        tr = _trader()
        asyncio.run(tr._execute_signal(_sig("buy"), _tick(10.0, 10.0)))
        asyncio.run(tr._execute_signal(_sig("sell"), _tick(12.0, 12.0)))
        assert tr.mark_to_market_equity({"600519.SH": 12.0}) == pytest.approx(
            tr.current_capital)
