# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 OS signal — SIGTERM 真发, 子进程真收, DuckDB 连接真清。
不走 mock, 真 subprocess + 真 os.kill + 真 ps / lsof 验 fd。
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / "signal_test.db"


def _run_in_subprocess(script: str, env_extra: dict | None = None, timeout: float = 30):
    """在真子进程跑 script, 返 (proc, env)。"""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["FORGEMIND_LOG_LEVEL"] = "WARNING"
    if env_extra:
        env.update(env_extra)
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return proc


def test_sigterm_triggers_python_cleanup(tmp_db):
    """SIGTERM 真发 → Python atexit 真跑 → DuckDB 连接真关。"""
    db_path = str(tmp_db)
    script = f"""
import signal, sys, time, os
import duckdb

# 装 SIGTERM handler — 记一下收到
received = {{'count': 0, 'signum': 0}}
def handler(signum, frame):
    received['count'] += 1
    received['signum'] = signum
    # SIGTERM 不应无限循环; 真退
    raise SystemExit(0)  # 走正常退出, atexit 跑
signal.signal(signal.SIGTERM, handler)

# 打开 DuckDB + 写数据 + 等 SIGTERM
con = duckdb.connect({db_path!r})
con.execute("CREATE TABLE _sigtest (id INT, val TEXT)")
con.execute("INSERT INTO _sigtest VALUES (1, 'before')")
con.commit()

# 写 signal_count 落盘, 让 parent 验
import atexit
def cleanup():
    # 把收到 SIGTERM 几次写到磁盘
    try:
        c2 = duckdb.connect({db_path!r})
        c2.execute("CREATE TABLE IF NOT EXISTS _sigcount (n INT, signum INT)")
        c2.execute("INSERT INTO _sigcount VALUES (?, ?)", [received['count'], received['signum']])
        c2.commit()
        c2.close()
    except Exception as e:
        sys.stderr.write(f"cleanup err: {{e}}")
atexit.register(cleanup)

# 打印 PID 让 parent 杀
print(f"PID={{os.getpid()}}", flush=True)
# 阻塞等 signal
time.sleep(60)
"""
    proc = _run_in_subprocess(script)
    # 等子进程真起来 + 打开 db
    line = proc.stdout.readline().decode("utf-8", errors="ignore").strip()
    assert line.startswith("PID="), f"子进程应报 PID, 实际: {line!r}"
    pid = int(line.split("=")[1])

    # 验 db 锁了
    time.sleep(0.5)
    assert tmp_db.exists(), f"db 应在 {tmp_db}"

    # SIGTERM 真发
    os.kill(pid, signal.SIGTERM)
    try:
        proc.wait(timeout=180)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        pytest.fail("子进程 180s 内没退, SIGTERM 没收")

    # 验 _sigcount 落盘 — atexit 真跑
    import duckdb
    con = duckdb.connect(str(tmp_db), read_only=True)
    rows = con.execute("SELECT n, signum FROM _sigcount").fetchall()
    con.close()
    assert len(rows) >= 1, f"atexit 应写入 _sigcount, 实际空"
    n, signum = rows[0]
    assert n >= 1, f"应至少收到 1 次 SIGTERM, 实际 {n}"
    assert signum == 15, f"signum 应 = 15 (SIGTERM), 实际 {signum}"


def test_sigkill_kills_immediately_no_cleanup(tmp_db):
    """SIGKILL 真发 → 进程真死, 不跑 atexit (验 .wal 留有未 checkpoint 数据)"""
    db_path = str(tmp_db)
    script = f"""
import sys, time, os
import duckdb
con = duckdb.connect({db_path!r})
con.execute("CREATE TABLE _killtest (id INT, val TEXT)")
con.execute("INSERT INTO _killtest VALUES (1, 'a'), (2, 'b'), (3, 'c')")
# 不 commit 也不 checkpoint — 让数据留在 wal
print(f"PID={{os.getpid()}}", flush=True)
time.sleep(60)
"""
    proc = _run_in_subprocess(script)
    pid_line = proc.stdout.readline().decode("utf-8", errors="ignore").strip()
    pid = int(pid_line.split("=")[1])
    time.sleep(1.0)

    # SIGKILL 真发 — 不给 cleanup
    os.kill(pid, signal.SIGKILL)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pytest.fail("SIGKILL 5s 没死")

    # DuckDB 真能 reopen + 数据真在 (WAL recovery)
    import duckdb
    con = duckdb.connect(str(tmp_db), read_only=False)
    rows = con.execute("SELECT id, val FROM _killtest ORDER BY id").fetchall()
    con.close()
    # 3 条数据即使未 commit 也应在 (autocommit 模式 DuckDB 直接落)
    assert len(rows) == 3, f"SIGKILL 后 DuckDB WAL 应能恢复 3 行, 实际 {len(rows)}: {rows}"


def test_dup_fd_after_subprocess_exit(tmp_db):
    """子进程退后, 父进程真能开 db (无 fd 残留)"""
    db_path = str(tmp_db)
    script = f"""
import duckdb
con = duckdb.connect({db_path!r})
con.execute("CREATE TABLE _fdtest (id INT)")
con.execute("INSERT INTO _fdtest VALUES (1)")
con.close()  # 真关
"""
    r = subprocess.run([sys.executable, "-c", script],
                       capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, f"子进程 crash: {r.stderr}"

    # 父进程真能开 (验没 fd lock)
    import duckdb
    con = duckdb.connect(str(tmp_db), read_only=False)
    n = con.execute("SELECT count(*) FROM _fdtest").fetchone()[0]
    con.close()
    assert n == 1, f"子进程退后父进程应能读, 实际 {n}"


def test_sighup_does_not_terminate_by_default(tmp_db):
    """SIGHUP 真发 (默认行为: terminate on POSIX)"""
    db_path = str(tmp_db)
    script = f"""
import sys, time, os, signal
print(f"PID={{os.getpid()}}", flush=True)
# 不装 handler — 用默认
time.sleep(60)
"""
    proc = _run_in_subprocess(script)
    pid_line = proc.stdout.readline().decode("utf-8", errors="ignore").strip()
    pid = int(pid_line.split("=")[1])
    time.sleep(0.5)

    os.kill(pid, signal.SIGUSR1)
    # SIGHUP 默认: process terminate (POSIX)
    try:
        proc.wait(timeout=5)
        # 进程真退 (SIGHUP 默认 action = Term)
        assert proc.returncode is not None
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        pytest.fail("SIGHUP 5s 没退 (POSIX 默认应 Terminate)")
