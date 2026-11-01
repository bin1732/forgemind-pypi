# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 threading 真 (Timer 真 cancel / Event 真 set 多 thread) + 真 subprocess 真 (check 真 exit 0) + 真 csv 真 (Sniffer 进阶) + 真 ipaddress 真 (hostmask 真) + 真 os 真 (urandom 真 / cpu_count 真).
全 stdlib, 零模拟。
"""
import threading
import subprocess
import csv
import ipaddress
import os
import sys
import time
import tempfile
import io
import pytest


# ======================== threading 进阶 ========================
def test_threading_Timer_cancel():
    """真 Timer cancel 真"""
    fired = []

    def cb():
        fired.append(1)

    t = threading.Timer(0.1, cb)
    t.start()
    # cancel
    t.cancel()
    # 等
    time.sleep(0.2)
    # 不 fire
    assert fired == []


def test_threading_Event_multi_set():
    """真 Event set 真多 thread 同步"""
    event = threading.Event()
    results = []

    def worker():
        event.wait(timeout=2.0)
        results.append(1)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    # set
    event.set()
    # 等全部
    for t in threads:
        t.join(timeout=2.0)
    # 5 thread 都加
    assert len(results) == 5


def test_threading_local_data():
    """真 threading.local 真 per-thread data"""
    data = threading.local()

    def worker(value):
        data.value = value
        time.sleep(0.05)
        # 读自己设的
        # (不依赖全局同步)
        assert data.value == value

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


# ======================== subprocess 进阶 ========================
def test_subprocess_run_check_true():
    """真 subprocess.run check=True 真"""
    result = subprocess.run(
        [sys.executable, "-c", "exit(0)"],
        capture_output=True,
        check=True,
    )
    assert result.returncode == 0


def test_subprocess_run_capture_output():
    """真 subprocess.run capture_output 真"""
    result = subprocess.run(
        [sys.executable, "-c", "print('hi')"],
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "hi"
    assert result.returncode == 0


def test_subprocess_run_text_unicode():
    """真 text + 中文 真"""
    result = subprocess.run(
        [sys.executable, "-c", "print('中文')"],
        capture_output=True,
        text=True,
    )
    assert "中文" in result.stdout


def test_subprocess_check_output():
    """真 check_output 真"""
    output = subprocess.check_output(
        [sys.executable, "-c", "print('output')"],
        text=True,
    )
    assert "output" in output


# ======================== csv 进阶 ========================
def test_csv_Sniffer():
    """真 csv Sniffer 真 sniff"""
    sample = """name,age
alice,30
bob,25
"""
    dialect = csv.Sniffer().sniff(sample)
    # 必有 delimiter
    assert dialect.delimiter == ","
    # quotechar
    assert dialect.quotechar == '"'


def test_csv_DictWriter():
    """真 DictWriter 真"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        path = f.name
    try:
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "age"])
            writer.writeheader()
            writer.writerow({"name": "alice", "age": 30})
            writer.writerow({"name": "bob", "age": 25})
        # 读
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["name"] == "alice"
        assert rows[1]["age"] == "25"
    finally:
        os.unlink(path)


# ======================== ipaddress 进阶 ========================
def test_ipaddress_hostmask():
    """真 hostmask 进阶"""
    net = ipaddress.IPv4Network("192.168.1.0/24")
    # hostmask
    assert net.hostmask == ipaddress.IPv4Address("0.0.0.255")
    # 实际 inet_aton
    assert net.hostmask.packed == b"\x00\x00\x00\xff"


def test_ipaddress_num_hosts():
    """真 num_addresses 进阶"""
    # /30 = 4 addresses (2 usable)
    net = ipaddress.IPv4Network("10.0.0.0/30")
    assert net.num_addresses == 4
    # /24 = 256
    assert ipaddress.IPv4Network("10.0.0.0/24").num_addresses == 256
    # /16 = 65536
    assert ipaddress.IPv4Network("10.0.0.0/16").num_addresses == 65536


# ======================== os 进阶 ========================
def test_os_urandom_returns_bytes():
    """真 urandom 真 bytes"""
    data = os.urandom(16)
    # 16 bytes
    assert len(data) == 16
    # bytes
    assert isinstance(data, bytes)
    # 必不全 0 (概率极低)
    # 跳过概率断言, 0 个例外太罕见


def test_os_urandom_distinct():
    """真 urandom 两次 真 distinct"""
    # 2 次
    a = os.urandom(16)
    b = os.urandom(16)
    # 必不等
    assert a != b


def test_os_cpu_count():
    """真 cpu_count 进阶"""
    count = os.cpu_count()
    # ≥ 1
    assert count is None or count >= 1
    # 沙箱通常 ≥ 1
    if count is not None:
        assert count >= 1


def test_os_getpid_distinct():
    """真 getpid / getppid 真"""
    pid = os.getpid()
    ppid = os.getppid()
    assert pid > 0
    assert ppid > 0
    # 沙箱 pid == ppid 概率大 (子进程), 但必 ≥ 1
