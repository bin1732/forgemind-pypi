# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`urllib.request` + `selectors` + `sched` + `queue` 真底层测试。

覆盖 HTTP 客户端 / I/O 多路复用 / 调度器 / 线程安全队列:
  - 起本地 WSGI 服务,`urllib.request.urlopen` 真发 GET,200 + 'hi forge'
  - `selectors.DefaultSelector` 真注册 socket + select,read 事件触发
  - `sched.scheduler` 真按延迟时间顺序触发 3 个事件,记录实际 vs 计划延迟
  - `queue.Queue` 真多线程 put/get,`task_done` + `join` 同步
  - `queue.PriorityQueue` 真按 (priority, item) 顺序取出
  - `queue.LifoQueue` 真后进先出
"""
import heapq
import queue
import sched
import selectors
import socket
import sys
import threading
import time
import urllib.request
import wsgiref.simple_server

import pytest


# -- urllib.request ------------------------------------------------------------

def _forge_app(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [b"hi forge"]


def _start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = wsgiref.simple_server.make_server("127.0.0.1", port, _forge_app)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, port


class TestUrllibRequest:
    def test_urlopen_against_local_wsgiref(self):
        """`urllib.request.urlopen(http://127.0.0.1:port/)` 真发 GET,200 + b'hi forge'。"""
        server, port = _start_server()
        try:
            time.sleep(0.05)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as resp:
                assert resp.status == 200
                body = resp.read()
            assert body == b"hi forge", f"body 应为 b'hi forge',实际 {body!r}"
        finally:
            server.shutdown()
            server.server_close()


# -- selectors ----------------------------------------------------------------

class TestSelectors:
    def test_default_selector_register_and_select(self):
        """`DefaultSelector.register(sock, EVENT_READ)` 真监控 socket,数据到来时 select 触发。"""
        sel = selectors.DefaultSelector()
        # server socket:accept 一个连接
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        sel.register(server, selectors.EVENT_READ)

        # client 连过来
        client_evt = threading.Event()
        def do_connect():
            c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c.connect(("127.0.0.1", port))
            c.close()  # close 后 server 端会触发 EVENT_READ
            client_evt.set()
        threading.Thread(target=do_connect, daemon=True).start()
        client_evt.wait(timeout=2)

        # 等最多 1 秒,期待 server socket 变为可读 (accept-ready)
        events = sel.select(timeout=1.0)
        assert events, "1s 内 server socket 仍不可读"
        key, _mask = events[0]
        assert key.fileobj is server
        sel.unregister(server)
        sel.close()
        server.close()


# -- sched --------------------------------------------------------------------

class TestSched:
    def test_scheduler_runs_events_in_delay_order(self):
        """`sched.scheduler.enter(delay, ...)` 真按 delay 顺序触发 3 个事件。"""
        s = sched.scheduler(time.monotonic, time.sleep)
        order = []

        def make_callback(label):
            def cb():
                order.append(label)
            return cb

        # 注意:enter 的 delay 是相对值,从 enter() 调用开始计时
        start = time.monotonic()
        s.enter(0.05, 1, make_callback("late"))
        s.enter(0.02, 1, make_callback("mid"))
        s.enter(0.01, 1, make_callback("early"))
        s.run()
        elapsed = time.monotonic() - start
        assert order == ["early", "mid", "late"], (
            f"应按 delay 升序触发,实际 {order}"
        )
        # 实际耗时 ≥ 0.05s (最长一个 delay)
        assert elapsed >= 0.05, f"总耗时应 ≥ 0.05s,实际 {elapsed:.3f}s"

    def test_scheduler_cancel_pending(self):
        """`sched.scheduler.cancel(ev)` 真从队列移除未触发事件,run 不再调它。"""
        s = sched.scheduler(time.monotonic, time.sleep)
        fired = []
        ev1 = s.enter(0.01, 1, lambda: fired.append("a"))
        ev2 = s.enter(0.02, 1, lambda: fired.append("b"))
        # 取消 ev2
        s.cancel(ev2)
        s.run()
        assert fired == ["a"], f"应只有 a 触发,实际 {fired}"


# -- queue --------------------------------------------------------------------

class TestQueue:
    def test_queue_put_get_thread_safe(self):
        """`queue.Queue` 真线程安全,10 个 producer + 1 consumer 收 100 项。"""
        q = queue.Queue()
        producers_done = threading.Event()

        def producer(n_items):
            for i in range(n_items):
                q.put(i)
            producers_done.set()

        threads = [threading.Thread(target=producer, args=(10,)) for _ in range(10)]
        for t in threads:
            t.start()

        # 等所有 producer 结束
        for t in threads:
            t.join(timeout=2)

        # 收 100 项
        received = []
        while not q.empty():
            received.append(q.get())
        assert len(received) == 100, f"应收 100 项,实际 {len(received)}"

    def test_priority_queue_orders_by_priority(self):
        """`queue.PriorityQueue` 真按 (priority, item) 顺序取出,小优先先出。"""
        pq = queue.PriorityQueue()
        pq.put((3, "third"))
        pq.put((1, "first"))
        pq.put((2, "second"))
        assert pq.get() == (1, "first")
        assert pq.get() == (2, "second")
        assert pq.get() == (3, "third")

    def test_lifo_queue_pops_in_reverse(self):
        """`queue.LifoQueue` 真后进先出,栈语义。"""
        lq = queue.LifoQueue()
        lq.put(1)
        lq.put(2)
        lq.put(3)
        assert lq.get() == 3, f"LIFO 第一个应=3,实际 {lq.get()}"
        assert lq.get() == 2
        assert lq.get() == 1

    def test_queue_task_done_and_join(self):
        """`Queue.task_done` + `Queue.join` 真同步:consumer 处理完所有项后 join 返。"""
        q = queue.Queue()
        for i in range(5):
            q.put(i)

        consumer_done = threading.Event()
        def consumer():
            while True:
                try:
                    item = q.get_nowait()
                except queue.Empty:
                    return
                # 模拟处理
                time.sleep(0.01)
                q.task_done()
            # 这里实际不会执行,join 会等所有 task_done

        t = threading.Thread(target=consumer, daemon=True)
        t.start()
        # join 等所有 task_done
        q.join()  # 不超时,5 项都应被处理
        t.join(timeout=1)
        # q.join() 成功返回 = consumer 调过 5 次 task_done
        assert q.empty() or q.qsize() < 5  # 全被取出过
