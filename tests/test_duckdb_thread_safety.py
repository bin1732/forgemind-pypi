# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""DuckDB 连接在多线程下不能共用 —— 结果槽会被互相顶掉

当初的岔子:连接按 path 缓存,所有线程拿到**同一个**连接。DuckDB 的
连接上"最后一次查询的结果"只有一个槽位,一个线程的 execute 会把另一个
线程还没取的结果顶掉:

  * fetchdf 取不到结果 → 返回 None → 上层 .empty / .iterrows() 直接炸
    ("'NoneType' object has no attribute 'iterrows'")
  * 更糟的情况是静默返回**别人的行** —— 没有报错,数据却是错的

这个错在单线程下永远看不出来,而桌面端与 API 都会并发查库(接口层把
工具执行丢进 asyncio.to_thread),于是表现为"偶发 500"。

修法:缓存根连接,每次 with 拿一个 cursor() —— 同一个数据库实例,
结果槽各自独立。

    python -m pytest tests/test_duckdb_thread_safety.py -v
"""

from __future__ import annotations

import pathlib
import threading
import time

import pytest

from forgemind.core.data.storage import DuckDBStorage


@pytest.fixture
def db_path(tmp_path: pathlib.Path) -> str:
    path = tmp_path / "thread_safety.db"
    # 先建好表, 免得并发测试里混进 DDL 的噪声
    with DuckDBStorage(path=str(path)) as db:
        db.execute("CREATE TABLE t (marker INTEGER)")
    return str(path)


def _hammer(db_path: str, threads: int, rounds: int) -> tuple[list[str], list[int]]:
    """并发查询, 返回 (报错, 拿到别人的结果的次数)"""
    errors: list[str] = []
    wrong: list[int] = []
    lock = threading.Lock()

    def worker(idx: int) -> None:
        try:
            for k in range(rounds):
                with DuckDBStorage(path=db_path) as db:
                    df = db.query_df("SELECT ? AS marker", [idx * 1000 + k])
                if df is None:
                    with lock:
                        errors.append("query_df 返回 None")
                    continue
                got = int(df.iloc[0]["marker"])
                if got != idx * 1000 + k:
                    with lock:
                        wrong.append(got)
        except Exception as exc:  # noqa: BLE001
            with lock:
                errors.append(f"{type(exc).__name__}: {exc}")

    barrier = threading.Barrier(threads)

    def run(idx: int) -> None:
        barrier.wait()
        worker(idx)

    ts = [threading.Thread(target=run, args=(i,)) for i in range(threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return errors, wrong


class TestDuckDBThreadSafety:
    def test_concurrent_queries_never_get_none(self, db_path: str):
        """并发查询时不能出现 None —— 那会让上层 .empty / .iterrows() 炸掉"""
        errors, wrong = _hammer(db_path, threads=12, rounds=12)
        assert not errors, f"并发查询报错: {errors[:3]}"
        assert not wrong, f"拿到了别人的结果: {wrong[:3]}"

    def test_concurrent_queries_return_own_rows(self, db_path: str):
        """每个线程必须拿到自己那行, 不能串"""
        errors, wrong = _hammer(db_path, threads=8, rounds=20)
        assert not errors
        assert not wrong

    def test_cold_cache_first_connect_is_serialized(self, tmp_path: pathlib.Path):
        """缓存冷的时候并发首次连接不能撞 DuckDB 的文件锁"""
        path = str(tmp_path / "cold.db")
        errors: list[str] = []
        lock = threading.Lock()
        barrier = threading.Barrier(8)

        def worker(idx: int) -> None:
            barrier.wait()
            try:
                with DuckDBStorage(path=path) as db:
                    db.query_df("SELECT ? AS marker", [idx])
            except Exception as exc:  # noqa: BLE001
                with lock:
                    errors.append(f"{type(exc).__name__}: {exc}")

        ts = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        assert not errors, f"并发首次连接报错: {errors[:3]}"


class TestDuckDBConnectionShape:
    def test_each_instance_gets_its_own_cursor(self, db_path: str):
        """两个 with 拿到的必须是不同游标(同实例、同库、不同结果槽)"""
        with DuckDBStorage(path=db_path) as a, DuckDBStorage(path=db_path) as b:
            assert a.conn is not None
            assert b.conn is not None
            assert a.conn is not b.conn

    def test_one_instance_cannot_steal_another_pending_result(self, db_path: str):
        """一个实例取数, 不能被另一个实例的查询顶掉

        这是那个 bug 的确定性版本:共用一个连接时,后执行的查询会把别人
        还没取的结果换掉 —— 取到的是别人的行(数据错了还没报错),或者
        干脆取不到(None,上层 .empty / .iterrows() 直接炸)。
        真并发下这个窗口很窄,所以这里直接把它摆出来。
        """
        with DuckDBStorage(path=db_path) as a, DuckDBStorage(path=db_path) as b:
            pending = a.conn.execute("SELECT 1 AS marker")
            b.conn.execute("SELECT 2 AS marker")
            df = pending.df()
            assert df is not None, "另一个实例的查询把待取结果顶掉了"
            assert int(df.iloc[0]["marker"]) == 1, "取到的是别人的结果"

    def test_same_path_shares_one_database_instance(self, db_path: str):
        """同一 path 的连接必须落在同一个数据库实例上(否则写进去读不到)"""
        with DuckDBStorage(path=db_path) as a:
            a.execute("CREATE TABLE shared_check (v INTEGER)")
            a.execute("INSERT INTO shared_check VALUES (7)")
        with DuckDBStorage(path=db_path) as b:
            df = b.query_df("SELECT v FROM shared_check")
            assert df is not None
            assert int(df.iloc[0]["v"]) == 7


class TestConcurrentWriteAndRead:
    """边写边读时,读到的必须是一个一致快照

    ETL 用的就是共享连接写(DuckDBStorage() 默认拿缓存连接的游标),
    而查询也在同一个数据库实例上读。两条路同时走时:

      * 不能抛错
      * 不能取不到结果(那个 None 会让上层 .empty / .iterrows() 炸)
      * 不能读到"写了一半"的状态 —— 读到的行数与聚合值必须对得上
    """

    def test_readers_never_see_a_torn_snapshot(self, tmp_path: pathlib.Path):
        db_path = str(tmp_path / "write_and_read.db")
        with DuckDBStorage(path=db_path) as db:
            db.execute("CREATE TABLE t (id INTEGER, v INTEGER)")
            db.execute("INSERT INTO t VALUES (-1, 0)")  # 占一行,sum 不会是 NULL

        errors: list[str] = []
        nones = 0
        reads: list[tuple[int, int]] = []
        lock = threading.Lock()
        stop = threading.Event()

        def writer() -> None:
            try:
                with DuckDBStorage(path=db_path) as db:
                    for i in range(150):
                        db.execute("INSERT INTO t VALUES (?, ?)", [i, i * 2])
            except Exception as exc:  # noqa: BLE001
                with lock:
                    errors.append(f"writer: {type(exc).__name__}: {exc}")

        def reader() -> None:
            nonlocal nones
            try:
                while not stop.is_set():
                    with DuckDBStorage(path=db_path) as db:
                        df = db.query_df("SELECT count(*) AS n, coalesce(sum(v), 0) AS s FROM t")
                    if df is None:
                        with lock:
                            nones += 1
                        continue
                    with lock:
                        reads.append((int(df.iloc[0]["n"]), int(df.iloc[0]["s"])))
            except Exception as exc:  # noqa: BLE001
                with lock:
                    errors.append(f"reader: {type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=writer)]
        threads += [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        threads[0].join()
        stop.set()
        for t in threads[1:]:
            t.join()

        assert not errors, f"并发写读报错: {errors[:3]}"
        assert nones == 0, f"并发读取到 None {nones} 次"
        assert reads, "一次都没读到 —— 并发读根本没跑起来"
        # 不变量:count=n 行时,sum 必须是前 n-1 个 id 的两倍之和
        torn = []
        for count, total in reads:
            expect = (count - 2) * (count - 1) if count >= 2 else 0
            if total != expect:
                torn.append((count, total, expect))
        assert not torn, f"读到写了一半的行: {torn[:3]}"


class TestDdlCoexistsWithReaders:
    """ETL 建索引的 DDL 与写入,必须能与并发读共存

    真实场景:桌面端开着面板读 DuckDB,用户同时在终端跑 `forgemind etl`
    —— ETL 会建索引(DDL)并写新行。DDL 是目录写,碰上并发读容易报
    catalog 冲突;读到的行数也必须跟着写入往前走,不能卡在旧快照上。
    """

    def test_index_ddl_and_insert_do_not_break_concurrent_readers(self, tmp_path: pathlib.Path):
        db_path = str(tmp_path / "ddl.db")
        with DuckDBStorage(path=db_path) as db:
            db.execute("CREATE TABLE k (d DATE, s VARCHAR, c DOUBLE)")
            db.execute("INSERT INTO k VALUES (DATE '2024-01-02', '600519', 10.5)")

        errors: list[str] = []
        reads: list[int] = []
        lock = threading.Lock()
        stop = threading.Event()

        def reader() -> None:
            try:
                while not stop.is_set():
                    with DuckDBStorage(path=db_path) as db:
                        df = db.query_df("SELECT count(*) AS n FROM k")
                    if df is None:
                        with lock:
                            errors.append("读到 None")
                    else:
                        with lock:
                            reads.append(int(df.iloc[0]["n"]))
            except Exception as exc:  # noqa: BLE001
                with lock:
                    errors.append(f"reader: {type(exc).__name__}: {exc}")

        def writer() -> None:
            try:
                time.sleep(0.3)
                with DuckDBStorage(path=db_path) as db:
                    db.execute("CREATE INDEX IF NOT EXISTS idx_k_s ON k(s)")
                time.sleep(0.2)
                with DuckDBStorage(path=db_path) as db:
                    db.execute("INSERT INTO k VALUES (DATE '2024-01-03', '600519', 11.5)")
                    db.execute("INSERT INTO k VALUES (DATE '2024-01-04', '600519', 12.5)")
            except Exception as exc:  # noqa: BLE001
                with lock:
                    errors.append(f"writer: {type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=reader) for _ in range(3)]
        writer_thread = threading.Thread(target=writer)
        for t in threads:
            t.start()
        writer_thread.start()
        time.sleep(2.0)
        stop.set()
        for t in threads:
            t.join()

        assert not errors, f"DDL 与并发读打架: {errors[:3]}"
        assert reads, "一次都没读到 —— 并发读根本没跑起来"
        assert max(reads) == 3, (
            f"读到的行数没有跟着写入往前走: {sorted(set(reads))} —— 读卡在旧快照上了"
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
