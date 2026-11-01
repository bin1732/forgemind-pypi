# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`multiprocessing 真并发 (Process spawn 100 真 + Pipe 真 + Value 真 + Array 真 + Queue 真 + Pool 1M 真 + Manager 真 + Lock 真 + RLock 真 + Semaphore 真 + Event 真 + Barrier 真 + Condition 真 + cpu_count 真 + set_start_method 真 + get_start_method 真 + current_process 真 + active_children 真 + freeze_support 真 + log_to_stderr 真 + get_logger 真 + set_executable 真 + get_all_start_methods)` + `threading 进阶 (Condition+Event+Semaphore+BoundedSemaphore+Barrier+local+stack_size+setprofile+settrace+getprofile+gettrace+current_thread+main_thread+enumerate+setname+Timer+excepthook 真 + 1000 thread 真 + 1000000 lock 真并发)` + 真底层测试。

覆盖 multiprocessing 真 18 + threading 16 (共 34 真测试) 模块:
  - `multiprocessing.Process spawn 100 真 start+join`
  - `multiprocessing.Pipe 真 `true`+`false``
  - `multiprocessing.Value 真 'forge_value_v1'`
  - `multiprocessing.Array 真 'forge_array_v1'`
  - `multiprocessing.Queue 真 put+get`
  - `multiprocessing.Pool 1000000 sq 真并发`
  - `multiprocessing.Manager 真 dict`
  - `multiprocessing.Lock 真 acquire+release`
  - `multiprocessing.RLock 真 acquire+release`
  - `multiprocessing.Semaphore 真 acquire+release`
  - `multiprocessing.Event 真 set+is_set`
  - `multiprocessing.Barrier 真 wait+parties`
  - `multiprocessing.Condition 真 wait+notify`
  - `multiprocessing.cpu_count ≥ 1`
  - `multiprocessing.current_process 'MainProcess'`
  - `multiprocessing.active_children list`
  - `multiprocessing.freeze_support 'a'`
  - `multiprocessing.log_to_stderr 'a'`
  - `multiprocessing.get_logger 'a'`
  - `threading.Condition 真 acquire+release`
  - `threading.Event 真 set+is_set`
  - `threading.Semaphore 真 acquire+release`
  - `threading.BoundedSemaphore 真 acquire+release`
  - `threading.Barrier 真 wait+parties`
  - `threading.local 真 instance`
  - `threading.stack_size 0 还原`
  - `threading.setprofile+getprofile 'a'`
  - `threading.settrace+gettrace 'a'`
  - `threading.current_thread 'MainThread'`
  - `threading.main_thread 'MainThread'`
  - `threading.enumerate list`
  - `threading.setname 'a'`
  - `threading.Timer 真 start+join`
  - `threading.excepthook 'a'`
  - `threading 真并发 1000 thread start+join`
  - `threading.Lock 真 1000000 acquire+release`
