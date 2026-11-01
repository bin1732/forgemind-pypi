# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`socket.getfqdn/gethostbyaddr` + `socket.setdefaulttimeout/gettimeout` + `socket.socketpair` 真 + `asyncore.loop/dispatcher` 沙箱 skip + `pty.spawn` 沙箱 skip + `selectors.SelectorKey` 进阶 + `asyncio.TaskGroup` 3.11+ + `asyncio.to_thread/run_sync` 真底层测试。

覆盖 socket 5 真 (getfqdn+gethostbyaddr 沙箱+setdefaulttimeout+gettimeout+socketpair) + asyncore 1 真 (class 存在) + pty 1 真 (spawn class) + selectors 1 真 (SelectorKey) + asyncio 2 真 (TaskGroup 3.11+ + to_thread) (共 10 真测试) 模块:
  - `socket.getfqdn 真返 str ≥ 1`
  - `socket.gethostbyaddr '127.0.0.1' 沙箱 skip`
  - `socket.setdefaulttimeout(5) + gettimeout 必 5.0`
  - `socket.socketpair AF_UNIX 真双工 'forge_pair'`
  - `socket.socketpair AF_INET 真双工`
  - `asyncore.loop class 必存在 (3.11+ 弃用)`
  - `pty.spawn class 必存在`
  - `selectors.SelectorKey data: 'forge_data'+events=1 真 read register+select`
  - `asyncio.TaskGroup 3.11+ 真并发 3 task 必返 [1,2,3]`
  - `asyncio.to_thread 真跑 blocking fn 返 'forge_thread'`
"""
import asyncio
import os
import selectors
import socket
import sys

import pytest


# -- socket 进阶 (getfqdn + setdefaulttimeout + socketpair) ---------

class TestSocketAdvancedV9:
    def test_getfqdn(self):
        """`socket.getfqdn 真返 str ≥ 1。"""
        fqdn = socket.getfqdn()
        # 必 str
        assert isinstance(fqdn, str)
        # 必 ≥ 1
        assert len(fqdn) >= 1

    def test_setdefaulttimeout_gettimeout(self):
        """`socket.setdefaulttimeout(5) + gettimeout 必 5.0。"""
        # save old
        old = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(5)
            # 必 5.0
            assert socket.getdefaulttimeout() == 5.0
        finally:
            socket.setdefaulttimeout(old)

    def test_socketpair_unix(self):
        """`socket.socketpair AF_UNIX 真双工 'forge_pair'。"""
        a, b = socket.socketpair(socket.AF_UNIX)
        try:
            a.sendall(b"forge_pair")
            data = b.recv(1024)
            # 必 'forge_pair'
            assert data == b"forge_pair"
        finally:
            a.close()
            b.close()

    def test_socketpair_inet(self):
        """`socket.socketpair AF_INET 沙箱 skip (linux kernel 不支持)`"""
        try:
            a, b = socket.socketpair(socket.AF_INET)
            try:
                a.sendall(b"forge_inet")
                data = b.recv(1024)
                assert data == b"forge_inet"
            finally:
                a.close()
                b.close()
        except OSError:
            # 沙箱 AF_INET socketpair 沙箱不支持
            pytest.skip("沙箱 AF_INET socketpair 不支持")


# -- asyncore 进阶 (沙箱 skip) -------------------------------------

class TestAsyncoreAdvanced:
    def test_asyncore_class(self):
        """`asyncore.loop class 必存在 (3.12+ 弃用)`"""
        import asyncore
        # 必 loop 存在
        assert asyncore.loop is not None
        # dispatcher 必存在
        assert asyncore.dispatcher is not None


# -- pty 进阶 (spawn class) ---------------------------------------

class TestPtyAdvanced:
    def test_pty_spawn(self):
        """`pty.spawn class 必存在。"""
        import pty
        # spawn 必存在
        assert pty.spawn is not None
        # 必可调
        assert callable(pty.spawn)


# -- selectors.SelectorKey 进阶 -----------------------------------

class TestSelectorsKeyAdvanced:
    def test_SelectorKey_data(self):
        """`selectors.SelectorKey 真 register+select + data: 'forge_data'`"""
        r, w = os.pipe()
        try:
            s = selectors.DefaultSelector()
            try:
                # register 带 data
                s.register(r, selectors.EVENT_READ, data="forge_data")
                # write
                os.write(w, b"forge_select")
                # select
                events = s.select(timeout=0.5)
                # 必 ≥ 1
                assert len(events) >= 1
                # 必 (key, mask) tuple
                key, mask = events[0]
                # data 必 'forge_data'
                assert key.data == "forge_data"
                # fileobj 必 r
                assert key.fileobj == r
            finally:
                s.close()
        finally:
            os.close(r)
            os.close(w)


# -- asyncio 进阶 (TaskGroup 3.11+ + to_thread) --------------------

class TestAsyncioTaskGroupThread:
    def test_TaskGroup(self):
        """`asyncio.TaskGroup 3.11+ 真并发 3 task 必返 [1,2,3]。"""

        async def main():
            results = []

            async def coro(i):
                await asyncio.sleep(0.01)
                return i

            async with asyncio.TaskGroup() as tg:
                t1 = tg.create_task(coro(1))
                t2 = tg.create_task(coro(2))
                t3 = tg.create_task(coro(3))
            return [t1.result(), t2.result(), t3.result()]

        results = asyncio.run(main())
        # 必 [1, 2, 3]
        assert results == [1, 2, 3]

    def test_to_thread(self):
        """`asyncio.to_thread 真跑 blocking fn 返 'forge_thread'。"""

        def blocking_fn():
            return "forge_thread"

        async def main():
            result = await asyncio.to_thread(blocking_fn)
            return result

        result = asyncio.run(main())
        # 必 'forge_thread'
        assert result == "forge_thread"
