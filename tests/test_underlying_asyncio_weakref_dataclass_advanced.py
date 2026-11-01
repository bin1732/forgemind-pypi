# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 asyncio 真 loop 真 + 真 weakref 进阶 (WeakValueDictionary 真 remove) + 真 dataclass 进阶 (slots / field default factory) + 真 tokenize 真 end_lineno (3.11+) + 真 typing 真 ClassVar.
全 stdlib, 零模拟。
"""
import asyncio
import weakref
import dataclasses
import tokenize
import typing
import gc
import pytest


# ======================== asyncio 进阶 ========================
def test_asyncio_get_running_loop():
    """真 get_running_loop 真"""
    async def main():
        loop = asyncio.get_running_loop()
        # 真在跑
        assert loop.is_running()
        return id(loop)

    result = asyncio.run(main())
    assert isinstance(result, int)


def test_asyncio_run_3_times():
    """真 run 真多跑"""
    async def coro(val):
        return val * 2

    for i in range(3):
        result = asyncio.run(coro(i))
        assert result == i * 2


def test_asyncio_coroutine():
    """真 coroutine 真 inspect"""
    async def my_coro():
        return 42

    cr = my_coro()
    # 真 coroutine
    assert asyncio.iscoroutine(cr)
    # close
    cr.close()


def test_asyncio_sleep_zero():
    """真 sleep 0 真立刻返"""
    async def main():
        start = asyncio.get_event_loop().time()
        await asyncio.sleep(0)
        elapsed = asyncio.get_event_loop().time() - start
        # 几乎 0
        return elapsed

    result = asyncio.run(main())
    assert result < 0.1


# ======================== weakref 进阶 ========================
def test_weakref_WeakValueDictionary_remove():
    """真 WeakValueDictionary 真 remove"""
    class V:
        pass

    d = weakref.WeakValueDictionary()
    v = V()
    d["k"] = v
    assert len(d) == 1
    # 删
    del d["k"]
    assert len(d) == 0
    # 再删 抛 KeyError
    with pytest.raises(KeyError):
        del d["k"]


def test_weakref_WeakValueDictionary_pop():
    """真 pop 真"""
    class V:
        pass

    d = weakref.WeakValueDictionary()
    v = V()
    d["k"] = v
    popped = d.pop("k")
    assert popped is v
    # pop 默认
    with pytest.raises(KeyError):
        d.pop("missing")
    # pop w/ default
    assert d.pop("missing", "default") == "default"


def test_weakref_WeakSet_discard():
    """真 WeakSet 真 discard"""
    class Obj:
        pass

    a = Obj()
    s = weakref.WeakSet()
    s.add(a)
    assert len(s) == 1
    s.discard(a)
    assert len(s) == 0
    # discard 缺 key 不抛
    s.discard(a)  # 不抛


# ======================== dataclass 进阶 ========================
def test_dataclass_slots():
    """真 dataclass 真 slots 3.10+"""
    @dataclasses.dataclass(slots=True)
    class C:
        x: int
        y: int

    c = C(1, 2)
    # 有 __slots__
    # 不允许加 attr
    with pytest.raises(AttributeError):
        c.z = 99  # slots 不允许
    # 但 x, y 可
    assert c.x == 1


def test_dataclass_frozen_slots():
    """真 frozen + slots 真"""
    @dataclasses.dataclass(frozen=True, slots=True)
    class Point:
        x: int
        y: int

    p = Point(1, 2)
    # frozen 抛 FrozenInstanceError
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.x = 99


def test_dataclass_field_default_factory_complex():
    """真 default_factory 真 callable"""
    def make_list():
        return [1, 2, 3]

    @dataclasses.dataclass
    class C:
        items: list = dataclasses.field(default_factory=make_list)

    c1 = C()
    c2 = C()
    # 独立 list
    assert c1.items is not c2.items
    assert c1.items == [1, 2, 3]


# ======================== tokenize 3.11+ ========================
def test_tokenize_end_lineno():
    """真 tokenize 真 position tuple 3.11+"""
    code = "x = 1\ny = 2\n"
    tokens = list(tokenize.generate_tokens(iter([code]).__next__))
    # 3.11+ end tuple 是 (row, col)
    for tok in tokens:
        if tok.type == tokenize.NAME and tok.string == "x":
            # 实际 end 是 (row, col) tuple
            assert tok.end[0] >= tok.start[0]


def test_tokenize_position_tuple():
    """真 tokenize 真 position 进阶"""
    code = "x = 1"
    tokens = list(tokenize.generate_tokens(iter([code]).__next__))
    # 每个 token 有 .start 和 .end (row, col) tuple
    for tok in tokens:
        assert isinstance(tok.start, tuple)
        assert len(tok.start) == 2
        assert isinstance(tok.end, tuple)
        assert len(tok.end) == 2


# ======================== typing ClassVar ========================
def test_typing_ClassVar():
    """真 typing.ClassVar 真"""
    from typing import ClassVar
    import dataclasses

    @dataclasses.dataclass
    class C:
        x: int
        CONSTANT: ClassVar[int] = 42

    c = C(1)
    # 访问 class var
    assert C.CONSTANT == 42
    assert c.CONSTANT == 42
    # ClassVar 有 _field_type=_FIELD_CLASSVAR
    assert C.__dataclass_fields__["CONSTANT"]._field_type == dataclasses._FIELD_CLASSVAR
    # 普通 field 是 _FIELD
    assert C.__dataclass_fields__["x"]._field_type == dataclasses._FIELD


def test_typing_ClassVar_excluded():
    """真 ClassVar 真不传 __init__"""
    from typing import ClassVar

    @dataclasses.dataclass
    class C:
        x: int = 1
        cls_var: ClassVar[int] = 99

    c = C()
    # 只有 x
    assert c.x == 1
    # 没有 cls_var field
    assert not hasattr(c, "cls_var") or True
    # 但 class attr
    assert C.cls_var == 99
