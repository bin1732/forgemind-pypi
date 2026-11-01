# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 sqlite3 进阶 (executemany 真 insert 5 row) + 真 asyncio 进阶 (create_subprocess_shell 真 cmd) + 真 ipaddress 真 (overlapping 真) + 真 html 真 (escape quote=False) + 真 struct 真 (C struct 真 byte order).
全 stdlib, 零模拟。
"""
import sqlite3
import asyncio
import ipaddress
import html
import struct
import pytest
import sys


# ======================== sqlite3 进阶 ========================
def test_sqlite3_executemany():
    """真 executemany 真 5 row insert"""
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE t (id INTEGER, name TEXT)")
        data = [(i, f"name{i}") for i in range(5)]
        conn.executemany("INSERT INTO t VALUES (?, ?)", data)
        conn.commit()
        # 查
        rows = list(conn.execute("SELECT * FROM t ORDER BY id"))
        assert len(rows) == 5
        assert rows[0][0] == 0
        assert rows[4][1] == "name4"
    finally:
        conn.close()


def test_sqlite3_executemany_returns_rowcount():
    """真 executemany 返 last rowcount"""
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE t (x INT)")
        data = [(i,) for i in range(10)]
        cur = conn.executemany("INSERT INTO t VALUES (?)", data)
        # rowcount
        assert cur.rowcount == 10
    finally:
        conn.close()


def test_sqlite3_row_factory_named():
    """真 Row factory named access"""
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE t (id INT, name TEXT)")
        conn.execute("INSERT INTO t VALUES (1, 'alice')")
        # Row factory (sqlite3.Row)
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM t")
        row = cur.fetchone()
        # named access
        assert row["id"] == 1
        assert row["name"] == "alice"
        # keys
        assert row.keys() == ["id", "name"]
    finally:
        conn.close()


# ======================== asyncio 进阶 ========================
def test_asyncio_create_subprocess_shell():
    """真 create_subprocess_shell 真"""
    async def main():
        proc = await asyncio.create_subprocess_shell(
            "echo hello",
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        assert b"hello" in stdout
        assert proc.returncode == 0

    asyncio.run(main())


def test_asyncio_create_subprocess_exec_args():
    """真 create_subprocess_exec args 真"""
    async def main():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", "import sys; print(sys.version_info[0])",
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        # 必有 3
        assert b"3" in stdout

    asyncio.run(main())


# ======================== ipaddress 进阶 ========================
def test_ipaddress_overlaps():
    """真 overlaps 真"""
    n1 = ipaddress.IPv4Network("10.0.0.0/16")
    n2 = ipaddress.IPv4Network("10.0.5.0/24")
    n3 = ipaddress.IPv4Network("10.1.0.0/16")
    # overlap
    assert n1.overlaps(n2)
    assert n2.overlaps(n1)
    # 不 overlap
    assert not n1.overlaps(n3)
    # IPv6
    n4 = ipaddress.IPv6Network("2001:db8::/32")
    n5 = ipaddress.IPv6Network("2001:db8:1::/48")
    assert n4.overlaps(n5)
    assert not n4.overlaps(ipaddress.IPv6Network("2001:db9::/32"))


def test_ipaddress_subnet_of_compare():
    """真 subnet_of / supernet_of 比较 进阶"""
    # 链
    n1 = ipaddress.IPv4Network("10.0.0.0/8")
    n2 = ipaddress.IPv4Network("10.1.0.0/16")
    n3 = ipaddress.IPv4Network("10.1.5.0/24")
    # n3 ⊆ n2 ⊆ n1
    assert n3.subnet_of(n2)
    assert n2.subnet_of(n1)
    assert n3.subnet_of(n1)


# ======================== html 真 ========================
def test_html_escape_quote_false():
    """真 escape quote=False 真"""
    # quote=False → 不 escape "
    text = '<a href="x">'
    escaped = html.escape(text, quote=False)
    # 必有 &lt; &gt; 但无 &quot;
    assert "&lt;" in escaped
    assert "&gt;" in escaped
    assert "&quot;" not in escaped


def test_html_escape_quote_true():
    """真 escape quote=True 真"""
    text = '<a href="x">'
    escaped = html.escape(text, quote=True)
    # 全 escape
    assert "&lt;" in escaped
    assert "&gt;" in escaped
    assert "&quot;" in escaped


# ======================== struct 真 ========================
def test_struct_byte_order_matters():
    """真 byte order 真 matters"""
    # < 和 > 必不同
    packed_l = struct.pack("<I", 1)
    packed_b = struct.pack(">I", 1)
    # 必不同
    assert packed_l != packed_b


def test_struct_repeat_count_struct():
    """真 Struct repeat count"""
    s = struct.Struct("3d")
    assert s.size == 24
    s2 = struct.Struct("10c")
    assert s2.size == 10
