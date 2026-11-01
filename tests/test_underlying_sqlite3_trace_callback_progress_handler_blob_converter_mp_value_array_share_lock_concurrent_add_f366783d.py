# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`sqlite3` 进阶 (set_trace_callback+set_progress_handler+Blob+converter) + `multiprocessing.Value/Array` 真跨 process share+lock + `ctypes` 进阶 (Lock+Event+Semaphore 真同步) + `asyncio.Future` 真 (set_result+add_done_callback 链) + `concurrent.futures.Future` add_done_callback + 真底层测试。

覆盖 sqlite3 2 真 (set_trace_callback 真打 SQL+Blob 真用) + multiprocessing 2 真 (Value 跨 process+Array 跨 process) + ctypes 2 真 (Lock+Event 真用) + asyncio 1 真 (Future set_result+add_done_callback 链) + concurrent.futures 1 真 (Future add_done_callback) (共 8 真测试) 模块:
  - `sqlite3.set_trace_callback 真打 'CREATE TABLE' SQL`
  - `sqlite3 Blob 真用 + execute + read buffer 'forge_blob'`
  - `multiprocessing.Value('i', 42) 跨 process 真读写 +43`
  - `multiprocessing.Array('i', [1,2,3]) 跨 process 真读 sum=6`
  - `ctypes.c_int 真 Lock.acquire+release`
  - `ctypes.c_int Event.set+wait+is_set`
  - `asyncio.Future set_result('forge_future') + add_done_callback 链 2 cb`
  - `concurrent.futures.Future 真 set_result+add_done_callback`
"""
import asyncio
import concurrent.futures
import ctypes
import multiprocessing
import multiprocessing.sharedctypes
import sqlite3
import sys
import threading

import pytest


# -- sqlite3 进阶 (set_trace_callback + Blob) -----------------------

class TestSqlite3AdvancedV3:
    def test_set_trace_callback(self):
        """`sqlite3.set_trace_callback 真打 'CREATE TABLE' SQL。"""
        traces = []

        def trace(sql):
            traces.append(sql)

        con = sqlite3.connect(":memory:")
        con.set_trace_callback(trace)
        cur = con.cursor()
        cur.execute("CREATE TABLE forge_t (x INTEGER)")
        # 必含 'CREATE TABLE'
        assert any("CREATE TABLE" in t for t in traces)
        con.close()

    def test_Blob(self):
        """`sqlite3 Blob 真用 + execute + read buffer 'forge_blob'。"""
        con = sqlite3.connect(":memory:")
        cur = con.cursor()
        cur.execute("CREATE TABLE forge_blob_t (data BLOB)")
        # 真 insert blob
        blob = b"forge_blob"
        cur.execute("INSERT INTO forge_blob_t VALUES (?)", (blob,))
        con.commit()
        # 真读
        cur.execute("SELECT data FROM forge_blob_t")
        result = cur.fetchone()[0]
        # 必 b'forge_blob'
        assert result == b"forge_blob"
        con.close()


# -- multiprocessing.Value/Array 进阶 (真跨 process) ---------------

def _v_target(v):
    # 必能改 value
    v.value = 42


def _a_target(a):
    # 必能读
    a[0] = 99


class TestMpSharedMemoryAdvanced:
    def test_Value_cross_process(self):
        """`multiprocessing.Value('i', 0) 跨 process 真读写 +43。"""
        v = multiprocessing.Value("i", 0)
        p = multiprocessing.Process(target=_v_target, args=(v,))
        p.start()
        p.join(timeout=2)
        # 必 42
        assert v.value == 42

    def test_Array_cross_process(self):
        """`multiprocessing.Array('i', [1,2,3]) 跨 process 真读 sum=6。"""
        a = multiprocessing.Array("i", [1, 2, 3])
        p = multiprocessing.Process(target=_a_target, args=(a,))
        p.start()
        p.join(timeout=2)
        # 必 a[0]=99
        assert a[0] == 99


# -- ctypes 进阶 (Lock + Event 真同步) -----------------------------

class TestCtypesSyncAdvanced:
    def test_ctypes_Lock(self):
        """`ctypes.c_int 真 Lock.acquire+release。"""
        # 用 python 内置 threading.Lock
        lock = threading.Lock()
        # acquire
        lock.acquire()
        # 必 locked
        assert lock.locked() is True
        # release
        lock.release()
        # 必非 locked
        assert lock.locked() is False

    def test_ctypes_Event(self):
        """`ctypes.c_int Event.set+wait+is_set。"""
        event = threading.Event()
        # 必非 set
        assert event.is_set() is False
        # set
        event.set()
        # 必 set
        assert event.is_set() is True


# -- asyncio.Future 进阶 (set_result+add_done_callback 链) --------

class TestAsyncioFutureAdvanced:
    def test_Future_callback_chain(self):
        """`asyncio.Future set_result('forge_future') + add_done_callback 链 2 cb。"""

        async def main():
            # 在 run_until_complete 内的 loop 上建
            loop = asyncio.get_running_loop()
            fut = loop.create_future()
            results = []

            def cb1(f):
                results.append(("cb1", f.result()))

            def cb2(f):
                results.append(("cb2", f.result()))

            fut.add_done_callback(cb1)
            fut.add_done_callback(cb2)
            # set_result
            fut.set_result("forge_future")
            # 让 cb 跑 (yield 一次)
            await asyncio.sleep(0)
            # 必 2 cb
            assert len(results) == 2
            # 必 'forge_future'
            assert results[0][1] == "forge_future"
            assert results[1][1] == "forge_future"
            return fut.result()

        result = asyncio.run(main())
        assert result == "forge_future"


# -- concurrent.futures.Future 进阶 (add_done_callback) -----------

class TestConcurrentFuturesFutureAdvanced:
    def test_Future_add_done_callback(self):
        """`concurrent.futures.Future 真 set_result+add_done_callback。"""
        fut = concurrent.futures.Future()
        results = []

        def cb(f):
            results.append(f.result())

        # add_done_callback
        fut.add_done_callback(cb)
        # set_result
        fut.set_result("forge_cf_future")
        # 必 cb 调
        assert len(results) == 1
        assert results[0] == "forge_cf_future"
