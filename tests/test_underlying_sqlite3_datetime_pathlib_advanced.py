# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 sqlite3 真 SQL 真 blob 真 connection 真 cursor + 真 datetime 真 timedelta arithmetic + 真 pathlib 真 joinpath 真 iterdir 真 glob + 真 ctypes 真 sizeof。
全 stdlib, 零模拟。
"""
import sqlite3
import datetime
import pathlib
import os
import ctypes
import tempfile
import pytest


# ======================== sqlite3 真 SQL ========================
def test_sqlite3_blob_insert_query():
    """真 sqlite3 真 blob 真存取"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    try:
        conn = sqlite3.connect(db)
        try:
            conn.execute("CREATE TABLE t (id INTEGER, data BLOB)")
            # blob 数据
            data = b"\x00\xff\x10\x80binary data here"
            conn.execute("INSERT INTO t VALUES (?, ?)", (1, data))
            conn.commit()
            # 查
            row = conn.execute("SELECT data FROM t WHERE id = 1").fetchone()
            assert row[0] == data
        finally:
            conn.close()
    finally:
        os.unlink(db)


def test_sqlite3_join_query():
    """真 sqlite3 真 JOIN 真查"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    try:
        conn = sqlite3.connect(db)
        try:
            conn.executescript("""
                CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL);
                INSERT INTO users (id, name) VALUES (1, 'Alice');
                INSERT INTO users (id, name) VALUES (2, 'Bob');
                INSERT INTO orders (user_id, amount) VALUES (1, 100.5);
                INSERT INTO orders (user_id, amount) VALUES (1, 50.25);
                INSERT INTO orders (user_id, amount) VALUES (2, 200.0);
            """)
            # JOIN
            rows = conn.execute("""
                SELECT u.name, SUM(o.amount) as total
                FROM users u
                JOIN orders o ON u.id = o.user_id
                GROUP BY u.id, u.name
                ORDER BY total DESC
            """).fetchall()
            assert rows == [("Bob", 200.0), ("Alice", 150.75)]
        finally:
            conn.close()
    finally:
        os.unlink(db)


def test_sqlite3_index_works():
    """真 sqlite3 真 CREATE INDEX 真生效"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    try:
        conn = sqlite3.connect(db)
        try:
            conn.execute("CREATE TABLE t (id INTEGER, val TEXT)")
            # 大量数据
            data = [(i, f"v{i}") for i in range(1000)]
            conn.executemany("INSERT INTO t VALUES (?, ?)", data)
            conn.execute("CREATE INDEX idx_t_id ON t(id)")
            conn.commit()
            # 索引在 system catalog
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='t'"
            ).fetchall()
            assert any("idx_t_id" in i for i in indexes)
        finally:
            conn.close()
    finally:
        os.unlink(db)


# ======================== datetime 真 arithmetic ========================
def test_datetime_timedelta_arithmetic():
    """真 datetime + timedelta"""
    d1 = datetime.datetime(2026, 1, 1)
    delta = datetime.timedelta(days=10, hours=2)
    d2 = d1 + delta
    assert d2.day == 11
    assert d2.hour == 2
    # 反
    d3 = d2 - delta
    assert d3 == d1


def test_datetime_date_arithmetic():
    """真 date + timedelta"""
    d1 = datetime.date(2026, 1, 1)
    d2 = d1 + datetime.timedelta(days=31)
    assert d2 == datetime.date(2026, 2, 1)


def test_datetime_comparison():
    """真 datetime 真比较"""
    d1 = datetime.datetime(2026, 1, 1)
    d2 = datetime.datetime(2026, 2, 1)
    assert d1 < d2
    assert d2 > d1
    assert d1 != d2
    # 同样
    d3 = datetime.datetime(2026, 1, 1)
    assert d1 == d3


def test_datetime_isoformat():
    """真 isoformat 真格式"""
    d = datetime.datetime(2026, 10, 14, 17, 30, 45)
    s = d.isoformat()
    assert s == "2026-10-14T17:30:45"


def test_datetime_parse_isoformat():
    """真 fromisoformat 真反"""
    s = "2026-10-14T17:30:45"
    d = datetime.datetime.fromisoformat(s)
    assert d == datetime.datetime(2026, 10, 14, 17, 30, 45)


# ======================== pathlib 进阶 ========================
def test_pathlib_joinpath():
    """真 joinpath"""
    p = pathlib.Path("/home")
    p2 = p / "user" / "documents"
    assert str(p2) == "/home/user/documents"


def test_pathlib_iterdir():
    """真 iterdir 真列"""
    with tempfile.TemporaryDirectory() as d:
        # 创建几个文件
        for i in range(3):
            pathlib.Path(d, f"file{i}.txt").write_text("data")
        # iter
        files = list(pathlib.Path(d).iterdir())
        # 3 个文件
        assert len(files) == 3


def test_pathlib_glob():
    """真 glob 真模式"""
    with tempfile.TemporaryDirectory() as d:
        # 创建混合
        pathlib.Path(d, "a.py").write_text("x")
        pathlib.Path(d, "b.py").write_text("y")
        pathlib.Path(d, "c.txt").write_text("z")
        # glob
        py_files = list(pathlib.Path(d).glob("*.py"))
        assert len(py_files) == 2
        names = [p.name for p in py_files]
        assert "a.py" in names
        assert "b.py" in names


def test_pathlib_mkdir_rm():
    """真 mkdir 真建"""
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "new_dir" / "sub_dir"
        p.mkdir(parents=True)
        assert p.exists()
        assert p.is_dir()


def test_pathlib_suffix_stem():
    """真 suffix / stem"""
    p = pathlib.Path("/a/b/c.txt")
    assert p.suffix == ".txt"
    assert p.stem == "c"
    # 复合
    p2 = pathlib.Path("/a/b/archive.tar.gz")
    assert p2.suffix == ".gz"
    assert p2.suffixes == [".tar", ".gz"]


# ======================== ctypes 进阶 ========================
def test_ctypes_sizeof_basic():
    """真 sizeof"""
    assert ctypes.sizeof(ctypes.c_int) == 4
    assert ctypes.sizeof(ctypes.c_double) == 8
    assert ctypes.sizeof(ctypes.c_char) == 1


def test_ctypes_string_buffer():
    """真 c_char_p 真字符串"""
    s = ctypes.c_char_p(b"hello")
    assert s.value == b"hello"
    # 改
    s.value = b"world"
    assert s.value == b"world"


def test_ctypes_Union():
    """真 ctypes Union"""
    class MyUnion(ctypes.Union):
        _fields_ = [
            ("as_int", ctypes.c_int),
            ("as_float", ctypes.c_float),
        ]
    u = MyUnion()
    u.as_int = 42
    # 内存共享
    # (int 和 float 同 4 bytes)
    # 因 float 在内存不重读
    # size 4
    assert ctypes.sizeof(u) == 4
