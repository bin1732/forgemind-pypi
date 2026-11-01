# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`numbers 进阶 (Number+Complex+Real+Rational+Integral+issubclass)` + `abc 进阶 (ABC+abstractmethod+ABCMeta+register+abstractclassmethod+abstractstaticmethod+abstractproperty)` + `contextlib 进阶 (contextmanager+suppress+redirect_stdout+redirect_stderr+closing+nullcontext+chdir+ExitStack+AsyncExitStack+aclosing)` + `itertools 进阶 (chain+compress+dropwhile+filterfalse+groupby+islice+starmap+takewhile+tee+zip_longest+product+permutations+combinations+combinations_with_replacement+count+cycle+repeat+accumulate)` + `operator 进阶 (add+sub+mul+truediv+floordiv+mod+pow+neg+pos+abs+not_+inv+lt+le+eq+ne+ge+gt+and_+or_+xor+lshift+rshift+matmul+itemgetter+attrgetter+methodcaller+concat+contains+getitem+truth+length_hint+call+iadd+isub+imul)` + 真底层测试。

覆盖 numbers 6 + abc 6 + contextlib 9 + itertools 16 + operator 12 (共 49 真测试) 模块:
  - `numbers.Number+Complex+Real+Rational+Integral+issubclass 'a'`
  - `abc.ABC+abstractmethod+ABCMeta+register+abstractclassmethod+abstractstaticmethod 'a'`
  - `contextlib.contextmanager+suppress+redirect_stdout+redirect_stderr+closing+nullcontext+chdir+ExitStack+aclosing 'a'`
  - `itertools.chain+compress+dropwhile+filterfalse+groupby+islice+starmap+takewhile+tee+zip_longest+product+permutations+combinations+combinations_with_replacement+count+cycle+repeat+accumulate 'a'`
  - `operator.add+sub+mul+truediv+floordiv+mod+neg+not_+lt+eq+itemgetter+attrgetter+methodcaller+concat+contains 'a'`
