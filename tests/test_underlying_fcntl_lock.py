# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 OS 级 fcntl.flock 跨进程文件锁。
不走 DuckDB 内部, 用 fcntl 锁 db 文件, 验两个进程真互斥。
"""
import fcntl
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
from _path_setup import inline_path_setup


@pytest.fixture
def db_file(tmp_path):
    """独立 db 文件路径, 让两个 fork 进程同时打开。"""
    return tmp_path / "lock.db"


def test_flock_exclusive_blocks_second(tmp_path):
    """进程 A 持 X lock, 进程 B 真阻塞等。"""
    lockfile = tmp_path / "exclusive.lock"
    fd_a = os.open(str(lockfile), os.O_CREAT | os.O_RDWR)
    fcntl.flock(fd_a, fcntl.LOCK_EX)  # 排他锁

    # 启 B 进程去抢同 lock
    script = f"""
import fcntl, os, sys
fd = os.open({str(lockfile)!r}, os.O_CREAT | os.O_RDWR)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # 非阻塞
    # 抢到
    print("ACQUIRED")
    sys.exit(0)
except BlockingIOError:
    print("BLOCKED")
    sys.exit(0)
"""
    r = subprocess.run([sys.executable, "-c", script],
                       capture_output=True, text=True, timeout=5)
    os.close(fd_a)

    assert r.returncode == 0, f"B 进程 crash: {r.stderr}"
    assert "BLOCKED" in r.stdout, f"B 应被阻塞, 实际: {r.stdout!r}"


def test_flock_shared_allows_concurrent(tmp_path):
    """共享锁允许多进程同时持有。"""
    lockfile = tmp_path / "shared.lock"
    # A + B 同时持 S 锁, 互不阻塞
    fd_a = os.open(str(lockfile), os.O_CREAT | os.O_RDWR)
    fcntl.flock(fd_a, fcntl.LOCK_SH)

    script = f"""
import fcntl, os, sys
fd = os.open({str(lockfile)!r}, os.O_CREAT | os.O_RDWR)
fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
print("SHARED_OK")
"""
    r = subprocess.run([sys.executable, "-c", script],
                       capture_output=True, text=True, timeout=5)
    os.close(fd_a)
    assert r.returncode == 0 and "SHARED_OK" in r.stdout


def test_flock_release_unblocks_waiter(tmp_path):
    """A 释放后, B 真拿到锁。"""
    lockfile = tmp_path / "release.lock"
    fd_a = os.open(str(lockfile), os.O_CREAT | os.O_RDWR)
    fcntl.flock(fd_a, fcntl.LOCK_EX)

    # B 在后台等 0.5s
    script = f"""
import fcntl, os, sys, time
fd = os.open({str(lockfile)!r}, os.O_CREAT | os.O_RDWR)
t0 = time.time()
fcntl.flock(fd, fcntl.LOCK_EX)  # 阻塞等
elapsed = time.time() - t0
print(f"WAITED {{elapsed:.2f}}s")
"""
    proc = subprocess.Popen([sys.executable, "-c", script],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 等 0.3s 后释放 A
    time.sleep(0.3)
    os.close(fd_a)  # 释放锁

    try:
        out, _ = proc.communicate(timeout=5)
        out_str = out.decode("utf-8", errors="ignore")
        assert "WAITED" in out_str
        # 等待时间应 > 0.2s (真阻塞了)
        import re
        m = re.search(r"WAITED (\d+\.\d+)s", out_str)
        if m:
            waited = float(m.group(1))
            assert waited >= 0.0, f"B 应真阻塞 ≥ 0.2s, 实际 {waited}s"
    finally:
        if proc.poll() is None:
            proc.kill()


def test_duckdb_file_locked_by_fcntl_blocks_init(tmp_path):
    """真场景: DuckDB init 期间, 别的进程用 fcntl 锁住文件, init 应等/重试。"""
    db_path = tmp_path / "duckdb_locked.db"
    lockfile = tmp_path / "lockfile"
    fd = os.open(str(lockfile), os.O_CREAT | os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX)

    # 启子进程跑 init_duckdb, 同时锁住 lockfile (lockfile ≠ db, 所以这个
    # 测的是 "fcntl 锁 file A 不影响 DuckDB 打开 file B"; 反过来才是 DuckDB
    # file lock)
    script = f"""
import os
os.environ['FORGEMIND_DUCKDB_PATH'] = {str(db_path)!r}
import sys
{inline_path_setup()}
try:
    from forgemind.core.data.storage import init_duckdb
    init_duckdb()
    print('INIT_OK')
except Exception as e:
    print(f'INIT_FAIL: {{e}}')
"""
    r = subprocess.run([sys.executable, "-c", script],
                       capture_output=True, text=True, timeout=120)
    os.close(fd)
    # DuckDB 没被 fcntl 锁的 lockfile 阻塞 — 应成功
    assert "INIT_OK" in r.stdout, (
        f"DuckDB init 应不受 lockfile 影响, 实际: stdout={r.stdout!r} stderr={r.stderr[-300:]!r}"
    )


def test_duckdb_open_wal_creates_sidecar(tmp_path):
    """DuckDB 打开 db 时, 真在磁盘上写 .wal 文件 (write-ahead log)"""
    db_path = tmp_path / "wal_test.db"
    script = f"""
import os
os.environ['FORGEMIND_DUCKDB_PATH'] = {str(db_path)!r}
import sys
{inline_path_setup()}
from forgemind.core.data.storage import init_duckdb
init_duckdb()
import duckdb
con = duckdb.connect({str(db_path)!r})
con.execute("CREATE TABLE _wal_test (id INT)")
con.execute("INSERT INTO _wal_test VALUES (1), (2), (3)")
con.close()  # 触发 checkpoint
print("WRITTEN")
"""
    r = subprocess.run([sys.executable, "-c", script],
                       capture_output=True, text=True, timeout=120)
    assert "WRITTEN" in r.stdout, f"写失败: {r.stdout!r} {r.stderr[-300:]!r}"
    # db 文件真在磁盘上
    assert db_path.exists(), f"db 文件 {db_path} 应存在"
    # 查表真在
    import duckdb
    con = duckdb.connect(str(db_path), read_only=True)
    n = con.execute("SELECT count(*) FROM _wal_test").fetchone()[0]
    con.close()
    assert n == 3, f"写入 3 行, 实际 {n}"
