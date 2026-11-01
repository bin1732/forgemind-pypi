# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 pathlib 真 (PurePath 真 / PurePosixPath / PureWindowsPath) + 真 numbers 真 (Complex / Rational / Real abstract) + 真 traceback 进阶 + 真 platform 进阶 + 真 struct 进阶 (byte order) + 真 array 真 (type code 属性).
全 stdlib, 零模拟。
"""
import pathlib
import numbers
import traceback
import platform
import struct
import array
import pytest


# ======================== pathlib 进阶 ========================
def test_purepath_posix():
    """真 PurePosixPath 真"""
    p = pathlib.PurePosixPath("/usr/local/bin")
    # parts
    assert p.parts == ("/", "usr", "local", "bin")
    # parent
    assert p.parent == pathlib.PurePosixPath("/usr/local")
    # name
    assert p.name == "bin"
    # root
    assert p.root == "/"


def test_purepath_windows():
    """真 PureWindowsPath 真"""
    p = pathlib.PureWindowsPath("C:\\Users\\alice\\file.txt")
    # parts
    assert p.drive == "C:"
    assert p.parts[1:] == ("Users", "alice", "file.txt")
    # suffix
    assert p.suffix == ".txt"
    # stem
    assert p.stem == "file"


def test_purepath_is_absolute():
    """真 is_absolute 真"""
    assert pathlib.PurePosixPath("/etc").is_absolute()
    assert not pathlib.PurePosixPath("etc/passwd").is_absolute()
    assert pathlib.PureWindowsPath("C:\\Windows").is_absolute()
    assert not pathlib.PureWindowsPath("Windows").is_absolute()


def test_purepath_relative_to():
    """真 relative_to 真"""
    p = pathlib.PurePosixPath("/usr/local/bin/python")
    rel = p.relative_to("/usr/local")
    # bin/python
    assert rel == pathlib.PurePosixPath("bin/python")


# ======================== numbers 进阶 ========================
def test_numbers_Complex_abstract():
    """真 Complex abstract 进阶"""
    # numbers.Complex 是 ABC
    assert issubclass(complex, numbers.Complex)
    assert issubclass(int, numbers.Complex)
    assert issubclass(float, numbers.Complex)
    # 必有
    z = 1 + 2j
    assert z.real == 1
    assert z.imag == 2
    assert z.conjugate() == 1 - 2j


def test_numbers_Rational_abstract():
    """真 Rational 真 abstract"""
    from fractions import Fraction
    # Fraction 必 subclass
    assert issubclass(Fraction, numbers.Rational)
    assert issubclass(Fraction, numbers.Real)
    # int 必 Rational
    assert issubclass(int, numbers.Rational)
    assert issubclass(int, numbers.Integral)


def test_numbers_Real_arithmetic():
    """真 Real arithmetic 进阶"""
    # numbers.Real 是 ABC, 不可 instantiate
    # 但 1.5 + 2.5 = 4.0 真
    assert 1.5 + 2.5 == 4.0
    assert 1.5 > 1
    assert (1.5 * 2) == 3.0
    # float 是 Real
    assert isinstance(1.5, numbers.Real)
    # int 也 Real
    assert isinstance(5, numbers.Real)


# ======================== traceback 进阶 ========================
def test_traceback_walk_tb():
    """真 walk_tb 真"""
    try:
        raise ValueError("test")
    except ValueError:
        tb = sys.exc_info()[2]
        walked = list(traceback.walk_tb(tb))
        # 必有 frames
        assert len(walked) >= 1
        # (frame, lineno) tuples
        for frame, lineno in walked:
            assert hasattr(frame, "f_code")
            assert isinstance(lineno, int)


def test_traceback_walk_stack():
    """真 walk_stack 真 (从当前 frame)"""
    # walk_stack(f=None) 用 sys._getframe(0) 默认
    import sys as _sys
    f = _sys._getframe(0)
    walked = list(traceback.walk_stack(f))
    # 必有 1+ frame
    assert len(walked) >= 1
    # 顶层 (当前)
    top_frame, top_lineno = walked[-1]
    assert hasattr(top_frame, "f_code")


# 加 sys
import sys


# ======================== platform 进阶 ========================
def test_platform_uname():
    """真 uname 真"""
    u = platform.uname()
    # named tuple
    assert hasattr(u, "system")
    assert hasattr(u, "node")
    assert hasattr(u, "release")
    assert hasattr(u, "version")
    assert hasattr(u, "machine")


# ======================== struct 进阶 ========================
def test_struct_format_attribute():
    """真 struct format attribute 进阶"""
    s = struct.Struct("<2if")
    # format
    assert s.format == "<2if"
    # size: 2*4 + 4 = 12
    assert s.size == 12


def test_struct_pack_unpack_native():
    """真 native 字节序 (沙箱 Linux)"""
    # @ native
    packed = struct.pack("@i", 1)
    # 4 bytes
    assert len(packed) == 4
    # round-trip
    n, = struct.unpack("@i", packed)
    assert n == 1


# ======================== array 进阶 ========================
def test_array_typecode():
    """真 typecode 进阶"""
    a = array.array("d", [1.0, 2.0])
    # typecode
    assert a.typecode == "d"
    # itemsize
    assert a.itemsize == 8


def test_array_bytes_size():
    """真 array bytes size 进阶"""
    a = array.array("i", [1, 2, 3, 4])
    # 4 * 4 = 16
    assert a.buffer_info()[1] == 4
    # bytes 长度
    assert len(a.tobytes()) == 16
