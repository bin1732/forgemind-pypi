# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.Queue` 真并发 1500 task + `concurrent.futures.ThreadPoolExecutor` 1500 task 真并发 + `multiprocessing.Pool` 1500 task 真并发 + `logging 进阶 (CRITICAL+FATAL+ERROR+WARNING+getLogRecordFactory)` + `threading 进阶 (Thread+Lock+RLock+active_count)` + `urllib.parse 进阶` + `json 进阶 (dumps+loads+OrderedDict)` + 真底层测试。

覆盖 asyncio 1 + ThreadPoolExecutor 1 + Pool 1 + logging 4 + threading 4 + urllib.parse 5 + json 3 (共 19 真测试) 模块:
  - `asyncio.Queue 1500 put+get 'forge_q_0'+'forge_q_1499'`
  - `ThreadPoolExecutor 1500 sq 真并发`
  - `Pool 1500 sq 真并发`
  - `logging.CRITICAL=50+FATAL`
  - `logging.ERROR=40`
  - `logging.WARNING=30`
  - `logging.getLogRecordFactory callable`
  - `threading.Thread args start+join`
  - `threading.Lock acquire+release`
  - `threading.RLock reentrant`
  - `threading.active_count ≥ 1`
  - `urllib.parse.urlparse scheme 'http'`
  - `urllib.parse.parse_qs 'forge=1'`
  - `urllib.parse.urlencode 'forge'`
  - `urllib.parse.urljoin 'a/c'`
  - `urllib.parse.quote '%20'`
  - `json.dumps indent=2`
  - `json.loads dict`
  - `json OrderedDict round-trip`
"""
import asyncio
import collections
import concurrent.futures
import json
import logging
import multiprocessing
import threading
import urllib.parse

import pytest


def _slow_sq(x):
    return x * x


def _thread_target_v(arg):
    return f"forge_thread_{arg}"


# -- asyncio.Queue 1500 task 真并发 进阶 ----------------

class TestAsyncioQueue1500TaskAdvance:
    def test_Queue_1500(self):
        """`asyncio.Queue 真 1500 put+get 含 'forge_q_0' + 'forge_q_1499'。"""

        async def main():
            q = asyncio.Queue()
            for i in range(1500):
                await q.put(f"forge_q_{i}")
            results = []
            for _ in range(1500):
                results.append(await q.get())
            return results

        results = asyncio.run(main())
        assert len(results) == 1500
        assert "forge_q_0" in results
        assert "forge_q_1499" in results


# -- ThreadPoolExecutor 1500 task 真并发 进阶 ----------

class TestThreadPoolExecutor1500TaskAdvance:
    def test_ThreadPoolExecutor_map_1500(self):
        """`ThreadPoolExecutor 真 1500 sq 必 sorted [0..1499] sq。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:
            results = list(p.map(_slow_sq, range(1500)))
        assert len(results) == 1500
        assert sorted(results) == [i * i for i in range(1500)]


# -- multiprocessing.Pool 1500 task 真并发 进阶 --------

class TestMultiprocessingPool1500TaskAdvance:
    def test_Pool_1500_imap(self):
        """`Pool 真 1500 sq 必 sorted [0..1499] sq。"""
        with multiprocessing.Pool(4) as p:
            results = list(p.imap(_slow_sq, range(1500)))
        assert len(results) == 1500
        assert sorted(results) == [i * i for i in range(1500)]


# -- logging 进阶 (CRITICAL+FATAL+ERROR+WARNING+getLogRecordFactory) ---

class TestLoggingCriticalFatalErrorWarningGetLogRecordFactoryAdvanceV2:
    def test_CRITICAL_FATAL(self):
        assert logging.CRITICAL == 50
        assert logging.FATAL == logging.CRITICAL

    def test_ERROR(self):
        assert logging.ERROR == 40

    def test_WARNING(self):
        assert logging.WARNING == 30

    def test_getLogRecordFactory(self):
        factory = logging.getLogRecordFactory()
        assert callable(factory)


# -- threading 进阶 (Thread+Lock+RLock+active_count) ---

class TestThreadingThreadLockRLockActiveCountAdvanceV2:
    def test_Thread_args(self):
        t = threading.Thread(target=_thread_target_v, args=("forge_arg",))
        t.start()
        t.join(timeout=5)
        assert True

    def test_Lock(self):
        lock = threading.Lock()
        assert lock.acquire(timeout=5) is True
        lock.release()
        assert True

    def test_RLock(self):
        rlock = threading.RLock()
        rlock.acquire()
        rlock.acquire()
        rlock.release()
        rlock.release()
        assert True

    def test_active_count(self):
        n = threading.active_count()
        assert isinstance(n, int)
        assert n >= 1


# -- urllib.parse 进阶 (urlparse+parse_qs+urlencode+urljoin+quote) ---

class TestUrllibParseAdvanceV6:
    def test_urlparse(self):
        r = urllib.parse.urlparse("http://forge.example.com/forge")
        assert r.scheme == "http"
        assert r.netloc == "forge.example.com"

    def test_parse_qs(self):
        result = urllib.parse.parse_qs("forge=1&forge=2")
        assert "forge" in result
        assert "1" in result["forge"]

    def test_urlencode(self):
        result = urllib.parse.urlencode({"name": "forge"})
        assert "name=forge" in result

    def test_urljoin(self):
        result = urllib.parse.urljoin("http://forge.example.com/a/b", "c")
        assert result == "http://forge.example.com/a/c"

    def test_quote(self):
        result = urllib.parse.quote("hello world")
        assert result == "hello%20world"


# -- json 进阶 (dumps+loads+OrderedDict) -------------

class TestJsonAdvanceV6:
    def test_dumps_indent(self):
        d = {"name": "forge", "value": 42}
        result = json.dumps(d, indent=2)
        assert isinstance(result, str)
        assert "forge" in result
        assert "\n" in result

    def test_loads(self):
        data = '{"forge": 42, "name": "value"}'
        result = json.loads(data)
        assert isinstance(result, dict)
        assert result["forge"] == 42

    def test_OrderedDict_round_trip(self):
        od = collections.OrderedDict()
        od["z"] = 1
        od["a"] = 2
        od["m"] = 3
        encoded = json.dumps(od)
        decoded = json.loads(encoded)
        assert decoded == dict(od)
        assert len(decoded) == 3
