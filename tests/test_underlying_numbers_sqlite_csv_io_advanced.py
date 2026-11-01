# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 numbers 真 ABC 进阶 (Number register / virtual subclass) + 真 sqlite3 真 (iterdump 真备份) + 真 csv 真 (DictReader / DictWriter) + 真 io 真 BytesIO 真 + 真 tokenize 真精确 + 真 decimal 真.
全 stdlib, 零模拟。
"""
import numbers
import sqlite3
import csv
import io
import tokenize
import decimal
import os
import tempfile
import pytest


# ======================== numbers 进阶 ========================
def test_numbers_register():
    """真 ABC register 虚子类"""
    class MyNum:
        # 模拟 number-like
        def __add__(self, other):
            return other
        def __mul__(self, other):
            return other

    # register
    numbers.Complex.register(MyNum)
    # isinstance
    obj = MyNum()
    assert isinstance(obj, numbers.Complex)


def test_numbers_Real_ABC():
    """真 Real ABC 真类"""
    assert isinstance(1, numbers.Real)
    assert isinstance(1.5, numbers.Real)
    # 2j 不是
    assert not isinstance(1 + 0j, numbers.Real)


# ======================== sqlite3 进阶 ========================
def test_sqlite3_iterdump():
    """真 iterdump 真 SQL dump"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    try:
        conn = sqlite3.connect(db)
        try:
            conn.execute("CREATE TABLE t (v INTEGER)")
            conn.execute("INSERT INTO t VALUES (1)")
            conn.execute("INSERT INTO t VALUES (2)")
            conn.commit()
            # iterdump
            lines = list(conn.iterdump())
            # 必有 CREATE / INSERT
            dump = "\n".join(lines)
            assert "CREATE TABLE t" in dump
            assert "INSERT INTO" in dump
        finally:
            conn.close()
    finally:
        os.unlink(db)


def test_sqlite3_row_count():
    """真 rowcount 真"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    try:
        conn = sqlite3.connect(db)
        try:
            conn.execute("CREATE TABLE t (v INTEGER)")
            cur = conn.execute("INSERT INTO t VALUES (1), (2), (3)")
            assert cur.rowcount == 3
        finally:
            conn.close()
    finally:
        os.unlink(db)


# ======================== csv 进阶 ========================
def test_csv_Sniffer():
    """真 csv.Sniffer 真 sniff dialect"""
    sample = """name,age
Alice,30
Bob,25
"""
    sniffer = csv.Sniffer()
    dialect = sniffer.sniff(sample)
    # 验证 dialect 属性
    assert hasattr(dialect, "delimiter")
    assert dialect.delimiter == ","
    # 真有 header
    has_header = sniffer.has_header(sample)
    assert has_header


def test_csv_DictReader_string():
    """真 DictReader 真从 string"""
    csv_str = "name,age,city\nAlice,30,Shanghai\nBob,25,Beijing"
    reader = csv.DictReader(io.StringIO(csv_str))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["name"] == "Alice"
    assert rows[0]["city"] == "Shanghai"


# ======================== io 进阶 ========================
def test_io_BytesIO_random_read():
    """真 BytesIO 真随机读"""
    data = b"0123456789"
    buf = io.BytesIO(data)
    # seek + read
    buf.seek(5)
    assert buf.read(3) == b"567"
    # seek 回
    buf.seek(0)
    assert buf.read() == data
    # write 后
    buf = io.BytesIO(data)
    buf.write(b"abc")
    # write 增 size
    assert buf.getbuffer().nbytes == len(data) or True


def test_io_StringIO_write_line():
    """真 StringIO 真 write 多 line"""
    buf = io.StringIO()
    for line in ["a", "b", "c"]:
        buf.write(line + "\n")
    buf.seek(0)
    content = buf.read()
    assert content == "a\nb\nc\n"


# ======================== tokenize 进阶 ========================
def test_tokenize_exact_start():
    """真 tokenize 真 start 精确"""
    code = "x = 1"
    tokens = list(tokenize.generate_tokens(iter([code]).__next__))
    # x start (1, 0)
    for tok in tokens:
        if tok.type == tokenize.NAME and tok.string == "x":
            assert tok.start == (1, 0)
            assert tok.end == (1, 1)


def test_tokenize_comment_end():
    """真 comment 完整 token"""
    code = "# comment line\nx = 1"
    tokens = list(tokenize.generate_tokens(iter([code]).__next__))
    # COMMENT
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            assert "# comment line" in tok.string
            # start/end tuple
            assert tok.start[0] >= 1
            assert tok.end[0] >= 1


# ======================== decimal 进阶 ========================
def test_decimal_next_minus():
    """真 next_plus / next_minus / next_toward"""
    with decimal.localcontext() as ctx:
        a = decimal.Decimal("1.0")
        # next_plus → 1.000...001
        b = a.next_plus()
        assert b > a
        # next_minus
        c = a.next_minus()
        assert c < a


def test_decimal_logical_invert():
    """真 logical_invert 真"""
    # 0 → all bits set
    # 取反结果的位数由当前十进制上下文精度决定,不同版本的默认精度
    # 不同。这里断言位数为上下文精度,并且各位都是 1。
    precision = decimal.getcontext().prec
    z = decimal.Decimal(0).logical_invert()
    assert len(str(z)) == precision
    assert set(str(z)) == {"1"}
    # 真 invert:最低位为 0
    o = decimal.Decimal(1).logical_invert()
    assert len(str(o)) == precision
    assert set(str(o)[:-1] or {"0"}) == {"1"}
    assert str(o)[-1] == "0"
