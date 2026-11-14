# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""建库时等不等锁 —— 由调用方明确选择,不是隐式副作用

DuckDB 的进程间锁是**排他**的:同一个库文件,同一时间只能一个进程打开
(只读也不行)。于是"库被占着"有两种截然不同的成因:

- 另一个进程正在建表,建完就放开 ⇒ 等一等就轮到自己
- 桌面端这类长驻进程一直占着 ⇒ 等下去锁也不会自己放开

这两种混在一起,表现就是:库被占着的时候,命令要么让用户干等几十秒
才看到提示,要么立刻失败而后一种场景下本可以等到。

所以等不等由调用方选:

- init_duckdb() 默认**不等待** —— 锁冲突立刻抛,命令马上把"读不到"
  说清楚。库里有没有数据是另一回事,不该混成一句。
- init_duckdb(wait_for_lock=True) —— 明确知道"有人正在建表"时才等。

这两条都真跑:持锁的是另一个真进程,建库的是另一个真进程。
"""

from __future__ import annotations

import subprocess
import sys
import time

from _path_setup import child_env, inline_path_setup


def _hold_lock(db_path: str) -> subprocess.Popen:
    """起一个真进程占着这个库文件,返回那个进程。"""
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import duckdb, sys, time\n"
                "con = duckdb.connect(sys.argv[1])\n"
                "print('held', flush=True)\n"
                "time.sleep(600)\n"
            ),
            db_path,
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    proc.stdout.readline()  # 等它真的握住锁
    return proc


def _init_in_child(db_path: str, wait_for_lock: bool) -> tuple[str, float]:
    """在子进程里真跑一次建库,返回 (输出, 耗时秒)。

    放在子进程里是因为建库会动进程级状态(连接缓存、已初始化标记) ——
    污染当前进程的话,后面的用例拿到的是别的库。
    """
    call = (
        "init_duckdb(wait_for_lock=True)"
        if wait_for_lock
        else "init_duckdb()"
    )
    script = f"""
import os, sys, time
os.environ['FORGEMIND_DUCKDB_PATH'] = {db_path!r}
os.environ['FORGEMIND_LOG_LEVEL'] = 'ERROR'
{inline_path_setup()}
t0 = time.time()
from forgemind.core.data.storage import init_duckdb
try:
    {call}
    print('INIT_OK', flush=True)
except Exception as exc:
    print(f'INIT_FAIL: {{type(exc).__name__}}', flush=True)
print(f'ELAPSED: {{time.time() - t0:.2f}}', flush=True)
"""
    started = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        env=child_env(),
    )
    elapsed = time.monotonic() - started
    assert proc.returncode == 0, (
        f"建库子进程不该自己崩: rc={proc.returncode} stderr={proc.stderr[-400:]!r}"
    )
    return proc.stdout, elapsed


def test_default_init_reports_lock_conflict_without_waiting(tmp_path):
    """默认不等待:库被占着时立刻说是锁冲突,而且不干等。"""
    db_path = str(tmp_path / "locked.db")
    holder = _hold_lock(db_path)
    try:
        out, elapsed = _init_in_child(db_path, wait_for_lock=False)
    finally:
        holder.terminate()
        try:
            holder.wait(timeout=10)
        except subprocess.TimeoutExpired:
            holder.kill()

    assert "INIT_FAIL: LocalStoreLockedError" in out, (
        f"锁冲突应报成锁冲突(不是别的错),实际输出: {out!r}"
    )
    # 干等是白等:占着锁的进程不会自己放开。
    assert elapsed < 15, (
        f"库被占着时应立刻报出来,不该干等;实际等了 {elapsed:.1f} 秒"
    )


def test_wait_for_lock_waits_until_the_holder_releases(tmp_path):
    """显式等待:持锁进程放开锁之后,等着的一方真的能建上库。"""
    db_path = str(tmp_path / "waited.db")
    holder = _hold_lock(db_path)

    import threading

    def release_later() -> None:
        time.sleep(2.0)
        holder.terminate()
        try:
            holder.wait(timeout=10)
        except subprocess.TimeoutExpired:
            holder.kill()

    releaser = threading.Thread(target=release_later, daemon=True)
    releaser.start()
    try:
        out, _elapsed = _init_in_child(db_path, wait_for_lock=True)
    finally:
        releaser.join(timeout=20)
        if holder.poll() is None:
            holder.kill()

    assert "INIT_OK" in out, (
        f"显式等待时,持锁进程放开后应能建上库;实际输出: {out!r}"
    )
