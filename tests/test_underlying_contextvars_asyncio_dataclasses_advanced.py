# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`contextvars` + `asyncio` (advanced) + `dataclasses` 真底层测试。

覆盖跨协程变量与 dataclass 高级特性:
  - `contextvars.ContextVar` 真在 `copy_context().run(...)` 内 set,
    外部不可见 (协程隔离)
  - `contextvars.Token` 拿回原值,`var.reset(token)` 还原
  - `asyncio.run(coro)` 真跑 coroutine 拿回结果
  - `asyncio.gather(c1, c2, c3)` 真并发跑 3 个 coroutine,返 list
  - `asyncio.wait_for(coro, timeout=...)` 真超时抛 `asyncio.TimeoutError`
  - `dataclasses.dataclass(frozen=True, slots=True)` 真不可变 + __slots__
  - `dataclasses.fields(cls)` 真按定义顺序返 tuple,每个有 .name/.type
  - `dataclasses.asdict` + `astuple` 真 dict/tuple 转换 (递归)
"""
import asyncio
import contextvars
import dataclasses
import inspect
import sys
import time

import pytest


# -- contextvars --------------------------------------------------------------

CV = contextvars.ContextVar("forge_counter", default=0)


class TestContextVars:
    def test_context_var_isolated_in_run(self):
        """`ContextVar.set` 在 `Context.run()` 内 set,外部不可见。"""
        outer_value = CV.get()
        ctx = contextvars.copy_context()
        # 在 ctx 内 set 后,用 ctx.run 内部访问
        def in_ctx():
            CV.set(42)
            return CV.get()
        got_inside = ctx.run(in_ctx)
        # ctx 内 set 不影响主 context
        assert CV.get() == outer_value, (
            f"主 CV 不应被 ctx.run 改,实际 {CV.get()}"
        )
        # 在 ctx 内 CV 应是 42
        assert got_inside == 42, f"ctx.run 内 CV 应=42,实际 {got_inside}"

    def test_token_reset_restores_value(self):
        """`ContextVar.set(v)` 返 Token,`var.reset(token)` 还原旧值。"""
        CV.set(100)
        token = CV.set(200)
        assert CV.get() == 200
        CV.reset(token)
        assert CV.get() == 100, (
            f"reset(token) 后 CV 应回到 100,实际 {CV.get()}"
        )


# -- asyncio advanced ---------------------------------------------------------

class TestAsyncioAdvanced:
    def test_run_returns_value(self):
        """`asyncio.run(coro)` 真跑并返 coroutine 结果。"""
        async def add(a, b):
            return a + b

        result = asyncio.run(add(3, 4))
        assert result == 7

    def test_gather_concurrent(self):
        """`asyncio.gather(c1, c2, c3)` 真并发跑 3 个,返 list 顺序对齐。"""
        async def fetch(name, delay):
            await asyncio.sleep(delay)
            return name

        async def main():
            return await asyncio.gather(
                fetch("a", 0.05),
                fetch("b", 0.02),
                fetch("c", 0.01),
            )

        result = asyncio.run(main())
        assert result == ["a", "b", "c"], (
            f"gather 应保留输入顺序,实际 {result!r}"
        )

    def test_wait_for_timeout(self):
        """`asyncio.wait_for(slow, 0.05)` 真超时抛 `asyncio.TimeoutError`。"""
        async def slow():
            await asyncio.sleep(10)
            return "done"

        async def main():
            try:
                await asyncio.wait_for(slow(), timeout=0.05)
            except asyncio.TimeoutError:
                return "timed_out"

        result = asyncio.run(main())
        assert result == "timed_out", f"0.05s timeout 应触发 TimeoutError,实际 {result}"

    def test_task_name_and_done(self):
        """`asyncio.create_task(coro, name=...)` 真把 name 写入 task。"""
        async def work():
            await asyncio.sleep(0.01)

        async def main():
            t = asyncio.create_task(work(), name="forge-task")
            assert t.get_name() == "forge-task"
            assert t.done() is False
            await t
            assert t.done() is True

        asyncio.run(main())


# -- dataclasses advanced ----------------------------------------------------

class TestDataclassesAdvanced:
    def test_frozen_dataclass_rejects_mutation(self):
        """`frozen=True` dataclass 真禁止修改,set attr 抛 `FrozenInstanceError`。"""
        @dataclasses.dataclass(frozen=True)
        class Pt:
            x: int
            y: int

        p = Pt(1, 2)
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.x = 99

    def test_dataclass_with_slots(self):
        """`slots=True` dataclass 真的有 __slots__,不允许新 attr。"""
        @dataclasses.dataclass(slots=True)
        class V:
            val: int

        v = V(5)
        # slots 类不允许任意新 attr
        with pytest.raises(AttributeError):
            v.new_attr = 1  # type: ignore[attr-defined]

    def test_fields_preserves_order(self):
        """`dataclasses.fields(cls)` 真按定义顺序返 tuple。"""
        @dataclasses.dataclass
        class Triple:
            x: int
            y: int
            z: int

        names = [f.name for f in dataclasses.fields(Triple)]
        assert names == ["x", "y", "z"], f"字段顺序应为 x,y,z,实际 {names}"

    def test_asdict_astuple_recursive(self):
        """`asdict` + `astuple` 真递归把嵌套 dataclass 转 dict/tuple。"""
        @dataclasses.dataclass
        class Inner:
            v: int

        @dataclasses.dataclass
        class Outer:
            name: str
            inner: Inner

        o = Outer("forge", Inner(7))
        d = dataclasses.asdict(o)
        assert d == {"name": "forge", "inner": {"v": 7}}, (
            f"asdict 应递归,实际 {d!r}"
        )
        t = dataclasses.astuple(o)
        assert t == ("forge", (7,)), f"astuple 应递归,实际 {t!r}"

    def test_dataclass_inheritance_field_order(self):
        """子类 dataclass 字段顺序应保持父类在前,子类在后。"""
        @dataclasses.dataclass
        class A:
            a: int = 1

        @dataclasses.dataclass
        class B(A):
            b: int = 2

        names = [f.name for f in dataclasses.fields(B)]
        assert names == ["a", "b"], f"继承字段顺序应为 [a, b],实际 {names}"
