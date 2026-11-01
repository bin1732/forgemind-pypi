# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 dis 真 dis() 真 output + 真 struct 真 进阶 (C struct 真) + 真 typing 真 (Protocol runtime_checkable) + 真 array 真 (insert 真) + 真 io 真 (BytesIO 真 truncate) + 真 decimal 真 (compare 真).
全 stdlib, 零模拟。
"""
import dis
import struct
import typing
import array
import io
import decimal
import contextlib
import pytest


# ======================== dis 进阶 ========================
def test_dis_dis_function_output():
    """真 dis 真 dis() 真 output"""
    import io as _io
    def f(x, y):
        return x + y

    buf = _io.StringIO()
    dis.dis(f, file=buf)
    output = buf.getvalue()
    # 含 LOAD_FAST / RETURN
    assert "LOAD_FAST" in output
    assert "RETURN" in output


def test_dis_show_code():
    """真 show_code 真"""
    def f(x):
        return x

    # show_code 不会抛
    import io as _io
    buf = _io.StringIO()
    dis.show_code(f, file=buf)
    output = buf.getvalue()
    # 含 name "f"
    assert "f" in output or "Name:" in output


# ======================== struct 进阶 ========================
def test_struct_pack_big_endian():
    """真 ! big-endian 字节序"""
    packed = struct.pack("!I", 1)
    # 0x00000001
    assert packed == b"\x00\x00\x00\x01"
    # unpack
    n, = struct.unpack("!I", packed)
    assert n == 1


def test_struct_pack_little_endian():
    """真 < little-endian"""
    packed = struct.pack("<I", 1)
    # 0x01000000
    assert packed == b"\x01\x00\x00\x00"


def test_struct_repeat_count():
    """真 repeat count 真"""
    # 3 ints
    packed = struct.pack("3i", 1, 2, 3)
    assert len(packed) == 12
    assert struct.unpack("3i", packed) == (1, 2, 3)


# ======================== typing 进阶 ========================
def test_typing_Protocol_with_methods():
    """真 Protocol 真 methods 真"""
    @typing.runtime_checkable
    class Drawable(typing.Protocol):
        def draw(self) -> str: ...
        def erase(self) -> str: ...

    class C:
        def draw(self) -> str:
            return "drew"
        def erase(self) -> str:
            return "erased"

    c = C()
    assert isinstance(c, Drawable)


def test_typing_Union_deduplication():
    """真 Union 进阶 dedup"""
    U = typing.Union[int, int, str]
    args = typing.get_args(U)
    # dedup
    assert args.count(int) == 1
    assert str in args


# ======================== array 进阶 ========================
def test_array_insert():
    """真 insert 真"""
    a = array.array("i", [1, 2, 3])
    a.insert(1, 99)  # 在 index 1 插
    assert list(a) == [1, 99, 2, 3]
    # 越界 insert
    a.insert(100, 88)
    # append at end
    assert list(a) == [1, 99, 2, 3, 88]


# ======================== io 进阶 ========================
def test_io_BytesIO_truncate():
    """真 BytesIO truncate 真截"""
    buf = io.BytesIO(b"0123456789")
    # truncate 到 5
    buf.truncate(5)
    # size 5
    assert buf.getbuffer().nbytes == 5
    # read 5
    buf.seek(0)
    assert buf.read() == b"01234"


def test_io_BytesIO_write_extend():
    """真 BytesIO write 真 extend"""
    buf = io.BytesIO(b"abc")
    # seek 到 end
    buf.seek(0, 2)  # 位置 3
    # write extend
    buf.write(b"def")
    # 位置 6
    assert buf.tell() == 6
    # getvalue 返全内容
    assert buf.getvalue() == b"abcdef"


# ======================== decimal 进阶 ========================
def test_decimal_compare_total():
    """真 compare_total 真"""
    a = decimal.Decimal("1.0")
    b = decimal.Decimal("1.00")
    # compare → 0
    assert a.compare(b) == 0
    n = decimal.Decimal("NaN")
    # NaN compare_total -1 (NaN > 1.0)
    assert a.compare_total(n) == -1


def test_decimal_is_zero():
    """真 is_zero 真"""
    assert decimal.Decimal(0).is_zero()
    assert decimal.Decimal("0.0").is_zero()
    assert decimal.Decimal("-0").is_zero()
    # 1.5 不是
    assert not decimal.Decimal("1.5").is_zero()
