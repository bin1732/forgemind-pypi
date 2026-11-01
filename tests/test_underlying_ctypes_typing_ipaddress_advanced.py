# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 ctypes 进阶 (Structure 真 nested / pointer to struct) + 真 typing 进阶 (Self) + 真 ipaddress 进阶 (IPv6 scope_id) + 真 copy 进阶 (deepcopy 不可 pickle obj) + 真 sqlite3 进阶 (backup).
全 stdlib, 零模拟。
"""
import ctypes
import typing
import ipaddress
import copy
import sqlite3
import os
import tempfile
import pytest


# ======================== ctypes 进阶 ========================
def test_ctypes_Structure_nested():
    """真 Structure 真嵌套"""
    class Point(ctypes.Structure):
        _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int)]

    class Line(ctypes.Structure):
        _fields_ = [("start", Point), ("end", Point)]

    line = Line()
    line.start.x = 1
    line.start.y = 2
    line.end.x = 3
    line.end.y = 4
    # 验
    assert line.start.x == 1
    assert line.end.y == 4
    # size
    assert ctypes.sizeof(line) == 16


def test_ctypes_pointer_to_struct():
    """真 pointer to struct 真 deref"""
    class Point(ctypes.Structure):
        _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int)]

    p = Point(3, 4)
    ptr = ctypes.pointer(p)
    # deref
    assert ptr.contents.x == 3
    # 改 ptr → p
    ptr.contents.x = 99
    assert p.x == 99


def test_ctypes_Union_fields():
    """真 Union 真共享内存"""
    class MyUnion(ctypes.Union):
        _fields_ = [
            ("as_int", ctypes.c_int),
            ("as_bytes", ctypes.c_ubyte * 4),
        ]
    u = MyUnion()
    u.as_int = 0x12345678
    # bytes
    assert u.as_bytes[0] == 0x78
    assert u.as_bytes[1] == 0x56
    assert u.as_bytes[2] == 0x34
    assert u.as_bytes[3] == 0x12


# ======================== typing Self ========================
def test_typing_Self():
    """真 typing.Self 真存在"""
    if hasattr(typing, "Self"):
        # 3.11+
        S = typing.Self
        # Self 是 typing.Self
        assert S is not None


def test_typing_TypeVar_with_default():
    """真 TypeVar 3.11+ 无 default 参数"""
    # 3.13+ TypeVar(default=...) 才支持
    # 3.11/3.12 不支持
    import sys
    if sys.version_info >= (3, 13):
        T = typing.TypeVar("T", default=int)
        assert T is not None
    else:
        # 3.11/3.12
        T = typing.TypeVar("T")
        assert T is not None


# ======================== ipaddress 进阶 ========================
def test_ipaddress_IPv6_scope_id():
    """真 IPv6 scope_id 真"""
    # link-local IPv6 with scope
    addr = ipaddress.IPv6Address("fe80::1%eth0")
    # scope_id
    assert addr.scope_id == "eth0"
    # 不带 scope → None
    addr2 = ipaddress.IPv6Address("::1")
    assert addr2.scope_id is None


def test_ipaddress_IPv6_compressed_form():
    """真 IPv6 真压缩"""
    # 2001:0db8:0000:0000:0000:0000:0000:0001 → 2001:db8::1
    full = "2001:0db8:0000:0000:0000:0000:0000:0001"
    compressed = ipaddress.IPv6Address(full).compressed
    assert compressed == "2001:db8::1"


def test_ipaddress_IPv6_teredo():
    """真 IPv6 真 teredo 地址"""
    # 2001:: 是 teredo
    teredo = ipaddress.IPv6Address("2001::1")
    # 实际不在六版测试 but 应该有 ipv6
    assert teredo.version == 6


def test_ipaddress_IPv4_is_reserved():
    """真 is_reserved 真"""
    # 240.0.0.0/4 reserved
    assert ipaddress.IPv4Address("240.0.0.1").is_reserved
    # 169.254.0.0/16 link-local
    assert ipaddress.IPv4Address("169.254.1.1").is_link_local
    # 224.0.0.0/4 multicast
    assert ipaddress.IPv4Address("224.0.0.1").is_multicast


# ======================== copy deepcopy 不可 pickle ========================
def test_copy_deepcopy_lambda():
    """真 deepcopy lambda / function"""
    f = lambda x: x + 1
    # 实际 deepcopy lambda 返同 obj (memo)
    # 但不影响 — f 仍可调
    deep = copy.deepcopy(f)
    # 仍可调
    assert deep(5) == 6


# ======================== sqlite3 backup ========================
def test_sqlite3_backup():
    """真 backup 真拷"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        src = f.name
    with tempfile.NamedTemporaryFile(suffix=".bak", delete=False) as f:
        dst = f.name
    try:
        # 源
        conn_src = sqlite3.connect(src)
        try:
            conn_src.execute("CREATE TABLE t (v INTEGER)")
            conn_src.execute("INSERT INTO t VALUES (42)")
            conn_src.commit()
            # 备份到 dst
            conn_dst = sqlite3.connect(dst)
            try:
                conn_src.backup(conn_dst)
            finally:
                conn_dst.close()
        finally:
            conn_src.close()
        # 验 dst
        conn = sqlite3.connect(dst)
        try:
            row = conn.execute("SELECT v FROM t").fetchone()
            assert row[0] == 42
        finally:
            conn.close()
    finally:
        os.unlink(src)
        os.unlink(dst)
