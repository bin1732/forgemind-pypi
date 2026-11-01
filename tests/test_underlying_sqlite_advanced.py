# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""真 sqlite3 高级"""
import os
import sqlite3
import tempfile
import pytest

@pytest.fixture
def conn():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    c = sqlite3.connect(path)
    yield c, path
    c.close()
    os.unlink(path)

def test_sqlite_join_inner(conn):
    c, _ = conn
    c.execute("CREATE TABLE users (id INT, name TEXT)")
    c.execute("INSERT INTO users VALUES (1, 'Alice'), (2, 'Bob'), (3, 'Carol')")
    c.execute("CREATE TABLE orders (id INT, user_id INT, amount REAL)")
    c.execute("INSERT INTO orders VALUES (1, 1, 100.0), (2, 1, 50.0), (3, 2, 200.0)")
    rows = c.execute("""
        SELECT u.name, SUM(o.amount) as total
        FROM users u INNER JOIN orders o ON u.id = o.user_id
        GROUP BY u.id ORDER BY total DESC
    """).fetchall()
    assert rows == [("Bob", 200.0), ("Alice", 150.0)]

def test_sqlite_left_join(conn):
    c, _ = conn
    c.execute("CREATE TABLE users (id INT, name TEXT)")
    c.execute("INSERT INTO users VALUES (1, 'Alice'), (2, 'Bob'), (3, 'Carol')")
    c.execute("CREATE TABLE orders (id INT, user_id INT, amount REAL)")
    c.execute("INSERT INTO orders VALUES (1, 1, 100.0)")
    rows = c.execute("""
        SELECT u.name, COALESCE(SUM(o.amount), 0) as total
        FROM users u LEFT JOIN orders o ON u.id = o.user_id
        GROUP BY u.id ORDER BY u.id
    """).fetchall()
    assert rows == [("Alice", 100.0), ("Bob", 0), ("Carol", 0)]

def test_sqlite_having(conn):
    c, _ = conn
    c.execute("CREATE TABLE sales (id INT, region TEXT, amount REAL)")
    c.executemany("INSERT INTO sales VALUES (?, ?, ?)", [
        (1, "east", 100), (2, "east", 200), (3, "east", 50),
        (4, "west", 300), (5, "west", 100),
    ])
    rows = c.execute("""
        SELECT region, SUM(amount) as total
        FROM sales GROUP BY region HAVING SUM(amount) > 200
    """).fetchall()
    regions = sorted(r[0] for r in rows)
    assert regions == ["east", "west"]

def test_sqlite_window_function(conn):
    c, _ = conn
    c.execute("CREATE TABLE sales (region TEXT, amount REAL)")
    c.executemany("INSERT INTO sales VALUES (?, ?)", [
        ("east", 100), ("east", 200), ("east", 50),
        ("west", 300), ("west", 100),
    ])
    rows = c.execute("""
        SELECT region, amount,
               ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC) as rank
        FROM sales ORDER BY region, rank
    """).fetchall()
    assert rows[0] == ("east", 200, 1)
    assert rows[3] == ("west", 300, 1)

def test_sqlite_window_running_total(conn):
    c, _ = conn
    c.execute("CREATE TABLE t (n INT)")
    c.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,), (4,)])
    rows = c.execute("""
        SELECT n, SUM(n) OVER (ORDER BY n) as cum FROM t
    """).fetchall()
    assert rows == [(1, 1), (2, 3), (3, 6), (4, 10)]

def test_sqlite_cte_recursive(conn):
    c, _ = conn
    cur = c.execute("""
        WITH RECURSIVE fib(n, a, b) AS (
            SELECT 1, 0, 1
            UNION ALL
            SELECT n+1, b, a+b FROM fib WHERE n < 10
        )
        SELECT n, a FROM fib
    """)
    rows = cur.fetchall()
    assert [r[1] for r in rows] == [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]

def test_sqlite_subquery_exists(conn):
    c, _ = conn
    c.execute("CREATE TABLE users (id INT, name TEXT)")
    c.execute("INSERT INTO users VALUES (1, 'A'), (2, 'B')")
    c.execute("CREATE TABLE orders (user_id INT)")
    c.execute("INSERT INTO orders VALUES (1)")
    rows = c.execute("""
        SELECT name FROM users u
        WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)
    """).fetchall()
    assert rows == [("A",)]

def test_sqlite_case_when(conn):
    c, _ = conn
    c.execute("CREATE TABLE t (n INT)")
    c.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,), (4,), (5,)])
    rows = c.execute("""
        SELECT n, CASE
            WHEN n < 3 THEN 'small'
            WHEN n = 3 THEN 'medium'
            ELSE 'large' END as size
        FROM t
    """).fetchall()
    assert rows == [
        (1, "small"), (2, "small"), (3, "medium"), (4, "large"), (5, "large"),
    ]

def test_sqlite_index_real_used(conn):
    c, _ = conn
    c.execute("CREATE TABLE t (id INT PRIMARY KEY, val TEXT)")
    c.executemany("INSERT INTO t VALUES (?, ?)", [(i, f"v{i}") for i in range(1000)])
    c.execute("CREATE INDEX idx_val ON t(val)")
    plan = c.execute("EXPLAIN QUERY PLAN SELECT * FROM t WHERE val = 'v500'").fetchall()
    plan_str = " ".join(str(r) for r in plan)
    assert "USING INDEX" in plan_str or "USING COVERING INDEX" in plan_str

def test_sqlite_savepoint_rollback(conn):
    c, _ = conn
    c.execute("CREATE TABLE t (n INT)")
    c.execute("INSERT INTO t VALUES (1)")
    c.execute("SAVEPOINT s1")
    c.execute("INSERT INTO t VALUES (2)")
    c.execute("INSERT INTO t VALUES (3)")
    c.execute("ROLLBACK TO s1")
    rows = c.execute("SELECT n FROM t").fetchall()
    assert rows == [(1,)]

def test_sqlite_fts5_search(conn):
    c, _ = conn
    c.execute("CREATE VIRTUAL TABLE docs USING fts5(title, body)")
    c.executemany("INSERT INTO docs VALUES (?, ?)", [
        ("Python tutorial", "Learn Python programming language"),
        ("Java tutorial", "Java is also a programming language"),
        ("Cooking", "How to cook pasta"),
    ])
    rows = c.execute("SELECT title FROM docs WHERE docs MATCH 'python'").fetchall()
    assert "Python tutorial" in [r[0] for r in rows]

def test_sqlite_json1_extension(conn):
    c, _ = conn
    c.execute("CREATE TABLE t (data TEXT)")
    c.execute("INSERT INTO t VALUES (?)", ('{"name": "Alice", "age": 30}',))
    c.execute("INSERT INTO t VALUES (?)", ('{"name": "Bob", "age": 25}',))
    rows = c.execute("SELECT json_extract(data, '$.name') FROM t ORDER BY json_extract(data, '$.age')").fetchall()
    assert rows == [("Bob",), ("Alice",)]

def test_sqlite_generate_series(conn):
    c, _ = conn
    rows = c.execute("""
        WITH RECURSIVE cnt(x) AS (
            SELECT 1 UNION ALL SELECT x+1 FROM cnt WHERE x < 100
        )
        SELECT SUM(x) FROM cnt
    """).fetchone()[0]
    assert rows == 5050

def test_sqlite_in_memory_temp_db():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE t (n INT)")
    c.execute("INSERT INTO t VALUES (1), (2), (3)")
    rows = c.execute("SELECT * FROM t").fetchall()
    assert rows == [(1,), (2,), (3,)]
    c.close()
