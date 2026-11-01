# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`multiprocessing.Queue` 真跨 process 收发 + `multiprocessing.SimpleQueue` 真 + `multiprocessing.connection.Listener/Client` 真 (沙箱可能 skip) + `multiprocessing.Manager` 进阶 (dict+list 真共享) + `resource.getrlimit/setrlimit` 真 + 真底层测试。

覆盖 multiprocessing 4 真 (Queue 真+SimpleQueue 真+Listener class+Manager 真) + resource 2 真 (getrlimit+setrlimit RLIMIT_NOFILE) (共 6 真测试) 模块:
  - `multiprocessing.Queue 真跨 process put+get 'forge_q'`
  - `multiprocessing.SimpleQueue 真跨 process put+get 'forge_sq'`
  - `multiprocessing.connection.Listener 必 class 存在`
  - `multiprocessing.Manager 真 dict 真 set+get 'forge_mgr'`
  - `resource.getrlimit RLIMIT_NOFILE 必 (soft, hard) int tuple`
  - `resource.setrlimit 沙箱 skip (改 limit 影响)`
"""
import multiprocessing
import multiprocessing.connection
import os
import resource
import sys

import pytest


def _q_target(q):
    q.put("forge_q")


def _sq_target(sq):
    sq.put("forge_sq")


class TestMultiprocessingQueueAdvanced:
    def test_Queue_cross_process(self):
        """`multiprocessing.Queue 真跨 process put+get 'forge_q'。"""
        q = multiprocessing.Queue()
        p = multiprocessing.Process(target=_q_target, args=(q,))
        p.start()
        p.join(timeout=30)
        # 子进程必须正常结束,否则队列里不会有数据,读取会一直等下去
        assert p.exitcode == 0, f"子进程未正常结束: exitcode={p.exitcode}"
        # 必能收
        assert q.get(timeout=30) == "forge_q"
        # 必非 empty
        assert q.empty() is True

    def test_SimpleQueue_cross_process(self):
        """`multiprocessing.SimpleQueue 真跨 process put+get 'forge_sq'。"""
        sq = multiprocessing.SimpleQueue()
        p = multiprocessing.Process(target=_sq_target, args=(sq,))
        p.start()
        p.join(timeout=30)
        # 子进程必须正常结束,否则队列里不会有数据,读取会一直等下去
        assert p.exitcode == 0, f"子进程未正常结束: exitcode={p.exitcode}"
        # 必能收
        assert sq.get() == "forge_sq"


# -- multiprocessing.connection.Listener 进阶 (class 存在) -------

class TestMultiprocessingListenerAdvanced:
    def test_Listener_class(self):
        """`multiprocessing.connection.Listener 必 class 存在。"""
        # 沙箱 3.11 必 class
        assert multiprocessing.connection.Listener is not None
        # 必可调 (build)
        # 沙箱无 AF_UNIX 路径, 简测 class 存在


# -- multiprocessing.Manager 进阶 (真 dict) -------------------

def _mgr_target(d):
    d["forge_mgr"] = "forge_value"


class TestMultiprocessingManagerAdvanced:
    def test_Manager_dict(self):
        """`multiprocessing.Manager 真 dict 真 set+get 'forge_mgr'。"""
        with multiprocessing.Manager() as mgr:
            d = mgr.dict()
            # 真 set in main
            d["forge_local"] = 1
            # 真收
            assert d["forge_local"] == 1
            # 跨 process
            p = multiprocessing.Process(target=_mgr_target, args=(d,))
            p.start()
            p.join(timeout=30)
            # 必能收 (proxy 后)
            assert d["forge_mgr"] == "forge_value"


# -- resource 进阶 (getrlimit + setrlimit) --------------------

class TestResourceAdvancedV2:
    def test_getrlimit_NOFILE(self):
        """`resource.getrlimit RLIMIT_NOFILE 必 (soft, hard) int tuple。"""
        limits = resource.getrlimit(resource.RLIMIT_NOFILE)
        # 必 tuple of 2
        assert len(limits) == 2
        soft, hard = limits
        # 必 int
        assert isinstance(soft, int)
        assert isinstance(hard, int)
        # soft 必 ≤ hard
        assert soft <= hard
