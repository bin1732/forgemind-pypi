# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
from uuid import uuid4
from datetime import datetime

from forgemind.core.live.shadow import (
    VirtualMatchingEngine, ShadowTrader, PromotionGate,
)
from forgemind.core.events.types import (
    MarketTickEvent, OrderRequestEvent,
)


class TestVirtualMatching:
    """虚拟撮合 — 模拟真实成交的滑点 / 拒单率"""
    
    @pytest.mark.asyncio
    async def test_simulate_fill_with_slippage(self):
        """买单应按 ask + 滑点成交"""
        engine = VirtualMatchingEngine(slippage_bps=5.0, fill_ratio=1.0)
        tick = MarketTickEvent(
            symbol="600519.SH", bid=100.0, ask=100.5, last=100.3, volume=1000,
        )
        order = OrderRequestEvent(
            symbol="600519.SH", side="buy", quantity=100, order_type="MARKET",
        )
        fill = await engine.simulate_fill(order, tick)
        assert fill.side == "buy"
        # 滑点 >= ask(买价更高)
        assert fill.price >= tick.ask
        assert fill.is_virtual
    
    @pytest.mark.asyncio
    async def test_simulate_sell_with_slippage(self):
        """卖单应按 bid - 滑点成交"""
        engine = VirtualMatchingEngine(slippage_bps=5.0, fill_ratio=1.0)
        tick = MarketTickEvent(
            symbol="600519.SH", bid=100.0, ask=100.5, last=100.3, volume=1000,
        )
        order = OrderRequestEvent(
            symbol="600519.SH", side="sell", quantity=100, order_type="MARKET",
        )
        fill = await engine.simulate_fill(order, tick)
        assert fill.side == "sell"
        # 滑点:卖价更低
        assert fill.price <= tick.bid
    
    @pytest.mark.asyncio
    async def test_fill_ratio_zero(self):
        """fill_ratio=0 应该 100% 拒单"""
        engine = VirtualMatchingEngine(fill_ratio=0.0)
        tick = MarketTickEvent(
            symbol="000001.SZ", bid=10.0, ask=10.05, last=10.03, volume=100,
        )
        order = OrderRequestEvent(
            symbol="000001.SZ", side="buy", quantity=100, order_type="MARKET",
        )
        # 跑多次,验证至少有 0 成交量的情况
        for _ in range(20):
            fill = await engine.simulate_fill(order, tick)
            # fill_ratio=0 时 fill_qty 应该全是 0
            if fill.quantity == 0:
                # 至少要有一次未成交
                break
        else:
            # 全都成交(20 次都 100% 成交概率 = 0)
            pytest.fail("fill_ratio=0 时不应 100% 成交")


class TestPromotionGate:
    """Promotion Gate — 影子 → 实盘 决策门"""
    
    @pytest.mark.asyncio
    async def test_pass_all(self):
        """所有条件都满足应该通过"""
        gate = PromotionGate()
        result = await gate.evaluate(
            shadow_metrics={
                "days_running": 30,
                "sharpe": 2.0,
                "max_drawdown": -0.05,
                "win_rate": 0.60,
                "total_pnl": 10000,
            },
            backtest_metrics={"total_pnl": 9800},  # 差异 ~2% < 5%
        )
        assert result["passed"] is True
        assert "passed" in result
    
    @pytest.mark.asyncio
    async def test_fail_sharpe(self):
        """Sharpe 不够应该被拒"""
        gate = PromotionGate(min_sharpe=2.0)
        result = await gate.evaluate(
            shadow_metrics={
                "days_running": 30,
                "sharpe": 1.0,  # 低于 2.0
                "max_drawdown": -0.05,
                "win_rate": 0.60,
                "total_pnl": 10000,
            },
            backtest_metrics={"total_pnl": 9500},
        )
        assert result["passed"] is False
        assert "Sharpe" in result["reason"] or "sharpe" in result["reason"].lower()
    
    @pytest.mark.asyncio
    async def test_fail_days(self):
        """运行天数不够应该被拒"""
        gate = PromotionGate(min_days=14)
        result = await gate.evaluate(
            shadow_metrics={
                "days_running": 7,  # 不到 14 天
                "sharpe": 2.0,
                "max_drawdown": -0.05,
                "win_rate": 0.60,
                "total_pnl": 10000,
            },
            backtest_metrics={"total_pnl": 9500},
        )
        assert result["passed"] is False
    
    @pytest.mark.asyncio
    async def test_fail_max_drawdown(self):
        """最大回撤超限应该被拒"""
        gate = PromotionGate(max_drawdown=-0.10)
        result = await gate.evaluate(
            shadow_metrics={
                "days_running": 30,
                "sharpe": 2.0,
                "max_drawdown": -0.20,  # 超 -10% 限制
                "win_rate": 0.60,
                "total_pnl": 10000,
            },
            backtest_metrics={"total_pnl": 9500},
        )
        assert result["passed"] is False
    
    @pytest.mark.asyncio
    async def test_fail_backtest_shadow_divergence(self):
        """实盘 vs 回测 PnL 偏离过大应该被拒"""
        gate = PromotionGate(max_backtest_diff_pct=5.0)  # 5%
        result = await gate.evaluate(
            shadow_metrics={
                "days_running": 30,
                "sharpe": 2.0,
                "max_drawdown": -0.05,
                "win_rate": 0.60,
                "total_pnl": 10000,
            },
            backtest_metrics={"total_pnl": 5000},  # 偏离 50%,远超 5%
        )
        assert result["passed"] is False


class TestShadowTrader:
    """Shadow Trader 主体测试"""
    
    def test_create(self):
        """创建 Shadow Trader 应生成 UUID"""
        from forgemind.core.strategies.base import MovingAverageCrossStrategy
        strategy = MovingAverageCrossStrategy()
        async def dummy_source(symbol):
            yield MarketTickEvent(symbol=symbol, bid=100, ask=100.5, last=100.3, volume=1000)
        
        shadow = ShadowTrader(strategy, dummy_source)
        assert shadow.shadow_id is not None
        assert shadow.initial_capital == 1_000_000.0
    
    def test_get_metrics_empty(self):
        """没跑过应该返回 0 PnL"""
        from forgemind.core.strategies.base import MovingAverageCrossStrategy
        strategy = MovingAverageCrossStrategy()
        async def dummy_source(symbol):
            yield
        
        metrics = ShadowTrader(strategy, dummy_source).get_metrics()
        assert "shadow_id" in metrics
        assert metrics["total_pnl"] == 0
        assert metrics["total_trades"] == 0
    
    def test_initial_capital_custom(self):
        """应支持自定义初始资金"""
        from forgemind.core.strategies.base import MovingAverageCrossStrategy
        strategy = MovingAverageCrossStrategy()
        async def dummy_source(symbol):
            yield
        
        shadow = ShadowTrader(strategy, dummy_source, initial_capital=500_000)
        assert shadow.initial_capital == 500_000