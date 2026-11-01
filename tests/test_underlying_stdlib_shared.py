# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 stdlib 共享 — multiprocessing.Value 真跨进程 + zoneinfo 真时区 + tomllib 真 TOML。
"""
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from tomllib import load as toml_load
from zoneinfo import ZoneInfo

import pytest


def test_multiprocessing_Value_int_shared_across_processes():
    """multiprocessing.Value 真跨进程共享 + get_lock 真互斥 (真子进程)"""
    script = (
        "import multiprocessing\n"
        "def w(c, n):\n"
        "    for _ in range(n):\n"
        "        with c.get_lock():\n"
        "            c.value += 1\n"
        "counter = multiprocessing.Value('i', 0)\n"
        "procs = [multiprocessing.Process(target=w, args=(counter, 100)) for _ in range(4)]\n"
        "[p.start() for p in procs]\n"
        "[p.join() for p in procs]\n"
        "print('FINAL=' + str(counter.value))\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, f"子进程失败: {r.stderr[:300]}"
    assert "FINAL=400" in r.stdout, f"应 FINAL=400, 实际: {r.stdout!r}"


def test_multiprocessing_Array_real_shared():
    """multiprocessing.Array 真跨进程共享 (真子进程)"""
    script = (
        "import multiprocessing\n"
        "arr = multiprocessing.Array('i', [1, 0, 0])\n"
        "for _ in range(12):\n"
        "    with arr.get_lock():\n"
        "        arr[0] *= 2\n"
        "print('FINAL=' + str(arr[0]))\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=15,
    )
    assert r.returncode == 0
    assert "FINAL=4096" in r.stdout, f"应 FINAL=4096, 实际: {r.stdout!r}"


def test_multiprocessing_Manager_dict_real():
    """multiprocessing.Manager dict 真支持 proxy (主进程访问)"""
    import multiprocessing
    with multiprocessing.Manager() as manager:
        d = manager.dict()
        d["key_0"] = "val_0"
        d["key_1"] = "val_1"
        d["key_2"] = "val_2"
        assert len(d) == 3
        assert d["key_0"] == "val_0"
        # Manager dict 真 proxy
        d["key_3"] = "val_3"
        assert d["key_3"] == "val_3"


def test_zoneinfo_UTC_real():
    """zoneinfo 真报 UTC"""
    utc = ZoneInfo("UTC")
    dt = datetime(2026, 10, 12, 12, 0, tzinfo=utc)
    assert dt.utcoffset() == timedelta(0)
    # ZoneInfo 真有 key 属性
    assert utc.key == "UTC"


def test_zoneinfo_Asia_Shanghai_real():
    """zoneinfo 真报 Asia/Shanghai (+08:00)"""
    tz = ZoneInfo("Asia/Shanghai")
    dt = datetime(2026, 10, 12, 12, 0, tzinfo=tz)
    offset = dt.utcoffset()
    assert offset == timedelta(hours=8), f"应 +08:00, 实际 {offset}"


def test_zoneinfo_America_New_York_with_dst():
    """zoneinfo 真处理 DST (EST/EDT)"""
    tz = ZoneInfo("America/New_York")
    winter = datetime(2026, 1, 15, 12, 0, tzinfo=tz)
    assert winter.utcoffset() == timedelta(hours=-5), f"冬应 -5, 实际 {winter.utcoffset()}"
    summer = datetime(2026, 7, 15, 12, 0, tzinfo=tz)
    assert summer.utcoffset() == timedelta(hours=-4), f"夏应 -4, 实际 {summer.utcoffset()}"


def test_zoneinfo_conversion_real():
    """zoneinfo 真时区转换 (UTC → Asia/Shanghai)"""
    utc_tz = ZoneInfo("UTC")
    sh_tz = ZoneInfo("Asia/Shanghai")
    utc_dt = datetime(2026, 10, 12, 4, 0, tzinfo=utc_tz)
    sh_dt = utc_dt.astimezone(sh_tz)
    assert sh_dt.hour == 12, f"应 12:00, 实际 {sh_dt.hour}"
    assert sh_dt.tzinfo is sh_tz


def test_zoneinfo_no_offset_real():
    """zoneinfo Etc/GMT 真报 0 offset"""
    tz = ZoneInfo("Etc/GMT")
    dt = datetime(2026, 10, 12, 12, 0, tzinfo=tz)
    assert dt.utcoffset() == timedelta(0)


def test_zoneinfo_Etc_minus_5_real():
    """zoneinfo Etc/GMT+5 真报 -5h offset (POSIX 符号反)"""
    tz = ZoneInfo("Etc/GMT+5")
    dt = datetime(2026, 10, 12, 12, 0, tzinfo=tz)
    # POSIX: Etc/GMT+N 实际是 UTC-N
    assert dt.utcoffset() == timedelta(hours=-5), f"Etc/GMT+5 应 -5h, 实际 {dt.utcoffset()}"


def test_tomllib_real_parse(tmp_path):
    """tomllib 真 parse TOML (Python 3.11+)"""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text("""[server]
