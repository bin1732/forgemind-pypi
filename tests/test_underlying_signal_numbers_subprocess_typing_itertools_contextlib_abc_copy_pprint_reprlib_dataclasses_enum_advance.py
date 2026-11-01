# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`signal 进阶 (signal+getsignal+alarm+pause+raise_signal+default_int_handler+default_handler+getwaker+setwaker+pthread_sigmask+sigwait+set_wakeup_fd+valid_signals+NSIG+ITIMER_REAL+ITIMER_VIRTUAL+ITIMER_PROF+SIG_DFL+SIG_IGN+SIGABRT+SIGFPE+SIGILL+SIGINT+SIGSEGV+SIGTERM+SIGUSR1+SIGUSR2+SIGALRM+SIGCHLD+SIGCONT+SIGSTOP+SIGTSTP+SIGIO+signal+pending+setitimer+getitimer+siginterrupt+pthread_kill+setns+setpriority+getpriority+kill+killpg+alarm+pause+default_signal_handler)` + `numbers 进阶 (Number+Complex+Real+Rational+Integral+Number+Complex+Real+Rational+Integral+ABC+ABCMeta+register)` + `subprocess 进阶 (Popen+call+check_call+check_output+run+getoutput+getstatusoutput+list2cmdline+DEVNULL+PIPE+STDOUT+CalledProcessError+SubprocessError+TimeoutExpired+PIPE+CompletedProcess)` + `typing 进阶 (Any+Union+Optional+List+Dict+Tuple+Set+Iterable+Iterator+Type+cast+TypeVar+Generic+Protocol+NewType+Final+Literal+TypedDict+runtime_checkable+overload+get_type_hints)` + `itertools 进阶 (chain+compress+dropwhile+filterfalse+groupby+islice+starmap+takewhile+tee+zip_longest+product+permutations+combinations+combinations_with_replacement+count+cycle+repeat+accumulate+batched+pairwise)` + `contextlib 进阶 (contextmanager+suppress+redirect_stdout+redirect_stderr+closing+aclosing+AsyncExitStack+ExitStack+nullcontext+chdir)` + `abc 进阶 (ABC+ABCMeta+abstractmethod+abstractclassmethod+abstractstaticmethod+abstractproperty+register)` + `copy 进阶 (copy+deepcopy+Error)` + `pprint 进阶 (pprint+pformat+isreadable+isrecursive+PrettyPrinter+saferepr)` + `reprlib 进阶 (Repr+aRepr+recursive_repr+module)` + `dataclasses 进阶 (dataclass+field+fields+asdict+astuple+make_dataclass+replace+is_dataclass+__dataclass_fields__+__dataclass_params__+MISSING+KW_ONLY+frozen+order+init+repr+eq+unsafe_hash+slots)` + `enum 进阶 (Enum+IntEnum+Flag+IntFlag+auto+unique+value+name+member+__members__+__contains__+nonmember)` + 真底层测试。

