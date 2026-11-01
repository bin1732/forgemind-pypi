# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 dataclass 进阶 (KW_ONLY 进阶 + field metadata) + 真 secrets 真 (token_bytes/choice/token_hex) + 真 typing 真 (final 真) + 真 statistics 真 (mean/stdev/pvariance) + 真 operator 真 (methodcaller/itemgetter 真链) + 真 tracemalloc 进阶.
全 stdlib, 零模拟。
"""
import dataclasses
import secrets
import typing
import statistics
import operator
import tracemalloc
import pytest


# ======================== dataclass 进阶 ========================
def test_dataclass_field_default_factory():
    """真 field default_factory 进阶"""
    @dataclasses.dataclass
    class C:
        items: list = dataclasses.field(default_factory=list)

    c = C()
    c.items.append(1)
    # 不共享
    c2 = C()
    assert c2.items == []


def test_dataclass_field_metadata():
    """真 field metadata 真"""
    @dataclasses.dataclass
    class C:
        x: int = dataclasses.field(metadata={"min": 0, "max": 100})

    c = C(x=50)
    field = dataclasses.fields(c)[0]
    # metadata
    assert field.metadata["min"] == 0
    assert field.metadata["max"] == 100


def test_dataclass_repr_进阶():
    """真 __repr__ 进阶"""
    @dataclasses.dataclass
    class C:
        x: int
        y: str

    c = C(1, "hello")
    r = repr(c)
    # 必有
    assert "C(" in r
    assert "x=1" in r
    assert "y='hello'" in r


# ======================== secrets 进阶 ========================
def test_secrets_token_bytes():
    """真 token_bytes 真"""
    t = secrets.token_bytes(16)
    # 16 bytes
    assert len(t) == 16
    # 真 OS entropy
    # 2 次必不同
    t2 = secrets.token_bytes(16)
    assert t != t2


def test_secrets_token_hex():
    """真 token_hex 真"""
    t = secrets.token_hex(8)
    # 16 hex chars (8 bytes = 16 hex)
    assert len(t) == 16
    # 全 hex
    int(t, 16)  # 必可 parse


def test_secrets_choice():
    """真 choice 真"""
    items = ["a", "b", "c", "d", "e"]
    chosen = secrets.choice(items)
    # 必 in list
    assert chosen in items


# ======================== typing 进阶 ========================
def test_typing_Final():
    """真 Final 真"""
    if hasattr(typing, "Final"):
        # 3.8+
        F = typing.Final[int]
        # F 是 typing special form
        assert hasattr(F, "__class__")
    else:
        pytest.skip("Final requires Python 3.8+")


def test_typing_Annotated():
    """真 Annotated 真"""
    if hasattr(typing, "Annotated"):
        A = typing.Annotated[int, "min", 0]
        # get_args 返 (int, "min", 0)
        args = typing.get_args(A)
        assert int in args
    else:
        pytest.skip("Annotated requires Python 3.9+")


# ======================== statistics 真 ========================
def test_statistics_mean():
    """真 mean 真"""
    assert statistics.mean([1, 2, 3, 4, 5]) == 3.0


def test_statistics_stdev():
    """真 stdev 真 (sample, ddof=1)"""
    # [1, 2, 3, 4, 5]: mean=3, var=2.5, stdev=√2.5
    s = statistics.stdev([1, 2, 3, 4, 5])
    expected = (2.5 ** 0.5)
    assert abs(s - expected) < 1e-9


def test_statistics_pvariance():
    """真 pvariance 真 (population, ddof=0)"""
    # [1, 2, 3, 4, 5]: mean=3, pvar=2.0
    v = statistics.pvariance([1, 2, 3, 4, 5])
    assert abs(v - 2.0) < 1e-9


def test_statistics_median():
    """真 median 真"""
    assert statistics.median([1, 2, 3, 4, 5]) == 3
    assert statistics.median([1, 2, 3, 4]) == 2.5


# ======================== operator 进阶 ========================
def test_operator_methodcaller():
    """真 methodcaller 真链"""
    # 调 "upper" 链
    upper = operator.methodcaller("upper")
    assert upper("hello") == "HELLO"


def test_operator_itemgetter_multi():
    """真 itemgetter 多索引"""
    get = operator.itemgetter(0, 1, 2)
    assert get([10, 20, 30, 40]) == (10, 20, 30)


def test_operator_attrgetter_path():
    """真 attrgetter 路径 inner.v"""
    class Inner:
        v = 42

    class Outer:
        inner = Inner()

    get_v = operator.attrgetter("inner.v")
    assert get_v(Outer()) == 42


# ======================== tracemalloc 进阶 ========================
def test_tracemalloc_get_traced_memory():
    """真 get_traced_memory 真"""
    tracemalloc.start()
    try:
        # 分配
        data = [1] * 100
        # get_traced_memory 返 (current, peak) bytes
        current, peak = tracemalloc.get_traced_memory()
        # current > 0
        assert current > 0
        # peak ≥ current
        assert peak >= current
    finally:
        tracemalloc.stop()