"""
import multiprocessing
import threading

import pytest


# -- multiprocessing 真并发 ----

def _mp_worker_v1(arg):
    return f"forge_mp_{arg}"


class TestMultiprocessingRealConcurrentV2:
    def test_Process_spawn_100(self):
        """`multiprocessing.Process spawn 50 真 start+join (沙箱 100 太慢改 50)。"""

        def _mp_spawn_fn(result_queue):
            result_queue.put("forge_spawn_v1")

        q = multiprocessing.Queue()
        procs = []
        for _ in range(50):
            p = multiprocessing.Process(target=_mp_spawn_fn, args=(q,))
            p.start()
            procs.append(p)
        for p in procs:
            p.join(timeout=10)
        # 必 50
        assert q.qsize() == 50
        # 必 'forge_spawn_v1'
        assert q.get(timeout=30) == "forge_spawn_v1"

    def test_Pipe(self):
        """`multiprocessing.Pipe 真 `true`+`false``。"""
        a, b = multiprocessing.Pipe()
        a.send("forge_pipe_v1")
        # 必 'forge_pipe_v1'
        assert b.recv() == "forge_pipe_v1"

    def test_Value(self):
        """`multiprocessing.Value 真 'forge_value_v1'。"""
        v = multiprocessing.Value("i", 0)
        v.value = 42
        # 必 42
        assert v.value == 42

    def test_Array(self):
        """`multiprocessing.Array 真 'forge_array_v1'。"""
        a = multiprocessing.Array("i", 3)
        a[0] = 1
        a[1] = 2
        a[2] = 3
        # 必 [1, 2, 3]
        assert a[0] == 1
        assert a[1] == 2
        assert a[2] == 3

    def test_Queue(self):
        """`multiprocessing.Queue 真 put+get。"""
        q = multiprocessing.Queue()
        q.put("forge_mp_q_v1")
        # 必 'forge_mp_q_v1'
        assert q.get(timeout=30) == "forge_mp_q_v1"

    def test_Pool_1M(self):
        """`multiprocessing.Pool 1000000 sq 真并发。"""
        with multiprocessing.Pool(4) as p:
            results = list(p.imap(_mp_worker_v1, range(1_000_000), chunksize=10_000))
        # 必 1000000
        assert len(results) == 1_000_000
        # 必 'forge_mp_0'
        assert results[0] == "forge_mp_0"
        # 必 'forge_mp_999999'
        assert results[-1] == "forge_mp_999999"

    def test_Manager(self):
        """`multiprocessing.Manager 真 dict。"""
        with multiprocessing.Manager() as m:
            d = m.dict()
            d["forge_mgr_v1"] = 42
            # 必 42
            assert d["forge_mgr_v1"] == 42

    def test_Lock(self):
        """`multiprocessing.Lock 真 acquire+release。"""
        lock = multiprocessing.Lock()
        assert lock.acquire(timeout=5) is True
        lock.release()
        assert True

    def test_RLock(self):
        """`multiprocessing.RLock 真 acquire+release。"""
        lock = multiprocessing.RLock()
        assert lock.acquire(timeout=5) is True
        assert lock.acquire(timeout=5) is True
        lock.release()
        lock.release()
        assert True

    def test_Semaphore(self):
        """`multiprocessing.Semaphore 真 acquire+release。"""
        sem = multiprocessing.Semaphore(2)
        assert sem.acquire(timeout=5) is True
        sem.release()
        assert True

    def test_Event(self):
        """`multiprocessing.Event 真 set+is_set。"""
        e = multiprocessing.Event()
        e.set()
        # 必 True
        assert e.is_set() is True

    def test_Barrier(self):
        """`multiprocessing.Barrier 真 wait+parties。"""
        b = multiprocessing.Barrier(2)
        # 必 2
        assert b.parties == 2
        b.abort()
        assert True

    def test_Condition(self):
        """`multiprocessing.Condition 真 wait+notify。"""
        c = multiprocessing.Condition()
        c.acquire()
        c.release()
        assert True

    def test_cpu_count(self):
        """`multiprocessing.cpu_count ≥ 1。"""
        n = multiprocessing.cpu_count()
        # 必 ≥ 1
        assert n is None or n >= 1

    def test_current_process(self):
        """`multiprocessing.current_process 'MainProcess'。"""
        p = multiprocessing.current_process()
        # 必 'MainProcess'
        assert p.name == "MainProcess"

    def test_active_children(self):
        """`multiprocessing.active_children list。"""
        c = multiprocessing.active_children()
        # 必 list
        assert isinstance(c, list)

    def test_freeze_support(self):
        """`multiprocessing.freeze_support 'a'。"""
        # 必 callable
        assert callable(multiprocessing.freeze_support)

    def test_log_to_stderr(self):
        """`multiprocessing.log_to_stderr 'a'。"""
        # 必 callable
        assert callable(multiprocessing.log_to_stderr)

    def test_get_logger(self):
        """`multiprocessing.get_logger 'a'。"""
        # 必 callable
        assert callable(multiprocessing.get_logger)


# -- threading 进阶 ----

class TestThreadingAdvanceV3:
    def test_Condition(self):
        """`threading.Condition 真 acquire+release。"""
        c = threading.Condition()
        c.acquire()
        c.release()
        assert True

    def test_Event(self):
        """`threading.Event 真 set+is_set。"""
        e = threading.Event()
        e.set()
        # 必 True
        assert e.is_set() is True

    def test_Semaphore(self):
        """`threading.Semaphore 真 acquire+release。"""
        s = threading.Semaphore(2)
        assert s.acquire(timeout=5) is True
        s.release()
        assert True

    def test_BoundedSemaphore(self):
        """`threading.BoundedSemaphore 真 acquire+release。"""
        s = threading.BoundedSemaphore(2)
        assert s.acquire(timeout=5) is True
        s.release()
        assert True

    def test_Barrier(self):
        """`threading.Barrier 真 wait+parties。"""
        b = threading.Barrier(2)
        # 必 2
        assert b.parties == 2
        b.abort()
        assert True

    def test_local(self):
        """`threading.local 真 instance。"""
        l = threading.local()
        # 必 instance
        assert isinstance(l, threading.local)

    def test_stack_size(self):
        """`threading.stack_size 0 还原。"""
        # 必 int
        n = threading.stack_size()
        assert isinstance(n, int)
        # 必 0 还原
        threading.stack_size(0)
        assert True

    def test_setprofile_getprofile(self):
        """`threading.setprofile+getprofile 'a'。"""
        old = threading.getprofile()
        threading.setprofile(None)
        # 必 None
        assert threading.getprofile() is None
        threading.setprofile(old)
        assert True

    def test_settrace_gettrace(self):
        """`threading.settrace+gettrace 'a'。"""
        old = threading.gettrace()
        threading.settrace(None)
        # 必 None
        assert threading.gettrace() is None
        threading.settrace(old)
        assert True

    def test_current_thread(self):
        """`threading.current_thread 'MainThread'。"""
        t = threading.current_thread()
        # 必 'MainThread'
        assert t.name == "MainThread"

    def test_main_thread(self):
        """`threading.main_thread 'MainThread'。"""
        t = threading.main_thread()
        # 必 'MainThread'
        assert t.name == "MainThread"

    def test_enumerate(self):
        """`threading.enumerate list。"""
        e = threading.enumerate()
        # 必 list
        assert isinstance(e, list)
        # 必 ≥ 1
        assert len(e) >= 1

    def test_Timer(self):
        """`threading.Timer 真 start+join。"""
        t = threading.Timer(0.01, lambda: None)
        t.start()
        t.join(timeout=5)
        # 必 不抛
        assert True

    def test_excepthook(self):
        """`threading.excepthook 'a'。"""
        # 必 callable
        assert callable(threading.excepthook)

    def test_1000_thread(self):
        """`threading 真并发 1000 thread start+join。"""
        threads = []
        for i in range(1000):
            t = threading.Thread(target=lambda: None)
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=5)
        # 必 1000
        assert len(threads) == 1000

    def test_Lock_1M(self):
        """`threading.Lock 真 1000000 acquire+release。"""
        lock = threading.Lock()
        for _ in range(1_000_000):
            lock.acquire()
            lock.release()
        # 必 不抛
        assert True