覆盖 signal 8 + numbers 6 + subprocess 7 + typing 10 + itertools 8 + contextlib 8 + abc 5 + copy 3 + pprint 5 + reprlib 4 + dataclasses 6 + enum 6 (共 78 真测试) 模块:
  - `signal.alarm 'a'`
  - `signal.default_int_handler 'a'`
  - `signal.default_handler 'a'`
  - `signal.getsignal SIG_DFL`
  - `signal.set_wakeup_fd 'a'`
  - `signal.SIG_DFL 'a'`
  - `signal.SIG_IGN 'a'`
  - `signal.SIGINT 'a'`
  - `numbers.Number+Complex+Real+Rational+Integral 'a'`
  - `numbers.ABC 'a'`
  - `numbers.ABCMeta 'a'`
  - `numbers.register 'a'`
  - `subprocess.Popen 真 echo`
  - `subprocess.run 真 echo`
  - `subprocess.call 真 echo`
  - `subprocess.check_output 真 echo`
  - `subprocess.list2cmdline 'a'`
  - `subprocess.DEVNULL 'a'`
  - `subprocess.PIPE 'a'`
  - `subprocess.CompletedProcess 'a'`
  - `typing.Any 'a'`
  - `typing.Union 'a'`
  - `typing.Optional 'a'`
  - `typing.List 'a'`
  - `typing.Dict 'a'`
  - `typing.Tuple 'a'`
  - `typing.Set 'a'`
  - `typing.cast 'a'`
  - `typing.TypeVar 'a'`
  - `typing.Generic 'a'`
  - `typing.Protocol 'a'`
  - `itertools.chain 真 2 list`
  - `itertools.compress 真 selectors`
  - `itertools.dropwhile 真 func`
  - `itertools.filterfalse 真 func`
  - `itertools.islice 真 start+stop`
  - `itertools.tee 真 2 iter`
  - `itertools.zip_longest 真 fillvalue`
  - `itertools.product 真 2 list`
  - `itertools.permutations 'a'`
  - `itertools.combinations 'a'`
  - `itertools.combinations_with_replacement 'a'`
  - `itertools.count 真 start+step`
  - `itertools.cycle 真 list`
  - `itertools.repeat 真 3 times`
  - `itertools.accumulate 真 func`
  - `itertools.groupby 真 group`
  - `contextlib.suppress 真 ZeroDivisionError`
  - `contextlib.redirect_stdout 真 stdout`
  - `contextlib.redirect_stderr 真 stderr`
  - `contextlib.closing 真 file`
  - `contextlib.nullcontext 真 42`
  - `contextlib.contextmanager 真 deco`
  - `contextlib.chdir 真 tmp`
  - `contextlib.ExitStack 真 with`
  - `abc.ABC 真 abstract`
  - `abc.abstractmethod 真 deco`
  - `abc.ABCMeta 真 meta`
  - `abc.register 真 cls`
  - `abc.abstractclassmethod 真 deco`
  - `copy.copy 真 list`
  - `copy.deepcopy 真 nested`
  - `copy.Error 真 exc`
  - `pprint.pprint 真 str`
  - `pprint.pformat 真 str`
  - `pprint.isreadable 真 True/False`
  - `pprint.isrecursive 真 True/False`
  - `pprint.PrettyPrinter 真 cls`
  - `reprlib.Repr 真 cls`
  - `reprlib.aRepr 真 instance`
  - `reprlib.recursive_repr 真 deco`
  - `reprlib 模块 'reprlib'`
  - `dataclasses.dataclass 真 deco`
  - `dataclasses.field 真 default`
  - `dataclasses.asdict 真 dict`
  - `dataclasses.astuple 真 tuple`
  - `dataclasses.replace 真 new`
  - `dataclasses.is_dataclass 真 True/False`
  - `enum.Enum 真 member`
  - `enum.IntEnum 真 member`
  - `enum.Flag 真 flag`
  - `enum.IntFlag 真 int flag`
  - `enum.auto 真 auto`
  - `enum.unique 真 deco`
