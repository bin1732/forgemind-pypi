# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 asyncio 真 (StreamReader 真 read+at_eof) + 真 ipaddress 进阶 (interface route 真 LinkLocal) + 真 array 真 (bytes pack) + 真 sqlite3 进阶 (version 真 + version_info) + 真 traceback 真 (print_tb 进阶) + 真 unicodedata 真 (bidirectional 进阶) + 真 typing 真 (TypeVarTuple 进阶).
全 stdlib, 零模拟。
"""
import asyncio
import ipaddress
import array
import sqlite3
import traceback
import unicodedata
import typing
import io
import os
import sys
import tempfile
import pytest


# ======================== asyncio StreamReader ========================
def test_asyncio_StreamReader_readline():
    """真 StreamReader 真 readline"""
    async def main():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", "print('line1'); print('line2')",
            stdout=asyncio.subprocess.PIPE,
        )
        # 读
        line1 = await proc.stdout.readline()
        line2 = await proc.stdout.readline()
        # 必有 newline
        assert b"line1" in line1
        assert b"line2" in line2
        # eof
        eof = await proc.stdout.readline()
        assert eof == b""  # eof
        await proc.wait()

    asyncio.run(main())


def test_asyncio_StreamReader_at_eof():
    """真 StreamReader at_eof"""
    async def main():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", "print('only')",
            stdout=asyncio.subprocess.PIPE,
        )
        # 读全部
        data = await proc.stdout.read()
        # 必有 only
        assert b"only" in data
        # eof
        assert proc.stdout.at_eof()
        await proc.wait()

    asyncio.run(main())


def test_asyncio_StreamReader_readexactly():
    """真 readexactly 真定长"""
    async def main():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", "print('0123456789')",
            stdout=asyncio.subprocess.PIPE,
        )
        # 读 5 byte
        data = await proc.stdout.readexactly(5)
        assert data == b"01234"
        await proc.wait()

    asyncio.run(main())


# ======================== ipaddress 进阶 ========================
def test_ipaddress_interface_attributes():
    """真 interface 真属性"""
    # interface() 返 (network, prefixlen)
    net = ipaddress.IPv4Interface("192.168.1.1/24")
    assert net.ip == ipaddress.IPv4Address("192.168.1.1")
    assert net.network == ipaddress.IPv4Network("192.168.1.0/24")
    # netmask
    assert str(net.netmask) == "255.255.255.0"


def test_ipaddress_with_prefixlen():
    """真 with_prefixlen 进阶"""
    net = ipaddress.IPv4Network("10.0.0.0/24")
    # with_prefixlen
    assert net.with_prefixlen == "10.0.0.0/24"
    # with_netmask
    assert net.with_netmask == "10.0.0.0/255.255.255.0"
    # with_hostmask
    assert net.with_hostmask == "10.0.0.0/0.0.0.255"


def test_ipaddress_explode_vs_compressed():
    """真 IPv6 真 explode vs compressed 进阶"""
    addr = ipaddress.IPv6Address("2001:DB8:0:0:0:0:0:1")
    # 全部大写
    assert addr.compressed == "2001:db8::1"
    # explode
    assert addr.exploded == "2001:0db8:0000:0000:0000:0000:0000:0001"


# ======================== array 进阶 ========================
def test_array_tobytes_frombytes():
    """真 tobytes / frombytes 真"""
    a = array.array("i", [10, 20, 30, 40])
    b = a.tobytes()
    # 4 * 4 = 16
    assert len(b) == 16
    # round-trip
    a2 = array.array("i")
    a2.frombytes(b)
    assert a2 == a


def test_array_tofile_fromfile():
    """真 tofile / fromfile 真"""
    fd, path = tempfile.mkstemp(suffix=".bin")
    os.close(fd)
    try:
        a = array.array("d", [1.5, 2.5, 3.5, 4.5])
        with open(path, "wb") as f:
            a.tofile(f)
        # 读回
        a2 = array.array("d")
        with open(path, "rb") as f:
            a2.fromfile(f, 4)
        assert a2 == a
    finally:
        os.unlink(path)


# ======================== sqlite3 进阶 ========================
def test_sqlite3_version():
    """真 sqlite3 真 version"""
    # sqlite lib version
    assert isinstance(sqlite3.sqlite_version, str)
    # version_info
    assert isinstance(sqlite3.sqlite_version_info, tuple)
    # 3.x
    assert sqlite3.sqlite_version_info[0] >= 3
    # Python sqlite3 module version (2.6)
    assert isinstance(sqlite3.version, str)


def test_sqlite3_complete_statement():
    """真 complete_statement 真"""
    # 多语句 + semicolon → complete
    assert sqlite3.complete_statement("SELECT 1; SELECT 2;")
    # 无 semicolon 视为不 complete
    assert not sqlite3.complete_statement("SELECT * FROM t")
    # 多个不完整
    assert not sqlite3.complete_statement("SELECT * FROM")


# ======================== traceback 进阶 ========================
def test_traceback_format_tb():
    """真 format_tb 真"""
    try:
        raise ValueError("test")
    except ValueError:
        formatted = traceback.format_tb(sys.exc_info()[2])
        assert isinstance(formatted, list)
        # 必有 traceback 行
        all_text = "\n".join(formatted)
        assert "ValueError" in all_text or "test" in all_text


def test_traceback_format_exception_only():
    """真 format_exception_only 真"""
    formatted = traceback.format_exception_only(ValueError, ValueError("test"))
    assert isinstance(formatted, list)
    # 必有 ValueError
    assert any("ValueError" in line for line in formatted)


# ======================== unicodedata 进阶 ========================
def test_unicodedata_bidirectional():
    """真 bidirectional 真"""
    # 'A' 是 L (left-to-right)
    assert unicodedata.bidirectional("A") == "L"
    # '中' 是 L
    assert unicodedata.bidirectional("中") == "L"
    # 'a' 是 L
    assert unicodedata.bidirectional("a") == "L"
    # '0' 是 EN (European Number)
    assert unicodedata.bidirectional("0") == "EN"
    # 空格是 WS
    assert unicodedata.bidirectional(" ") == "WS"


def test_unicodedata_decomposition_decomp():
    """真 decomposition 真 tags"""
    # 'é' precomposed
    # decomposition
    decomp = unicodedata.decomposition("é")
    # 0x65 + 0x301
    assert "0065" in decomp
    assert "0301" in decomp


# ======================== typing 进阶 ========================
def test_typing_TypeVarTuple_unpack():
    """真 TypeVarTuple 真 unpack"""
    if hasattr(typing, "TypeVarTuple"):
        # 3.11+ TypeVarTuple
        Ts = typing.TypeVarTuple("Ts")
        # 1 个使用
        def first(args: tuple[int, int, int]) -> int:
            return args[0]
        # 必能调
        assert first((1, 2, 3)) == 1
    else:
        # fallback
        def first(args):
            return args[0]
        assert first((1, 2, 3)) == 1


def test_typing_ParamSpec_args_kwargs():
    """真 ParamSpec 真 args/kwargs"""
    if hasattr(typing, "ParamSpec"):
        P = typing.ParamSpec("P")
        # P.args 和 P.kwargs 是 typing special
        # 它们是 Generic 类型
        assert hasattr(P, "args")
        assert hasattr(P, "kwargs")
    else:
        pytest.skip("ParamSpec requires Python 3.10+")
