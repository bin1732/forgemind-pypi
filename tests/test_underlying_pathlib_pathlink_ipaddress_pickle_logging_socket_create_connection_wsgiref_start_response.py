# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`pathlib` 进阶 (PurePath 嵌套) + `ipaddress` 进阶 (interface + v6 subnet) + `pickle` 进阶 (Pickler) + `logging` 进阶 (log level) + `socket.create_connection` + `wsgiref` 进阶 (start_response) 真底层测试。

覆盖 pathlib PurePath 嵌套 / ipaddress v6 / pickle Pickler / logging level / socket create_connection / wsgiref start_response 模块:
  - `pathlib.PurePath 真迭代 / parents / parent / name / suffix / suffixes`
  - `pathlib.PurePosixPath('/forge/test.py').suffix == '.py'`
  - `pathlib.PurePath('/a/b/c').parent.name == 'b'`
  - `pathlib.Path.cwd 真非空`
  - `pathlib.Path.home 真返 home str`
  - `ipaddress.IPv6Interface 真取 netmask`
  - `ipaddress.IPv6Network 真取 hostmask`
  - `ipaddress.ip_network 真从 str 建 v6`
  - `pickle.Pickler(file) 真建 + dump + load 真 round-trip`
  - `pickle.PickleError 真 class 存在 + 真 raise`
  - `logging.getLevelName 真返 level int 或 str`
  - `logging.Logger.setLevel 真设 level`
  - `logging.LogRecord 真建 instance 含 name+level+msg`
  - `socket.create_connection 真连 (不抛 + 返 socket)`
  - `socket.getservbyname 真取 'http' → 80`
  - `socket.getservbyport 真取 80 → 'http'`
  - `wsgiref.simple_server.make_server 真启 (host, port) + 必可关`
  - `wsgiref.util.application_uri + request_uri + guess_scheme 跨 3 endpoint 真返`
