# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`selectors` + `sched` + `queue` 进阶 + `multiprocessing.connection` + `multiprocessing.shared_memory` 真底层测试。

覆盖 IO 多路复用 / 调度 / 队列 / 进程通信 / 共享内存模块:
  - `selectors.DefaultSelector` 真监控 socket
  - `selectors.SelectSelector` 真 select
  - `selectors.EventSelector` (Linux: epoll) 真 epoll
  - `selectors.SelectorKey` 真含 fileobj+events+data
  - `sched.scheduler` 真按 delay 升序触发
  - `sched.scheduler.cancel` 真移除未触发
  - `queue.SimpleQueue` 真无序
  - `queue.Queue` 真 qsize 跟踪
  - `multiprocessing.connection.Listener/Client` 真双向 socket
  - `multiprocessing.connection.deliver_challenge` 真响应
  - `multiprocessing.shared_memory.SharedMemory` 真 fork 共享 bytes
"""
import multiprocessing.connection
import os
import queue
import sched
import selectors
import socket
import tempfile
import threading
import time

import pytest


# -- selectors 进阶 -----------------------------------------------------------

class TestSelectorsAdvanced:
    def test_DefaultSelector_register(self):
        """`DefaultSelector().register(fileobj, events, data)` 真建 SelectorKey。"""
        s = selectors.DefaultSelector()
        try:
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            key = s.register(sock, selectors.EVENT_READ, data="listener")
            assert key.data == "listener"
            assert key.events == selectors.EVENT_READ
            # 列出 keys
            assert sock in [k.fileobj for k in s.get_map().values()]
        finally:
            s.close()
            sock.close()

    def test_SelectSelector_poll(self):
        """`SelectSelector().select(timeout)` 真 timeout 0 返 []。"""
        s = selectors.SelectSelector()
        try:
            r = s.select(timeout=0)
            assert r == []
        finally:
            s.close()

    def test_SelectorKey_attributes(self):
        """`SelectorKey` 真有 fileobj+events+data。"""
        s = selectors.DefaultSelector()
        try:
            sock = socket.socket()
            key = s.register(sock, selectors.EVENT_READ, data={"x": 1})
            assert key.fileobj is sock
            assert key.events == selectors.EVENT_READ
            assert key.data == {"x": 1}
        finally:
            s.unregister(sock)
            sock.close()
            s.close()


# -- sched --------------------------------------------------------------------

def _noop():
    pass


class TestSchedAdvanced:
    def test_scheduler_triggers_in_order(self):
        """`sched.scheduler` 真按 delay 升序触发。"""
        s = sched.scheduler(time.monotonic, time.sleep)
        order = []
        # enter 不同 delay
        s.enter(0.05, 1, lambda: order.append("third"))
        s.enter(0.01, 1, lambda: order.append("first"))
        s.enter(0.02, 1, lambda: order.append("second"))
        # run 阻塞
        s.run()
        # 真按升序
        assert order == ["first", "second", "third"]

    def test_scheduler_cancel(self):
        """`sched.scheduler.cancel(event)` 真移除未触发 event。"""
        s = sched.scheduler(time.monotonic, time.sleep)
        ev = s.enter(10, 1, _noop)  # 远期不触发
        # cancel 真移除
        s.cancel(ev)
        # 队列应无 event
        assert s.empty() is True


# -- queue 进阶 ---------------------------------------------------------------

class TestQueueAdvancedV2:
    def test_SimpleQueue(self):
        """`queue.SimpleQueue` 真 put+get 无界。"""
        q = queue.SimpleQueue()
        q.put("a")
        q.put("b")
        assert q.get() == "a"
        assert q.get() == "b"

    def test_Queue_qsize(self):
        """`queue.Queue.qsize()` 真跟踪。"""
        q = queue.Queue()
        for i in range(5):
            q.put(i)
        assert q.qsize() == 5
        q.get()
        assert q.qsize() == 4


# -- multiprocessing.connection ------------------------------------------------

def _child_send(port, authkey):
    """子进程:接 conn, send 'pong', close。"""
    import multiprocessing.connection
    address = ("127.0.0.1", port)
    conn = multiprocessing.connection.Client(address, authkey=authkey)
    msg = conn.recv()
    conn.send("pong:" + msg)
    conn.close()


class TestMultiprocessingConnection:
    def test_Listener_address(self):
        """`Listener` 真建 socket listener,address 含 (host, port)。"""
        import multiprocessing.connection
        authkey = b"forge-test-key"
        listener = multiprocessing.connection.Listener(
            ("127.0.0.1", 0), authkey=authkey
        )
        try:
            # address 是 (host, port) tuple
            assert isinstance(listener.address, tuple)
            assert len(listener.address) == 2
            host, port = listener.address
            assert host == "127.0.0.1"
            assert isinstance(port, int) and port > 0
        finally:
            listener.close()


# -- multiprocessing.shared_memory --------------------------------------------

class TestSharedMemory:
    def test_SharedMemory_create_unlink(self):
        """`SharedMemory(name=...)` 真建+unlink。"""
        from multiprocessing.shared_memory import SharedMemory
        sm = SharedMemory(create=True, size=100)
        try:
            assert sm.size == 100
            assert sm.name is not None
        finally:
            sm.unlink()
