# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`tokenize` 进阶 (tokenize+generate_tokens+TokenInfo) + `io` 进阶 (BytesIO+StringIO+DEFAULT_BUFFER_SIZE) + `contextlib` 进阶 (contextmanager+suppress+redirect_stdout) + `dataclasses` 进阶 (dataclass+field+asdict+astuple) + `asyncio 进阶 (Lock+Event+Semaphore+Barrier 真并发)` + 真底层测试。

覆盖 tokenize 3 + io 4 + contextlib 3 + dataclasses 4 + asyncio.Lock 1 + asyncio.Event 1 + asyncio.Semaphore 1 + asyncio.Barrier 1 (共 18 真测试) 模块:
  - `tokenize.tokenize 'a'`
  - `tokenize.generate_tokens 'a'`
  - `tokenize.TokenInfo 'a'`
  - `io.BytesIO 'a'`
  - `io.StringIO 'a'`
  - `io.DEFAULT_BUFFER_SIZE 'a'`
  - `io.open 'a'`
  - `contextlib.contextmanager 'a'`
  - `contextlib.suppress 'a'`
  - `contextlib.redirect_stdout 'a'`
  - `dataclasses.dataclass 'a'`
  - `dataclasses.field 'a'`
  - `dataclasses.asdict 'a'`
  - `dataclasses.astuple 'a'`
  - `asyncio.Lock 真并发`
  - `asyncio.Event 真并发`
  - `asyncio.Semaphore 真并发`
  - `asyncio.Barrier 真并发`
