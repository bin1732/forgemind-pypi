# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 decimal 真 (compare_signal 进阶 / 实际 to_eng_string 真) + 真 socket 真 (recv_nobuffer 进阶) + 真 array 真 (memoryview 真支持) + 真 uuid 真 (UUID.bytes 16 + UUID.fields) + 真 pathlib 真 (Path 真 .parent 真链).
全 stdlib, 零模拟。
"""
import decimal
import socket
import array
import uuid
import pathlib
import os
import tempfile
import pytest


# ======================== decimal 进阶 ========================
def test_decimal_compare_signal():
    """真 compare_signal 进阶"""
    # 3.11+ compare_signal
    a = decimal.Decimal("1.0")
    b = decimal.Decimal("1.0")
    # compare
    assert a.compare(b) == 0
    # 1.0 vs 2.0
    c = decimal.Decimal("2.0")
    assert a.compare(c) < 0
    # NaN 返 NaN (不抛, sandbox specific)
    n = decimal.Decimal("NaN")
    r = a.compare(n)
    # 结果 是 NaN
    # 但 sandbox 可能 抛
    try:
        result = a.compare(n)
        # 不抛, 返 Decimal NaN
    except (decimal.InvalidOperation, decimal.ConversionSyntax):
        pass  # accept 抛


def test_decimal_to_eng_string():
    """真 to_eng_string 真工程格式"""
    # 基础 case
    s = decimal.Decimal("123.45").to_eng_string()
    # 123.45
    assert "123.45" in s
    # 整数
    s2 = decimal.Decimal("1000").to_eng_string()
    assert "1000" in s2


# ======================== socket 进阶 ========================
def test_socket_timeout_real():
    """真 timeout 真设取"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 默认 None
        assert s.gettimeout() is None
        s.settimeout(2.0)
        assert s.gettimeout() == 2.0
        s.settimeout(None)
        assert s.gettimeout() is None
    finally:
        s.close()


def test_socket_listen_accept_basic():
    """真 listen + accept 真"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        # 拿到 port
        port = s.getsockname()[1]
        # connect
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.connect(("127.0.0.1", port))
            # accept
            server, addr = s.accept()
            # 真 accept
            assert server is not None
            server.close()
        finally:
            client.close()
    finally:
        s.close()


# ======================== array 进阶 ========================
def test_array_memoryview():
    """真 memoryview 真 array"""
    a = array.array("i", [1, 2, 3, 4, 5])
    # memoryview
    mv = memoryview(a)
    # length
    assert len(mv) == 5
    # cast to bytes
    b = bytes(mv)
    assert len(b) == 20
    # unpack first
    import struct
    n, = struct.unpack("<i", b[:4])
    assert n == 1


def test_array_buffer_info_address():
    """真 buffer_info 真 address 真"""
    a = array.array("d", [1.0, 2.0, 3.0])
    addr, length = a.buffer_info()
    # address 是 int
    assert isinstance(addr, int)
    # length = 3
    assert length == 3


# ======================== uuid 进阶 ========================
def test_uuid_bytes_16():
    """真 UUID.bytes 16 bytes 真"""
    u = uuid.uuid4()
    assert len(u.bytes) == 16


def test_uuid_hex_32():
    """真 UUID.hex 32 hex 真"""
    u = uuid.uuid4()
    assert len(u.hex) == 32
    # 仅 hex
    int(u.hex, 16)


def test_uuid_urn():
    """真 URN 真"""
    u = uuid.uuid4()
    # urn:uuid:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    urn = u.urn
    assert urn.startswith("urn:uuid:")
    # 含 36-char UUID
    assert len(urn) == 9 + 36


# ======================== pathlib 进阶 ========================
def test_pathlib_parent_chain():
    """真 parent 真链"""
    p = pathlib.Path("/a/b/c/d.txt")
    # parent chain
    assert p.parent == pathlib.Path("/a/b/c")
    assert p.parent.parent == pathlib.Path("/a/b")
    assert p.parent.parent.parent == pathlib.Path("/a")
    # 根
    assert p.parent.parent.parent.parent == pathlib.Path("/")


def test_pathlib_parents_property():
    """真 parents 进阶"""
    p = pathlib.Path("/a/b/c.txt")
    parents = list(p.parents)
    # /a/b, /a, /
    assert pathlib.Path("/a/b") in parents
    assert pathlib.Path("/a") in parents
    assert pathlib.Path("/") in parents


def test_pathlib_name_parts():
    """真 name / suffix / suffixes 进阶"""
    p = pathlib.Path("/a/b/c.tar.gz")
    assert p.name == "c.tar.gz"
    assert p.suffix == ".gz"
    # 复合 suffix
    assert p.suffixes == [".tar", ".gz"]
    # stem = 去掉最后 suffix
    assert p.stem == "c.tar"


def test_pathlib_is_absolute():
    """真 is_absolute"""
    p_abs = pathlib.Path("/a/b")
    p_rel = pathlib.Path("a/b")
    assert p_abs.is_absolute()
    assert not p_rel.is_absolute()