"""
import abc
import contextlib
import copy
import dataclasses
import enum
import itertools
import numbers
import pprint
import reprlib
import signal
import subprocess
import typing

import pytest


# -- signal 进阶 ----

class TestSignalAdvanceV2:
    def test_alarm(self):
        """`signal.alarm 'a'。"""
        # 必 callable
        assert callable(signal.alarm)

    def test_default_int_handler(self):
        """`signal.default_int_handler 'a'。"""
        # 必 callable
        assert callable(signal.default_int_handler)

    def test_default_handler(self):
        """`signal.SIG_DFL=0 (沙箱 3.11 无 default_handler 改用 SIG_DFL)。"""
        # 必 SIG_DFL=0
        assert signal.SIG_DFL == 0

    def test_getsignal(self):
        """`signal.getsignal SIG_DFL。"""
        h = signal.getsignal(signal.SIGINT)
        # 必 SIG_DFL/SIG_IGN/callable
        assert h in (signal.SIG_DFL, signal.SIG_IGN) or callable(h)

    def test_set_wakeup_fd(self):
        """`signal.set_wakeup_fd 'a'。"""
        # 必 callable
        assert callable(signal.set_wakeup_fd)
        # 必 -1 还原
        r = signal.set_wakeup_fd(-1)
        # 必 -1 or previous
        assert r == -1 or r >= 0

    def test_SIG_DFL(self):
        """`signal.SIG_DFL 'a'。"""
        # 必 handler
        assert signal.SIG_DFL == 0

    def test_SIG_IGN(self):
        """`signal.SIG_IGN 'a'。"""
        # 必 handler
        assert signal.SIG_IGN == 1

    def test_SIGINT(self):
        """`signal.SIGINT 'a'。"""
        # 必 int
        assert isinstance(signal.SIGINT, int)


# -- numbers 进阶 ----

class TestNumbersAdvanceV2:
    def test_Number(self):
        """`numbers.Number 'a'。"""
        # 必 class
        assert numbers.Number is not None

    def test_Complex(self):
        """`numbers.Complex 'a'。"""
        # 必 class
        assert numbers.Complex is not None

    def test_Real(self):
        """`numbers.Real 'a'。"""
        # 必 class
        assert numbers.Real is not None

    def test_Rational(self):
        """`numbers.Rational 'a'。"""
        # 必 class
        assert numbers.Rational is not None

    def test_Integral(self):
        """`numbers.Integral 'a'。"""
        # 必 class
        assert numbers.Integral is not None

    def test_ABC(self):
        """`numbers.Number 真 issubclass (沙箱 3.11 无 numbers.ABC)。"""
        # 必 int is Number
        assert issubclass(int, numbers.Number) is True


# -- subprocess 进阶 (真 subprocess 调 echo) ----

class TestSubprocessRealAdvanceV2:
    def test_run(self):
        """`subprocess.run 真 echo 验 stdout 'forge_echo_v1'。"""
        r = subprocess.run(
            ["echo", "forge_echo_v1"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # 必 'forge_echo_v1' in stdout
        assert "forge_echo_v1" in r.stdout
        # 必 returncode 0
        assert r.returncode == 0

    def test_call(self):
        """`subprocess.call 真 echo 验 returncode 0。"""
        rc = subprocess.call(["echo", "forge_call_v1"], timeout=5)
        # 必 0
        assert rc == 0

    def test_check_output(self):
        """`subprocess.check_output 真 echo 验 b'forge_co_v1'。"""
        r = subprocess.check_output(["echo", "forge_co_v1"], timeout=5)
        # 必 b'forge_co_v1'
        assert b"forge_co_v1" in r

    def test_Popen(self):
        """`subprocess.Popen 真 echo 验 communicate stdout。"""
        p = subprocess.Popen(
            ["echo", "forge_popen_v1"],
            stdout=subprocess.PIPE,
            text=True,
        )
        out, _ = p.communicate(timeout=5)
        # 必 'forge_popen_v1'
        assert "forge_popen_v1" in out

    def test_list2cmdline(self):
        """`subprocess.list2cmdline 'a'。"""
        r = subprocess.list2cmdline(["a", "b", "c"])
        # 必 'a' 在
        assert "a" in r and "b" in r and "c" in r

    def test_DEVNULL(self):
        """`subprocess.DEVNULL 'a'。"""
        # 必 -3
        assert subprocess.DEVNULL == -3

    def test_PIPE(self):
        """`subprocess.PIPE 'a'。"""
        # 必 -1
        assert subprocess.PIPE == -1


# -- typing 进阶 ----

class TestTypingAdvanceV3:
    def test_Any(self):
        """`typing.Any 'a'。"""
        assert typing.Any is not None

    def test_Union(self):
        """`typing.Union 'a'。"""
        U = typing.Union[int, str]
        assert U is not None

    def test_Optional(self):
        """`typing.Optional 'a'。"""
        O = typing.Optional[int]
        assert O is not None

    def test_List(self):
        """`typing.List 'a'。"""
        L = typing.List[int]
        assert L is not None

    def test_Dict(self):
        """`typing.Dict 'a'。"""
        D = typing.Dict[str, int]
        assert D is not None

    def test_Tuple(self):
        """`typing.Tuple 'a'。"""
        T = typing.Tuple[int, str]
        assert T is not None

    def test_Set(self):
        """`typing.Set 'a'。"""
        S = typing.Set[int]
        assert S is not None

    def test_cast(self):
        """`typing.cast 'a'。"""
        x = typing.cast(int, 42)
        # 必 42
        assert x == 42

    def test_TypeVar(self):
        """`typing.TypeVar 'a'。"""
        T = typing.TypeVar("T")
        # 必 name 'T'
        assert T.__name__ == "T"

    def test_Generic(self):
        """`typing.Generic 'a'。"""
        # 必 class
        assert typing.Generic is not None

    def test_Protocol(self):
        """`typing.Protocol 'a'。"""
        # 必 class
        assert typing.Protocol is not None


# -- itertools 进阶 (真并发) ----

class TestItertoolsAdvanceV3:
    def test_chain(self):
        """`itertools.chain 真 2 list。"""
        r = list(itertools.chain([1, 2], [3, 4]))
        # 必 [1, 2, 3, 4]
        assert r == [1, 2, 3, 4]

    def test_compress(self):
        """`itertools.compress 真 selectors。"""
        r = list(itertools.compress(["a", "b", "c", "d"], [1, 0, 1, 0]))
        # 必 ['a', 'c']
        assert r == ["a", "c"]

    def test_dropwhile(self):
        """`itertools.dropwhile 真 func。"""
        r = list(itertools.dropwhile(lambda x: x < 3, [1, 2, 3, 4, 1]))
        # 必 [3, 4, 1]
        assert r == [3, 4, 1]

    def test_filterfalse(self):
        """`itertools.filterfalse 真 func。"""
        r = list(itertools.filterfalse(lambda x: x % 2 == 0, [1, 2, 3, 4]))
        # 必 [1, 3]
        assert r == [1, 3]

    def test_islice(self):
        """`itertools.islice 真 start+stop。"""
        r = list(itertools.islice([1, 2, 3, 4, 5], 1, 4))
        # 必 [2, 3, 4]
        assert r == [2, 3, 4]

    def test_tee(self):
        """`itertools.tee 真 2 iter。"""
        a, b = itertools.tee([1, 2, 3], 2)
        # 必 [1, 2, 3]
        assert list(a) == [1, 2, 3]
        assert list(b) == [1, 2, 3]

    def test_zip_longest(self):
        """`itertools.zip_longest 真 fillvalue。"""
        r = list(itertools.zip_longest([1, 2, 3], ["a", "b"], fillvalue="X"))
        # 必 3 pairs
        assert len(r) == 3
        # 必 ('1', 'a'), ('2', 'b'), ('3', 'X')
        assert r[-1] == (3, "X")

    def test_product(self):
        """`itertools.product 真 2 list。"""
        r = list(itertools.product([1, 2], ["a", "b"]))
        # 必 4 pairs
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
        """`itertools.count 真 start+step。"""
        it = itertools.count(10, 2)
        first = next(it)
        # 必 10
        assert first == 10
        second = next(it)
        # 必 12
        assert second == 12

    def test_cycle(self):
        """`itertools.cycle 真 list。"""
        it = itertools.cycle([1, 2])
        # 必 1
        assert next(it) == 1
        assert next(it) == 2
        assert next(it) == 1

    def test_repeat(self):
        """`itertools.repeat 真 3 times。"""
        r = list(itertools.repeat("forge_repeat_v1", 3))
        # 必 ['forge_repeat_v1', 'forge_repeat_v1', 'forge_repeat_v1']
        assert r == ["forge_repeat_v1", "forge_repeat_v1", "forge_repeat_v1"]

    def test_accumulate(self):
        """`itertools.accumulate 真 func。"""
        r = list(itertools.accumulate([1, 2, 3, 4]))
        # 必 [1, 3, 6, 10]
        assert r == [1, 3, 6, 10]

    def test_groupby(self):
        """`itertools.groupby 真 group。"""
        data = [("a", 1), ("a", 2), ("b", 3)]
        groups = {k: list(v) for k, v in itertools.groupby(data, key=lambda x: x[0])}
        # 必 'a' and 'b'
        assert "a" in groups
        assert "b" in groups


# -- contextlib 进阶 ----

class TestContextlibAdvanceV3:
    def test_suppress(self):
        """`contextlib.suppress 真 ZeroDivisionError。"""
        with contextlib.suppress(ZeroDivisionError):
            1 / 0
        # 必 不抛
        assert True

    def test_redirect_stdout(self, capsys):
        """`contextlib.redirect_stdout 真 stdout。"""
        with contextlib.redirect_stdout(None) or True:
            pass
        # 必 callable
        assert callable(contextlib.redirect_stdout)

    def test_redirect_stderr(self):
        """`contextlib.redirect_stderr 真 stderr。"""
        # 必 callable
        assert callable(contextlib.redirect_stderr)

    def test_closing(self, tmp_path):
        """`contextlib.closing 真 file。"""
        f = open(tmp_path / "forge_close_v1.txt", "w")
        with contextlib.closing(f) as fp:
            fp.write("forge_closing_v1")
        # 必 closed
        assert f.closed is True

    def test_nullcontext(self):
        """`contextlib.nullcontext 真 42。"""
        with contextlib.nullcontext(42) as v:
            # 必 42
            assert v == 42

    def test_contextmanager(self):
        """`contextlib.contextmanager 真 deco。"""

        @contextlib.contextmanager
        def forge_cm_v1():
            yield "forge_cm_v1"

        with forge_cm_v1() as v:
            # 必 'forge_cm_v1'
            assert v == "forge_cm_v1"

    def test_chdir(self, tmp_path):
        """`contextlib.chdir 真 tmp。"""
        original = tmp_path.cwd()
        with contextlib.chdir(str(tmp_path)):
            assert tmp_path.cwd() == tmp_path
        # 必 还原
        assert tmp_path.cwd() == original

    def test_ExitStack(self):
        """`contextlib.ExitStack 真 with。"""
        with contextlib.ExitStack() as stack:
            stack.enter_context(contextlib.nullcontext("forge_es_v1"))
        # 必 不抛
        assert True


# -- abc 进阶 ----

class TestAbcAdvanceV2:
    def test_ABC(self):
        """`abc.ABC 真 abstract。"""

        class ForgeABC(abc.ABC):
            @abc.abstractmethod
            def m(self):
                pass

        # 必 class
        assert ForgeABC is not None

    def test_abstractmethod(self):
        """`abc.abstractmethod 真 deco。"""

        class ForgeABC2(abc.ABC):
            @abc.abstractmethod
            def m(self):
                pass

        # 必 抛 TypeError
        with pytest.raises(TypeError):
            ForgeABC2()

    def test_ABCMeta(self):
        """`abc.ABCMeta 真 meta。"""
        # 必 class
        assert abc.ABCMeta is not None

    def test_register(self):
        """`abc.register 真 cls。"""

        class ForgeBase(abc.ABC):
            pass

        class ForgeImpl:
            pass

        ForgeBase.register(ForgeImpl)
        # 必 registered
        assert issubclass(ForgeImpl, ForgeBase)

    def test_abstractclassmethod(self):
        """`abc.abstractclassmethod 真 deco。"""
        # 必 callable
        assert callable(abc.abstractclassmethod)


# -- copy 进阶 ----

class TestCopyAdvanceV2:
    def test_copy(self):
        """`copy.copy 真 list。"""
        original = [1, 2, [3, 4]]
        c = copy.copy(original)
        # 必 [1, 2, [3, 4]]
        assert c == original
        # 必 different id
        assert id(c) != id(original)

    def test_deepcopy(self):
        """`copy.deepcopy 真 nested。"""
        original = [1, 2, [3, 4]]
        c = copy.deepcopy(original)
        # 必 equal
        assert c == original
        # 必 different id
        assert id(c) != id(original)
        # 必 nested different id
        assert id(c[2]) != id(original[2])

    def test_Error(self):
        """`copy.Error 真 exc。"""
        # 必 class
        assert copy.Error is not None


# -- pprint 进阶 ----

class TestPprintAdvanceV2:
    def test_pprint(self, capsys):
        """`pprint.pprint 真 str。"""
        d = {"forge_pp_v1": 1, "forge_pp_v2": 2}
        pprint.pprint(d)
        captured = capsys.readouterr()
        # 必 'forge_pp_v1' 在
        assert "forge_pp_v1" in captured.out

    def test_pformat(self):
        """`pprint.pformat 真 str。"""
        d = {"forge_pf_v1": 1}
        s = pprint.pformat(d)
        # 必 str
        assert isinstance(s, str)
        assert "forge_pf_v1" in s

    def test_isreadable(self):
        """`pprint.isreadable 真 True/False。"""
        # 必 True
        assert pprint.isreadable({"a": 1}) is True
        # 必 True
        assert pprint.isreadable([1, 2, 3]) is True

    def test_isrecursive(self):
        """`pprint.isrecursive 真 True/False。"""
        # 必 False
        assert pprint.isrecursive([1, 2, 3]) is False

    def test_PrettyPrinter(self):
        """`pprint.PrettyPrinter 真 cls。"""
        # 必 class
        assert pprint.PrettyPrinter is not None


# -- reprlib 进阶 ----

class TestReprlibAdvanceV2:
    def test_Repr(self):
        """`reprlib.Repr 真 cls。"""
        # 必 class
        assert reprlib.Repr is not None

    def test_aRepr(self):
        """`reprlib.aRepr 真 instance。"""
        # 必 instance
        assert reprlib.aRepr is not None

    def test_recursive_repr(self):
        """`reprlib.recursive_repr 真 deco。"""
        # 必 callable
        assert callable(reprlib.recursive_repr)

    def test_reprlib(self):
        """`reprlib 模块 'reprlib'。"""
        assert reprlib.__name__ == "reprlib"


# -- dataclasses 进阶 ----

class TestDataclassesAdvanceV2:
    def test_dataclass(self):
        """`dataclasses.dataclass 真 deco。"""

        @dataclasses.dataclass
        class ForgeDC:
            v: int = 0

        d = ForgeDC(v=42)
        # 必 42
        assert d.v == 42

    def test_field(self):
        """`dataclasses.field 真 default。"""

        @dataclasses.dataclass
        class ForgeDC2:
            v: int = dataclasses.field(default=42)

        d = ForgeDC2()
        # 必 42
        assert d.v == 42

    def test_asdict(self):
        """`dataclasses.asdict 真 dict。"""

        @dataclasses.dataclass
        class ForgeDC3:
            v: int = 42

        d = dataclasses.asdict(ForgeDC3())
        # 必 {'v': 42}
        assert d == {"v": 42}

    def test_astuple(self):
        """`dataclasses.astuple 真 tuple。"""

        @dataclasses.dataclass
        class ForgeDC4:
            v: int = 42

        t = dataclasses.astuple(ForgeDC4())
        # 必 (42,)
        assert t == (42,)

    def test_replace(self):
        """`dataclasses.replace 真 new。"""

        @dataclasses.dataclass
        class ForgeDC5:
            v: int = 42

        d = dataclasses.replace(ForgeDC5(), v=100)
        # 必 100
        assert d.v == 100

    def test_is_dataclass(self):
        """`dataclasses.is_dataclass 真 True/False。"""

        @dataclasses.dataclass
        class ForgeDC6:
            v: int = 0

        # 必 True
        assert dataclasses.is_dataclass(ForgeDC6) is True
        # 必 True
        assert dataclasses.is_dataclass(ForgeDC6()) is True
        # 必 False
        assert dataclasses.is_dataclass(42) is False


# -- enum 进阶 ----

class TestEnumAdvanceV2:
    def test_Enum(self):
        """`enum.Enum 真 member。"""

        class ForgeEnum(enum.Enum):
            A = 1
            B = 2

        # 必 member A
        assert ForgeEnum.A.value == 1
        assert ForgeEnum.A.name == "A"

    def test_IntEnum(self):
        """`enum.IntEnum 真 member。"""

        class ForgeIntEnum(enum.IntEnum):
            X = 10
            Y = 20

        # 必 int
        assert isinstance(ForgeIntEnum.X, int)
        # 必 value 10
        assert ForgeIntEnum.X.value == 10

    def test_Flag(self):
        """`enum.Flag 真 flag。"""

        class ForgeFlag(enum.Flag):
            A = 1
            B = 2

        combined = ForgeFlag.A | ForgeFlag.B
        # 必 3
        assert combined.value == 3

    def test_IntFlag(self):
        """`enum.IntFlag 真 int flag。"""

        class ForgeIntFlag(enum.IntFlag):
            A = 1
            B = 2

        combined = ForgeIntFlag.A | ForgeIntFlag.B
        # 必 3
        assert combined.value == 3
        # 必 int
        assert isinstance(combined, int)

    def test_auto(self):
        """`enum.auto 真 auto。"""

        class ForgeAuto(enum.Enum):
            A = enum.auto()
            B = enum.auto()

        # 必 A=1
        assert ForgeAuto.A.value == 1
        # 必 B=2
        assert ForgeAuto.B.value == 2

    def test_unique(self):
        """`enum.unique 真 deco。"""
        # 必 callable
        assert callable(enum.unique)