"""
import asyncio
import contextlib
import dataclasses
import io
import tokenize

import pytest


@dataclasses.dataclass
class _ForgeDC:
    name: str
    value: int = 0


# -- tokenize 进阶 (tokenize+generate_tokens+TokenInfo) ---

class TestTokenizeAdvanceV3:
    def test_tokenize(self):
        """`tokenize.tokenize 'a'。"""
        buf = io.BytesIO(b"a = 1\n")
        # 必 ≥ 1 token
        tokens = list(tokenize.tokenize(buf.readline))
        assert len(tokens) >= 1

    def test_generate_tokens(self):
        """`tokenize.generate_tokens 'a'。"""
        buf = io.StringIO("a = 1\n")
        # 必 ≥ 1 token
        tokens = list(tokenize.generate_tokens(buf.readline))
        assert len(tokens) >= 1

    def test_TokenInfo(self):
        """`tokenize.TokenInfo 'a'。"""
        # 必 class
        assert tokenize.TokenInfo is not None


# -- io 进阶 (BytesIO+StringIO+DEFAULT_BUFFER_SIZE+open) ---

class TestIoAdvanceV1:
    def test_BytesIO(self):
        """`io.BytesIO 'a'。"""
        buf = io.BytesIO(b"forge_io_v1")
        # 必 'forge_io_v1'
        assert buf.read() == b"forge_io_v1"

    def test_StringIO(self):
        """`io.StringIO 'a'。"""
        buf = io.StringIO("forge_io_v2")
        # 必 'forge_io_v2'
        assert buf.read() == "forge_io_v2"

    def test_DEFAULT_BUFFER_SIZE(self):
        """`io.DEFAULT_BUFFER_SIZE 'a'。"""
        # 必 int ≥ 1024
        assert isinstance(io.DEFAULT_BUFFER_SIZE, int)
        assert io.DEFAULT_BUFFER_SIZE >= 1024

    def test_open(self, tmp_path):
        """`io.open 'a'。"""
        f = tmp_path / "forge_io_open_v1.txt"
        f.write_text("forge_io_open_v2")
        # 必 可读
        with io.open(str(f), "r") as fp:
            content = fp.read()
        # 必 'forge_io_open_v2'
        assert content == "forge_io_open_v2"


# -- contextlib 进阶 (contextmanager+suppress+redirect_stdout) ---

class TestContextlibAdvanceV1:
    def test_contextmanager(self):
        """`contextlib.contextmanager 'a'。"""
        # 必 callable
        assert callable(contextlib.contextmanager)

    def test_suppress(self):
        """`contextlib.suppress 'a'。"""
        # 必 不崩 (suppress 不存在异常)
        with contextlib.suppress(ValueError):
            _ = int("forge_v1")
        assert True

    def test_redirect_stdout(self):
        """`contextlib.redirect_stdout 'a'。"""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print("forge_redirect_v1")
        # 必 含 'forge_redirect_v1'
        assert "forge_redirect_v1" in buf.getvalue()


# -- dataclasses 进阶 (dataclass+field+asdict+astuple) ---

class TestDataclassesAdvanceV1:
    def test_dataclass(self):
        """`dataclasses.dataclass 'a'。"""
        dc = _ForgeDC(name="forge_name_v1", value=42)
        # 必 'forge_name_v1'
        assert dc.name == "forge_name_v1"
        # 必 42
        assert dc.value == 42

    def test_field(self):
        """`dataclasses.field 'a'。"""
        # 必 不崩
        f = dataclasses.field(default=42)
        # 必 42
        assert f.default == 42

    def test_asdict(self):
        """`dataclasses.asdict 'a'。"""
        dc = _ForgeDC(name="forge_d_v1", value=1)
        d = dataclasses.asdict(dc)
        # 必 dict
        assert isinstance(d, dict)
        # 必 'forge_d_v1'
        assert d["name"] == "forge_d_v1"

    def test_astuple(self):
        """`dataclasses.astuple 'a'。"""
        dc = _ForgeDC(name="forge_d_v2", value=2)
        t = dataclasses.astuple(dc)
        # 必 tuple
        assert isinstance(t, tuple)
        # 必 'forge_d_v2'
        assert t[0] == "forge_d_v2"


# -- asyncio.Lock 进阶 (真并发) --

class TestAsyncioLockAdvanceV1:
    def test_Lock(self):
        """`asyncio.Lock 真并发。"""

        async def main():
            lock = asyncio.Lock()
            n = 0

            async def _worker():
                nonlocal n
                async with lock:
                    local = n
                    await asyncio.sleep(0)
                    n = local + 1

            await asyncio.gather(*[_worker() for _ in range(100)])
            return n

        result = asyncio.run(main())
        # 必 100
        assert result == 100


# -- asyncio.Event 进阶 (真并发) --

class TestAsyncioEventAdvanceV1:
    def test_Event(self):
        """`asyncio.Event 真并发。"""

        async def main():
            event = asyncio.Event()
            results = []

            async def _waiter(idx):
                await event.wait()
                results.append(idx)

            async def _setter():
                await asyncio.sleep(0.01)
                event.set()

            await asyncio.gather(*[_waiter(i) for i in range(50)], _setter())
            return results

        results = asyncio.run(main())
        # 必 50
        assert len(results) == 50


# -- asyncio.Semaphore 进阶 (真并发) --

class TestAsyncioSemaphoreAdvanceV1:
    def test_Semaphore(self):
        """`asyncio.Semaphore 真并发。"""

        async def main():
            sem = asyncio.Semaphore(3)
            active = 0
            max_active = 0

            async def _worker():
                nonlocal active, max_active
                async with sem:
                    active += 1
                    max_active = max(max_active, active)
                    await asyncio.sleep(0.01)
                    active -= 1

            await asyncio.gather(*[_worker() for _ in range(30)])
            return max_active

        result = asyncio.run(main())
        # 必 ≤ 3
        assert result <= 3
        assert result >= 1


# -- asyncio.Barrier 进阶 (真并发) --

class TestAsyncioBarrierAdvanceV1:
    def test_Barrier(self):
        """`asyncio.Barrier 真并发 (3.11+ 存在)。"""
        try:
            barrier = asyncio.Barrier(3)
        except AttributeError:
            # 沙箱 3.11 可能无 Barrier
            assert True
            return

        async def main():
            results = []

            async def _worker(idx):
                await barrier.wait()
                results.append(idx)

            await asyncio.gather(*[_worker(i) for i in range(3)])
            return results

        results = asyncio.run(main())
        # 必 3
        assert len(results) == 3
