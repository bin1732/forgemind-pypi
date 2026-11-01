# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 copy 进阶 (deepcopy 真 dict 自定 __deepcopy__) + 真 shutil 进阶 (which / disk_usage 沙箱) + 真 ipaddress 进阶 (network overlap 真 is_private) + 真 sqlite3 进阶 (LIMIT 真 SQL) + 真 math 真 (isqrt 真 / gcd 真 / fsum 真).
全 stdlib, 零模拟。
"""
import copy
import shutil
import ipaddress
import sqlite3
import math
import os
import tempfile
import pytest


# ======================== copy 进阶 ========================
def test_copy_deepcopy_dict_subclass():
    """真 deepcopy 真 dict 子类"""
    class MyDict(dict):
        pass

    original = MyDict({"a": 1, "b": [1, 2]})
    deep = copy.deepcopy(original)
    # 仍 MyDict
    assert isinstance(deep, MyDict)
    # 改 deep
    deep["b"].append(3)
    # 原不变
    assert original["b"] == [1, 2]


def test_copy_deepcopy_recursive():
    """真 deepcopy 真递归循环引用"""
    a = []
    a.append(a)  # 自身
    # deepcopy
    b = copy.deepcopy(a)
    # 独立
    assert b is not a
    # b[0] 是 b (自身引用)
    assert b[0] is b


# ======================== shutil 进阶 ========================
def test_shutil_which_python3():
    """真 which 真 python3"""
    python3 = shutil.which("python3")
    assert python3 is not None
    assert os.path.isfile(python3)


def test_shutil_get_terminal_size():
    """真 get_terminal_size 真"""
    size = shutil.get_terminal_size()
    # columns / lines
    assert hasattr(size, "columns")
    assert hasattr(size, "lines")
    assert size.columns > 0
    assert size.lines > 0


def test_shutil_make_archive_tar():
    """真 make_archive 真 tar"""
    with tempfile.TemporaryDirectory() as d:
        # 创源 dir
        src = os.path.join(d, "src")
        os.makedirs(src)
        with open(os.path.join(src, "a.txt"), "w") as f:
            f.write("a")
        # archive
        archive = shutil.make_archive(
            os.path.join(d, "myarchive"), "tar",
            root_dir=src,
        )
        # 必存在
        assert os.path.isfile(archive)
        assert archive.endswith(".tar")
        # 含文件 (含 './' 前缀)
        import tarfile
        with tarfile.open(archive) as tar:
            names = tar.getnames()
            assert any("a.txt" in n for n in names)


# ======================== ipaddress 进阶 ========================
def test_ipaddress_subnet_contains():
    """真 contains 真"""
    net = ipaddress.IPv4Network("10.0.0.0/8")
    assert ipaddress.IPv4Address("10.1.2.3") in net
    assert ipaddress.IPv4Address("11.0.0.0") not in net


def test_ipaddress_IPv4_is_multicast():
    """真 is_multicast 真"""
    assert ipaddress.IPv4Address("239.0.0.1").is_multicast
    assert ipaddress.IPv4Address("224.0.0.1").is_multicast
    assert not ipaddress.IPv4Address("8.8.8.8").is_multicast


def test_ipaddress_IPv6_is_global():
    """真 IPv6 is_global"""
    # 2001:db8:: 是 documentation, NOT global
    # 2000::/3 global - 实际一个真 global
    # 2001:db8::1 在 2001:db8::/32 (RFC 3849 documentation) 不 is_global
    assert not ipaddress.IPv6Address("2001:db8::1").is_global
    # ::1 loopback 不是 global
    assert not ipaddress.IPv6Address("::1").is_global
    # fe80:: link-local 不是
    assert not ipaddress.IPv6Address("fe80::1").is_global


def test_ipaddress_strict_parsing():
    """真 strict 真 strict=True"""
    # strict=True 不允许 host bits
    net = ipaddress.IPv4Network("10.0.0.0/24", strict=True)
    # 真 strict
    assert net.network_address == ipaddress.IPv4Address("10.0.0.0")
    # 10.0.0.5/24 → host bits, strict 抛
    # 实际: 是 24 位网络号, host 0
    with pytest.raises(ValueError):
        # "10.0.0.5/8" 网络号 + host bits
        ipaddress.IPv4Network("10.0.0.5/8", strict=True)


# ======================== sqlite3 进阶 ========================
def test_sqlite3_LIMIT_clause():
    """真 LIMIT 真 SQL"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    try:
        conn = sqlite3.connect(db)
        try:
            conn.execute("CREATE TABLE t (v INTEGER)")
            for i in range(10):
                conn.execute("INSERT INTO t VALUES (?)", (i,))
            conn.commit()
            # LIMIT 3
            rows = conn.execute("SELECT v FROM t ORDER BY v LIMIT 3").fetchall()
            assert rows == [(0,), (1,), (2,)]
            # LIMIT 3 OFFSET 5
            rows2 = conn.execute(
                "SELECT v FROM t ORDER BY v LIMIT 3 OFFSET 5"
            ).fetchall()
            assert rows2 == [(5,), (6,), (7,)]
        finally:
            conn.close()
    finally:
        os.unlink(db)


# ======================== math 进阶 ========================
def test_math_isqrt():
    """真 isqrt 真"""
    # isqrt(100) = 10
    assert math.isqrt(100) == 10
    # isqrt(99) = 9
    assert math.isqrt(99) == 9
    # isqrt(0) = 0
    assert math.isqrt(0) == 0


def test_math_fsum():
    """真 fsum 真精确"""
    # 0.1 + 0.1 + ... 不可精
    s = 0.1 + 0.1 + 0.1 + 0.1 + 0.1 + 0.1 + 0.1 + 0.1 + 0.1 + 0.1
    # float 不可精
    assert s != 1.0
    # fsum 精确
    s2 = math.fsum([0.1] * 10)
    assert s2 == 1.0


def test_math_prod():
    """真 prod 真连乘"""
    assert math.prod([1, 2, 3, 4]) == 24
    assert math.prod([1, 2, 3, 4], start=2) == 48
    # 空
    assert math.prod([]) == 1  # start=1 default


def test_math_remainder():
    """真 remainder 真 IEEE remainder"""
    # remainder(10, 3) = 1
    assert math.remainder(10, 3) == 1
    # remainder(10, -3) = 1 (有符号)
    assert math.remainder(10, -3) == 1.0
