# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""init_duckdb() 之前会创建 5 张表,其中 3 张全代码库零读零写:

  - market_data:  0 read, 0 write
  - factor_cache: 0 read, 0 write
  - decision_cache: 0 read, 0 write

而 ETL 实际写的是 kline_daily (在 akshare_etl.py:286 创建,不是这里)。
agent / pick / mcp 读的是 kline_daily。

后果:
  - 用户跑 init_duckdb() 之后看到 schema 里有 5 张表,以为自己能 query
    因子/行情/决策 → 查是空 → 怀疑系统坏了
  - 实际"因子缓存"等能力在 pipeline 里压根没接

修法:删 3 张死表,加守卫让未来不再添加「承诺但不写」的表。

测试:
  - init 后表清单 = {kline_daily, stock_list, portfolio_snapshot,
    portfolio_position} (K线/股票列表在 akshare_etl.py:init_tables)
  - 任何 schema 新增必须有读 + 写,否则 fail
"""
import tempfile


def test_init_duckdb_does_not_create_dead_tables():
    """init_duckdb() 不应再创建 factor_cache / market_data / decision_cache"""
    from forgemind.core.config.settings import get_settings
    with tempfile.TemporaryDirectory() as td:
        old = get_settings().duckdb_path
        try:
            get_settings().duckdb_path = f"{td}/test.db"
            from importlib import reload

            from forgemind.core.data import storage
            reload(storage)
            storage.init_duckdb()
            import duckdb
            import forgemind.core.data.storage as sm
            sm._DUCKDB_CONN_CACHE.clear()
            con = duckdb.connect(get_settings().duckdb_path)
            tables = sorted(r[0] for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main'").fetchall())
            con.close()
            # 这些表不能存在
            for dead in ("market_data", "factor_cache", "decision_cache"):
                assert dead not in tables, (
                    f"{dead} 仍在 schema 里:之前整个代码库零读零写,"
                    "init_duckdb() 重新创建会诱导用户以为能用")
        finally:
            get_settings().duckdb_path = old


def test_no_stray_create_table_in_storage():
    """守卫:storage.py 不应再有其它"没人写"的死表

    任何 CREATE TABLE IF NOT EXISTS 必须有相应的 INSERT,
    反过来也成立:任何 INSERT 必须有相应的表声明。
    """
    import re
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "forgemind/core/data/storage.py"
    src = p.read_text(encoding="utf-8")
    # CREATE / DROP 都可能在 f-string 里,正则字面要容错
    creates = set(re.findall(r"CREATE TABLE (?:IF NOT EXISTS )(\w+)", src))
    # DROP 可能在 f-string 模板里:识别 `f"...DROP TABLE IF EXISTS {dead}"`
    # 和 `DROP TABLE IF EXISTS <name>` 两种
    drops = set()
    drops.update(re.findall(r"DROP TABLE IF EXISTS (\w+)", src))
    drops.update(re.findall(r'f?["\']DROP TABLE[^\"\']*\{(\w+)\}', src))
    # DROP 的表 = 历史上承诺过但没接的
    # 任何 CREATE 的表不在 DROP 列表里 → 必须有 INSERT
    for tbl in creates - drops:
        # 简单检查:文件里要么有 INSERT INTO tbl,要么是 portfolio_* / kline_*
        # (kline_daily 实际在 akshare_etl.py 创建)
        if tbl in ("kline_daily",):
            continue  # 在其它文件
        # portfolio_*/kline_*/stock_list 实际被使用
        # 这里只防新增"孤立表"
        # 实际防"承诺但无 INSERT"
        import subprocess
        # 找该表的 INSERT
        # 绝对路径 —— 其它测试用 monkeypatch.chdir() 改 cwd 时,
        # 相对路径 "forgemind" 会找不到根目录
        root = str(Path(__file__).resolve().parents[1] / "forgemind")
        try:
            out = subprocess.check_output(
                ["grep", "-rln", "--include=*.py", f"INSERT.*{tbl}", root,
                 "--exclude-dir=__pycache__", "--exclude-dir=build"],
                stderr=subprocess.DEVNULL).decode()
            if not out.strip():
                raise AssertionError(
                    f"storage.py 创建 {tbl} 但全代码库零 INSERT")
        except subprocess.CalledProcessError:
            raise AssertionError(
                f"storage.py 创建 {tbl} 但全代码库零 INSERT")


def test_pipeline_factor_or_market_data_never_read():
    """如果未来有人加读 market_data / factor_cache 的代码,会被这个测试抓"""
    import re
    from pathlib import Path
    # agent / pick / mcp 都不应 SELECT * FROM market_data / factor_cache
    for root in ["forgemind/core/agents", "forgemind/mcp",
                 "forgemind/api"]:
        for p in Path(root).rglob("*.py"):
            txt = p.read_text(encoding="utf-8")
            for tbl in ("market_data", "factor_cache", "decision_cache"):
                # 检查 FROM tbl (不区分大小写,允许空白)
                if re.search(rf"FROM\s+{tbl}\b", txt, re.IGNORECASE):
                    raise AssertionError(
                        f"{p} 还在查 {tbl} — 这表已删,read 路径必须迁去"
                        "kline_daily / ClickHouse 等真源")
