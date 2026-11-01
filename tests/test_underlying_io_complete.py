# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""真 io"""
import os
import io
import tempfile
import pytest

def test_file_open_read_basic():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("line 1\nline 2\nline 3\n")
        path = f.name
    try:
        with open(path) as f:
            assert f.read() == "line 1\nline 2\nline 3\n"
    finally:
        os.unlink(path)

def test_file_buffered_vs_raw():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
        f.write(b"x" * 10_000)
    try:
        with open(path, "rb", buffering=8192) as f:
            assert len(f.read()) == 10_000
        with open(path, "rb", buffering=0) as f:
            assert len(f.read(100)) == 100
    finally:
        os.unlink(path)

def test_file_seek_tell():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
        f.write(b"0123456789")
    try:
        with open(path, "rb") as f:
            f.seek(5)
            assert f.tell() == 5
            assert f.read(3) == b"567"
            f.seek(0, 2)
            assert f.tell() == 10
            f.seek(-3, 1)
            assert f.tell() == 7
    finally:
        os.unlink(path)

def test_file_flush_real():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
        f.write(b"data")
        f.flush()
        os.fsync(f.fileno())
    try:
        with open(path, "rb") as f:
            assert f.read() == b"data"
    finally:
        os.unlink(path)

def test_file_append_mode():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
    try:
        with open(path, "w") as f:
            f.write("first")
        with open(path, "a") as f:
            f.write("-second")
        with open(path) as f:
            assert f.read() == "first-second"
    finally:
        os.unlink(path)

def test_bytesio_stringio():
    bio = io.BytesIO()
    bio.write(b"hello world")
    bio.seek(0)
    assert bio.read() == b"hello world"
    bio.seek(5)
    assert bio.read() == b" world"
    bio.truncate(5)
    assert bio.getvalue() == b"hello"
    bio.close()
    sio = io.StringIO("initial")
    sio.seek(0, 2)
    sio.write("-more")
    sio.seek(0)
    assert sio.read() == "initial-more"

def test_stringio_unicode():
    sio = io.StringIO()
    sio.write("中文 hello 🎉")
    assert sio.getvalue() == "中文 hello 🎉"
    sio.close()

def test_fileio_wrapper():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
        f.write(b"\x00\x01\x02\x03")
    try:
        with open(path, "rb", buffering=0) as f:
            assert f.read() == b"\x00\x01\x02\x03"
    finally:
        os.unlink(path)

def test_textiowrapper_encoding():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        path = f.name
        f.write("中文 hello".encode("utf-8"))
    try:
        with open(path, encoding="utf-8") as f:
            assert f.read() == "中文 hello"
    finally:
        os.unlink(path)

def test_bufferedreader_peek():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
        f.write(b"abcdefghij" * 100)
    try:
        with open(path, "rb") as f:
            br = io.BufferedReader(f, buffer_size=50)
            peeked = br.peek(20)
            assert len(peeked) >= 20
            assert peeked[:10] == b"abcdefghij"
            br.close()
    finally:
        os.unlink(path)

def test_truncate_real():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
        f.write(b"1234567890")
    try:
        with open(path, "r+b") as f:
            f.truncate(5)
        with open(path, "rb") as f:
            assert f.read() == b"12345"
    finally:
        os.unlink(path)

def test_tempfile_real():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        path = f.name
    assert os.path.exists(path)
    os.unlink(path)
    assert not os.path.exists(path)

def test_os_read_write_os_close():
    fd, path = tempfile.mkstemp()
    try:
        n = os.write(fd, b"hello world")
        assert n == 11
        os.lseek(fd, 0, 0)
        d = os.read(fd, 5)
        assert d == b"hello"
    finally:
        os.close(fd)
        os.unlink(path)
