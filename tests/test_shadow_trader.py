# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""ShadowTrader 契约测试

`market_data_source` 标注为 `Callable[[str], Awaitable]`,
但 `start()` 内部用的是 `async for` —— 签名与用法自相矛盾,按签名传入的
用户会直接 TypeError。同时 tick 必须是 MarketTickEvent,传 dict 会因
缺 .symbol 抛 AttributeError。这两点都没有任何测试覆盖。
"""

import asyncio
from datetime import datetime, timedelta

from forgemind.core.events.types import MarketTickEvent
from forgemind.core.live.shadow import ShadowTrader
from forgemind.core.strategies.base import MovingAverageCrossStrategy


def _strategy():
    return MovingAverageCrossStrategy(parameters={"fast_period": 3, "slow_period": 6})


def _ticks(symbol: str, n: int = 30):
    """按真实契约产出 MarketTickEvent"""
    px = 100.0
    base = datetime(2024, 1, 1)
    for i in range(n):
        px *= (1.002 if i % 3 else 0.998)
        yield MarketTickEvent(
            timestamp=base + timedelta(minutes=i),
            symbol=symbol, bid=px - 0.01, ask=px + 0.01, last=px,
            volume=1000 + i, bid_size=100, ask_size=100,
        )


class TestShadowTraderContract:
    def test_source_signature_matches_async_iteration(self):
        """签名必须是 AsyncIterable —— 与 `async for` 的实际用法一致"""
        import inspect
        from collections.abc import AsyncIterable
        from typing import get_args, get_origin

        hints = inspect.get_annotations(
            ShadowTrader.__init__, eval_str=True
        )
        ret = hints["market_data_source"].__args__[-1]
        origin = get_origin(ret)
        assert origin is AsyncIterable, (
            f"返回值应标注 AsyncIterable,实际 {ret} —— 与 async for 用法不符"
        )
        (arg,) = get_args(ret)
        assert arg is MarketTickEvent, f"应产出 MarketTickEvent,实际 {arg}"

    def test_start_consumes_async_generator(self):
        """最自然的用法(异步生成器)必须能跑通"""
        async def src(symbol):
            for t in _ticks(symbol):
                yield t

        async def run():
            tr = ShadowTrader(strategy=_strategy(), market_data_source=src)
            await asyncio.wait_for(tr.start("600519.SH"), timeout=20)
            return tr

        tr = asyncio.run(run())
        assert tr.shadow_id is not None

    def test_reports_stop_metrics(self):
        async def src(symbol):
            for t in _ticks(symbol, 10):
                yield t

        async def run():
            tr = ShadowTrader(strategy=_strategy(), market_data_source=src)
            await asyncio.wait_for(tr.start("600519.SH"), timeout=20)
            await tr.stop()
            return tr

        tr = asyncio.run(run())
        assert tr.running is False
        assert isinstance(tr.total_trades, int)
        assert tr.current_capital > 0

    def test_stop_before_start_is_safe(self):
        """不订阅直接 stop 不应抛异常"""
        tr = ShadowTrader(strategy=_strategy(), market_data_source=lambda s: src_empty())
        asyncio.run(tr.stop())
        assert tr.total_trades == 0


def src_empty():
    async def _gen():
        return
        yield  # pragma: no cover

    return _gen()
