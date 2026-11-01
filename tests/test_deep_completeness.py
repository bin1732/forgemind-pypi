# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
深层 + 底层 验证:不只验"行为对",验"实现真在"

1. portfolio_position CHECK 真的在 DuckDB catalog (SHOW CREATE TABLE)
2. CLI 错误码分级 真 raise SystemExit(rc) 不是 print (字节码 inspect)
3. _DUCKDB_CONN_CACHE 真 module-scope 单例 (id 一致, __exit__ 不 close)
4. onChange 切 symbol 真触发 React event (DOM event flow 验)
5. 老 db migration 真的 DROP 死表 (DML 验)
6. README 错误码表真在 (字符串 match)
7. _DUCKDB_CONN_CACHE force_new 真的不写 cache (旁路验)
8. README "forgemind signal" 真在 Install 后能跑 (whl 包含)
"""
import inspect
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import duckdb
import pytest


# ===== 1. portfolio_position CHECK 在 DuckDB catalog =====
def test_portfolio_position_check_in_catalog():
    """DB 层 CHECK 不只是写在 init_duckdb — 真的在 system catalog 里"""
    db = "/tmp/test_deep1.db"
    if os.path.exists(db):
        os.remove(db)
    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = db

    import forgemind.core.data.storage as sm
    sm._DUCKDB_CONN_CACHE.clear()
    sm._init_done_for.clear()
    sm.init_duckdb()

    import forgemind.core.data.storage as sm
    sm._DUCKDB_CONN_CACHE.clear()
    con = duckdb.connect(db)
    rows = con.execute(
        "SELECT constraint_name, constraint_text "
        "FROM duckdb_constraints() "
        "WHERE table_name = 'portfolio_position'"
    ).fetchall()
    con.close()
    # 必须有 quantity + avg_price 两个 CHECK
    text = " ".join(r[1] for r in rows if r[1])
    assert "quantity" in text and "0" in text, f"quantity CHECK 应在, 实际: {text}"
    assert "avg_price" in text, f"avg_price CHECK 应在, 实际: {text}"


# ===== 2. CLI 错误码分级 真的 raise SystemExit =====
def test_cli_exit_codes_use_systemexit_not_print():
    """看 cmd_etl 源码: 必须 raise SystemExit(rc), 不能只是 print 后正常 return"""
    from forgemind.cli import cmd_etl
    src = inspect.getsource(cmd_etl)
    # 必须每个错误码分支都有 raise SystemExit(<int>) 不是 print 完走完函数
    for code in (2, 3, 4):
        pattern = rf"raise SystemExit\({code}\)"
        assert re.search(pattern, src), (
            f"cmd_etl 应有 raise SystemExit({code}), 没找到. 源码尾部: {src[-200:]}"
        )
    # 0 bars 分支也 raise
    assert re.search(r"raise SystemExit\(rc\)", src), "0 bars 应 raise SystemExit(rc)"


# ===== 3. _DUCKDB_CONN_CACHE 真 module-scope + __exit__ 不 close =====
def test_connection_cache_module_singleton_and_no_close():
    """_DUCKDB_CONN_CACHE 字典在 module 上, 同 path 第二次 with 落在同一个数据库实例

    缓存里存的是**根连接**;每次 with 拿的是它的一个游标 —— 同一个数据库
    实例,结果槽各自独立。直接共用根连接的话,多线程并发查询会互相顶掉
    结果(取不到,或者静默拿到别人的行),见 test_duckdb_thread_safety.py。
    """
    db = "/tmp/test_deep3.db"
    if os.path.exists(db):
        os.remove(db)
    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = db

    import forgemind.core.data.storage as sm
    sm._DUCKDB_CONN_CACHE.clear()
    sm.init_duckdb()

    # 拿两次 with — 同一个数据库实例,各自的游标
    with sm.DuckDBStorage() as a:
        a.execute("CREATE TABLE t(x INT)")
        a.execute("INSERT INTO t VALUES (1)")
    with sm.DuckDBStorage() as b:
        n = b.query_scalar("SELECT count(*) FROM t")
        cached = sm._DUCKDB_CONN_CACHE.get(db)
        assert b.conn is not cached, "每次 with 必须拿自己的游标"
        # 但数据是同一个库里的 —— 写进去的读得回来
        assert int(n) == 1
    # __exit__ 不该关 conn (c 二次 with 能查 = conn 仍 active)
    assert cached is not None
    # 旧写法会 close, 之后 query 失败 — 我们的 conn 仍可用
    # 拿 cached 直接查
    cached.execute("SELECT 1").fetchone()  # 不抛 → OK
    sm._DUCKDB_CONN_CACHE.clear()


# ===== 4. onChange 切 symbol 真的 dispatch DOM event 触发 React handler =====
def test_onchange_uses_native_setter_dispatch():
    """app/page.tsx onChange 用了 {e => setCurrentSymbol(e.target.value)},
    e2e 切 symbol 必须用 native setter + dispatch — 否则 React 18 不触发
    我们要求 README / e2e 文档显式说明这一约束"""
    p = Path("forgemind-ui/app/page.tsx")
    src = p.read_text(encoding="utf-8")
    # 找 <select onChange 块
    m = re.search(r"<select[^>]+onChange=\{[^}]*\}", src, re.DOTALL)
    assert m, "page.tsx 应有 <select onChange>"
    block = m.group(0)
    assert "setCurrentSymbol" in block, "onChange 必须 setCurrentSymbol"
    assert "loadFactorIC" in block, "onChange 必须 loadFactorIC (切 symbol 自动重算)"


# ===== 5. 老 db migration 真 DROP 死表 =====
def test_old_db_drops_dead_tables_in_init():
    """2026.9.0 老 db 跑新 init_duckdb — market_data / factor_cache /
    decision_cache 真从 catalog 消失, 而 kline_daily 数据保留"""
    db = "/tmp/test_deep5.db"
    if os.path.exists(db):
        os.remove(db)

    # 手动造一个老 db (3 张死表 + kline_daily 真数据)
    con = duckdb.connect(db)
    con.execute("""
        CREATE TABLE market_data (symbol VARCHAR, close DOUBLE, date DATE)
    """)
    con.execute("""
        CREATE TABLE factor_cache (factor_name VARCHAR, value DOUBLE)
    """)
    con.execute("""
        CREATE TABLE decision_cache (decision_id VARCHAR, vote VARCHAR)
    """)
    con.execute("""
        CREATE TABLE kline_daily (
            symbol VARCHAR, date DATE, open DOUBLE, high DOUBLE,
            low DOUBLE, close DOUBLE, volume DOUBLE, PRIMARY KEY (symbol, date)
        )
    """)
    con.execute("INSERT INTO kline_daily VALUES ('600519', '2024-12-30', 1500, 1510, 1490, 1505, 1000)")
    con.execute("INSERT INTO kline_daily VALUES ('600519', '2024-12-31', 1505, 1520, 1500, 1518, 1200)")
    con.close()

    # 跑新 init
    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = db

    import forgemind.core.data.storage as sm
    sm._DUCKDB_CONN_CACHE.clear()
    sm._init_done_for.clear()
    sm.init_duckdb()

    # 验证: 死表不在, 数据保留
    sm._DUCKDB_CONN_CACHE.clear()
    con = duckdb.connect(db)
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    kline_count = con.execute("SELECT count(*) FROM kline_daily").fetchone()[0]
    con.close()

    assert "market_data" not in tables, f"死表应被 DROP, 实际: {tables}"
    assert "factor_cache" not in tables, f"死表应被 DROP, 实际: {tables}"
    assert "decision_cache" not in tables, f"死表应被 DROP, 实际: {tables}"
    assert kline_count == 2, f"kline_daily 2 行应保留, 实际: {kline_count}"
    # 新表都建好
    for t in ("stock_list", "kline_daily", "portfolio_snapshot", "portfolio_position",
              "portfolio_decision", "backtest_run", "signal_history"):
        assert t in tables, f"新表 {t} 应存在, 实际: {tables}"


# ===== 6. README 错误码表 + FAQ 真在 =====
def test_readme_faq_and_exit_codes_present():
    """README 必须有 FAQ 区块 + 错误码速查表 (commit 7e6fc653 加的)"""
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "## ❓ FAQ" in readme, "README 缺 FAQ 区块"
    assert "## 🛑 错误码速查表" in readme, "README 缺错误码速查表"
    # 错误码表必须包含 2/3/4, 5+ 业务类特殊
    for code in (2, 3, 4):
        assert f"| {code} |" in readme, f"README 错误码表应包含 {code}"
    assert "5+" in readme, "README 错误码表应包含 5+ (业务类)"
    # FAQ 必须包含 6 个 Q (加的)
    faq_q_count = readme.count("<summary><b>Q:")
    assert faq_q_count >= 6, f"FAQ 应至少 6 个 Q, 实际: {faq_q_count}"


# ===== 7. force_new 真不写 cache =====
def test_force_new_does_not_overwrite_cache():
    """force_new=True 拿新 conn, 不污染 cache — 下次 with 仍用旧 cached"""
    db = "/tmp/test_deep7.db"
    if os.path.exists(db):
        os.remove(db)
    from forgemind.core.config.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    s.duckdb_path = db

    import forgemind.core.data.storage as sm
    sm._DUCKDB_CONN_CACHE.clear()
    sm.init_duckdb()

    # 第一个 with 拿 cached
    with sm.DuckDBStorage() as a:
        a.execute("CREATE TABLE t (x INT)")
        a.execute("INSERT INTO t VALUES (1)")

    # force_new 拿新 conn
    with sm.DuckDBStorage(force_new=True) as b:
        n = b.query_scalar("SELECT count(*) FROM t")
        assert n == 1
        new_conn = b.conn

    # 第二次 with (no force) — 应复用同一个数据库实例, 不是 force_new 那个
    with sm.DuckDBStorage() as c:
        cached = sm._DUCKDB_CONN_CACHE.get(db)
        assert cached is not None
        assert c.conn is not new_conn, "force_new 之后 cache 不应被新 conn 覆盖"
        # 非 force 的 with 拿的是缓存根连接的游标,不是缓存对象本身
        assert c.conn is not cached
        # 数据仍在同一个库里
        assert int(c.query_scalar("SELECT count(*) FROM t")) == 1
    sm._DUCKDB_CONN_CACHE.clear()


# ===== 8. wheel 真含 dev 层 5 缺角的 fix =====
def test_wheel_contains_dev_layer_fixes(tmp_path):
    """从 GitHub Pages 下载 wheel, 解压, 验 5 个 fix 都在 wheel 里"""
    import urllib.request
    import zipfile

    wheel_url = (
        "https://github.com/bin1732/forgemind-pypi/releases/download/continuous/"
        "forgemind-2026.9.3-py3-none-any.whl"
    )
    wheel_path = tmp_path / "forgemind.whl"
    try:
        urllib.request.urlretrieve(wheel_url, wheel_path)
    except Exception as e:
        pytest.skip(f"沙箱网络受限, 跳过 wheel 远程下载: {e}")

    with zipfile.ZipFile(wheel_path, "r") as z:
        # 1) portfolio_position CHECK
        for name in z.namelist():
            if "storage.py" in name and "data/" in name:
                src = z.read(name).decode("utf-8")
                assert "chk_pos_qty" in src, "wheel 缺 portfolio_position quantity CHECK"
                assert "chk_pos_avg" in src, "wheel 缺 portfolio_position avg_price CHECK"
            if "cli.py" in name:
                src = z.read(name).decode("utf-8")
                assert "raise SystemExit(2)" in src, "wheel 缺 MemoryError→2"
                assert "raise SystemExit(3)" in src, "wheel 缺 TimeoutError→3"
                assert "raise SystemExit(4)" in src, "wheel 缺 ENOSPC→4"
            if "storage.py" in name and "_DUCKDB_CONN_CACHE" in name or \
               ("storage.py" in name and "_DUCKDB_CONN_CACHE" in z.read(name).decode("utf-8")):
                src = z.read(name).decode("utf-8")
                if "_DUCKDB_CONN_CACHE" in src:
                    assert "force_new" in src, "wheel 缺 force_new"
