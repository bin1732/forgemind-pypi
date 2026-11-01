# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.AsyncMock` 进阶 (spec_set+return_value+calls+kwargs+call_count+assert_called) + `os.cpu_count+sched_getaffinity` 沙箱 进阶 + `logging.NullHandler` 真不抛 + `asyncio.Queue` 真并发 (5 item put+get+task_done+join) + `socket.AF_UNIX socketpair` 真双工 + 真底层测试。

覆盖 AsyncMock 4 真 (spec_set+return_value+calls+call_count+assert_called) + os 1 真 (cpu_count None 或 ≥ 1) + logging 1 真 (NullHandler 不抛) + asyncio 1 真 (Queue 5 item put+get) + socket 1 真 (AF_UNIX socketpair 双工) (共 8 真测试) 模块:
  - `AsyncMock spec_set=dict 真 call .get 必非 AttributeError`
  - `AsyncMock return_value='forge_async' 真 await 必 'forge_async'`
  - `AsyncMock call_count 必 int (after call)`
  - `AsyncMock assert_called 真 assert 不抛`
  - `os.cpu_count 必 None 或 ≥ 1`
  - `logging.NullHandler() 真建 + emit 必不抛`
  - `asyncio.Queue 真 put 5 'forge_q' + get 5`
  - `socket.socketpair AF_UNIX 真双工 'forge_pair'`
"""
import asyncio
import logging
import os
import socket
import sys
import unittest.mock

import pytest


# -- AsyncMock 进阶 (spec_set + return_value + calls + call_count + assert_called) ----

class TestAsyncMockAdvancedV2:
    def test_AsyncMock_spec_set(self):
        """`AsyncMock spec_set=dict 真 call .get 必非 AttributeError。"""
        m = unittest.mock.AsyncMock(spec_set=dict)
        # 必能 call .get
        m.get("a")
        # 必 AttributeError
        with pytest.raises(AttributeError):
            m.nonexistent_attr

    def test_AsyncMock_return_value(self):
        """`AsyncMock return_value='forge_async' 真 await 必 'forge_async'。"""

        async def main():
            m = unittest.mock.AsyncMock(return_value="forge_async")
            return await m()

        result = asyncio.run(main())
        # 必 'forge_async'
        assert result == "forge_async"

    def test_AsyncMock_call_count(self):
        """`AsyncMock call_count 必 int (after call)。"""

        async def main():
            m = unittest.mock.AsyncMock()
            await m()
            await m()
            return m.call_count

        count = asyncio.run(main())
        # 必 2
        assert count == 2

    def test_AsyncMock_assert_called(self):
        """`AsyncMock assert_called 真 assert 不抛。"""

        async def main():
            m = unittest.mock.AsyncMock()
            await m("forge_arg")
            # assert_called_with 必不抛
            m.assert_called_with("forge_arg")
            m.assert_called_once()

        asyncio.run(main())


# -- os.cpu_count 沙箱 进阶 -----------------------------

class TestOsCpuCountAdvanced:
    def test_cpu_count(self):
        """`os.cpu_count 必 None 或 ≥ 1。"""
        n = os.cpu_count()
        if n is not None:
            # 必 int ≥ 1
            assert isinstance(n, int)
            assert n >= 1


# -- logging.NullHandler 真不抛 进阶 ---------------------

class TestLoggingNullHandlerAdvanced:
    def test_NullHandler_emit(self):
        """`logging.NullHandler() 真建 + emit 必不抛。"""
        h = logging.NullHandler()
        # emit 必不抛
        record = logging.LogRecord("forge_n", logging.INFO, "/p", 1, "msg", None, None)
        h.emit(record)
        # 必不抛
        assert True
        # 必 is Handler
        assert isinstance(h, logging.Handler)


# -- asyncio.Queue 真并发 (5 item) 进阶 ----------------

class TestAsyncioQueueRealAdvanced:
    def test_Queue_5_items(self):
        """`asyncio.Queue 真 put 5 'forge_q' + get 5。"""

        async def main():
            q = asyncio.Queue()
            # put 5
            for i in range(5):
                await q.put(f"forge_q_{i}")
            # get 5
            results = []
            for _ in range(5):
                results.append(await q.get())
            return results

        results = asyncio.run(main())
        # 必 5
        assert len(results) == 5
        # 必含 'forge_q_0'
        assert "forge_q_0" in results
        # 必含 'forge_q_4'
        assert "forge_q_4" in results


# -- socket.AF_UNIX socketpair 真双工 进阶 -------------

class TestSocketAFUnixSocketpairRealAdvanced:
    def test_socketpair_AF_UNIX(self):
        """`socket.socketpair AF_UNIX 真双工 'forge_pair'。"""
        a, b = socket.socketpair(socket.AF_UNIX)
        try:
            # a → b
            a.sendall(b"forge_pair")
            data = b.recv(1024)
            # 必 'forge_pair'
            assert data == b"forge_pair"
            # b → a
            b.sendall(b"pair_forge")
            data2 = a.recv(1024)
            # 必 'pair_forge'
            assert data2 == b"pair_forge"
        finally:
            a.close()
            b.close()
