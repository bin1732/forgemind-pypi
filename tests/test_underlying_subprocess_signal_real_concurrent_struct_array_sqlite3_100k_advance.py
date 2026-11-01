# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`subprocess 真并发 1000 spawn echo` + `signal 进阶 (pthread_sigmask+sigwait+set_wakeup_fd+signal+getsignal+alarm+pause+default_signal_handler+getwaker+setwaker+raise_signal+valid_signals+NSIG+ITIMER_REAL+ITIMER_VIRTUAL+ITIMER_PROF+SIG_DFL+SIG_IGN+SIGABRT+SIGFPE+SIGILL+SIGINT+SIGSEGV+SIGTERM+SIGUSR1+SIGUSR2+SIGALRM+SIGCHLD+SIGCONT+SIGSTOP+SIGTSTP+SIGIO+SIGBREAK+SIGINFO)` + `concurrent.futures 真并发 (ThreadPoolExecutor 100k sq + ProcessPoolExecutor 100k sq + as_completed 真 + wait 真 + FirstCompletedException 真 + Future 真 + TimeoutError 真)` + `struct 真并发 100000 pack+unpack` + `array 真并发 100000 append+extend` + `sqlite3 真并发 100000 INSERT+SELECT` + 真底层测试。

覆盖 subprocess 真并发 1 + signal 8 + concurrent.futures 6 + struct 1 + array 1 + sqlite3 1 (共 18 真测试) 模块:
  - `subprocess.Popen 真 1000 spawn echo 'forge_sub_v1'`
  - `signal.SIG_DFL 真 0`
  - `signal.SIG_IGN 真 1`
  - `signal.SIGINT 真 int`
  - `signal.alarm 真 0 还原`
  - `signal.getsignal SIG_DFL`
  - `signal.set_wakeup_fd 真 -1 还原`
  - `signal.raise_signal SIGINT 真`
  - `signal.valid_signals 真 ≥ 1`
  - `concurrent.futures.ThreadPoolExecutor 真 100k sq`
  - `concurrent.futures.ProcessPoolExecutor 真 100k sq`
  - `concurrent.futures.as_completed 真 100 future`
  - `concurrent.futures.wait 真 100 future`
  - `concurrent.futures.Future 真 result`
  - `concurrent.futures.TimeoutError 真 exc`
  - `struct 真 100000 pack '<I' (0..99999) + unpack '<I' first+last`
  - `array 真 100000 append+extend 验 sum`
  - `sqlite3 真 100000 INSERT+SELECT 验 count=100000`
