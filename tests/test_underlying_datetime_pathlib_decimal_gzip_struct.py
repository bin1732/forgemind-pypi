# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 datetime 真 (replace 真 / timedelta add 真) + 真 pathlib 真 (cwd() / home() / resolve() 真) + 真 decimal 真 (quantize 真) + 真 gzip 真 (mtime 进阶) + 真 struct 真 (nested 进阶) + 真 ipaddress 真.
全 stdlib, 零模拟。
"""
import datetime
import pathlib
import decimal
import gzip
import struct
import ipaddress
import os
import time
import tempfile
import pytest


# ======================== datetime 进阶 ========================
def test_datetime_replace():
    """真 datetime replace 真"""
    d = datetime.datetime(2024, 1, 15, 10, 30, 45)
    # replace year
    d2 = d.replace(year=2025)
    assert d2.year == 2025
    assert d2.month == 1
    assert d2.day == 15


def test_datetime_timedelta_add():
    """真 timedelta add 进阶"""
    d = datetime.datetime(2024, 1, 15)
    delta = datetime.timedelta(days=30, hours=12)
    d2 = d + delta
    # 1月+30天 = 2月14
    assert d2.month == 2
    assert d2.day == 14
    # 时
    assert d2.hour == 12


def test_datetime_timedelta_total_seconds():
    """真 timedelta total_seconds 真"""
    delta = datetime.timedelta(days=1, hours=2, minutes=30)
    # 1*86400 + 2*3600 + 30*60 = 86400+7200+1800 = 95400
    assert delta.total_seconds() == 95400


def test_datetime_date_weekday():
    """真 date weekday 真"""
    d = datetime.date(2024, 1, 15)  # Monday
    assert d.weekday() == 0  # Monday = 0
    assert d.isoweekday() == 1  # ISO Monday = 1


def test_datetime_isoformat():
    """真 isoformat 真"""
    d = datetime.datetime(2024, 1, 15, 10, 30, 45)
    # 2024-01-15T10:30:45
    assert "2024-01-15" in d.isoformat()
    assert "10:30:45" in d.isoformat()


# ======================== pathlib 进阶 ========================
def test_pathlib_cwd():
    """真 cwd 真"""
    cwd = pathlib.Path.cwd()
    assert isinstance(cwd, pathlib.Path)
    assert cwd.is_dir()
    assert cwd.exists()


def test_pathlib_home():
    """真 home 真"""
    home = pathlib.Path.home()
    assert isinstance(home, pathlib.Path)
    # home 必存在 (sandbox 也)
    assert home.exists()


def test_pathlib_resolve():
    """真 resolve 真"""
    with tempfile.TemporaryDirectory() as d:
        sub = pathlib.Path(d) / "subdir"
        sub.mkdir()
        # resolve
        resolved = sub.resolve()
        assert resolved.exists()
        assert resolved.is_absolute()


def test_pathlib_with_suffix():
    """真 with_suffix 进阶"""
    p = pathlib.Path("/tmp/test.txt")
    p2 = p.with_suffix(".md")
    # .md
    assert p2.suffix == ".md"
    assert p2.name == "test.md"


def test_pathlib_with_name():
    """真 with_name 真"""
    p = pathlib.Path("/tmp/old.txt")
    p2 = p.with_name("new.txt")
    assert p2.name == "new.txt"


# ======================== decimal 进阶 ========================
def test_decimal_quantize():
    """真 quantize 真"""
    d = decimal.Decimal("1.2345")
    # 量化到 2 位
    d2 = d.quantize(decimal.Decimal("0.01"))
    assert d2 == decimal.Decimal("1.23")
    # 量化到 0 位
    d3 = d.quantize(decimal.Decimal("1"))
    assert d3 == decimal.Decimal("1")


def test_decimal_normalize():
    """真 normalize 真"""
    d = decimal.Decimal("1.2300")
    # normalize 去尾 0
    d2 = d.normalize()
    assert d2 == decimal.Decimal("1.23")


# ======================== gzip 进阶 ========================
def test_gzip_mtime_attribute():
    """真 gzip mtime 真在 header bytes 4-7"""
    import gzip as _gzip
    import struct as _struct
    with tempfile.NamedTemporaryFile(suffix=".gz", delete=False) as f:
        path = f.name
    try:
        mtime = 1234567890
        with _gzip.GzipFile(path, "wb", mtime=mtime) as f:
            f.write(b"data")
        # 读 raw bytes
        with open(path, "rb") as f:
            header = f.read(10)
        # bytes 4-7 是 mtime (little-endian uint32)
        mtime_from_header = _struct.unpack("<I", header[4:8])[0]
        assert mtime_from_header == mtime
    finally:
        os.unlink(path)


def test_gzip_text_mode():
    """真 gzip text mode 进阶"""
    with tempfile.NamedTemporaryFile(suffix=".gz", delete=False) as f:
        path = f.name
    try:
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write("中文")
        # 读
        with gzip.open(path, "rt", encoding="utf-8") as f:
            content = f.read()
        assert content == "中文"
    finally:
        os.unlink(path)


# ======================== struct 进阶 ========================
def test_struct_pack_into():
    """真 pack_into 真 buffer 真写"""
    buf = bytearray(8)
    struct.pack_into("<I", buf, 0, 1)
    struct.pack_into("<I", buf, 4, 2)
    # unpack_from
    a = struct.unpack_from("<I", buf, 0)[0]
    b = struct.unpack_from("<I", buf, 4)[0]
    assert a == 1
    assert b == 2


def test_struct_iter_unpack():
    """真 iter_unpack 真"""
    data = struct.pack("<2i", 1, 2)
    data += struct.pack("<2i", 3, 4)
    data += struct.pack("<2i", 5, 6)
    # iter
    results = list(struct.iter_unpack("<2i", data))
    assert len(results) == 3
    assert results[0] == (1, 2)
    assert results[1] == (3, 4)
    assert results[2] == (5, 6)


# ======================== ipaddress 进阶 ========================
def test_ipaddress_is_unspecified():
    """真 is_unspecified 真"""
    assert ipaddress.IPv4Address("0.0.0.0").is_unspecified
    assert ipaddress.IPv6Address("::").is_unspecified
    # 1.1.1.1 不
    assert not ipaddress.IPv4Address("1.1.1.1").is_unspecified


def test_ipaddress_teredo():
    """真 teredo attribute 真"""
    # 2001::/32 is Teredo prefix
    assert ipaddress.IPv6Address("2001::1").teredo is not None
    # 1.1.1.1 IPv4 不
    assert not hasattr(ipaddress.IPv4Address("1.1.1.1"), "teredo")
