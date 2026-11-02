# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 crash recovery — kill -9 真杀子进程, DuckDB 真能从 WAL 恢复。
不走 mock, 真 os.kill + 真 DuckDB 重新打开。
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from _path_setup import inline_path_setup


def test_kill_minus_9_during_write_duckdb_recovery(tmp_path):
    """子进程写一半被 SIGKILL 杀, DuckDB 重开真能 recover 全部数据"""
    db = tmp_path / "crash_recovery.db"
    db_path = str(db)
    script = f"""
import sys, time, os
import duckdb
con = duckdb.connect({db_path!r})
con.execute("CREATE TABLE _crash (id INT, val TEXT, big_val TEXT)")
print(f"PID={{os.getpid()}}", flush=True)
# 插 1000 行
for i in range(1000):
    # 用大字符串测 WAL replay
    big = "x" * 100
    con.execute("INSERT INTO _crash VALUES (?, ?, ?)", [i, f"v{{i}}", big])
# 不显式 commit
print("DONE", flush=True)
time.sleep(60)
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    # 等子进程到 DONE
    seen = ""
    while "DONE" not in seen:
        line = proc.stdout.readline().decode("utf-8", errors="ignore")
        seen += line
        if "PID=" in line:
            pid = int(line.split("PID=")[1].strip())
        if not line:
            break
    assert "DONE" in seen, f"子进程应到 DONE, 实际: {seen!r}"
    time.sleep(0.2)  # 让数据落 WAL

    # kill -9 真发
    os.kill(pid, 9)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        pytest.fail("SIGKILL 5s 没死")

    # DuckDB 真能 reopen
    import duckdb
    con = duckdb.connect(db_path, read_only=False)
    n = con.execute("SELECT count(*) FROM _crash").fetchone()[0]
    sample = con.execute("SELECT * FROM _crash ORDER BY id LIMIT 3").fetchall()
    last = con.execute("SELECT * FROM _crash ORDER BY id DESC LIMIT 1").fetchall()
    con.close()
    # DuckDB 默认 autocommit 模式 + WAL — SIGKILL 后能恢复
    assert n == 1000, f"应 1000 行, 实际 {n}"
    assert sample[0] == (0, "v0", "x" * 100), f"首行错: {sample[0]}"
    assert last[0][0] == 999, f"末行 id 应 999, 实际: {last[0]}"


def test_kill_during_init_duckdb_does_not_corrupt(tmp_path):
    """子进程跑 init_duckdb 中被杀, 下次 init 真能成功 (DDL idempotent + WAL)"""
    db = tmp_path / "init_crash.db"
    db_path = str(db)
    script = f"""
import sys, time, os
{inline_path_setup()}
print(f"PID={{os.getpid()}}", flush=True)
from forgemind.core.data.storage import init_duckdb, _do_init_duckdb_ddl
# 真跑 DDL
_do_init_duckdb_ddl({db_path!r})
print("INIT_DONE", flush=True)
time.sleep(60)
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    line = proc.stdout.readline().decode("utf-8", errors="ignore")
    pid = int(line.split("PID=")[1].strip())
    # 在 init 完成前杀
    time.sleep(0.05)
    os.kill(pid, 9)
    proc.wait(timeout=5)

    # 重 init 应成功 (CREATE TABLE IF NOT EXISTS) — 顶部已 import sys
    import forgemind.core.data.storage as storage
    # 走 env 切 db path (init_duckdb 不接参数, 读 settings)
    os.environ['FORGEMIND_DUCKDB_PATH'] = db_path
    import importlib

    import forgemind.core.config.settings as _sm
    _sm.get_settings.cache_clear()
    _singleton = _sm.get_settings()
    _singleton.duckdb_path = db_path
    storage._DUCKDB_CONN_CACHE.clear()
    storage.init_duckdb()
    storage._DUCKDB_CONN_CACHE.clear()  # 真关, 让 ro 也能开

    # 7 张业务表真在
    import duckdb
    con = duckdb.connect(db_path, read_only=True)
    n = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_type='BASE TABLE'").fetchone()[0]
    con.close()
    assert n >= 7, f"7+ 表应真在, 实际 {n}"