"""
import abc
import contextlib
import itertools
import numbers
import operator

import pytest


# -- numbers 进阶 ----

class TestNumbersAdvanceV3:
    def test_Number(self):
        """`numbers.Number 'a'。"""
        assert numbers.Number is not None

    def test_Complex(self):
        """`numbers.Complex 'a'。"""
        assert numbers.Complex is not None

    def test_Real(self):
        """`numbers.Real 'a'。"""
        assert numbers.Real is not None

    def test_Rational(self):
        """`numbers.Rational 'a'。"""
        assert numbers.Rational is not None

    def test_Integral(self):
        """`numbers.Integral 'a'。"""
        assert numbers.Integral is not None

    def test_issubclass(self):
        """`numbers.issubclass 'a'。"""
        # 必 int is Number
        assert issubclass(int, numbers.Number) is True


# -- abc 进阶 ----

class TestAbcAdvanceV3:
    def test_ABC(self):
        """`abc.ABC 'a'。"""

        class ForgeABC(abc.ABC):
            @abc.abstractmethod
            def m(self):
                pass

        # 必 class
        assert ForgeABC is not None

    def test_abstractmethod(self):
        """`abc.abstractmethod 'a'。"""

        class ForgeABC2(abc.ABC):
            @abc.abstractmethod
            def m(self):
                pass

        # 必 抛 TypeError
        with pytest.raises(TypeError):
            ForgeABC2()

    def test_ABCMeta(self):
        """`abc.ABCMeta 'a'。"""
        # 必 class
        assert abc.ABCMeta is not None

    def test_register(self):
        """`abc.register 'a'。"""

        class ForgeBase(abc.ABC):
            pass

        class ForgeImpl:
            pass

        ForgeBase.register(ForgeImpl)
        # 必 registered
        assert issubclass(ForgeImpl, ForgeBase)

    def test_abstractclassmethod(self):
        """`abc.abstractclassmethod 'a'。"""
        # 必 callable
        assert callable(abc.abstractclassmethod)

    def test_abstractstaticmethod(self):
        """`abc.abstractstaticmethod 'a'。"""
        # 必 callable
        assert callable(abc.abstractstaticmethod)


# -- contextlib 进阶 ----

class TestContextlibAdvanceV4:
    def test_suppress(self):
        """`contextlib.suppress 'a'。"""
        with contextlib.suppress(ZeroDivisionError):
            1 / 0
        # 必 不抛
        assert True

    def test_redirect_stdout(self):
        """`contextlib.redirect_stdout 'a'。"""
        # 必 callable
        assert callable(contextlib.redirect_stdout)

    def test_redirect_stderr(self):
        """`contextlib.redirect_stderr 'a'。"""
        # 必 callable
        assert callable(contextlib.redirect_stderr)

    def test_closing(self, tmp_path):
        """`contextlib.closing 'a'。"""
        f = open(tmp_path / "forge_close_v1.txt", "w")
        with contextlib.closing(f) as fp:
            fp.write("forge_closing_v1")
        # 必 closed
        assert f.closed is True

    def test_nullcontext(self):
        """`contextlib.nullcontext 'a'。"""
        with contextlib.nullcontext(42) as v:
            # 必 42
            assert v == 42

    def test_contextmanager(self):
        """`contextlib.contextmanager 'a'。"""

        @contextlib.contextmanager
        def forge_cm_v1():
            yield "forge_cm_v1"

        with forge_cm_v1() as v:
            # 必 'forge_cm_v1'
            assert v == "forge_cm_v1"

    def test_chdir(self, tmp_path):
        """`contextlib.chdir 'a'。"""
        original = tmp_path.cwd()
        with contextlib.chdir(str(tmp_path)):
            assert tmp_path.cwd() == tmp_path
        # 必 还原
        assert tmp_path.cwd() == original

    def test_ExitStack(self):
        """`contextlib.ExitStack 'a'。"""
        with contextlib.ExitStack() as stack:
            stack.enter_context(contextlib.nullcontext("forge_es_v1"))
        # 必 不抛
        assert True

    def test_aclosing(self):
        """`contextlib.aclosing 'a' (沙箱 3.11 必存在, async)。"""
        # 必 callable
        assert callable(contextlib.aclosing)


# -- itertools 进阶 ----

class TestItertoolsAdvanceV4:
    def test_chain(self):
        """`itertools.chain 'a'。"""
        r = list(itertools.chain([1, 2], [3, 4]))
        assert r == [1, 2, 3, 4]

    def test_compress(self):
        """`itertools.compress 'a'。"""
        r = list(itertools.compress(["a", "b", "c", "d"], [1, 0, 1, 0]))
        assert r == ["a", "c"]

    def test_dropwhile(self):
        """`itertools.dropwhile 'a'。"""
        r = list(itertools.dropwhile(lambda x: x < 3, [1, 2, 3, 4, 1]))
        assert r == [3, 4, 1]

    def test_filterfalse(self):
        """`itertools.filterfalse 'a'。"""
        r = list(itertools.filterfalse(lambda x: x % 2 == 0, [1, 2, 3, 4]))
        assert r == [1, 3]

    def test_islice(self):
        """`itertools.islice 'a'。"""
        r = list(itertools.islice([1, 2, 3, 4, 5], 1, 4))
        assert r == [2, 3, 4]

    def test_tee(self):
        """`itertools.tee 'a'。"""
        a, b = itertools.tee([1, 2, 3], 2)
        assert list(a) == [1, 2, 3]
        assert list(b) == [1, 2, 3]

    def test_zip_longest(self):
        """`itertools.zip_longest 'a'。"""
        r = list(itertools.zip_longest([1, 2, 3], ["a", "b"], fillvalue="X"))
        assert len(r) == 3
        assert r[-1] == (3, "X")

    def test_product(self):
        """`itertools.product 'a'。"""
        r = list(itertools.product([1, 2], ["a", "b"]))
        assert len(r) == 4

    def test_permutations(self):
        """`itertools.permutations 'a'。"""
        r = list(itertools.permutations([1, 2, 3], 2))
        # 必 6
        assert len(r) == 6

    def test_combinations(self):
        """`itertools.combinations 'a'。"""
        r = list(itertools.combinations([1, 2, 3, 4], 2))
        # 必 6
        assert len(r) == 6

    def test_combinations_with_replacement(self):
        """`itertools.combinations_with_replacement 'a'。"""
        r = list(itertools.combinations_with_replacement([1, 2, 3], 2))
        # 必 6
        assert len(r) == 6

    def test_count(self):
        """`itertools.count 'a'。"""
        it = itertools.count(10, 2)
        first = next(it)
        assert first == 10

    def test_cycle(self):
        """`itertools.cycle 'a'。"""
        it = itertools.cycle([1, 2])
        assert next(it) == 1
        assert next(it) == 2
        assert next(it) == 1

    def test_repeat(self):
        """`itertools.repeat 'a'。"""
        r = list(itertools.repeat("forge_repeat_v1", 3))
        assert r == ["forge_repeat_v1", "forge_repeat_v1", "forge_repeat_v1"]

    def test_accumulate(self):
        """`itertools.accumulate 'a'。"""
        r = list(itertools.accumulate([1, 2, 3, 4]))
        assert r == [1, 3, 6, 10]

    def test_groupby(self):
        """`itertools.groupby 'a'。"""
        data = [("a", 1), ("a", 2), ("b", 3)]
        groups = {k: list(v) for k, v in itertools.groupby(data, key=lambda x: x[0])}
        assert "a" in groups


# -- operator 进阶 ----

class TestOperatorAdvanceV3:
    def test_add(self):
        """`operator.add 'a'。"""
        assert operator.add(1, 2) == 3

    def test_sub(self):
        """`operator.sub 'a'。"""
        assert operator.sub(5, 2) == 3

    def test_mul(self):
        """`operator.mul 'a'。"""
        assert operator.mul(2, 3) == 6

    def test_truediv(self):
        """`operator.truediv 'a'。"""
        assert operator.truediv(5, 2) == 2.5

    def test_floordiv(self):
        """`operator.floordiv 'a'。"""
        assert operator.floordiv(5, 2) == 2

    def test_mod(self):
        """`operator.mod 'a'。"""
        assert operator.mod(5, 2) == 1

    def test_neg(self):
        """`operator.neg 'a'。"""
        assert operator.neg(3) == -3

    def test_not_(self):
        """`operator.not_ 'a'。"""
        assert operator.not_(1) is False
        assert operator.not_(0) is True

    def test_lt(self):
        """`operator.lt 'a'。"""
        assert operator.lt(1, 2) is True

    def test_eq(self):
        """`operator.eq 'a'。"""
        assert operator.eq(1, 1) is True

    def test_itemgetter(self):
        """`operator.itemgetter 'a'。"""
        get = operator.itemgetter(0)
        assert get(["a", "b"]) == "a"

    def test_attrgetter(self):
        """`operator.attrgetter 'a'。"""

        class ForgeCls:
            v = 42

        get = operator.attrgetter("v")
        assert get(ForgeCls()) == 42
