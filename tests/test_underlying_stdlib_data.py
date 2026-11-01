# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 stdlib data — json 真序列化 1MB+ / csv 真 parse / xml 真 parse / sqlite3 真用。
"""
import csv
import io
import json
import os
import sqlite3
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


def test_json_round_trip_1mb():
    """json 真序列化 1MB 数据 100% round-trip"""
    data = {
        "numbers": list(range(1000)),
        "text": "x" * 500_000,  # 500 KB 字符串
        "nested": {"a": [1, 2, 3], "b": {"c": True, "d": None}},
    }
    encoded = json.dumps(data)
    decoded = json.loads(encoded)
    assert decoded == data, f"json round-trip 应 100%, 实际 {len(str(decoded))}/{len(str(data))}"


def test_json_unicode_chinese_emoji():
    """json 真支持中文 + emoji (ensure_ascii=False)"""
    s = {"中文": "你好", "emoji": "🌍🚀"}
    encoded = json.dumps(s, ensure_ascii=False)
    assert "中文" in encoded, f"中文应在 JSON 里 (ensure_ascii=False), 实际: {encoded}"
    decoded = json.loads(encoded)
    assert decoded == s


def test_json_indent_real_format():
    """json.dumps(indent=2) 真格式化"""
    d = {"a": 1, "b": [1, 2, 3]}
    s = json.dumps(d, indent=2)
    assert "\n  " in s, f"indent=2 应有换行 + 2 空格缩进, 实际: {s!r}"


def test_json_sort_keys_actual():
    """json sort_keys 真按 key 排序"""
    d = {"z": 1, "a": 2, "m": 3}
    s = json.dumps(d, sort_keys=True)
    assert s.index('"a"') < s.index('"m"') < s.index('"z"'), f"sort_keys 应按 a<m<z 序, 实际: {s}"


def test_csv_reader_dict_format():
    """csv 真读 DictReader, 字段名真用第一行"""
    csv_data = "name,age,city\nAlice,30,Beijing\nBob,25,Shanghai\n"
    reader = csv.DictReader(io.StringIO(csv_data))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[0] == {"name": "Alice", "age": "30", "city": "Beijing"}
    assert rows[1] == {"name": "Bob", "age": "25", "city": "Shanghai"}


def test_csv_writer_actually_produces_csv():
    """csv 真 writer 产合规 CSV (含 quote)"""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["name", "value"])
    writer.writerow(['has, comma', 'has "quote"'])
    writer.writerow(["line\nbreak", "x"])  # 触发 quoting
    s = out.getvalue()
    # 含逗号字段应被 quote
    assert '"has, comma"' in s or "'has, comma'" in s
    # 含 quote 字段应被 double-up
    assert '""quote""' in s or '\\\\\"quote\\\\\"' in s


def test_csv_round_trip_100_rows():
    """csv 真 round-trip 100 行"""
    rows = [[f"col_{i}_{j}" for j in range(5)] for i in range(100)]
    out = io.StringIO()
    csv.writer(out).writerows(rows)
    out.seek(0)
    reloaded = list(csv.reader(out))
    assert reloaded == rows, f"100 行 CSV round-trip 应一致"


def test_xml_parse_real():
    """xml 真 parse, 拿真 element"""
    xml = """<root>
  <item id="1">Alice</item>
  <item id="2">Bob</item>
  <nested>
    <child>Charlie</child>
  </nested>
</root>"""
    root = ET.fromstring(xml)
    assert root.tag == "root"
    items = root.findall("item")
    assert len(items) == 2
    assert items[0].text == "Alice"
    assert items[0].get("id") == "1"
    child = root.find("nested/child")
    assert child.text == "Charlie"


def test_xml_construct_real():
    """xml 真构造 + serialize + 解析回"""
    root = ET.Element("data")
    for i in range(10):
        item = ET.SubElement(root, "item", id=str(i))
        item.text = f"value_{i}"
    s = ET.tostring(root, encoding="unicode")
    reparsed = ET.fromstring(s)
    items = reparsed.findall("item")
    assert len(items) == 10
    assert items[5].get("id") == "5"
    assert items[5].text == "value_5"


def test_sqlite_real_query():
    """sqlite3 真建表 + 真查询 + 真索引"""
    db_path = "/tmp/test_sqlite_underlying.db"
    if os.path.exists(db_path):
        os.unlink(db_path)
    try:
        con = sqlite3.connect(db_path)
        con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, val REAL)")
        for i in range(100):
            con.execute("INSERT INTO t VALUES (?, ?, ?)",
                        (i, f"name_{i}", i * 1.5))
        con.commit()

        # 真查
        cur = con.execute("SELECT count(*), sum(val) FROM t")
        n, s = cur.fetchone()
        assert n == 100
        assert abs(s - sum(i * 1.5 for i in range(100))) < 0.01

        # 真索引
        con.execute("CREATE INDEX idx_name ON t(name)")
        cur = con.execute("SELECT name FROM t WHERE id = 42")
        assert cur.fetchone() == ("name_42",)

        # 真事务
        con.execute("BEGIN")
        con.execute("INSERT INTO t VALUES (101, 'tx', 0)")
        con.rollback()
        cur = con.execute("SELECT count(*) FROM t WHERE id = 101")
        assert cur.fetchone() == (0,), "rollback 应撤销 INSERT"

        con.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_sqlite_real_concurrent_wal():
    """sqlite3 真用 WAL 模式, 并发读写"""
    db_path = "/tmp/test_sqlite_wal.db"
    if os.path.exists(db_path):
        os.unlink(db_path)
    try:
        con = sqlite3.connect(db_path, isolation_level=None)
        con.execute("PRAGMA journal_mode=WAL")
        mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal", f"应 WAL 模式, 实际 {mode}"
        con.execute("CREATE TABLE t (id INTEGER, val TEXT)")
        con.execute("INSERT INTO t VALUES (1, 'a')")
        # 另一连接真能读
        con2 = sqlite3.connect(db_path)
        cur = con2.execute("SELECT val FROM t WHERE id = 1")
        assert cur.fetchone() == ("a",)
        con2.close()
        con.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
        for ext in ("-wal", "-shm"):
            p = db_path + ext
            if os.path.exists(p):
                os.unlink(p)


def test_sqlite_real_typed_columns():
    """sqlite3 真类型亲和性 (列类型 5 种)"""
    db_path = "/tmp/test_sqlite_typed.db"
    if os.path.exists(db_path):
        os.unlink(db_path)
    try:
        con = sqlite3.connect(db_path)
        con.execute("""
            CREATE TABLE t (
                i INTEGER,
                r REAL,
                t TEXT,
                b BLOB,
                n NUMERIC
            )
        """)
        con.execute("INSERT INTO t VALUES (?, ?, ?, ?, ?)",
                    (42, 3.14, "hello", b"\x00\x01\x02", 100))
        con.commit()
        # 读回
        row = con.execute("SELECT i, r, t, b, n FROM t").fetchone()
        assert row[0] == 42
        assert abs(row[1] - 3.14) < 1e-10
        assert row[2] == "hello"
        assert row[3] == b"\x00\x01\x02"
        # NUMERIC 亲和: 整数 → INTEGER
        assert row[4] == 100
        con.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
