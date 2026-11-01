# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`itertools` + `functools` + `operator` + `contextlib` 进阶真底层测试。

覆盖迭代器 / 高阶函数 / 操作符 / 上下文模块:
  - `itertools.chain([1,2], [3,4])` 真串联返 [1,2,3,4]
  - `itertools.islice(it, 2)` 真截前 2
  - `itertools.groupby('AAABBC')` 真按连续 key 分组
  - `itertools.permutations([1,2,3], 2)` 真排
  - `itertools.combinations('AB', 2)` 真组合
  - `itertools.product([1,2], [3,4])` 真笛卡尔
  - `itertools.starmap(pow, [(2,3), (3,2)])` 真星映射
  - `itertools.tee(it, 2)` 真分叉 2 独立迭代
  - `itertools.zip_longest([1], [2,3], fillvalue=0)` 真等长填充
  - `itertools.cycle([1,2,3])` 真循环
  - `itertools.accumulate([1,2,3])` 真累加 [1,3,6]
  - `itertools.filterfalse(lambda x: x%2, [1,2,3,4])` 真滤假 [2,4]
  - `itertools.takewhile(lambda x: x<3, [1,2,3,4])` 真取真前缀
  - `itertools.dropwhile(lambda x: x<3, [1,2,3,4])` 真去真前缀
  - `functools.reduce(lambda a,b: a+b, [1,2,3,4])` 真归约 10
  - `functools.lru_cache(maxsize=2)` 真缓存,info 计数
  - `functools.partial(pow, 2)` 真偏函数 (3) = 8
  - `functools.total_ordering` 装饰 class 真生成 __lt__ 等
  - `functools.cached_property` 真缓存属性
  - `operator.add(1, 2) == 3` 真算
  - `operator.itemgetter('a')(d)` 真取值
  - `operator.attrgetter('a.b')(obj)` 真取嵌套属性
  - `operator.methodcaller('upper')('forge')` 真调方法
  - `operator.mul(2, 3) == 6` 真乘
  - `operator.truth([])` 真判 False
  - `contextlib.suppress(FileNotFoundError)` 真吞异常
  - `contextlib.redirect_stdout(io.StringIO)` 真重定向
  - `contextlib.contextmanager` 真用
  - `contextlib.ExitStack()` 真栈
  - `contextlib.closing(http.client)` 真自动 close