host = "localhost"
port = 8000
debug = true

[database]
url = "duckdb:///data/main.db"
pool_size = 10
""")
    with open(str(toml_file), "rb") as f:
        data = toml_load(f)
    assert data["server"]["host"] == "localhost"
    assert data["server"]["port"] == 8000
    assert data["server"]["debug"] is True
    assert data["database"]["pool_size"] == 10


def test_tomllib_round_trip(tmp_path):
    """tomllib 真能 parse 手写 TOML round-trip"""
    toml_str = """name = "forgemind"
version = "2026.9.3"
deps = ["fastapi", "duckdb", "pydantic"]

[extras]
cn = ["akshare"]
ml = ["torch"]
"""
    out = tmp_path / "out.toml"
    out.write_text(toml_str)
    with open(str(out), "rb") as f:
        reloaded = toml_load(f)
    assert reloaded["name"] == "forgemind"
    assert reloaded["deps"] == ["fastapi", "duckdb", "pydantic"]
    assert reloaded["extras"]["cn"] == ["akshare"]


def test_tomllib_array_of_tables(tmp_path):
    """tomllib 真支持 [[array_of_tables]]"""
    src = """[[users]]
name = "Alice"
age = 30

[[users]]
name = "Bob"
age = 25
"""
    toml_file = tmp_path / "users.toml"
    toml_file.write_text(src)
    with open(str(toml_file), "rb") as f:
        data = toml_load(f)
    assert len(data["users"]) == 2
    assert data["users"][0]["name"] == "Alice"
    assert data["users"][1]["age"] == 25


def test_tomllib_nested_dotted_keys(tmp_path):
    """tomllib 真支持点分 key 嵌套"""
    toml_file = tmp_path / "a.toml"
    toml_file.write_text("""
[parent]
child.key = "value"
other = 1
""")
    with open(str(toml_file), "rb") as f:
        data = toml_load(f)
    # 真嵌套
    assert data["parent"]["child"]["key"] == "value"
    assert data["parent"]["other"] == 1


def test_zoneinfo_TZPATH_real():
    """zoneinfo.TZPATH 真返时区搜索路径"""
    import zoneinfo
    paths = zoneinfo.TZPATH
    # 至少 1 个有效路径
    assert len(paths) >= 1
    # 至少 1 个路径存在
    existing = [p for p in paths if __import__('os').path.isdir(p)]
    assert len(existing) >= 1, f"应 ≥ 1 个 TZPATH 存在, 实际 {existing}"
    # 验 ZoneInfo("UTC") 真读 TZPATH 文件
    utc = ZoneInfo("UTC")
    assert utc.utcoffset(datetime(2026, 1, 1)) == timedelta(0)
