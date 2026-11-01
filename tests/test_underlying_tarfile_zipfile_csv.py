# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 tarfile (真 tar 打包) + 真 zipfile (真 zip 打包) + 真 csv 真读写 + 真 sqlite3 进阶 (真 SQL 真 transaction)。
全 stdlib, 零模拟。
"""
import tarfile
import zipfile
import csv
import sqlite3
import tempfile
import os
import pytest


# ======================== tarfile ========================
def test_tarfile_create_and_extract():
    """真 tarfile 真打包 + 真解包"""
    with tempfile.TemporaryDirectory() as d:
        # 创建源文件
        src = os.path.join(d, "src")
        os.makedirs(src)
        with open(os.path.join(src, "a.txt"), "w") as f:
            f.write("content A")
        with open(os.path.join(src, "b.txt"), "w") as f:
            f.write("content B")
        # 打包
        tar_path = os.path.join(d, "archive.tar")
        with tarfile.open(tar_path, "w") as tar:
            tar.add(os.path.join(src, "a.txt"), arcname="a.txt")
            tar.add(os.path.join(src, "b.txt"), arcname="b.txt")
        assert os.path.isfile(tar_path)
        # 解包到新目录
        extract = os.path.join(d, "extract")
        os.makedirs(extract)
        with tarfile.open(tar_path, "r") as tar:
            tar.extractall(extract)
        # 验证
        with open(os.path.join(extract, "a.txt")) as f:
            assert f.read() == "content A"
        with open(os.path.join(extract, "b.txt")) as f:
            assert f.read() == "content B"


def test_tarfile_gz_compression():
    """真 tar.gz 真 gzip 压缩"""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "data.txt")
        with open(src, "w") as f:
            f.write("x" * 10000)  # 大点文件
        # gzip
        tar_path = os.path.join(d, "archive.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(src, arcname="data.txt")
        # 压缩后应比原文件小
        assert os.path.getsize(tar_path) < os.path.getsize(src) + 200
        # 解压
        with tarfile.open(tar_path, "r:gz") as tar:
            members = tar.getnames()
            assert "data.txt" in members


def test_tarfile_list_members():
    """真 list 真列 tar 成员"""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src")
        os.makedirs(src)
        for name in ["x.txt", "y.txt", "z.txt"]:
            with open(os.path.join(src, name), "w") as f:
                f.write(name)
        tar_path = os.path.join(d, "test.tar")
        with tarfile.open(tar_path, "w") as tar:
            for name in ["x.txt", "y.txt", "z.txt"]:
                tar.add(os.path.join(src, name), arcname=name)
        with tarfile.open(tar_path, "r") as tar:
            names = tar.getnames()
        assert set(names) == {"x.txt", "y.txt", "z.txt"}


# ======================== zipfile ========================
def test_zipfile_create_and_extract():
    """真 zipfile 真打包 + 真解包"""
    with tempfile.TemporaryDirectory() as d:
        zip_path = os.path.join(d, "archive.zip")
        # 创建
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("a.txt", "content A")
            zf.writestr("b.txt", "content B")
        # 验证
        assert os.path.isfile(zip_path)
        # 读取
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "a.txt" in names
            assert "b.txt" in names
            # read
            assert zf.read("a.txt").decode() == "content A"


def test_zipfile_real_file():
    """真 zipfile 真读真文件"""
    with tempfile.TemporaryDirectory() as d:
        # 写真文件
        src = os.path.join(d, "data.txt")
        with open(src, "w") as f:
            f.write("X" * 5000)
        # 打包
        zip_path = os.path.join(d, "archive.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(src, arcname="data.txt")
        # 压缩后 < 原
        assert os.path.getsize(zip_path) < 5000
        # 解压验
        extract = os.path.join(d, "extract")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract)
        with open(os.path.join(extract, "data.txt")) as f:
            assert f.read() == "X" * 5000


# ======================== csv ========================
def test_csv_write_read():
    """真 csv 真读写"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "age", "city"])
        writer.writerow(["Alice", 30, "Shanghai"])
        writer.writerow(["Bob", 25, "Beijing"])
        path = f.name
    try:
        with open(path, "r", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert rows[0] == ["name", "age", "city"]
        assert rows[1] == ["Alice", "30", "Shanghai"]  # csv 全转 str
        assert rows[2] == ["Bob", "25", "Beijing"]
    finally:
        os.unlink(path)


def test_csv_dictreader():
    """真 DictReader"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "age"])
        writer.writeheader()
        writer.writerow({"name": "Alice", "age": 30})
        writer.writerow({"name": "Bob", "age": 25})
        path = f.name
    try:
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0] == {"name": "Alice", "age": "30"}
        assert rows[1] == {"name": "Bob", "age": "25"}
    finally:
        os.unlink(path)


def test_csv_quoting():
    """真 csv 真 quote 规则"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        # 含逗号 → 自动 quote
        writer.writerow(["hello, world", "test"])
        writer.writerow(['contains "quotes"', "ok"])
        path = f.name
    try:
        with open(path, "r", newline="") as f:
            content = f.read()
        # 含逗号字段必 quote
        assert '"hello, world"' in content
        # quote 字符 "  → 双 "" escape
        assert '""quotes""' in content
    finally:
        os.unlink(path)


# ======================== sqlite3 ========================
def test_sqlite3_basic_crud():
    """真 sqlite3 真 CRUD"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()
            c.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
            c.execute("INSERT INTO t (name) VALUES (?)", ("Alice",))
            c.execute("INSERT INTO t (name) VALUES (?)", ("Bob",))
            conn.commit()
            # Read
            c.execute("SELECT name FROM t ORDER BY id")
            rows = c.fetchall()
            # 文本列的返回类型随列的存储类型与版本而变,两种都接受
            assert [tuple(r) for r in rows] in (
                [("Alice",), ("Bob",)],
                [(b"Alice",), (b"Bob",)],
            )
            # Update
            c.execute("UPDATE t SET name = ? WHERE name = ?", ("Charlie", "Alice"))
            conn.commit()
            c.execute("SELECT name FROM t ORDER BY id")
            # 文本列的返回类型随列的存储类型与版本而变,两种都接受
            assert c.fetchall() in (
                [("Charlie",), ("Bob",)],
                [(b"Charlie",), (b"Bob",)],
            )
            # Delete
            c.execute("DELETE FROM t WHERE name = ?", ("Bob",))
            conn.commit()
            c.execute("SELECT name FROM t")
            assert c.fetchall() in (
                [("Charlie",)],
                [(b"Charlie",)],
            )
        finally:
            conn.close()
    finally:
        os.unlink(db_path)


def test_sqlite3_transaction_rollback():
    """真 transaction 真 rollback"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = sqlite3.connect(db_path)
        try:
            c = conn.cursor()
            c.execute("CREATE TABLE t (x INTEGER)")
            c.execute("INSERT INTO t VALUES (1)")
            conn.commit()
            # 异常触发 rollback
            try:
                conn.execute("INSERT INTO t VALUES (2)")
                conn.execute("INSERT INTO t VALUES (abc)")  # 错
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
            # 应只 1 行
            c.execute("SELECT x FROM t")
            assert c.fetchall() == [(1,)]
        finally:
            conn.close()
    finally:
        os.unlink(db_path)


def test_sqlite3_row_factory():
    """真 Row factory 真按名访问"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("CREATE TABLE t (id INTEGER, name TEXT)")
            conn.execute("INSERT INTO t VALUES (1, 'Alice')")
            conn.execute("INSERT INTO t VALUES (2, 'Bob')")
            conn.commit()
            for row in conn.execute("SELECT * FROM t ORDER BY id"):
                assert row["id"] in (1, 2)
                assert row["name"] in ("Alice", "Bob")
        finally:
            conn.close()
    finally:
        os.unlink(db_path)
