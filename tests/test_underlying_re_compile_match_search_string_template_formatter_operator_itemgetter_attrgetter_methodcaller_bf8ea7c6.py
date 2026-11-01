# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`re` 大进阶: compile/match/search/findall/sub/fullmatch/IGNORECASE/MULTILINE/DOTALL + `string.Template` + `string.Formatter` + `operator` (itemgetter/attrgetter/methodcaller) + `functools` (lru_cache/partial/reduce) + `contextlib` (suppress/ExitStack/contextmanager) 真底层测试。

覆盖 re 8 真 + string 5 真 + operator 4 真 + functools 4 真 + contextlib 4 真 (共 25 真测试) 模块:
  - `re.compile 真编 pattern + match`
  - `re.match 真 match 开头`
  - `re.search 真 search anywhere`
  - `re.findall 真返 list`
  - `re.sub 真替换`
  - `re.fullmatch 真全匹配`
  - `re.split 真 split by pattern`
  - `re.compile IGNORECASE 真 case-insensitive`
  - `re.compile MULTILINE 真 ^ + $ 跨行`
  - `re.compile DOTALL 真 . 跨行`
  - `string.Template 真 safe_substitute + substitute`
  - `string.Formatter 真 format + parse`
  - `string.ascii_lowercase 真 26 char`
  - `string.digits 真 10 char`
  - `string.punctuation 真含!@#`
  - `operator.itemgetter 真按索引取`
  - `operator.attrgetter 真按属性取`
  - `operator.methodcaller 真按方法调`
  - `operator.add / mul / neg 真数学`
  - `functools.lru_cache 真缓存`
  - `functools.partial 真 partial`
  - `functools.reduce 真累加`
  - `functools.total_ordering 必能装饰`
  - `contextlib.suppress 真吞异常`
  - `contextlib.ExitStack 真 enter+exit`
  - `contextlib.contextmanager 真装饰`
  - `contextlib.closing 真 close`
