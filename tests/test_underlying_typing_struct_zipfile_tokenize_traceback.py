# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 typing 真 (TypeVar bound 真 constrains 进阶) + 真 struct 真 (大小 真实测) + 真 zipfile 真 (压缩级别差异) + 真 tokenize 真 (f-string 进阶) + 真 traceback 真 (print_tb 真).
全 stdlib, 零模拟。
"""
import sys
import typing
import struct
import zipfile
import tokenize
import traceback
import io
import os
import tempfile
import pytest


# ======================== typing 进阶 ========================
def test_typing_TypeVar_constrained():
    """真 TypeVar constrained 进阶"""
    T = typing.TypeVar("T", int, str, float)
    # 必可 call
    T.__name__  # 不抛
    # bound/constrained 不可在 instantiate 设
    # runtime int|str|float
    assert T.__constraints__ == (int, str, float)


def test_typing_Concatenate():
    """真 Concatenate 进阶"""
    if hasattr(typing, "Concatenate"):
        P = typing.ParamSpec("P")
        # Concatenate[str, P]
        c = typing.Concatenate[str, P]
        # 必 1 元素
        assert hasattr(c, "__args__")
    else:
        pytest.skip("Concatenate requires Python 3.10+")


def test_typing_Optional_equals_Union():
    """真 Optional 真"""
    assert typing.Optional[int] == typing.Union[int, None]


# ======================== struct 进阶 ========================
def test_struct_size_native():
    """真 struct native size"""
    # native byte order
    fmt = struct.Struct("i")
    # 4 bytes
    assert fmt.size == 4


def test_struct_size_explicit():
    """真 struct 显式 < size"""
    fmt = struct.Struct("<i")
    assert fmt.size == 4


def test_struct_format_attribute():
    """真 struct format attribute"""
    s = struct.Struct("!HI")
    # format
    assert s.format == "!HI"
    # size: 2 + 4 = 6
    assert s.size == 6


# ======================== zipfile 进阶 ========================
def test_zipfile_compresslevel_9_vs_0():
    """真 zipfile compresslevel 真差异"""
    data = b"x" * 10000
    # 9 max
    buf9 = io.BytesIO()
    with zipfile.ZipFile(buf9, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("f.txt", data)
    # 1 fast
    buf1 = io.BytesIO()
    with zipfile.ZipFile(buf1, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        z.writestr("f.txt", data)
    # 9 ≤ 1 (相同内容重复, 应可压缩)
    assert len(buf9.getvalue()) <= len(buf1.getvalue())


def test_zipfile_real_zipfile_with_file():
    """真 zipfile 真 file"""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        path = f.name
    try:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("a.txt", "content A")
            z.writestr("b.txt", "content B")
        # 读
        with zipfile.ZipFile(path, "r") as z:
            names = z.namelist()
            assert "a.txt" in names
            assert "b.txt" in names
            # 读
            assert z.read("a.txt") == b"content A"
    finally:
        os.unlink(path)


# ======================== tokenize 进阶 ========================
def test_tokenize_fstring():
    """真 f-string 真"""
    src = "x = f'hello {1+2}'\n"
    tokens = list(tokenize.tokenize(io.BytesIO(src.encode()).readline))
    # 必有 NAME 'x', OP '=', STRING (f-string)
    token_strs = [(t.string, t.type) for t in tokens]
    # STRING with f
    string_tokens = [t for t in tokens if t.type == tokenize.STRING]
    assert any("f" in t.string for t in string_tokens)


def test_tokenize_bytes_source():
    """真 tokenize 真 bytes source 进阶"""
    src = b"x = 1 + 2\n"
    tokens = list(tokenize.tokenize(io.BytesIO(src).readline))
    # 必有 NAME 'x', OP '=', NUMBER '1'
    assert any(t.string == "x" and t.type == tokenize.NAME for t in tokens)
    assert any(t.string == "1" and t.type == tokenize.NUMBER for t in tokens)


# ======================== traceback 进阶 ========================
def test_traceback_print_tb_to_stringio():
    """真 print_tb 真"""
    try:
        raise ValueError("oops")
    except ValueError:
        buf = io.StringIO()
        traceback.print_tb(sys.exc_info()[2], file=buf)
        # 必含 stack
        output = buf.getvalue()
        assert "ValueError" in output or "test" in output


def test_traceback_extract_tb():
    """真 extract_tb 真"""
    try:
        raise RuntimeError("test")
    except RuntimeError:
        et = traceback.extract_tb(sys.exc_info()[2])
        assert isinstance(et, list)
        # 必有 1+ frame
        assert len(et) >= 1
        # 顶层 frame
        frame = et[-1]
        assert hasattr(frame, "filename")
        assert hasattr(frame, "line")


