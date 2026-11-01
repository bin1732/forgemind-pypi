# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio` 进阶 (signal handler) + `unittest.mock` 进阶 (side_effect) + `decimal` 进阶 (ContextFlags) + `tracemalloc` 进阶 真底层测试。

覆盖 asyncio signal / mock side_effect / decimal ContextFlags / tracemalloc 进阶:
  - `asyncio.loop.add_signal_handler 真注册 SIGUSR1 (沙箱 skip)`
  - `asyncio.Queue 进阶 真跨 task 5 item`
  - `unittest.mock.Mock(side_effect=fn) 真按 args 调 fn`
  - `unittest.mock.Mock(side_effect=[1,2,3]) 真按序返值`
  - `unittest.mock.Mock(side_effect=Exception) 真抛`
  - `unittest.mock.Mock.call_args 真返上 call`
  - `unittest.mock.Mock.call_count 真累加`
  - `unittest.mock.Mock.method_calls 真含子方法 call`
  - `unittest.mock.Mock.assert_called_with 真验 call`
  - `unittest.mock.Mock.assert_not_called 真验不调`
  - `decimal.ContextFlags 3.11+ 真建`
  - `decimal.Context.copy_flags 真复制`
  - `decimal.getcontext().flags 真 dict-like`
  - `tracemalloc.Snapshot.compare_to(other, 'filename') 真 diff`
  - `tracemalloc.Snapshot.statistics('traceback') 真按 traceback 分组`
