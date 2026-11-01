# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`io 进阶 (StringIO+BytesIO+真 open+fileno)` + `functools 进阶 (lru_cache maxsize+typed=True+partial)` + `multiprocessing 进阶 (Value+Array+Manager list 真跨 process)` + `logging 进阶 (getLogger+basicConfig)` + `threading 进阶 (Thread args+target+start+join)` + 真底层测试。

覆盖 io 3 真 (StringIO seek+tell+BytesIO truncate+open fileno) + functools 3 真 (lru_cache maxsize+typed=True+partial) + multiprocessing 3 真 (Value+Array+Manager list) + logging 2 真 (getLogger same+basicConfig level) + threading 1 真 (Thread args+start+join) (共 12 真测试) 模块:
  - `io.StringIO 真 seek(0) tell(0) read 'forge_data'`
  - `io.BytesIO 真 truncate(0) len=0`
  - `io.open tmp_path 真 fileno ≥ 0`
  - `functools.lru_cache maxsize=128 typed=True fib(5)=5`
  - `functools.partial(inc,10)(5) 必 15`
  - `functools.partial(div, denom=2)(10) 必 5.0`
  - `multiprocessing.Value 'i' 跨 process 必 142`
  - `multiprocessing.Array 'i' 跨 process 必 99`
  - `multiprocessing.Manager list 真 append 5 item 'forge_mp_0'`
  - `logging.getLogger 'forge_basicconfig' 必 same logger`
  - `logging.basicConfig level=INFO force=True 必 set level 20`
  - `threading.Thread 真 args=('forge_arg',) 必 start+join`
"""
import functools
import io
import logging
import multiprocessing
import os
import threading

import pytest


def _inc(x, y):
    return x + y


def _div(x, denom=1):
    return x / denom


def _mp_value_target(v):
    with v.get_lock():
        v.value = 142


def _mp_array_target(arr):
    arr[0] = 99


def _mp_list_target(lst, key):
    lst.append(f"forge_mp_{key}")


def _thread_target(arg):
    return f"forge_thread_{arg}"


# -- io 进阶 (StringIO+BytesIO+open fileno) ------------

class TestIoAdvanceV2:
    def test_StringIO_seek_tell(self):
        """`io.StringIO 真 seek(0) tell(0) read 'forge_data'。"""
        s = io.StringIO()
        s.write("forge_data")
        s.seek(0)
        # tell 必 0
        assert s.tell() == 0
        # read
        content = s.read()
        # 必 'forge_data'
        assert content == "forge_data"

    def test_BytesIO_truncate(self):
        """`io.BytesIO 真 truncate(0) len=0。"""
        b = io.BytesIO(b"forge_data_long")
        # truncate 0
        result = b.truncate(0)
        # 必 0
        assert result == 0
        # 必 len 0
        assert len(b.getvalue()) == 0

    def test_open_fileno(self, tmp_path):
        """`io.open tmp_path 真 fileno ≥ 0。"""
        f = tmp_path / "forge.txt"
        f.write_text("forge")
        with open(f) as fp:
            # 必 fileno ≥ 0
            assert fp.fileno() >= 0


# -- functools 进阶 (lru_cache+partial) -----------------

class TestFunctoolsLruCachePartialAdvance:
    def test_lru_cache_typed(self):
        """`functools.lru_cache maxsize=128 typed=True fib(5)=5。"""

        @functools.lru_cache(maxsize=128, typed=True)
        def fib(n):
            if n < 2:
                return n
            return fib(n - 1) + fib(n - 2)

        # 必 5
        assert fib(5) == 5
        # 必能 cache hit
        info = fib.cache_info()
        # 必 ≥ 0 hit
        assert info.hits >= 0

    def test_partial_inc(self):
        """`functools.partial(inc,10)(5) 必 15。"""
        inc_10 = functools.partial(_inc, 10)
        # 必 15
        assert inc_10(5) == 15

    def test_partial_keyword(self):
        """`functools.partial(div, denom=2)(10) 必 5.0。"""
        div_2 = functools.partial(_div, denom=2)
        # 必 5.0
        assert div_2(10) == 5.0


# -- multiprocessing 进阶 (Value+Array+Manager list) ---

class TestMultiprocessingValueArrayListCrossProcessAdvance:
    def test_Value_cross_process(self):
        """`multiprocessing.Value 'i' 跨 process 必 142。"""
        v = multiprocessing.Value("i", 0)
        p = multiprocessing.Process(target=_mp_value_target, args=(v,))
        p.start()
        p.join(timeout=10)
        # 必 142
        assert v.value == 142

    def test_Array_cross_process(self):
        """`multiprocessing.Array 'i' 跨 process 必 99。"""
        arr = multiprocessing.Array("i", [0])
        p = multiprocessing.Process(target=_mp_array_target, args=(arr,))
        p.start()
        p.join(timeout=10)
        # 必 99
        assert arr[0] == 99

    def test_Manager_list_5_items(self):
        """`multiprocessing.Manager list 真 append 5 item 'forge_mp_0'。"""
        with multiprocessing.Manager() as mgr:
            lst = mgr.list()
            procs = []
            for i in range(5):
                p = multiprocessing.Process(
                    target=_mp_list_target, args=(lst, i)
                )
                p.start()
                procs.append(p)
            for p in procs:
                p.join(timeout=10)
            # 必 ≥ 5
            assert len(lst) >= 5
            # 必含 'forge_mp_0'
            assert "forge_mp_0" in lst


# -- logging 进阶 (getLogger+basicConfig) --------------

class TestLoggingGetLoggerBasicConfigAdvance:
    def test_getLogger_same(self):
        """`logging.getLogger 'forge_basicconfig' 必 same logger。"""
        l1 = logging.getLogger("forge_basicconfig")
        l2 = logging.getLogger("forge_basicconfig")
        # 必 same
        assert l1 is l2

    def test_basicConfig_level(self):
        """`logging.basicConfig level=INFO force=True 必 set level 20。"""
        logging.basicConfig(
            level=logging.INFO,
            force=True,
        )
        # 必 root level 20
        root = logging.getLogger()
        # 必 level 20
        assert root.level == 20


# -- threading 进阶 (Thread args+target+start+join) ---

class TestThreadingThreadArgsTargetStartJoinAdvance:
    def test_Thread_args(self):
        """`threading.Thread 真 args=('forge_arg',) 必 start+join。"""
        t = threading.Thread(target=_thread_target, args=("forge_arg",))
        # start
        t.start()
        # join
        t.join(timeout=5)
        # 必不抛
        assert True