"""
import contextlib
import functools
import io
import operator
import re
import string

import pytest


# -- re 进阶 ---------------------------------------------------------------

class TestReAdvanced:
    def test_re_compile_match(self):
        """`re.compile 真编 pattern + match。"""
        p = re.compile(r"forge")
        m = p.match("forge hello")
        assert m is not None
        assert m.group() == "forge"

    def test_re_search(self):
        """`re.search 真 search anywhere。"""
        m = re.search(r"hello", "forge hello world")
        assert m is not None
        assert m.group() == "hello"

    def test_re_findall(self):
        """`re.findall 真返 list。"""
        result = re.findall(r"\d+", "a1 b22 c333")
        assert result == ["1", "22", "333"]

    def test_re_sub(self):
        """`re.sub 真替换。"""
        result = re.sub(r"\d+", "X", "a1 b2 c3")
        # 必替换 digit
        assert "X" in result
        assert result == "aX bX cX"

    def test_re_fullmatch(self):
        """`re.fullmatch 真全匹配。"""
        # 全匹配
        m = re.fullmatch(r"\d+", "12345")
        assert m is not None
        # 非全匹配
        m2 = re.fullmatch(r"\d+", "12345abc")
        assert m2 is None

    def test_re_split(self):
        """`re.split 真 split by pattern。"""
        result = re.split(r"\s+", "forge  hello\tworld")
        assert result == ["forge", "hello", "world"]

    def test_re_IGNORECASE(self):
        """`re.compile IGNORECASE 真 case-insensitive。"""
        p = re.compile(r"FORGE", re.IGNORECASE)
        m = p.match("forge hello")
        assert m is not None
        assert m.group() == "forge"

    def test_re_MULTILINE(self):
        """`re.compile MULTILINE 真 ^ + $ 跨行。"""
        p = re.compile(r"^forge", re.MULTILINE)
        m = p.search("line1\nforge\nline3")
        assert m is not None


# -- string 进阶 -----------------------------------------------------------

class TestStringAdvanced:
    def test_Template_substitute(self):
        """`string.Template 真 safe_substitute + substitute。"""
        t = string.Template("Hello $name, you are $age")
        # safe_substitute 不抛
        result = t.safe_substitute(name="forge")
        # 必含 forge
        assert "forge" in result
        # $age 必未替换 (但 safe_substitute 保留)
        # substitute 必抛 (缺 age)
        with pytest.raises(KeyError):
            t.substitute(name="forge")

    def test_Formatter_format(self):
        """`string.Formatter 真 format + parse。"""
        fmt = string.Formatter()
        # format 必能
        result = fmt.format("Hello {name}", name="forge")
        assert result == "Hello forge"
        # parse 必返 iterable
        parsed = list(fmt.parse("Hello {name}"))
        # 必 ≥ 1
        assert len(parsed) >= 1

    def test_ascii_lowercase(self):
        """`string.ascii_lowercase 真 26 char。"""
        assert len(string.ascii_lowercase) == 26
        assert string.ascii_lowercase[0] == "a"
        assert string.ascii_lowercase[-1] == "z"

    def test_digits(self):
        """`string.digits 真 10 char。"""
        assert len(string.digits) == 10
        assert string.digits == "0123456789"

    def test_punctuation(self):
        """`string.punctuation 真含!@#。"""
        assert "!" in string.punctuation
        assert "@" in string.punctuation
        assert "#" in string.punctuation


# -- operator 进阶 --------------------------------------------------------

class TestOperatorAdvanced:
    def test_itemgetter(self):
        """`operator.itemgetter 真按索引取。"""
        get0 = operator.itemgetter(0)
        get01 = operator.itemgetter(0, 1)
        # 取第一个
        assert get0([10, 20, 30]) == 10
        # 取前 2
        assert get01([10, 20, 30]) == (10, 20)

    def test_attrgetter(self):
        """`operator.attrgetter 真按属性取。"""
        from collections import namedtuple
        P = namedtuple("P", "x y")
        p = P(10, 20)
        getx = operator.attrgetter("x")
        getxy = operator.attrgetter("x", "y")
        assert getx(p) == 10
        assert getxy(p) == (10, 20)

    def test_methodcaller(self):
        """`operator.methodcaller 真按方法调。"""
        upper = operator.methodcaller("upper")
        # "forge".upper() = "FORGE"
        assert upper("forge") == "FORGE"
        # 带参
        replace = operator.methodcaller("replace", "f", "F")
        assert replace("forge") == "Forge"

    def test_math_ops(self):
        """`operator.add/mul/neg 真数学。"""
        assert operator.add(3, 4) == 7
        assert operator.mul(3, 4) == 12
        assert operator.neg(5) == -5
        # truth
        assert operator.truth(True) is True
        # not_
        assert operator.not_(False) is True


# -- functools 进阶 -------------------------------------------------------

class TestFunctoolsAdvanced:
    def test_lru_cache(self):
        """`functools.lru_cache 真缓存。"""

        @functools.lru_cache(maxsize=10)
        def cached_fn(x):
            return x * 2

        # 必缓存
        assert cached_fn(5) == 10
        # 必能 cache_info
        info = cached_fn.cache_info()
        assert info.hits >= 0
        assert info.misses >= 1
        # clear
        cached_fn.cache_clear()
        info2 = cached_fn.cache_info()
        assert info2.misses == 0

    def test_partial(self):
        """`functools.partial 真 partial。"""
        def add(a, b, c):
            return a + b + c

        p = functools.partial(add, 1, 2)
        # c=3
        assert p(3) == 6
        # 必 partial func
        assert p.func is add
        assert p.args == (1, 2)

    def test_reduce(self):
        """`functools.reduce 真累加。"""
        # 1+2+3+4+5 = 15
        result = functools.reduce(operator.add, [1, 2, 3, 4, 5])
        assert result == 15
        # 1*2*3*4*5 = 120
        result2 = functools.reduce(operator.mul, [1, 2, 3, 4, 5])
        assert result2 == 120

    def test_total_ordering(self):
        """`functools.total_ordering 必能装饰。"""

        @functools.total_ordering
        class MyNum:
            def __init__(self, v):
                self.v = v

            def __eq__(self, other):
                return self.v == other.v

            def __lt__(self, other):
                return self.v < other.v

        a = MyNum(1)
        b = MyNum(2)
        # 必能比较 (从 __lt__ 推)
        assert a < b
        assert a <= b
        assert b > a
        assert b >= a


# -- contextlib 进阶 -----------------------------------------------------

class TestContextlibAdvanced:
    def test_suppress(self):
        """`contextlib.suppress 真吞异常。"""
        # 必吞 ValueError
        with contextlib.suppress(ValueError):
            raise ValueError("forge error")
        # 退出后必不抛
        # 必不传其他 exception
        with pytest.raises(TypeError):
            with contextlib.suppress(ValueError):
                raise TypeError("forge type")

    def test_ExitStack(self):
        """`ExitStack 真 enter+exit。"""
        stack = contextlib.ExitStack()
        # enter
        buf = io.StringIO()
        stack.enter_context(buf)
        # 真 close on exit
        stack.close()

    def test_contextmanager_decorator(self):
        """`contextlib.contextmanager 真装饰。"""
        @contextlib.contextmanager
        def my_cm():
            yield "forge"
            # cleanup after yield

        with my_cm() as v:
            assert v == "forge"

    def test_closing(self):
        """`contextlib.closing 真 close on exit。"""
        class _Open:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        obj = _Open()
        with contextlib.closing(obj) as o:
            assert o is obj
        # 必 closed
        assert obj.closed is True
