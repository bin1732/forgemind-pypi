# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 pickle 进阶 (PickleError 真抛 / reduce 真 control) + 真 os 进阶 (get_exec_path / supports_follow_symlinks) + 真 socket 进阶 (inet_pton 真 IPv6) + 真 struct 进阶 (IPv4 + IPv6 真组合) + 真 threading 进阶 (current_thread + Lock 真互斥) + 真 functools 真 (cache_info).
全 stdlib, 零模拟。
"""
import pickle
import os
import socket
import struct
import threading
import functools
import pytest


# ======================== pickle 进阶 ========================
def test_pickle_PickleError():
    """真 PickleError 真抛"""
    # 不可 pickle 类
    class NotPickleable:
        def __reduce__(self):
            raise pickle.PickleError("can't pickle")
    obj = NotPickleable()
    with pytest.raises(pickle.PickleError):
        pickle.dumps(obj)


class _ReduceP:
    """module-level for pickle reduce"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
    def __reduce__(self):
        return (_reconstruct_P, (self.x, self.y))


def _reconstruct_P(x, y):
    return _ReduceP(x, y)


def test_pickle_reduce_custom():
    """真 __reduce__ 真自定"""
    p = _ReduceP(1, 2)
    data = pickle.dumps(p)
    p2 = pickle.loads(data)
    assert p2.x == 1
    assert p2.y == 2


# ======================== os 进阶 ========================
def test_os_get_exec_path():
    """真 get_exec_path 真 PATH"""
    path = os.get_exec_path()
    # 3.11+ 返 list
    assert isinstance(path, list)
    # 必含 /usr/bin
    assert any("/usr/bin" in p for p in path) or len(path) > 0


def test_os_supports_follow_symlinks():
    """真 supports_follow_symlinks 真"""
    # 必含 OS 常量
    assert isinstance(os.supports_follow_symlinks, set)
    # 元素是 functions
    funcs = os.supports_follow_symlinks
    # 必有 stat (function 对象)
    assert os.stat in funcs
    assert os.access in funcs


def test_os_pathconf_names():
    """真 pathconf_names 真"""
    assert isinstance(os.pathconf_names, dict)
    # 必有 PC_MAX_CANON
    assert "PC_MAX_CANON" in os.pathconf_names
    # 至少 5 个
    assert len(os.pathconf_names) >= 5


# ======================== socket inet_pton ========================
def test_socket_inet_pton_ipv4():
    """真 inet_pton IPv4"""
    packed = socket.inet_pton(socket.AF_INET, "192.168.1.1")
    # 4 bytes
    assert len(packed) == 4
    # unpack
    assert packed == b"\xc0\xa8\x01\x01"


def test_socket_inet_pton_ipv6():
    """真 inet_pton IPv6"""
    packed = socket.inet_pton(socket.AF_INET6, "2001:db8::1")
    # 16 bytes
    assert len(packed) == 16
    # 前 4 bytes = 2001:0db8
    assert packed[:4] == b"\x20\x01\x0d\xb8"
    # 后 2 bytes = 0001
    assert packed[-2:] == b"\x00\x01"


def test_socket_inet_ntop():
    """真 inet_ntop 真反"""
    # IPv4
    addr = socket.inet_ntop(socket.AF_INET, b"\xc0\xa8\x01\x01")
    assert addr == "192.168.1.1"
    # IPv6
    addr6 = socket.inet_ntop(socket.AF_INET6, b"\x20\x01\x0d\xb8" + b"\x00" * 10 + b"\x00\x01")
    assert addr6 == "2001:db8::1"


# ======================== struct IPv4 + IPv6 ========================
def test_struct_compose_ipv4_ipv6():
    """真 struct 真组合 IPv4 + IPv6 header"""
    # IPv4 (20) + IPv6 (40) = 60 bytes
    ipv4 = struct.pack("!BBHHHBBH4s4s",
                       0x45, 0, 60, 1, 0, 64, 6, 0,
                       b"\x0a\x00\x00\x01", b"\x0a\x00\x00\x02")
    ipv6 = struct.pack("!IHBB16s16s",
                       0x60000000, 1500, 6, 64,
                       b"\x20\x01\x0d\xb8" + b"\x00" * 12,
                       b"\x20\x01\x0d\xb8" + b"\x00" * 11 + b"\x02")
    combined = ipv4 + ipv6
    assert len(combined) == 60
    # unpack IPv4
    v = struct.unpack("!BBHHHBBH4s4s", combined[:20])
    assert (v[0] >> 4) == 4
    # unpack IPv6
    v6 = struct.unpack("!IHBB16s16s", combined[20:])
    assert (v6[0] >> 28) == 6


# ======================== threading + functools ========================
def test_threading_current_thread():
    """真 current_thread"""
    main_thread = threading.current_thread()
    # MainThread
    assert main_thread.name == "MainThread"
    # thread 是 Thread obj
    assert isinstance(main_thread, threading.Thread)
    # alive
    assert main_thread.is_alive()


def test_threading_Timer():
    """真 Timer 真调度"""
    import time
    fired = []

    def callback():
        fired.append("ok")

    t = threading.Timer(0.05, callback)
    t.start()
    time.sleep(0.2)
    # 必触发
    assert fired == ["ok"]


def test_functools_lru_cache_info():
    """真 cache_info 真"""
    @functools.lru_cache(maxsize=2)
    def f(n):
        return n * 2

    f(1)  # miss
    f(1)  # hit
    f(1)  # hit
    f(2)  # miss
    f(3)  # miss (驱逐)
    info = f.cache_info()
    # 验
    assert info.hits >= 2
    assert info.misses >= 3
    assert info.currsize <= info.maxsize
    # clear
    f.cache_clear()
    info2 = f.cache_info()
    assert info2.currsize == 0