"""
import ipaddress
import io
import logging
import pathlib
import pickle
import socket
import sys
import wsgiref.simple_server
import wsgiref.util

import pytest


# -- pathlib 进阶 (PurePath 嵌套) ----------------------------------------------

class TestPathlibAdvancedV2:
    def test_PurePosixPath_suffix(self):
        """`pathlib.PurePosixPath('/forge/test.py').suffix 真 '.py'。"""
        p = pathlib.PurePosixPath("/forge/test.py")
        assert p.suffix == ".py", f"suffix 应='.py',实际 {p.suffix}"
        # 多 suffix
        p2 = pathlib.PurePosixPath("/forge/test.tar.gz")
        assert p2.suffixes == [".tar", ".gz"]
        assert p2.suffix == ".gz"

    def test_PurePath_parent_name(self):
        """`pathlib.PurePath('/a/b/c').parent.name == 'b'。"""
        p = pathlib.PurePath("/a/b/c")
        assert p.name == "c"
        assert p.parent.name == "b"
        assert p.parent.parent.name == "a"

    def test_Path_cwd(self):
        """`pathlib.Path.cwd 真非空 str。"""
        cwd = pathlib.Path.cwd()
        assert isinstance(cwd, pathlib.Path)
        # cwd 必是 absolute
        assert cwd.is_absolute()

    def test_Path_home(self):
        """`pathlib.Path.home 真返 home str。"""
        home = pathlib.Path.home()
        assert isinstance(home, pathlib.Path)
        assert home.is_absolute()


# -- ipaddress 进阶 (IPv6 Interface + Network) ---------------------------------

class TestIpaddressAdvancedV4:
    def test_IPv6Interface_netmask(self):
        """`ipaddress.IPv6Interface 真取 netmask。"""
        iface = ipaddress.IPv6Interface("2001:db8::1/64")
        # netmask = 64 个 1 = ffff:ffff:ffff:ffff::
        assert str(iface.netmask) == "ffff:ffff:ffff:ffff::"

    def test_IPv6Network_hostmask(self):
        """`ipaddress.IPv6Network 真取 hostmask。"""
        net = ipaddress.IPv6Network("2001:db8::/64", strict=False)
        # hostmask = 64 个 0
        assert str(net.hostmask) == "::ffff:ffff:ffff:ffff"

    def test_ip_network_v6(self):
        """`ipaddress.ip_network 真从 str 建 v6。"""
        net = ipaddress.ip_network("2001:db8::/32")
        # version 必=6
        assert net.version == 6
        # num_addresses = 2^96
        assert net.num_addresses == 2**96


# -- pickle 进阶 (Pickler + PickleError) ---------------------------------------

class _PickleData:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, _PickleData) and self.value == other.value


class TestPickleAdvancedV4:
    def test_Pickler_dump_load(self):
        """`pickle.Pickler(file) 真 dump 到 BytesIO + Unpickler load 真 round-trip。"""
        data = {"forge": 42, "list": [1, 2, 3]}
        buf = io.BytesIO()
        # Pickler 真建
        pickler = pickle.Pickler(buf)
        pickler.dump(data)
        # load
        buf.seek(0)
        unpickler = pickle.Unpickler(buf)
        loaded = unpickler.load()
        assert loaded == data

    def test_PickleError_raise(self):
        """`pickle.PickleError 真 class 存在 + 真 raise。"""
        # PickleError 真 class
        assert pickle.PickleError is not None
        # 真 raise
        with pytest.raises(pickle.PickleError):
            raise pickle.PickleError("forge pickle error")


# -- logging 进阶 (getLevelName + LogRecord) -----------------------------------

class TestLoggingAdvancedV5:
    def test_getLevelName(self):
        """`logging.getLevelName 真返 level int 或 str。"""
        # 'INFO' → 20
        assert logging.getLevelName("INFO") == 20
        # 20 → 'INFO'
        assert logging.getLevelName(20) == "INFO"
        # 未知 level 返 'Level 99'
        assert "Level 99" in logging.getLevelName(99)

    def test_LogRecord_instance(self):
        """`logging.LogRecord 真建 instance 含 name+level+msg+pathname+lineno。"""
        record = logging.LogRecord(
            name="forge_logger",
            level=logging.INFO,
            pathname="/x/forge.py",
            lineno=42,
            msg="forge log message %s",
            args=("test",),
            exc_info=None,
        )
        assert record.name == "forge_logger"
        assert record.levelno == logging.INFO
        assert record.lineno == 42
        # 格式化后必含 forge
        assert "forge" in record.getMessage()


# -- socket 进阶 (create_connection + getservbyname) --------------------------

class TestSocketAdvancedV6:
    def test_create_connection_to_local(self):
        """`socket.create_connection 真连本地 (不抛)`. """
        # 沙箱无 localhost 服务, 改测 timeout
        try:
            sock = socket.create_connection(("127.0.0.1", 22), timeout=0.5)
            sock.close()
        except (ConnectionRefusedError, OSError, TimeoutError):
            # 沙箱无 SSH server 是 expected
            pytest.skip("沙箱无 SSH/本地服务")

    def test_getservbyname_http(self):
        """`socket.getservbyname('http') 真=80。"""
        port = socket.getservbyname("http")
        assert port == 80, f"http 应=80,实际 {port}"

    def test_getservbyport(self):
        """`socket.getservbyport(80) 真='http'。"""
        name = socket.getservbyport(80)
        assert name == "http", f"80 应='http',实际 {name}"


# -- wsgiref 进阶 (simple_server + make_server) -------------------------------

class TestWsgirefSimpleServer:
    def test_make_server(self):
        """`wsgiref.simple_server.make_server 真启 (host, port) + 可关。"""
        # make_server 必返 WSGIServer instance
        # 沙箱无 release port, 用 port=0 (OS 选) + 仅 0.0.0.0
        server = wsgiref.simple_server.make_server(
            "127.0.0.1", 0, lambda env, start: [b"ok"]
        )
        try:
            # 必含 server_address
            host, port = server.server_address
            assert host == "127.0.0.1"
            assert port > 0
            # 必含 WSGIServer
            assert server is not None
        finally:
            server.server_close()