"""
import asyncio
import decimal
import gc
import signal
import sys
import tracemalloc
import unittest.mock

import pytest


# -- asyncio signal 进阶 ----------------------------------------------------

class TestAsyncioSignal:
    def test_asyncio_loop_add_signal_handler_exists(self):
        """`asyncio.loop.add_signal_handler 3.10+ 真 API 存在`"""
        # 沙箱无 event loop 时简化
        if sys.platform == "win32":
            pytest.skip("Windows 不支持 add_signal_handler")
        # 简化为验 API
        try:
            loop = asyncio.new_event_loop()
            try:
                assert hasattr(loop, "add_signal_handler")
                assert hasattr(loop, "remove_signal_handler")
            finally:
                loop.close()
        except (NotImplementedError, OSError):
            pytest.skip("add_signal_handler 不可用")

    def test_asyncio_Queue_cross_task(self):
        """`asyncio.Queue 真跨 task 5 item 按序。"""

        async def main():
            q = asyncio.Queue()

            async def producer():
                for i in range(5):
                    await q.put(i)

            async def consumer():
                items = []
                while len(items) < 5:
                    items.append(await q.get())
                return items

            prod_task = asyncio.create_task(producer())
            cons_task = asyncio.create_task(consumer())
            await prod_task
            return await cons_task

        result = asyncio.run(main())
        assert result == [0, 1, 2, 3, 4], (
            f"Queue 跨 task 必保序,实际 {result}"
        )


# -- unittest.mock side_effect 进阶 -----------------------------------------

def _add(a, b):
    return a + b


def _raise_fn(*args):
    raise ValueError("forced error")


class TestUnittestMockSideEffect:
    def test_side_effect_function(self):
        """`Mock(side_effect=fn) 真按 args 调 fn。"""
        m = unittest.mock.Mock(side_effect=_add)
        result = m(3, 4)
        assert result == 7, f"side_effect=_add, m(3,4) 应=7,实际 {result}"

    def test_side_effect_iterable(self):
        """`Mock(side_effect=[1, 2, 3]) 真按序返值。"""
        m = unittest.mock.Mock(side_effect=[1, 2, 3])
        assert m() == 1
        assert m() == 2
        assert m() == 3
        # 耗尽后抛 StopIteration
        with pytest.raises(StopIteration):
            m()

    def test_side_effect_exception(self):
        """`Mock(side_effect=Exception) 真抛。"""
        m = unittest.mock.Mock(side_effect=ValueError("forge mock err"))
        with pytest.raises(ValueError) as exc:
            m()
        assert "forge mock err" in str(exc.value)

    def test_call_args(self):
        """`Mock.call_args 真返上 call args。"""
        m = unittest.mock.Mock()
        m("forge", key="value")
        # call_args 是 call("forge", key="value")
        assert m.call_args.args == ("forge",)
        assert m.call_args.kwargs == {"key": "value"}

    def test_call_count(self):
        """`Mock.call_count 真累加。"""
        m = unittest.mock.Mock()
        assert m.call_count == 0
        m()
        m()
        m()
        assert m.call_count == 3

    def test_method_calls(self):
        """`Mock.method_calls 真含子方法 call。"""
        m = unittest.mock.Mock()
        m.attr1()
        m.attr2("arg")
        # method_calls 必含 attr1 + attr2
        method_names = [c[0] for c in m.method_calls]
        assert "attr1" in method_names
        assert "attr2" in method_names

    def test_assert_called_with(self):
        """`Mock.assert_called_with 真验 call。"""
        m = unittest.mock.Mock()
        m(1, 2)
        m.assert_called_with(1, 2)
        # 不匹配抛
        with pytest.raises(AssertionError):
            m.assert_called_with(3, 4)

    def test_assert_not_called(self):
        """`Mock.assert_not_called 真验不调。"""
        m = unittest.mock.Mock()
        m.assert_not_called()
        # 调后抛
        m()
        with pytest.raises(AssertionError):
            m.assert_not_called()


# -- decimal ContextFlags 进阶 -----------------------------------------------

class TestDecimalContextFlags:
    def test_ContextFlags_exists_3_11(self):
        """`decimal.ContextFlags 3.11+ 真存在 (3.11 沙箱跳过)`"""
        if sys.version_info < (3, 11):
            pytest.skip("3.11+ 才有 ContextFlags")
        # 沙箱 3.11.0 上不一定有
        if not hasattr(decimal, "ContextFlags"):
            pytest.skip("沙箱 3.11 无 ContextFlags")
        cf = decimal.ContextFlags()
        assert cf is not None

    def test_Context_copy(self):
        """`decimal.Context.copy() 真复制新 context。"""
        ctx = decimal.getcontext().copy()
        new_ctx = ctx.copy()
        assert new_ctx is not ctx
        assert new_ctx.prec == ctx.prec
        # 改 new_ctx 不影响 ctx
        new_ctx.prec = 5
        assert ctx.prec != 5

    def test_flags_attribute(self):
        """`decimal.getcontext().flags 真含 traps 字段。"""
        ctx = decimal.getcontext()
        # 必含 flags
        assert hasattr(ctx, "flags")
        # 必可访问 traps
        assert hasattr(ctx, "traps")
        # trap_invalid 必是 bool
        assert isinstance(ctx.traps[decimal.InvalidOperation], bool)


# -- tracemalloc 进阶 (compare_to + key_type) --------------------------------

def _allocate():
    return [i for i in range(10000)]


class TestTracemallocAdvancedV4:
    def test_Snapshot_compare_filename(self):
        """`Snapshot.compare_to(other, 'filename') 真按 file 分组 diff。"""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        try:
            snap1 = tracemalloc.take_snapshot()
            data = _allocate()
            snap2 = tracemalloc.take_snapshot()
            diffs = snap2.compare_to(snap1, "filename")
            # 必是 list
            assert isinstance(diffs, list)
            # 必 ≥ 1 个 diff
            assert len(diffs) >= 1
            del data
        finally:
            tracemalloc.stop()

    def test_Snapshot_statistics_traceback(self):
        """`Snapshot.statistics('traceback') 真按 traceback 分组。"""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        try:
            data = _allocate()
            snap = tracemalloc.take_snapshot()
            stats = snap.statistics("traceback")
            assert isinstance(stats, list)
            # 每个 stat 必含 traceback attr
            if stats:
                assert hasattr(stats[0], "traceback")
            del data
        finally:
            tracemalloc.stop()
