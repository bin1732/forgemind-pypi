# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 stdlib functional — functools.lru_cache 真命中 / itertools 真算 / operator 真用。
"""
import functools
import itertools
import operator
import time

import pytest


def test_lru_cache_actually_caches():
    """functools.lru_cache 真缓存: 第二次调不走函数体"""
    call_count = [0]

    @functools.lru_cache(maxsize=128)
    def expensive(n):
        call_count[0] += 1
        return n * 2

    # 第一次: 真调
    assert expensive(5) == 10
    assert call_count[0] == 1
    # 第二次: 命中缓存, 不调
    assert expensive(5) == 10
    assert call_count[0] == 1
    # 不同 arg: 调
    expensive(6)
    assert call_count[0] == 2


def test_lru_cache_info_real():
    """lru_cache_info 真报 hits / misses / maxsize / currsize"""
    @functools.lru_cache(maxsize=10)
    def f(x):
        return x

    f(1); f(1); f(2); f(3)  # 4 calls: 1 hit (1 dup)
    info = f.cache_info()
    assert info.hits == 1, f"hits 应 1, 实际 {info.hits}"
    assert info.misses == 3, f"misses 应 3, 实际 {info.misses}"
    assert info.maxsize == 10
    assert info.currsize == 3


def test_lru_cache_clear_real():
    """cache_clear 真清空"""
    @functools.lru_cache(maxsize=10)
    def f(x):
        return x

    f(1)
    f.cache_clear()
    info = f.cache_info()
    assert info.currsize == 0
    assert info.hits == 0


def test_functools_reduce_real():
    """functools.reduce 真折叠"""
    result = functools.reduce(operator.add, [1, 2, 3, 4, 5])
    assert result == 15
    # 带 initial
    result2 = functools.reduce(operator.mul, [1, 2, 3], 10)
    assert result2 == 60  # 10 * 1 * 2 * 3


def test_partial_real():
    """functools.partial 真绑部分参数"""
    def power(base, exp):
        return base ** exp

    square = functools.partial(power, exp=2)
    cube = functools.partial(power, exp=3)
    assert square(5) == 25
    assert cube(5) == 125
    # partial.func / args / keywords
    assert square.func is power
    assert square.keywords == {"exp": 2}


def test_itertools_chain_real():
    """itertools.chain 真串联多 iter"""
    result = list(itertools.chain([1, 2], (3, 4), "ab"))
    assert result == [1, 2, 3, 4, "a", "b"]


def test_itertools_cycle_real():
    """itertools.cycle 真无限循环"""
    cycler = itertools.cycle(["a", "b", "c"])
    first_8 = [next(cycler) for _ in range(8)]
    assert first_8 == ["a", "b", "c", "a", "b", "c", "a", "b"]


def test_itertools_islice_real():
    """itertools.islice 真切片无限 iter"""
    result = list(itertools.islice(itertools.count(10), 5))
    assert result == [10, 11, 12, 13, 14]


def test_itertools_combinations_real():
    """itertools.combinations 真产 C(n, k)"""
    result = list(itertools.combinations([1, 2, 3, 4], 2))
    assert result == [(1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)]
    assert len(result) == 6


def test_itertools_permutations_real():
    """itertools.permutations 真产 P(n, k)"""
    result = list(itertools.permutations([1, 2, 3], 2))
    assert result == [(1, 2), (1, 3), (2, 1), (2, 3), (3, 1), (3, 2)]
    assert len(result) == 6


def test_itertools_groupby_real():
    """itertools.groupby 真按 key 分组 (需先排序)"""
    data = sorted([("a", 1), ("b", 2), ("a", 3), ("a", 4), ("b", 5)])
    grouped = {k: [v for _, v in g] for k, g in itertools.groupby(data, key=lambda x: x[0])}
    assert grouped == {"a": [1, 3, 4], "b": [2, 5]}


def test_itertools_accumulate_real():
    """itertools.accumulate 真累加"""
    result = list(itertools.accumulate([1, 2, 3, 4, 5]))
    assert result == [1, 3, 6, 10, 15]
    # 带 func
    result_max = list(itertools.accumulate([3, 1, 4, 1, 5, 9, 2, 6], max))
    assert result_max == [3, 3, 4, 4, 5, 9, 9, 9]


def test_operator_itemgetter_real():
    """operator.itemgetter 真取 index/key"""
    get_first = operator.itemgetter(0)
    get_name = operator.itemgetter("name")
    assert get_first([10, 20, 30]) == 10
    assert get_name({"name": "Alice", "age": 30}) == "Alice"
    # multi
    get_0_2 = operator.itemgetter(0, 2)
    assert get_0_2([10, 20, 30]) == (10, 30)


def test_operator_attrgetter_real():
    """operator.attrgetter 真取 attr"""
    class Point:
        def __init__(self, x, y):
            self.x = x
            self.y = y
    p = Point(3, 4)
    get_xy = operator.attrgetter("x", "y")
    assert get_xy(p) == (3, 4)
    assert operator.attrgetter("x")(p) == 3


def test_itertools_starmap_real():
    """itertools.starmap 真展开 tuple 调 func"""
    result = list(itertools.starmap(pow, [(2, 3), (3, 2), (10, 2)]))
    assert result == [8, 9, 100]


def test_itertools_tee_real():
    """itertools.tee 真复制 iter 为 N 份独立"""
    a, b = itertools.tee([1, 2, 3, 4, 5], 2)
    assert list(a) == [1, 2, 3, 4, 5]
    assert list(b) == [1, 2, 3, 4, 5]
    # 独立 (改 a 不影响 b)
    a_list = list(a)
    b_list = list(b)
    # 都消费
    assert a_list == b_list