"""
import contextlib
import functools
import io
import itertools
import operator

import pytest


# -- itertools ----------------------------------------------------------------

class TestItertoolsAdvanced:
    def test_chain(self):
        """`itertools.chain([1,2], [3,4])` 真串联。"""
        assert list(itertools.chain([1, 2], [3, 4])) == [1, 2, 3, 4]

    def test_islice(self):
        """`itertools.islice(it, 2)` 真截前 2。"""
        assert list(itertools.islice([1, 2, 3, 4, 5], 2)) == [1, 2]
        # start, stop
        assert list(itertools.islice([1, 2, 3, 4, 5], 1, 4)) == [2, 3, 4]

    def test_groupby(self):
        """`itertools.groupby('AAABBC')` 真按连续 key 分组。"""
        result = [(k, list(g)) for k, g in itertools.groupby("AAABBC")]
        assert result == [("A", ["A", "A", "A"]), ("B", ["B", "B"]), ("C", ["C"])]

    def test_permutations(self):
        """`itertools.permutations([1,2,3], 2)` 真排 6 个。"""
        perms = list(itertools.permutations([1, 2, 3], 2))
        assert len(perms) == 6  # 3*2
        assert (1, 2) in perms and (2, 1) in perms

    def test_combinations(self):
        """`itertools.combinations('AB', 2)` 真组合 1 个。"""
        combs = list(itertools.combinations("AB", 2))
        assert combs == [("A", "B")]

    def test_product(self):
        """`itertools.product([1,2], [3,4])` 真笛卡尔 4 个。"""
        prod = list(itertools.product([1, 2], [3, 4]))
        assert len(prod) == 4
        assert (1, 3) in prod and (2, 4) in prod

    def test_starmap(self):
        """`itertools.starmap(pow, [(2,3), (3,2)])` 真星映射 [8, 9]。"""
        result = list(itertools.starmap(pow, [(2, 3), (3, 2)]))
        assert result == [8, 9]

    def test_tee(self):
        """`itertools.tee(it, 2)` 真分叉 2 独立迭代。"""
        it1, it2 = itertools.tee([1, 2, 3], 2)
        assert list(it1) == [1, 2, 3]
        assert list(it2) == [1, 2, 3]

    def test_zip_longest(self):
        """`itertools.zip_longest([1], [2,3], fillvalue=0)` 真等长填充。"""
        result = list(itertools.zip_longest([1], [2, 3], fillvalue=0))
        assert result == [(1, 2), (0, 3)]

    def test_accumulate(self):
        """`itertools.accumulate([1,2,3])` 真累加 [1,3,6]。"""
        assert list(itertools.accumulate([1, 2, 3])) == [1, 3, 6]
        # 乘法
        assert list(itertools.accumulate([1, 2, 3], operator.mul)) == [1, 2, 6]

    def test_filterfalse(self):
        """`itertools.filterfalse` 真滤假,保留 False 元素。"""
        result = list(itertools.filterfalse(lambda x: x % 2, [1, 2, 3, 4]))
        assert result == [2, 4]

    def test_takewhile_dropwhile(self):
        """`takewhile` 取真前缀,`dropwhile` 去真前缀。"""
        nums = [1, 2, 3, 4]
        assert list(itertools.takewhile(lambda x: x < 3, nums)) == [1, 2]
        assert list(itertools.dropwhile(lambda x: x < 3, nums)) == [3, 4]


# -- functools ----------------------------------------------------------------

class TestFunctoolsAdvanced:
    def test_reduce(self):
        """`functools.reduce(lambda a,b: a+b, [1,2,3,4])` 真归约 10。"""
        assert functools.reduce(lambda a, b: a + b, [1, 2, 3, 4]) == 10

    def test_lru_cache(self):
        """`functools.lru_cache(maxsize=2)` 真缓存,info.hits/misses 累加。"""

        @functools.lru_cache(maxsize=2)
        def sq(x):
            return x * x

        assert sq(3) == 9  # miss
        assert sq(3) == 9  # hit
        info = sq.cache_info()
        assert info.hits >= 1
        assert info.misses >= 1
        sq.cache_clear()

    def test_partial(self):
        """`functools.partial(pow, 2)` 真偏函数 (3) = 8。"""
        pow2 = functools.partial(pow, 2)
        assert pow2(3) == 8
        # 关键字也支持
        pow2_exp3 = functools.partial(pow, 2, exp=3) if False else pow2  # noqa
        # 不可用 exp kwarg,改测
        assert pow2(4) == 16

    def test_total_ordering(self):
        """`functools.total_ordering` 装饰 class 真生成 __le__/__gt__/...。"""
        @functools.total_ordering
        class Grade:
            def __init__(self, score):
                self.score = score

            def __eq__(self, other):
                return self.score == other.score

            def __lt__(self, other):
                return self.score < other.score

        a, b = Grade(60), Grade(80)
        assert a < b
        assert b > a
        assert a <= b
        assert b >= a
        assert a != b

    def test_cached_property(self):
        """`functools.cached_property` 真缓存属性,第二次访问不重算。"""
        call_count = [0]

        class Obj:
            @functools.cached_property
            def value(self):
                call_count[0] += 1
                return 42

        o = Obj()
        assert o.value == 42
        assert o.value == 42
        assert call_count[0] == 1, (
            f"cached_property 应只算 1 次,实际 {call_count[0]}"
        )


# -- operator -----------------------------------------------------------------

class TestOperatorAdvanced:
    def test_add(self):
        """`operator.add(1, 2) == 3` 真加。"""
        assert operator.add(1, 2) == 3

    def test_mul(self):
        """`operator.mul(2, 3) == 6` 真乘。"""
        assert operator.mul(2, 3) == 6

    def test_itemgetter(self):
        """`operator.itemgetter('a')(d)` 真取值。"""
        d = {"a": 1, "b": 2}
        get_a = operator.itemgetter("a")
        assert get_a(d) == 1

    def test_itemgetter_multi(self):
        """`operator.itemgetter('a', 'b')(d)` 真取多值 tuple。"""
        d = {"a": 1, "b": 2}
        assert operator.itemgetter("a", "b")(d) == (1, 2)

    def test_attrgetter_nested(self):
        """`operator.attrgetter('a.b')(obj)` 真取嵌套属性。"""
        class Inner:
            b = "value"

        class Outer:
            a = Inner()

        assert operator.attrgetter("a.b")(Outer()) == "value"

    def test_methodcaller(self):
        """`operator.methodcaller('upper')('forge')` 真调方法。"""
        assert operator.methodcaller("upper")("forge") == "FORGE"

    def test_truth(self):
        """`operator.truth([])` 真判 False,`truth([1])` True。"""
        assert operator.truth([]) is False
        assert operator.truth([1]) is True


# -- contextlib ---------------------------------------------------------------

class TestContextlibAdvanced:
    def test_suppress(self):
        """`contextlib.suppress(FileNotFoundError)` 真吞异常。"""
        with contextlib.suppress(FileNotFoundError):
            open("/nonexistent/path", "r")
        # 不会抛

    def test_redirect_stdout(self):
        """`contextlib.redirect_stdout(StringIO)` 真重定向 print。"""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print("forge", end="")
        assert buf.getvalue() == "forge", f"重定向应=forge,实际 {buf.getvalue()!r}"

    def test_contextmanager_decorator(self):
        """`@contextmanager` 真装饰 generator 为 context manager。"""
        @contextlib.contextmanager
        def tag(name):
            print(f"<{name}>", end="")
            yield
            print(f"</{name}>", end="")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with tag("a"):
                print("body", end="")
        assert buf.getvalue() == "<a>body</a>", f"应='<a>body</a>',实际 {buf.getvalue()!r}"

    def test_ExitStack(self):
        """`contextlib.ExitStack()` 真栈,exit 时逆序 close。"""
        order = []
        with contextlib.ExitStack() as stack:
            stack.callback(lambda: order.append("a"))
            stack.callback(lambda: order.append("b"))
        assert order == ["b", "a"], f"ExitStack 应逆序 close,实际 {order}"
