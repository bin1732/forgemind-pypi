# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 struct: 真 pack/unpack 所有 format char (大小端/有符号/浮点/字节序前缀)。
真字节级布局, 零模拟。
"""
import struct
import pytest


def test_struct_basic_formats():
    """真基本 format chars"""
    # b/B (signed/unsigned char 1)
    assert struct.pack("b", -128) == b"\x80"
    assert struct.pack("b", 127) == b"\x7f"
    assert struct.pack("B", 255) == b"\xff"
    # h/H (short 2)
    assert struct.pack("h", -1) == b"\xff\xff"
    assert struct.pack("H", 65535) == b"\xff\xff"
    # i/I (int 4)
    assert struct.pack("i", -1) == b"\xff\xff\xff\xff"
    assert struct.pack("I", 0xFFFFFFFF) == b"\xff\xff\xff\xff"
    # l/L (long 看平台 — 4 或 8 字节)
    # q 是 8 字节 long long
    assert struct.pack("q", 1) == b"\x01\x00\x00\x00\x00\x00\x00\x00"
    assert struct.pack("Q", 0xFFFFFFFFFFFFFFFF) == b"\xff\xff\xff\xff\xff\xff\xff\xff"


def test_struct_endianness():
    """真大小端 prefix (<>!@)"""
    # < little-endian, > big-endian, ! network (= big-endian)
    val = 0x01020304
    assert struct.pack("<I", val) == b"\x04\x03\x02\x01"
    assert struct.pack(">I", val) == b"\x01\x02\x03\x04"
    assert struct.pack("!I", val) == b"\x01\x02\x03\x04"  # network = big

    # unpack round-trip
    assert struct.unpack("<I", b"\x04\x03\x02\x01")[0] == val
    assert struct.unpack(">I", b"\x01\x02\x03\x04")[0] == val


def test_struct_native_size():
    """真 native prefix @ (本地 size + 本地 endian)"""
    # 本地 size + 本地 byte order
    data = struct.pack("@i", 42)
    assert len(data) == 4
    # round-trip
    assert struct.unpack("@i", data)[0] == 42
    # 6 个 int
    data = struct.pack("@6i", *range(6))
    assert len(data) == 24


def test_struct_float_double():
    """真浮点 (f=float, d=double)"""
    # double IEEE 754
    pi = 3.14159265358979
    data = struct.pack("d", pi)
    assert len(data) == 8
    unpacked, = struct.unpack("d", data)
    assert abs(unpacked - pi) < 1e-15
    # NaN
    nan_data = struct.pack("d", float("inf"))
    inf, = struct.unpack("d", nan_data)
    assert inf == float("inf")


def test_struct_format_size():
    """真 calcsize + 真 size 验证"""
    assert struct.calcsize("i") == 4
    assert struct.calcsize("l") in (4, 8)  # 平台
    assert struct.calcsize("q") == 8
    assert struct.calcsize("d") == 8
    assert struct.calcsize("f") == 4
    # 多 field
    assert struct.calcsize("iid") == 4 + 4 + 8
    # 重复
    assert struct.calcsize("4i") == 16
    # 字符串
    assert struct.calcsize("10s") == 10


def test_struct_repeat_format():
    """真 Nx format (重复)"""
    # 5 个 int = "5i"
    data = struct.pack("5i", 1, 2, 3, 4, 5)
    assert len(data) == 20
    assert struct.unpack("5i", data) == (1, 2, 3, 4, 5)


def test_struct_string_format():
    """真 s (bytes string)"""
    # s = bytes string (固定长度)
    data = struct.pack("5s", b"hi")
    assert data == b"hi\x00\x00\x00"  # null-padded
    # round-trip 实际只 5 字节
    assert struct.unpack("5s", data)[0] == b"hi\x00\x00\x00"


def test_struct_pascal_string():
    """真 p (Pascal string)"""
    # p = 长度前缀 + bytes (max 255)
    data = struct.pack("10p", b"hello")
    # 首字节是长度, data 总 10 字节 (1 length + 9 data)
    assert len(data) == 10
    assert data[0] == 5  # length prefix
    assert data[1:6] == b"hello"
    # 后面 4 字节 null padding
    assert data[6:] == b"\x00" * 4


def test_struct_padding():
    """真对齐 (struct 默认加 padding)"""
    # 'ci' = char + int (4 字节对齐)
    # char 1 字节 + 3 padding + int 4 字节 = 8 字节
    data = struct.pack("ci", b"X", 1)
    assert len(data) == 8
    # 但 '<ci' (no alignment) = 5 字节
    data_le = struct.pack("<ci", b"X", 1)
    assert len(data_le) == 5


def test_struct_pack_into_buffer():
    """真 pack_into / unpack_from 预分配 buffer"""
    buf = bytearray(20)
    struct.pack_into("ii", buf, 0, 1, 2)
    struct.pack_into("i", buf, 8, 3)
    # unpack
    assert struct.unpack_from("ii", buf, 0) == (1, 2)
    assert struct.unpack_from("i", buf, 8) == (3,)
    # 范围外
    with pytest.raises(struct.error):
        struct.pack_into("i", buf, 18, 99)  # 只 2 字节剩


def test_struct_nested_format():
    """真嵌套 format (round-trip)"""
    fmt = "i 5s d"  # int + 5-byte string + double (native alignment)
    data = struct.pack(fmt, 42, b"abcde", 3.14)
    # 实际带 padding (native alignment)
    assert len(data) >= 4 + 5 + 8
    # round-trip
    n, s, f = struct.unpack(fmt, data)
    assert n == 42
    assert s == b"abcde"
    assert abs(f - 3.14) < 1e-15
    # 用 < (little-endian, no padding) 精确算
    fmt_le = "<i 5s d"
    assert struct.calcsize(fmt_le) == 4 + 5 + 8


def test_struct_arrays():
    """真数组 (重复)"""
    # 3 个 short
    data = struct.pack("<3h", 1, 2, 3)
    assert len(data) == 6
    assert struct.unpack("<3h", data) == (1, 2, 3)


def test_struct_signed_unsigned_extremes():
    """真有符号/无符号极值"""
    # signed char
    for v in (-128, -1, 0, 1, 127):
        d = struct.pack("b", v)
        assert struct.unpack("b", d)[0] == v
    # unsigned char
    for v in (0, 1, 127, 128, 255):
        d = struct.pack("B", v)
        assert struct.unpack("B", d)[0] == v
    # signed short
    for v in (-32768, 0, 32767):
        d = struct.pack("<h", v)
        assert struct.unpack("<h", d)[0] == v
    # signed long
    for v in (-2**31, 0, 2**31 - 1):
        d = struct.pack("<i", v)
        assert struct.unpack("<i", d)[0] == v
    # signed long long
    for v in (-2**63, 0, 2**63 - 1):
        d = struct.pack("<q", v)
        assert struct.unpack("<q", d)[0] == v


def test_struct_iter_unpack():
    """真 iter_unpack 真迭代"""
    data = struct.pack(">i", 1) + struct.pack(">i", 2) + struct.pack(">i", 3)
    # 3 个 big-endian int
    unpacked = list(struct.iter_unpack(">i", data))
    assert unpacked == [(1,), (2,), (3,)]


def test_struct_sizeof_via_struct():
    """真 sizeof + 真 pack 大小匹配"""
    for fmt in ("b", "B", "h", "H", "i", "I", "l", "L", "q", "Q",
                "f", "d", "?"):
        size = struct.calcsize(fmt)
        # pack 一值应 length == size
        if fmt == "?":
            data = struct.pack(fmt, True)
        elif fmt in ("f", "d"):
            data = struct.pack(fmt, 1.0)
        elif fmt in ("q", "Q"):
            data = struct.pack(fmt, 1)
        else:
            data = struct.pack(fmt, 1)
        assert len(data) == size, f"{fmt} calcsize={size} but pack={len(data)}"
