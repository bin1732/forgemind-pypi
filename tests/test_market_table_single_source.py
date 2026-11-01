# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""行情表的建表语句只能有一份。

ETL 与初始化各写一遍建表语句时,索引名会对不上:同一个索引被建出两个
名字,写放大一倍,而库里到底有几个索引还取决于哪条路径先跑。

这里两头都钉住:行为上,跑完 ETL 建表后表上只能有一个 K 线索引;
结构上,别的模块不许再写一遍这张表的 DDL。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from forgemind.core.data.akshare_etl import AKShareETL
from forgemind.core.data.storage import DuckDBStorage

REPO = Path(__file__).resolve().parent.parent


def _index_names(db, table: str = "kline_daily") -> list[str]:
    df = db.query_df(
        "SELECT index_name FROM duckdb_indexes() WHERE table_name = ?", [table])
    return sorted(str(x) for x in df["index_name"].tolist())


class TestMarketTablesSingleSource:
    def test_etl_path_creates_exactly_one_kline_index(self, tmp_path):
        db_path = str(tmp_path / "etl.duckdb")
        etl = AKShareETL(storage=DuckDBStorage(path=db_path))
        asyncio.run(etl.init_tables())
        with DuckDBStorage(path=db_path) as db:
            names = _index_names(db)
        assert "idx_kline_symbol_date" in names, names
        assert "idx_kline_symbol" not in names, (
            f"同一个索引被建出了两个名字: {names}")
        assert len([n for n in names if n.startswith("idx_kline_symbol")]) == 1, names

    def test_etl_path_is_idempotent(self, tmp_path):
        """建两遍不能多出索引"""
        db_path = str(tmp_path / "etl.duckdb")
        etl = AKShareETL(storage=DuckDBStorage(path=db_path))
        asyncio.run(etl.init_tables())
        asyncio.run(etl.init_tables())
        with DuckDBStorage(path=db_path) as db:
            names = _index_names(db)
        assert len([n for n in names if n.startswith("idx_kline_symbol")]) == 1, names

    def test_provider_column_is_present(self, tmp_path):
        db_path = str(tmp_path / "etl.duckdb")
        etl = AKShareETL(storage=DuckDBStorage(path=db_path))
        asyncio.run(etl.init_tables())
        with DuckDBStorage(path=db_path) as db:
            cols = [str(c) for c in
                    db.query_df("SELECT * FROM kline_daily LIMIT 0").columns]
        for expected in ("date", "symbol", "open", "high", "low", "close",
                         "volume", "provider"):
            assert expected in cols, f"kline_daily 缺列 {expected}: {cols}"

    def test_ddl_is_not_duplicated_in_other_modules(self):
        """建表语句只能写在 storage.py 里,别处再写一遍就一定会漂"""
        offenders = []
        for path in sorted((REPO / "forgemind").rglob("*.py")):
            if path.name == "storage.py":
                continue
            text = path.read_text(encoding="utf-8")
            if "CREATE TABLE IF NOT EXISTS kline_daily" in text:
                offenders.append(str(path.relative_to(REPO)))
        assert not offenders, (
            f"kline_daily 的建表语句在多处定义,迟早对不上: {offenders}")