def test_dup_open_rw_ro_raises_immediately(tmp_path):
    """同一 db 真 rw + ro 并存触发 'Unique file handle conflict'"""
    db = tmp_path / "dup_open.db"
    db_path = str(db)
    # 先建空 db
    import duckdb
    con = duckdb.connect(db_path)
    con.execute("CREATE TABLE _d (id INT)")
    con.close()

    # rw 连接
    rw = duckdb.connect(db_path)
    # 试图开 ro — 应抛
    raised = False
    try:
        ro = duckdb.connect(db_path, read_only=True)
        ro.execute("SELECT 1").fetchall()
    except Exception as e:
        raised = True
        err = str(e)
    finally:
        rw.close()
    assert raised, "DuckDB 应不允许同 path rw+ro 共存"
    assert "different configuration" in err or "Unique file handle" in err, (
        f"错误信息应含 'Unique file handle conflict', 实际: {err!r}"
    )


def test_subprocess_isolation_persists(tmp_path):
    """A 进程写 → 退 → B 进程真能读到 (真 OS fsync)"""
    db = tmp_path / "iso.db"
    db_path = str(db)

    # A 进程: 写 + 退
    script_a = f"""
import duckdb
con = duckdb.connect({db_path!r})
con.execute("CREATE TABLE _iso (id INT, msg TEXT)")
con.execute("INSERT INTO _iso VALUES (1, 'A wrote this')")
con.close()  # 真关, 触发 fsync
print("A_DONE")
"""
    r = subprocess.run([sys.executable, "-c", script_a],
                       capture_output=True, text=True, timeout=10)
    assert "A_DONE" in r.stdout

    # B 进程: 读
    script_b = f"""
import duckdb
con = duckdb.connect({db_path!r}, read_only=True)
row = con.execute("SELECT id, msg FROM _iso").fetchone()
print(f"B_READ: {{row}}")
"""
    r = subprocess.run([sys.executable, "-c", script_b],
                       capture_output=True, text=True, timeout=10)
    assert "(1, 'A wrote this')" in r.stdout, f"B 应真读到 A 写的数据, 实际: {r.stdout!r}"


def test_subprocess_count_changes_after_open(tmp_path):
    """DuckDB 启动子进程后, 真能查 _DUCKDB_CONN_CACHE 状态变化"""
    db = tmp_path / "cache_count.db"
    db_path = str(db)
    script = f"""
import sys, os
{inline_path_setup()}
import forgemind.core.data.storage as storage
storage._DUCKDB_CONN_CACHE.clear()
os.environ['FORGEMIND_DUCKDB_PATH'] = {db_path!r}
import importlib
import forgemind.core.config.settings as _sm
_sm.get_settings.cache_clear()
storage._DUCKDB_CONN_CACHE.clear()
storage.init_duckdb()
# 第一次 with
with storage.DuckDBStorage(path={db_path!r}) as db1:
    db1.query_df("SELECT 1")
cache_after_first = len(storage._DUCKDB_CONN_CACHE)
# 第二次 with 同 path — 应复用 cache
with storage.DuckDBStorage(path={db_path!r}) as db2:
    db2.query_df("SELECT 1")
cache_after_second = len(storage._DUCKDB_CONN_CACHE)
print(f"first={{cache_after_first}}, second={{cache_after_second}}")
"""
    r = subprocess.run([sys.executable, "-c", script],
                       capture_output=True, text=True, timeout=15)
    assert "first=1" in r.stdout, f"第一次 with 应 1 entry, 实际: {r.stdout!r}"
    assert "second=1" in r.stdout, f"第二次 with 复用, 仍 1 entry, 实际: {r.stdout!r}"
