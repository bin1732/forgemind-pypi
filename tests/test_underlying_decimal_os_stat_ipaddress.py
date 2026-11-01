# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 decimal 真 (0 阶乘 / 真 from_float 0.1 精确) + 真 os 真 stat (真文件 + symlink) + 真 ipaddress 真 (summarize_address 进阶) + 真 socket 真 (CMOT 真 + IP 真) + 真 struct 真 (C struct 真).
全 stdlib, 零模拟。
"""
import decimal
import os
import stat as stat_mod
import ipaddress
import socket
import struct
import tempfile
import pytest


# ======================== decimal 进阶 ========================
def test_decimal_from_float_precise():
    """真 from_float 真 0.1 精确"""
    # 0.1 float 实际 0.1000000000000000055...
    d = decimal.Decimal.from_float(0.1)
    # 完整精度
    expected = "0.1000000000000000055511151231257827021181583404541015625"
    assert str(d) == expected


def test_decimal_zero_zero():
    """真 Decimal(0) 0 阶乘"""
    z = decimal.Decimal(0)
    assert z == 0
    assert z.is_zero()
    # 加 0
    assert z + decimal.Decimal(1) == decimal.Decimal(1)


def test_decimal_is_finite():
    """真 is_finite 真"""
    assert decimal.Decimal("1.5").is_finite()
    assert not decimal.Decimal("Inf").is_finite()
    assert not decimal.Decimal("NaN").is_finite()


# ======================== os.stat 真 ========================
def test_os_stat_real_file():
    """真 stat 真文件"""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
    try:
        s = os.stat(path)
        # mode
        assert stat_mod.S_ISREG(s.st_mode)
        # size
        assert s.st_size == 0
        # nlink
        assert s.st_nlink >= 1
        # uid/gid
        assert isinstance(s.st_uid, int)
        assert isinstance(s.st_gid, int)
    finally:
        os.unlink(path)


def test_os_lstat_symlink():
    """真 lstat 真 symlink 真"""
    with tempfile.TemporaryDirectory() as d:
        # 创 file
        target = os.path.join(d, "target.txt")
        with open(target, "w") as f:
            f.write("data")
        # 创 symlink
        link = os.path.join(d, "link")
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            # 沙箱 filesystem 不支持
            pytest.skip("symlink not supported")
        try:
            # lstat 不 follow
            s = os.lstat(link)
            # symlink
            assert stat_mod.S_ISLNK(s.st_mode)
        finally:
            os.unlink(link)


# ======================== ipaddress 进阶 ========================
def test_ipaddress_summarize_address():
    """真 summarize_address 真合并"""
    # 多个 /24 合并
    n1 = ipaddress.IPv4Network("10.0.0.0/24")
    n2 = ipaddress.IPv4Network("10.0.1.0/24")
    n3 = ipaddress.IPv4Network("10.0.2.0/24")
    n4 = ipaddress.IPv4Network("10.0.3.0/24")
    collapsed = list(ipaddress.collapse_addresses([n1, n2, n3, n4]))
    # 合并 1 个 /22
    assert len(collapsed) == 1
    assert collapsed[0] == ipaddress.IPv4Network("10.0.0.0/22")


def test_ipaddress_explode_ipv6():
    """真 explode 真 IPv6"""
    addr = ipaddress.IPv6Address("2001:db8::1")
    exploded = addr.exploded
    # 8 段全 4 hex
    parts = exploded.split(":")
    assert len(parts) == 8
    for p in parts:
        assert len(p) == 4


# ======================== socket 进阶 ========================
def test_socket_CMSG_SPACE():
    """真 socket 真 CMSG_SPACE 真常量"""
    if hasattr(socket, "CMSG_SPACE"):
        # 至少 1 个
        space = socket.CMSG_SPACE(1)
        assert space > 0


def test_socket_htonl():
    """真 htonl / ntohl 真字节序"""
    # 1 → 0x01000000 (big-endian)
    assert socket.htonl(1) == 0x01000000
    # ntohl 反
    assert socket.ntohl(0x01000000) == 1


def test_socket_inet_aton():
    """真 inet_aton 真"""
    packed = socket.inet_aton("10.0.0.1")
    assert len(packed) == 4
    assert packed == b"\x0a\x00\x00\x01"


# ======================== struct 进阶 ========================
def test_struct_class_layout():
    """真 struct 真 C struct 真 layout"""
    # C struct { int a; double b; char c; }
    # native size: 4 + 8 + 1 = 13 + padding = 24 (因 8-byte alignment)
    # 用 < 显式 no padding
    packed_size = struct.calcsize("<idc")
    # 4 + 8 + 1 = 13
    assert packed_size == 13


def test_struct_array_size():
    """真 struct 真 array size"""
    # 3 doubles = 24
    assert struct.calcsize("<3d") == 24
    # 5 ints = 20
    assert struct.calcsize("<5i") == 20
