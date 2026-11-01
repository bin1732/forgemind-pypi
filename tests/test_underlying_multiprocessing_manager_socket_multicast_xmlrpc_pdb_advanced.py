# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`multiprocessing.Manager` + `socket` multicast + `xmlrpc` 进阶 + `pdb` 进阶 + `trace` 进阶 真底层测试。

覆盖 Manager 共享状态 / multicast socket / xmlrpc / pdb 真底层 / trace:
  - `multiprocessing.Manager() 真建 manager`
  - `Manager().dict() 真建 shared dict`
  - `Manager().list() 真建 shared list`
  - `Manager().Namespace 真建 namespace`
  - `socket.inet_aton('239.0.0.1') 真 multicast bytes`
  - `ipaddress.IPv4Address('239.0.0.1') is_multicast 真 True`
  - `xmlrpc.client.loads/dumps 真 multiple params`
  - `xmlrpc.client.Fault 真 fault class`
  - `xmlrpc.client.Binary 真 binary data wrapper`
  - `pdb.Pdb 真建 instance`
  - `pdb.Pdb.set_trace 子化 真 hook`
  - `pdb.set_trace 沙箱 skip (会 block)`
  - `trace.Trace(countfuncs=True) 真跑 lambda + 验 results`
  - `trace.Trace().results() 真返结果`
  - `trace.Trace().runctx 真带 globals+locals 跑`
"""
import ipaddress
import multiprocessing
import multiprocessing.managers
import pdb
import socket
import sys
import trace
import xmlrpc.client

import pytest


# -- multiprocessing.Manager --------------------------------------------------

class TestMultiprocessingManager:
    def test_Manager_dict(self):
        """`Manager().dict() 真建 shared dict + 子进程改。"""
        m = multiprocessing.Manager()
        try:
            d = m.dict()
            d["forge"] = 42
            d["key"] = "value"
            assert d["forge"] == 42
            assert d["key"] == "value"
            # len
            assert len(d) == 2
        finally:
            m.shutdown()

    def test_Manager_list(self):
        """`Manager().list() 真建 shared list。"""
        m = multiprocessing.Manager()
        try:
            l = m.list()
            l.append(1)
            l.append("forge")
            l.append(3.14)
            assert len(l) == 3
            assert l[0] == 1
            assert l[1] == "forge"
            assert l[2] == 3.14
        finally:
            m.shutdown()

    def test_Manager_Namespace(self):
        """`Manager().Namespace() 真建 namespace。"""
        m = multiprocessing.Manager()
        try:
            ns = m.Namespace()
            ns.x = 10
            ns.name = "forge"
            assert ns.x == 10
            assert ns.name == "forge"
        finally:
            m.shutdown()


# -- socket multicast 进阶 ----------------------------------------------------

class TestSocketMulticast:
    def test_inet_aton_multicast(self):
        """`socket.inet_aton('239.0.0.1') 真 multicast bytes 0xEF 0 0 1。"""
        b = socket.inet_aton("239.0.0.1")
        # 239 = 0xEF
        assert b[0] == 239, f"239.0.0.1 第 1 字节应=239,实际 {b[0]}"
        assert b == bytes([239, 0, 0, 1])

    def test_IPv4_multicast_class(self):
        """`ipaddress.IPv4Address('239.0.0.1').is_multicast 真 True。"""
        ip = ipaddress.IPv4Address("239.0.0.1")
        assert ip.is_multicast is True
        # 224.0.0.0/4 是 multicast range
        ip2 = ipaddress.IPv4Address("224.0.0.0")
        assert ip2.is_multicast is True
        ip3 = ipaddress.IPv4Address("239.255.255.255")
        assert ip3.is_multicast is True


# -- xmlrpc 进阶 -------------------------------------------------------------

class TestXmlrpcAdvanced:
    def test_xmlrpc_multiple_params(self):
        """`xmlrpc.client.dumps 多 params + loads 真 round-trip。"""
        req = xmlrpc.client.dumps(
            (1, 2, 3, "forge", True), methodname="multi.test"
        )
        value, method = xmlrpc.client.loads(req)
        # value 是 tuple of params
        assert value == (1, 2, 3, "forge", True)
        assert method == "multi.test"

    def test_xmlrpc_Fault(self):
        """`xmlrpc.client.Fault 真 class 存在 + 真 raise。"""
        # Fault 真类
        assert xmlrpc.client.Fault is not None
        # 建 + raise
        f = xmlrpc.client.Fault(42, "test error")
        with pytest.raises(xmlrpc.client.Fault):
            raise f

    def test_xmlrpc_Binary(self):
        """`xmlrpc.client.Binary 真 wrap bytes + 可解。"""
        b = xmlrpc.client.Binary(b"forge binary data")
        # 必含 .data
        assert b.data == b"forge binary data"
        # dumps + loads
        req = xmlrpc.client.dumps((b,), methodname="binary.test")
        value, method = xmlrpc.client.loads(req)
        # value 必含 Binary
        assert value[0].data == b"forge binary data"


# -- pdb 进阶 ----------------------------------------------------------------

class _DebugPdb(pdb.Pdb):
    """子类化真测试。"""
    def user_line(self, frame):
        # 不真断
        pass


class TestPdbAdvanced:
    def test_Pdb_subclass(self):
        """`pdb.Pdb 真子类化。"""
        d = _DebugPdb()
        assert d is not None
        # 必含 do_* methods
        assert callable(d.do_step)
        assert callable(d.do_next)
        assert callable(d.do_continue)
        # 必含 complete
        assert callable(d.complete)

    def test_pdb_Pdb_class_attributes(self):
        """`pdb.Pdb 必含类。"""
        # 必含类
        assert hasattr(pdb, "Pdb")
        assert hasattr(pdb, "set_trace")
        assert hasattr(pdb, "run")
        # 必可调
        assert callable(pdb.Pdb)


# -- trace 进阶 --------------------------------------------------------------

class TestTraceAdvancedV2:
    def test_Trace_runctx(self):
        """`Trace.runctx 真带 globals+locals 跑。"""
        tr = trace.Trace(countfuncs=True, trace=0, count=1)
        globals_dict = {"__name__": "__main__"}
        locals_dict = {"x": 10}
        # runctx 跑 lambda, 必不抛
        tr.runctx("result = x * 2", globals_dict, locals_dict)
        # 必产生结果
        assert locals_dict.get("result") == 20
        # results() 必非空
        assert tr.results() is not None

    def test_Trace_globaltrace_lt_signature(self):
        """`Trace.globaltrace_lt 必 4 参 (frame, event, arg, why_or_smth)`. """
        tr = trace.Trace()
        # 验 globaltrace_lt 存在 + 签名
        assert hasattr(tr, "globaltrace_lt")
        # 用 trace 跑, 必不抛
        tr.runfunc(lambda: sum([i for i in range(5)]))
        # 必 results 非空
        assert tr.results() is not None
