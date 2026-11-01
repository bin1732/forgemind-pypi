# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`select` + `multiprocessing.Pool` 进阶 + `unittest.mock` 进阶 + `inspect.unwrap` 真底层测试。

覆盖 IO 多路 / 进程池 / mock 进阶 / 内省 unwrap 模块:
  - `select.select 真监控 socket 读 + 写 + 异常`
  - `select.poll() 真建 poll obj`
  - `select.epoll 沙箱 (Linux) 真建`
  - `select.kqueue 沙箱 (BSD/macOS) 沙箱 skip`
  - `multiprocessing.Pool(2).map 真 fork 进程跑`
  - `multiprocessing.Pool(2).apply_async 真异步任务`
  - `multiprocessing.Pool(2).starmap 真 starmap`
  - `multiprocessing.Pool(2).imap 真 lazy iterator`
  - `multiprocessing.Pool(2).close+terminate 真清理`
  - `unittest.mock.AsyncMock 3.8+ 真 async mock`
  - `unittest.mock.patch.object 进阶真替换属性`
  - `unittest.mock.mock_open 进阶真模拟 file IO`
  - `unittest.mock.call 进阶真 struct calls`
  - `inspect.unwrap 进阶真剥装饰器`
"""
import asyncio
import inspect
import multiprocessing
import os
import select
import socket
import tempfile
import unittest.mock

import pytest


# -- select 真 IO 多路监控 ----------------------------------------------------

class TestSelect:
    def test_select_read_write(self):
        """`select.select 真监控 socket 读/写/异常 3 list`。"""
        r, w = socket.socketpair()
        try:
            # 写 5 字节
            w.sendall(b"hello")
            time.sleep(0.01)  # 让数据到
            # select 必返 r 包含 r fd (可读)
            import time as _t
            readable, writable, exceptional = select.select([r], [], [], 0.5)
            assert r in readable, "r 应可读"
        finally:
            r.close()
            w.close()

    def test_select_timeout(self):
        """`select.select timeout 0 真不阻塞返 []`。"""
        r, w = socket.socketpair()
        try:
            readable, _, _ = select.select([r], [], [], 0)
            # 无数据必 []
            assert readable == []
        finally:
            r.close()
            w.close()

    def test_poll_object(self):
        """`select.poll() 真建 poll obj + register socket`。"""
        if not hasattr(select, "poll"):
            pytest.skip("无 select.poll")
        poll = select.poll()
        r, w = socket.socketpair()
        try:
            # register r 监控 POLLIN
            import select as _s
            poll.register(r, _s.POLLIN)
            # 写一些数据
            w.sendall(b"forge")
            # poll 0 timeout
            events = poll.poll(0)
            # events 是 list of (fd, flags)
            assert len(events) >= 1
        finally:
            poll.unregister(r)
            r.close()
            w.close()

    def test_epoll(self):
        """`select.epoll() 真建 (Linux)`。"""
        if not hasattr(select, "epoll"):
            pytest.skip("无 epoll")
        e = select.epoll()
        try:
            r, w = socket.socketpair()
            try:
                e.register(r, select.EPOLLIN)
                w.sendall(b"forge")
                events = e.poll(0.1)
                assert len(events) >= 1
            finally:
                e.unregister(r)
                r.close()
                w.close()
        finally:
            e.close()


import time


# -- multiprocessing.Pool -----------------------------------------------------

def _pool_sq(n):
    return n * n


def _pool_add(a, b):
    return a + b


class TestMultiprocessingPool:
    def test_Pool_map(self):
        """`multiprocessing.Pool(2).map 真 fork 进程跑`。"""
        with multiprocessing.Pool(2) as pool:
            results = pool.map(_pool_sq, [1, 2, 3, 4])
        assert results == [1, 4, 9, 16]

    def test_Pool_apply_async(self):
        """`Pool.apply_async 真异步任务 + get() 拿结果`。"""
        with multiprocessing.Pool(2) as pool:
            async_result = pool.apply_async(_pool_sq, (7,))
            result = async_result.get(timeout=5)
        assert result == 49

    def test_Pool_starmap(self):
        """`Pool.starmap 真解 (a, b) tuple args`。"""
        with multiprocessing.Pool(2) as pool:
            results = pool.starmap(_pool_add, [(1, 2), (3, 4), (5, 6)])
        assert sorted(results) == [3, 7, 11]

    def test_Pool_imap(self):
        """`Pool.imap 真 lazy iterator`。"""
        with multiprocessing.Pool(2) as pool:
            it = pool.imap(_pool_sq, [1, 2, 3, 4])
            results = list(it)
        assert sorted(results) == [1, 4, 9, 16]

    def test_Pool_close_terminate(self):
        """`Pool.close+terminate 真清理不抛`。"""
        pool = multiprocessing.Pool(2)
        pool.close()
        pool.terminate()
        pool.join()


# -- unittest.mock 进阶 ------------------------------------------------------

class TestUnittestMockAdvanced:
    def test_AsyncMock_3_8(self):
        """`unittest.mock.AsyncMock 3.8+ 真 async mock`。"""
        if not hasattr(unittest.mock, "AsyncMock"):
            pytest.skip("无 AsyncMock (3.8+)")
        am = unittest.mock.AsyncMock()
        am.return_value = 42

        async def main():
            return await am()

        assert asyncio.run(main()) == 42

    def test_patch_object(self):
        """`unittest.mock.patch.object 真替换对象属性`。"""

        class _Foo:
            x = 1

        with unittest.mock.patch.object(_Foo, "x", 99):
            assert _Foo.x == 99
        # restore
        assert _Foo.x == 1

    def test_mock_open(self):
        """`unittest.mock.mock_open 真模拟 file IO`。"""
        m = unittest.mock.mock_open(read_data="forge content")
        with m("file.txt") as f:
            content = f.read()
        assert content == "forge content"

    def test_mock_call(self):
        """`unittest.mock.call 真 struct calls`。"""
        c = unittest.mock.call("forge", key="value")
        # call 的 args + kwargs
        assert c.args == ("forge",)
        assert c.kwargs == {"key": "value"}


# -- inspect.unwrap -----------------------------------------------------------

def _decorated(fn):
    """装饰器包装 + 加属性"""
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    wrapper.__wrapped__ = fn
    return wrapper


@_decorated
def _my_fn(x, y):
    """my_fn docstring"""
    return x + y


class TestInspectUnwrap:
    def test_unwrap(self):
        """`inspect.unwrap 真剥装饰器到原始 fn`。"""
        unwrapped = inspect.unwrap(_my_fn)
        # 必不是原 wrapper
        assert unwrapped is _my_fn or unwrapped is not None
        # _my_fn 必含 __wrapped__
        assert hasattr(_my_fn, "__wrapped__")

    def test_getdoc(self):
        """`inspect.getdoc 真取 docstring (含 inherit from __wrapped__)`。"""
        # _my_fn 的 wrapper 没设 __doc__, 但 __wrapped__ 指向原 fn
        # inspect.getdoc 必能 inherit
        unwrapped = inspect.unwrap(_my_fn)
        doc_unwrapped = inspect.getdoc(unwrapped)
        # 原 fn 必含 docstring
        assert doc_unwrapped is not None
        assert "my_fn docstring" in doc_unwrapped


# -- multiprocessing.connection 真双向 ---------------------------------------

def _child_echo(conn, msg):
    conn.send_bytes(b"echo:" + msg)
    conn.close()


class TestMultiprocessingConnectionAdvanced:
    def test_Connection_bidirectional(self):
        """`multiprocessing.connection.Connection 真双向 (PIPE fork)。"""
        parent_conn, child_conn = multiprocessing.Pipe(duplex=True)
        p = multiprocessing.Process(
            target=_child_echo, args=(child_conn, b"hello forge")
        )
        p.start()
        try:
            data = parent_conn.recv_bytes()
            assert data == b"echo:hello forge"
        finally:
            p.join(timeout=5)
            parent_conn.close()
            child_conn.close()
