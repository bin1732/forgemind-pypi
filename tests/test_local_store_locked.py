# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""本地库被另一个进程占着时,说法必须是真的。

活证据(2026-11-13):桌面端开着的时候,它占着同一个 DuckDB 文件,终端里
的命令连不上那个库。命令行说的是"查本地行情库失败(IOException)" ——
异常类名是内部实现;更要紧的是,紧接着又说"600519 在库里没有 K 线" ——
**我们连都没连上,凭什么说库里没有**。用户照着提示去跑 etl,而 etl 同样
连不上那个库。

DuckDB 的文件锁是独占的:同一个库文件,同一时间只能一个进程打开(只读
模式也不行 —— 实测过)。所以这件事不是偶发,是"桌面端开着时必然发生"。

这里不用 mock:真的把锁占住,再真的去连。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


from forgemind.core.data.storage import (  # noqa: E402
    DuckDBStorage,
    LocalStoreLockedError,
    is_lock_conflict,
)


@pytest.fixture
def locked_db(tmp_path):
    """一个真被**另一个进程**占着的库文件。

    DuckDB 的锁是跨进程的:同一进程内可以再开一个连接(桌面端自己的那些
    连接就互不影响),但另一个进程来连就报锁冲突 —— 这正是"桌面端开着,
    终端里连不上"的情形。所以占用者要是真的另一个进程。
    """
    path = tmp_path / "main.db"
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import duckdb, sys, time\n"
                "con = duckdb.connect(sys.argv[1])\n"
                "con.execute('CREATE TABLE t (a INTEGER)')\n"
                "print('held', flush=True)\n"
                "time.sleep(120)\n"
            ),
            str(path),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "held", "占用者没起来"
        yield str(path)
    finally:
        holder.terminate()
        try:
            holder.wait(timeout=15)
        except subprocess.TimeoutExpired:
            holder.kill()


class TestLockConflictIsRecognized:
    def test_lock_conflict_is_detected(self):
        exc = RuntimeError(
            'IO Error: Could not set lock on file "/x/main.db": '
            "Conflicting lock is held in /usr/bin/python3.11 (PID 1)."
        )
        assert is_lock_conflict(exc) is True

    def test_other_errors_are_not_lock_conflicts(self):
        assert is_lock_conflict(RuntimeError("Table with name x does not exist")) is False

    def test_connecting_to_a_locked_file_raises_the_dedicated_error(self, locked_db):
        with pytest.raises(LocalStoreLockedError) as exc:
            with DuckDBStorage(path=locked_db):
                pass
        message = str(exc.value)
        # 说清是"被占用",并给出下一步;不带异常类名、不带本机路径
        assert "占用" in message
        assert "FORGEMIND_DATA_DIR" in message
        assert "IOException" not in message
        assert locked_db not in message

    def test_the_lock_is_per_process(self, locked_db):
        """锁按进程算,不按连接算 —— 桌面端自己的那些连接就靠这个

        同一个进程里再开一个连接是允许的;另一个进程来连才会撞上锁。
        所以"库被占着"这件事只发生在**别的进程**来连的时候。
        """
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import duckdb, sys\n"
                    "a = duckdb.connect(sys.argv[1])\n"
                    "b = duckdb.connect(sys.argv[1])\n"
                    "print(b.execute('SELECT count(*) FROM t').fetchone()[0])\n"
                ),
                locked_db,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # 占用者还握着锁的时候,第三个进程连不上 ⇒ 报锁冲突
        assert probe.returncode != 0, probe.stdout
        assert "Conflicting lock" in (probe.stderr + probe.stdout), probe.stderr[-300:]


class TestCliTellsTheTruth:
    """命令行在库被占着时说的话"""

    def _run_backtest(self, db_path: str) -> str:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "forgemind.cli",
                "backtest",
                "--symbol",
                "600519",
                "--start",
                "2024-01-01",
                "--end",
                "2024-06-30",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(REPO),
            env={
                "PATH": "/usr/bin:/bin",
                "PYTHONPATH": str(REPO),
                "FORGEMIND_DATA_DIR": str(Path(db_path).parent),
                "FORGEMIND_DUCKDB_PATH": db_path,
                "HOME": "/tmp",
            },
        )
        return proc.stdout + proc.stderr

    def test_locked_db_is_reported_as_locked_not_as_missing(self, locked_db):
        out = self._run_backtest(locked_db)
        assert "占用" in out, out
        # 不能说"库里没有" —— 连都没连上,不知道有没有
        assert "在库里没有 K 线" not in out, out
        # 异常类名是内部实现,不该出现在用户看得到的文字里
        assert "IOException" not in out, out
        assert "LocalStoreLockedError" not in out, out


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
