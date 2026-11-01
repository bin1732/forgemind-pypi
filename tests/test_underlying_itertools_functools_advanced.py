# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 itertools 进阶 (starmap / compress / filterfalse / zip_longest / accumulate) + 真 functools 进阶 (reduce / wraps / total_ordering / lru_cache 进阶) + 真 operator 真 add 真 mul 真 truediv。
全 stdlib, 零模拟。
"""
import itertools
import functools
import operator
import pytest


# ======================== itertools 进阶 ========================
def test_itertools_starmap():
    """真 starmap 真解包"""
    data = [(1, 2), (3, 4), (5, 6)]
    result = list(itertools.starmap(operator.add, data))
    assert result == [3, 7, 11]


def test_itertools_compress():
    """真 compress 真按 mask 筛"""
    data = ["a", "b", "c", "d", "e"]
    selectors = [True, False, True, False, True]
    result = list(itertools.compress(data, selectors))
    assert result == ["a", "c", "e"]


def test_itertools_filterfalse():
    """真 filterfalse 真反向"""
    data = [1, 2, 3, 4, 5, 6]
    result = list(itertools.filterfalse(lambda x: x % 2 == 0, data))
    # 奇数
    assert result == [1, 3, 5]


def test_itertools_zip_longest():
    """真 zip_longest 真补短"""
    a = [1, 2, 3]
    b = ["a", "b"]
    result = list(itertools.zip_longest(a, b, fillvalue=0))
    # (1, 'a'), (2, 'b'), (3, 0)
    assert result == [(1, "a"), (2, "b"), (3, 0)]


def test_itertools_accumulate():
    """真 accumulate 真累加"""
    data = [1, 2, 3, 4, 5]
    # 默认 operator.add
    result = list(itertools.accumulate(data))
    assert result == [1, 3, 6, 10, 15]
    # 乘
    result2 = list(itertools.accumulate(data, operator.mul))
    assert result2 == [1, 2, 6, 24, 120]
    # max
    result3 = list(itertools.accumulate([3, 1, 4, 1, 5, 9, 2, 6], max))
    assert result3 == [3, 3, 4, 4, 5, 9, 9, 9]


def test_itertools_count():
    """真 count 真无限计数"""
    counter = itertools.count(start=10, step=2)
    assert next(counter) == 10
    assert next(counter) == 12
    assert next(counter) == 14


def test_itertools_cycle():
    """真 cycle 真循环"""
    pool = ["A", "B", "C"]
    cycled = list(itertools.islice(itertools.cycle(pool), 7))
    assert cycled == ["A", "B", "C", "A", "B", "C", "A"]


def test_itertools_repeat():
    """真 repeat 真重复"""
    repeated = list(itertools.repeat("x", 5))
    assert repeated == ["x", "x", "x", "x", "x"]


def test_itertools_product():
    """真 product 真笛卡尔积"""
    prod = list(itertools.product([1, 2], ["a", "b"]))
    assert prod == [(1, "a"), (1, "b"), (2, "a"), (2, "b")]


def test_itertools_combinations():
    """真 combinations"""
    combs = list(itertools.combinations([1, 2, 3], 2))
    assert combs == [(1, 2), (1, 3), (2, 3)]


# ======================== functools 进阶 ========================
def test_functools_lru_cache():
    """真 lru_cache 真 LRU"""
    @functools.lru_cache(maxsize=3)
    def fib(n):
        if n < 2:
            return n
        return fib(n - 1) + fib(n - 2)

    assert fib(20) == 6765
    info = fib.cache_info()
    assert info.hits >= 1
    assert info.misses >= 1


def test_functools_wraps():
    """真 wraps 真保留元数据"""
    def my_decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)
        return wrapper

    @my_decorator
    def my_func():
        """my docstring"""
        return 42

    # wraps 保留 name / doc
    assert my_func.__name__ == "my_func"
    assert my_func.__doc__ == "my docstring"


def test_functools_total_ordering():
    """真 total_ordering"""
    @functools.total_ordering
    class V:
        def __init__(self, n):
            self.n = n
        def __eq__(self, other):
            return self.n == other.n
        def __lt__(self, other):
            return self.n < other.n

    a, b = V(1), V(2)
    # 所有比较算
    assert a < b
    assert a <= b
    assert b > a
    assert b >= a
    assert a != b
    assert a == V(1)


def test_functools_reduce_complex():
    """真 reduce 真多层"""
    # sum
    assert functools.reduce(operator.add, [1, 2, 3, 4]) == 10
    # max
    assert functools.reduce(lambda a, b: a if a > b else b, [3, 1, 4, 1, 5, 9, 2, 6]) == 9
    # 字符串拼接
    assert functools.reduce(operator.add, ["h", "i"], "") == "hi"


def test_functools_cached_property():
    """真 cached_property 真缓存"""
    class C:
        def __init__(self):
            self.count = 0

        @functools.cached_property
        def expensive(self):
            self.count += 1
            return "computed"

    c = C()
    # 多次访问, 只算 1 次
    v1 = c.expensive
    v2 = c.expensive
    v3 = c.expensive
    assert c.count == 1
    assert v1 == v2 == v3 == "computed"


# ======================== operator 进阶 ========================
def test_operator_truediv_matmul():
    """真 operator 真除 / 矩阵乘"""
    assert operator.truediv(10, 4) == 2.5
    assert operator.floordiv(10, 4) == 2
    # 3.5 用 matmul (3.5+)
    if hasattr(operator, "matmul"):
        # 矩阵
        import numpy as np
        a = np.array([[1, 2], [3, 4]])
        b = np.array([[5, 6], [7, 8]])
        result = operator.matmul(a, b)
        assert result[0][0] == 19


def test_operator_neg_pos_abs():
    """真 neg / pos / abs"""
    assert operator.neg(5) == -5
    # pos 不取 abs
    assert operator.pos(-5) == -5
    assert operator.pos(5) == 5
    assert operator.abs(-5) == 5
    assert operator.abs(-3.14) == 3.14
    # not_ 真按位取反
    assert operator.not_(True) is False
    # invert 真按位
    assert operator.invert(0) == -1
    assert operator.invert(1) == -2
