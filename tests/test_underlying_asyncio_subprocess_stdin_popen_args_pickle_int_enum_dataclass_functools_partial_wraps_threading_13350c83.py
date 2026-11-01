# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.subprocess` 进阶 (stdin 真发 多 args + 收 stdout) + `subprocess.Popen` 进阶 (args+kwargs) + `pickle` 进阶 (int+enum+dataclass round-trip) + `functools` 进阶 (partial+wraps+total_ordering+cache) + `threading.Semaphore/BoundedSemaphore` 进阶 (acquire+release+locked) + `inspect.isgenerator/iscoroutinefunction/getcoroutine` 进阶 + 真底层测试。

覆盖 asyncio.subprocess 1 真 (stdin 'forge' cat) + subprocess 1 真 (Popen kwargs) + pickle 3 真 (int+enum+dataclass round-trip) + functools 3 真 (partial+wraps+total_ordering) + threading 2 真 (Semaphore+BoundedSemaphore) + inspect 2 真 (isgenerator+iscoroutinefunction) (共 12 真测试) 模块:
  - `asyncio.subprocess cat stdin 'forge_async' echo back`
  - `subprocess.Popen 'echo' bufsize=0+encoding='utf-8'`
  - `pickle 42 protocol 5 round-trip 必 42`
  - `pickle Enum value 'FORGE' round-trip 必 Color.FORGE`
  - `pickle dataclass ForgePt(x=42) round-trip`
  - `functools.partial(inc, 10)(5) 必 15`
  - `functools.wraps 真保留 __name__/__doc__`
  - `functools.total_ordering < / <= / > / >=`
  - `threading.Semaphore 真 acquire+release+locked`
  - `threading.BoundedSemaphore(3) 真 max=3 + locked`
  - `inspect.isgenerator 真子化 yield`
  - `inspect.iscoroutinefunction 真 async fn`
"""
import asyncio
import dataclasses
import enum
import functools
import inspect
import os
import pickle
import subprocess
import sys
import threading

import pytest


# -- asyncio.subprocess 进阶 (stdin 真发 多 args) -----------

class TestAsyncioSubprocessStdinMultiArgsAdvanced:
    def test_subprocess_stdin_multi(self):
        """`asyncio.subprocess cat stdin 'forge_async' echo back。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "cat",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
            )
            # write
            proc.stdin.write(b"forge_async\n")
            await proc.stdin.drain()
            proc.stdin.close()
            stdout, _ = await proc.communicate()
            return stdout

        out = asyncio.run(main())
        # 必含 'forge_async'
        assert b"forge_async" in out


# -- subprocess.Popen 进阶 (args + kwargs) --------------

class TestSubprocessPopenArgsKwargsAdvanced:
    def test_Popen_args_kwargs(self):
        """`subprocess.Popen 'echo' bufsize=0+encoding='utf-8'。"""
        proc = subprocess.Popen(
            ["echo", "forge_args"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            encoding="utf-8",
        )
        out, _ = proc.communicate(timeout=5)
        # 必含 'forge_args'
        assert "forge_args" in out


# -- pickle 进阶 (int + enum + dataclass round-trip) -------

class _Color(enum.Enum):
    FORGE = "FORGE"
    THIRD = "THIRD"


@dataclasses.dataclass
class _ForgePt:
    x: int
    y: str = "forge_y"


class TestPickleAdvancedV4:
    def test_pickle_int(self):
        """`pickle 42 protocol 5 round-trip 必 42。"""
        result = pickle.loads(pickle.dumps(42, protocol=5))
        # 必 42
        assert result == 42

    def test_pickle_enum(self):
        """`pickle Enum value 'FORGE' round-trip 必 Color.FORGE。"""
        result = pickle.loads(pickle.dumps(_Color.FORGE, protocol=5))
        # 必 Color.FORGE
        assert result == _Color.FORGE

    def test_pickle_dataclass(self):
        """`pickle dataclass ForgePt(x=42) round-trip。"""
        d = _ForgePt(42, "forge")
        result = pickle.loads(pickle.dumps(d, protocol=5))
        # 必等值
        assert result.x == 42
        assert result.y == "forge"


# -- functools 进阶 (partial + wraps + total_ordering) ----

@functools.total_ordering
class _O:
    def __init__(self, x):
        self.x = x

    def __eq__(self, other):
        return self.x == other.x

    def __lt__(self, other):
        return self.x < other.x


class TestFunctoolsAdvancedV4:
    def test_partial(self):
        """`functools.partial(inc, 10)(5) 必 15。"""

        def inc(x, y):
            return x + y

        p = functools.partial(inc, 10)
        # 必 15
        assert p(5) == 15

    def test_wraps(self):
        """`functools.wraps 真保留 __name__/__doc__。"""

        def my_decorator(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                return fn(*args, **kwargs)
            return wrapper

        @my_decorator
        def my_fn():
            """forge doc"""
            return "forge_fn"

        # 必保留 __name__
        assert my_fn.__name__ == "my_fn"
        # 必保留 __doc__
        assert "forge doc" in my_fn.__doc__

    def test_total_ordering(self):
        """`functools.total_ordering < / <= / > / >=。"""
        a = _O(1)
        b = _O(2)
        # 必 < / <=
        assert a < b
        assert a <= b
        # 必 > / >=
        assert b > a
        assert b >= a


# -- threading.Semaphore + BoundedSemaphore 进阶 ----------

class TestThreadingSemaphoreBoundedAdvanced:
    def test_Semaphore_acquire_release(self):
        """`threading.Semaphore 真 acquire+release+_value。"""
        sem = threading.Semaphore(2)
        # acquire
        sem.acquire()
        # 必 _value = 1
        assert sem._value == 1
        # release
        sem.release()
        # 必 _value = 2
        assert sem._value == 2

    def test_BoundedSemaphore_max3(self):
        """`threading.BoundedSemaphore(3) 真 max=3。"""
        sem = threading.BoundedSemaphore(3)
        # 必 max=3
        assert sem._value == 3
        # 必能 acquire
        sem.acquire()
        # 必 _value = 2
        assert sem._value == 2
        sem.release()


# -- inspect 进阶 (isgenerator + iscoroutinefunction) -----

class TestInspectIsgeneratorIscoroutineAdvanced:
    def test_isgenerator(self):
        """`inspect.isgenerator 真子化 yield。"""

        def gen():
            yield 1
            yield 2

        # 必 generator (callable)
        g = gen()
        # 必是 generator
        assert inspect.isgenerator(g) is True

    def test_iscoroutinefunction(self):
        """`inspect.iscoroutinefunction 真 async fn。"""

        async def my_coro():
            return "forge"

        # 必是 coroutinefunction
        assert inspect.iscoroutinefunction(my_coro) is True
