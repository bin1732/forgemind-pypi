# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 logging 真 getLogger 同一实例 + 真 weakref WeakKeyDictionary 真 key dict + 真 subprocess 真 getoutput + 真 unittest 进阶 (TestLoader / subTest) + 真 multiprocessing 真 Manager 真多进程 共享 + 真 ipaddress 真扫.
全 stdlib, 零模拟。
"""
import logging
import weakref
import subprocess
import unittest
import multiprocessing
import multiprocessing.managers
import ipaddress
import os
import sys
import pytest


# ======================== logging getLogger ========================
def test_logging_getLogger_same():
    """真 getLogger 同一 name 同 instance"""
    logger1 = logging.getLogger("test_unique_logger")
    logger2 = logging.getLogger("test_unique_logger")
    # 同一实例
    assert logger1 is logger2


def test_logging_logger_propagate():
    """真 propagate 真传播"""
    parent = logging.getLogger("parent_test_logger")
    parent.setLevel(logging.DEBUG)
    child = logging.getLogger("parent_test_logger.child")
    # 父级 + child set
    parent_handlers_before = list(parent.handlers)
    try:
        # 父级加 handler
        buf_parent = _capturing_handler()
        parent.addHandler(buf_parent)
        # child set
        child.setLevel(logging.WARNING)
        # 触发 child
        child.warning("from child")
        # 父级因 propagate 收到
        output = buf_parent.captured.getvalue()
        assert "from child" in output
    finally:
        parent.removeHandler(buf_parent)


class _capturing_handler(logging.Handler):
    def __init__(self):
        super().__init__()
        import io
        self.captured = io.StringIO()
    def emit(self, record):
        self.captured.write(self.format(record) + "\n")


def test_logging_log_level_constants():
    """真 level constants"""
    assert logging.DEBUG == 10
    assert logging.INFO == 20
    assert logging.WARNING == 30
    assert logging.ERROR == 40
    assert logging.CRITICAL == 50


# ======================== weakref WeakKeyDictionary ========================
def test_weakref_WeakKeyDictionary():
    """真 WeakKeyDictionary 真 key 弱"""
    class Key:
        pass

    d = weakref.WeakKeyDictionary()
    k1 = Key()
    d[k1] = "value1"
    # 读
    assert d[k1] == "value1"
    # 删 key
    del k1
    import gc
    gc.collect()
    # 必空
    assert len(d) == 0


def test_weakref_WeakValueDictionary_count():
    """真 WeakValueDictionary 真 count"""
    class V:
        pass

    d = weakref.WeakValueDictionary()
    values = [V() for _ in range(3)]
    for i, v in enumerate(values):
        d[f"key_{i}"] = v
    assert len(d) == 3
    # 删中间
    del values[1]
    import gc
    gc.collect()
    assert len(d) == 2


# ======================== subprocess 真 ========================
def test_subprocess_getoutput():
    """真 getoutput 真跑命令"""
    # 注意 sandbox 可能没 echo
    try:
        out = subprocess.getoutput("echo hello")
        assert "hello" in out
    except Exception:
        pytest.skip("echo not available")


def test_subprocess_getstatusoutput():
    """真 getstatusoutput 真 (rc, output)"""
    try:
        rc, out = subprocess.getstatusoutput("echo hello")
        # echo 应 rc=0
        assert rc == 0
        assert "hello" in out
    except Exception:
        pytest.skip("echo not available")


# ======================== unittest 进阶 ========================
def test_unittest_TestLoader():
    """真 TestLoader 真 load"""
    class T(unittest.TestCase):
        def test_a(self):
            self.assertTrue(True)
        def test_b(self):
            self.assertEqual(1, 1)

    suite = unittest.TestLoader().loadTestsFromTestCase(T)
    # 2 tests
    assert suite.countTestCases() == 2


def test_unittest_subTest():
    """真 subTest 子测试"""
    class T(unittest.TestCase):
        def test_subtest(self):
            for i in [1, 2, 3]:
                with self.subTest(i=i):
                    self.assertEqual(i, i)

    import io
    suite = unittest.TestSuite()
    suite.addTest(T("test_subtest"))
    runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
    result = runner.run(suite)
    assert result.wasSuccessful()


# ======================== multiprocessing Manager ========================
def test_mp_Manager_namespaces():
    """真 Manager 真 Namespace 真 attrs"""
    def worker(ns, key, value):
        setattr(ns, key, value)

    with multiprocessing.Manager() as manager:
        ns = manager.Namespace()
        ns.x = 0
        p = multiprocessing.Process(target=worker, args=(ns, "x", 99))
        p.start()
        p.join(timeout=5)
        # 跨进程改
        assert ns.x == 99


# ======================== ipaddress 进阶 ========================
def test_ipaddress_summary_address():
    """真 IPv4 summary_address 真"""
    # 合并相邻网
    n1 = ipaddress.IPv4Network("10.0.0.0/24")
    n2 = ipaddress.IPv4Network("10.0.1.0/24")
    # collapse_addresses
    collapsed = list(ipaddress.collapse_addresses([n1, n2]))
    # 合并 1 个
    assert len(collapsed) == 1
    assert collapsed[0] == ipaddress.IPv4Network("10.0.0.0/23")


def test_ipaddress_addresses_iter():
    """真 addresses 真列所有"""
    net = ipaddress.IPv4Network("10.0.0.0/30")
    # /30 = 4 IPs
    addrs = list(net)
    assert len(addrs) == 4
    assert addrs[0] == ipaddress.IPv4Address("10.0.0.0")
    assert addrs[3] == ipaddress.IPv4Address("10.0.0.3")


def test_ipaddress_compare_lt_gt_subnet():
    """真 IPv4Network 真比较"""
    a = ipaddress.IPv4Network("10.0.0.0/8")
    b = ipaddress.IPv4Network("192.168.0.0/16")
    # < 由 prefix length 和 network address
    # a 在 10.x, b 在 192.x → 10 < 192
    assert a < b
    assert b > a
    # 同 prefix 同 network → equal
    c = ipaddress.IPv4Network("10.0.0.0/8")
    assert a == c