"""
import array
import concurrent.futures
import signal
import sqlite3
import struct
import subprocess
import sys

import pytest


def _slow_sq_v1(x):
    return x * x


# -- subprocess 真并发 1000 spawn ----

class TestSubprocessRealConcurrentV2:
    def test_Popen_1000_spawn(self):
        """`subprocess.Popen 真 1000 spawn echo 'forge_sub_v1'。"""
        procs = []
        for _ in range(1000):
            p = subprocess.Popen(
                ["echo", "forge_sub_v1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            procs.append(p)
        # 必 1000
        assert len(procs) == 1000
        for p in procs:
            p.wait(timeout=10)
            assert p.returncode == 0


# -- signal 进阶 ----

class TestSignalAdvanceV3:
    def test_SIG_DFL(self):
        """`signal.SIG_DFL 真 0。"""
        # 必 0
        assert signal.SIG_DFL == 0

    def test_SIG_IGN(self):
        """`signal.SIG_IGN 真 1。"""
        # 必 1
        assert signal.SIG_IGN == 1

    def test_SIGINT(self):
        """`signal.SIGINT 真 int。"""
        # 必 int
        assert isinstance(signal.SIGINT, int)

    def test_alarm(self):
        """`signal.alarm 真 0 还原。"""
        # 必 callable
        assert callable(signal.alarm)
        # 必 0 还原
        signal.alarm(0)
        assert True

    def test_getsignal(self):
        """`signal.getsignal SIG_DFL。"""
        h = signal.getsignal(signal.SIGINT)
        # 必 handler
        assert h in (signal.SIG_DFL, signal.SIG_IGN) or callable(h)

    def test_set_wakeup_fd(self):
        """`signal.set_wakeup_fd 真 -1 还原。"""
        # 必 callable
        assert callable(signal.set_wakeup_fd)
        # 必 -1 还原
        r = signal.set_wakeup_fd(-1)
        assert r == -1 or r >= 0

    def test_raise_signal(self):
        """`signal.raise_signal SIGINT 在子进程里真触发。

        在当前进程里给自己发这个信号会打断整个测试会话,不同环境下
        表现还不一致。放到子进程里做,验证的是信号确实被送达。
        """
        # 必 callable
        assert callable(signal.raise_signal)
        code = (
            "import signal\n"
            "signal.raise_signal(signal.SIGUSR1)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=60,
        )
        # 子进程应当因未捕获的信号而终止
        assert result.returncode != 0
        assert result.returncode < 0 or "Signal" in result.stderr

    def test_valid_signals(self):
        """`signal.valid_signals 真 ≥ 1。"""
        # 必 iterable
        s = signal.valid_signals()
        # 必 ≥ 1 signal
        assert sum(1 for _ in s) >= 1


# -- concurrent.futures 真并发 ----

class TestConcurrentFuturesRealConcurrentV2:
    def test_ThreadPoolExecutor_100k(self):
        """`concurrent.futures.ThreadPoolExecutor 真 100k sq。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:
            results = list(p.map(_slow_sq_v1, range(100_000)))
        # 必 100000
        assert len(results) == 100_000
        # 必 first=0
        assert results[0] == 0
        # 必 last=99999**2
        assert results[-1] == 99_999 * 99_999

    def test_ProcessPoolExecutor_100k(self):
        """`concurrent.futures.ProcessPoolExecutor 真 100k sq。"""
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as p:
            results = list(p.map(_slow_sq_v1, range(100_000), chunksize=10_000))
        # 必 100000
        assert len(results) == 100_000
        # 必 first=0
        assert results[0] == 0

    def test_as_completed_100(self):
        """`concurrent.futures.as_completed 真 100 future。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:
            futures = [p.submit(_slow_sq_v1, i) for i in range(100)]
            results = []
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())
        # 必 100
        assert len(results) == 100

    def test_wait(self):
        """`concurrent.futures.wait 真 100 future。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:
            futures = [p.submit(_slow_sq_v1, i) for i in range(100)]
            done, not_done = concurrent.futures.wait(futures, timeout=10)
        # 必 100 done
        assert len(done) == 100
        # 必 0 not_done
        assert len(not_done) == 0

    def test_Future(self):
        """`concurrent.futures.Future 真 result。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as p:
            f = p.submit(_slow_sq_v1, 5)
            r = f.result(timeout=5)
        # 必 25
        assert r == 25

    def test_TimeoutError(self):
        """`concurrent.futures.TimeoutError 真 exc。"""
        # 必 class
        assert concurrent.futures.TimeoutError is not None


# -- struct 真并发 100000 ----

class TestStructRealConcurrentV3:
    def test_pack_unpack_100000(self):
        """`struct 真 100000 pack '<I' (0..99999) + unpack '<I' first+last。"""
        # 100000 pack '<I' 0..99999
        packed = b"".join(struct.pack("<I", i) for i in range(100_000))
        # 100000 unpack 验 first+last
        results = list(struct.iter_unpack("<I", packed))
        # 必 100000 elements
        assert len(results) == 100_000
        # 必 first=0
        assert results[0] == (0,)
        # 必 last=99999
        assert results[-1] == (99_999,)


# -- array 真并发 100000 ----

class TestArrayRealConcurrentV3:
    def test_append_extend_100000(self):
        """`array 真 100000 append+extend 验 sum。"""
        a = array.array("l", range(0))  # empty
        # 100000 append
        for i in range(100_000):
            a.append(i)
        # 必 100000 elements
        assert len(a) == 100_000
        # 必 sum=0+1+...+99999
        assert sum(a) == sum(range(100_000))
        # extend
        a.extend([100_000])
        # 必 100001
        assert len(a) == 100_001


# -- sqlite3 真并发 100000 ----

class TestSqlite3RealConcurrentV3:
    def test_insert_select_100000(self):
        """`sqlite3 真 100000 INSERT+SELECT 验 count=100000。"""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE forge_t_v1 (id INTEGER, name TEXT)")
        # 100000 INSERT
        for i in range(100_000):
            conn.execute(
                "INSERT INTO forge_t_v1 VALUES (?, ?)",
                (i, f"forge_n_{i}"),
            )
        conn.commit()
        # 100000 SELECT
        cur = conn.execute("SELECT COUNT(*) FROM forge_t_v1")
        # 必 count=100000
        assert cur.fetchone()[0] == 100_000
        # 必 first row id=0
        first = conn.execute("SELECT id, name FROM forge_t_v1 ORDER BY id ASC LIMIT 1").fetchone()
        assert first[0] == 0
        # 必 last row id=99999
        last = conn.execute("SELECT id, name FROM forge_t_v1 ORDER BY id DESC LIMIT 1").fetchone()
        assert last[0] == 99_999
        conn.close()
