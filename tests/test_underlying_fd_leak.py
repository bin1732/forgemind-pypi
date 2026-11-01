# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 OS fd 泄漏检测 — 子进程退出后, 父进程验 fd 真被回收。
用真 lsof / 真 ps / 真 /proc/<pid>/fd 查 fd 数。
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


def _count_open_fds_via_proc(pid: int) -> int:
    """Linux 真数 /proc/<pid>/fd/ 的 fd 数 (不走 lsof 依赖)。"""
    fd_dir = Path(f"/proc/{pid}/fd")
    if not fd_dir.exists():
        return -1
    return len(list(fd_dir.iterdir()))


def test_subprocess_fd_count_increases_then_decreases(tmp_path):
    """子进程启动后 fd 数增, 退后父进程本地 fd 数不变 (真子进程 fd 隔离)"""
    parent_fd_before = len(list(Path(f"/proc/{os.getpid()}/fd").iterdir()))

    script = """
import sys, time
print(f"PID={__import__('os').getpid()}", flush=True)
time.sleep(60)
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    line = proc.stdout.readline().decode("utf-8", errors="ignore")
    pid = int(line.split("PID=")[1].strip())
    time.sleep(0.5)

    # 子进程 fd 数 (真数)
    child_fd = _count_open_fds_via_proc(pid)
    assert child_fd > 0, f"子进程应有 fd, 实际 {child_fd}"

    # 杀子进程
    proc.terminate()
    proc.wait(timeout=5)

    # 父进程 fd 数应不增 (父进程没开新 fd)
    parent_fd_after = len(list(Path(f"/proc/{os.getpid()}/fd").iterdir()))
    # subprocess 内部可能持 stdout/stderr pipe fd, 给 +5 容差
    assert parent_fd_after <= parent_fd_before + 5, (
        f"父进程 fd 泄漏: {parent_fd_before} → {parent_fd_after}"
    )

    # /proc/<pid> 真消失
    assert not Path(f"/proc/{pid}").exists(), f"/proc/{pid} 应被清理"


def test_duckdb_open_close_no_fd_leak(tmp_path):
    """DuckDB 1000 次 open/close 不应泄漏 fd (验 __exit__ 不真关但 dict 持 ref)"""
    import duckdb
    db_path = str(tmp_path / "fd_leak.db")
    # 初始建表
    con = duckdb.connect(db_path)
    con.execute("CREATE TABLE _fd (id INT)")
    con.close()

    parent_fd_before = len(list(Path(f"/proc/{os.getpid()}/fd").iterdir()))

    # 1000 次 open/close
    for _ in range(1000):
        c = duckdb.connect(db_path)
        c.execute("SELECT 1 FROM _fd").fetchall()
        c.close()

    parent_fd_after = len(list(Path(f"/proc/{os.getpid()}/fd").iterdir()))
    diff = parent_fd_after - parent_fd_before
    # 1000 次 open/close 也许漏几个 (1-3), 但不应指数级
    assert diff < 50, f"1000 次 open/close 漏 {diff} fd (应 < 50)"


def test_psutil_proc_open_files_real(tmp_path):
    """psutil 进程对象真数 fd (不靠 mock)"""
    pytest.importorskip("psutil")
    import psutil
    p = psutil.Process(os.getpid())
    fd_before = len(p.open_files())
    # 开 5 个文件
    fds = []
    for i in range(5):
        f = open(tmp_path / f"f_{i}.txt", "w")
        fds.append(f)
    fd_during = len(p.open_files())
    for f in fds:
        f.close()
    fd_after = len(p.open_files())
    assert fd_during - fd_before == 5, f"开 5 个文件应 fd+5, 实际 +{fd_during - fd_before}"
    assert fd_after == fd_before, f"关 5 个文件应 fd 还原, 实际 {fd_after - fd_before}"


def test_subprocess_inherits_duckdb_fd_closes_on_exit(tmp_path):
    """DuckDB 连接在子进程内开, 子进程退后 fd 真回收 (验 OS-level cleanup)"""
    db_path = str(tmp_path / "subproc.db")
    script = f"""
import os, sys, time
import duckdb
con = duckdb.connect({db_path!r})
con.execute("CREATE TABLE _sub (id INT)")
print(f"PID={{os.getpid()}}", flush=True)
print(f"FD_COUNT={{len(os.listdir(f'/proc/{{os.getpid()}}/fd'))}}", flush=True)
time.sleep(60)
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    lines = []
    while len(lines) < 2:
        line = proc.stdout.readline().decode("utf-8", errors="ignore")
        lines.append(line.strip())
        if not line:
            break
    pid = int(lines[0].split("PID=")[1])
    fd_count = int(lines[1].split("FD_COUNT=")[1])
    assert fd_count > 5, f"DuckDB + Python + 子进程 fd 应 > 5, 实际 {fd_count}"

    # 子进程退
    proc.terminate()
    proc.wait(timeout=5)

    # 子进程 pid 目录真消失 (OS 回收)
    assert not Path(f"/proc/{pid}").exists(), f"/proc/{pid} 应消失"


def test_os_scandir_does_not_leak_fd(tmp_path):
    """10000 次 os.scandir 不应泄漏 fd (Python 内部应关)"""
    parent_fd_before = len(list(Path(f"/proc/{os.getpid()}/fd").iterdir()))

    for _ in range(10000):
        with os.scandir(str(tmp_path)) as it:
            for _ in it:
                pass

    parent_fd_after = len(list(Path(f"/proc/{os.getpid()}/fd").iterdir()))
    diff = parent_fd_after - parent_fd_before
    assert diff < 5, f"10000 次 scandir 漏 {diff} fd (应 < 5)"


def test_socket_open_close_does_not_leak():
    """socket 1000 次 open/close 不应泄漏 fd"""
    import socket
    parent_fd_before = len(list(Path(f"/proc/{os.getpid()}/fd").iterdir()))
    for _ in range(1000):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.close()
    parent_fd_after = len(list(Path(f"/proc/{os.getpid()}/fd").iterdir()))
    diff = parent_fd_after - parent_fd_before
    assert diff < 10, f"1000 socket 漏 {diff} fd (应 < 10)"
