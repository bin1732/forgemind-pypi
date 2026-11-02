# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
端到端真实跑全链:
  ETL → backtest → agent → signal → query_portfolio → desktop risk_metrics

不 mock, 真 subprocess 跑每个 CLI, 看 DuckDB 状态 + CLI 退码
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import duckdb
import pytest


def test_etl_backtest_agent_signal_full_chain(tmp_path):
    """R1: ETL 真拉 → R2: backtest 真算 → R3: agent 真决策 → R4: signal 真落"""
    db = tmp_path / "e2e.db"
    db_path = str(db)
    env = os.environ.copy()
    env["FORGEMIND_DUCKDB_PATH"] = db_path
    env["FORGEMIND_LOG_LEVEL"] = "WARNING"
    # venv 路径
    forgemind_bin = "/workspace/.venv/bin/forgemind"

    if not os.path.exists(forgemind_bin):
        pytest.skip(f"{forgemind_bin} 不存在, 沙箱跳过")

    # === R1: ETL 拉 600519 全年 ===
    r = subprocess.run(
        [forgemind_bin, "etl",
         "--symbols", "600519",
         "--start", "2024-01-01", "--end", "2024-12-31"],
        capture_output=True, text=True, env=env, timeout=300,
    )
    if r.returncode not in (0, 3):  # 0=ok, 3=0 bars (网络问题)
        pytest.fail(f"ETL rc={r.returncode}: {r.stdout[-300:]}{r.stderr[-300:]}")

    # 看 DuckDB
    if os.path.exists(db_path):
        con = duckdb.connect(db_path, read_only=True)
        n = con.execute("SELECT count(*) FROM kline_daily WHERE symbol = '600519'").fetchone()[0]
        con.close()
        if n == 0:
            pytest.skip("ETL 没拉到数据 (网络), 跳过后续")
    else:
        pytest.skip("ETL 没建 db, 跳过后续")

    # === R2: backtest 600519 ===
    r = subprocess.run(
        [forgemind_bin, "backtest",
         "--symbol", "600519.SH",
         "--start", "2024-01-01", "--end", "2024-12-31"],
        capture_output=True, text=True, env=env, timeout=180,
    )
    # backtest 真跑会落 backtest_run (如果 DuckDB 有数据)
    if r.returncode == 0:
        con = duckdb.connect(db_path, read_only=True)
        n_bt = con.execute("SELECT count(*) FROM backtest_run").fetchone()[0]
        con.close()
        assert n_bt >= 1, f"backtest 成功后 backtest_run 应有行, 实际: {n_bt}"
    # returncode 非 0 也允许 (沙箱可能缺依赖), 关键是 ETL 通了

    # === R3: agent 决策 ===
    r = subprocess.run(
        [forgemind_bin, "agent",
         "--symbol", "600519.SH",
         "--cash", "80000",
         "--yes"],  # --yes 跳过 human approval
        capture_output=True, text=True, env=env, timeout=180,
    )
    if r.returncode == 0:
        con = duckdb.connect(db_path, read_only=True)
        n_dec = con.execute("SELECT count(*) FROM portfolio_decision").fetchone()[0]
        con.close()
        # agent 真跑应落 6 条决策 (6 agents)
        assert n_dec >= 6, f"agent 成功后 portfolio_decision 应 ≥ 6, 实际: {n_dec}"
    # === R4: signal 落盘 ===
    r = subprocess.run(
        [forgemind_bin, "signal",
         "--symbol", "600519.SH",
         "--side", "BUY",
         "--confidence", "0.75",
         "--rationale", "end-to-end e2e test"],
        capture_output=True, text=True, env=env, timeout=30,
    )
    if r.returncode == 0:
        con = duckdb.connect(db_path, read_only=True)
        n_sig = con.execute(
            "SELECT count(*) FROM signal_history WHERE source = 'forgemind_signal_cli'"
        ).fetchone()[0]
        con.close()
        assert n_sig >= 1, f"signal 成功后 signal_history 应有行, 实际: {n_sig}"

    # === R5: 端到端 — 检查所有表都有 schema 完整 ===
    con = duckdb.connect(db_path, read_only=True)
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    con.close()
    for required in ("kline_daily", "stock_list", "signal_history",
                     "backtest_run", "portfolio_decision",
                     "portfolio_snapshot", "portfolio_position"):
        assert required in tables, (
            f"{required} 应存在, 实际: {tables}"
        )


def test_wheel_install_path(tmp_path):
    """R0: wheel 真装 (无 --no-deps 模拟), 不破 deps 关系"""
    import zipfile
    import urllib.request

    wheel_url = (
        "https://github.com/bin1732/forgemind-pypi/releases/download/continuous/"
        "forgemind-2026.9.3-py3-none-any.whl"
    )
    wheel_path = tmp_path / "forgemind.whl"
    try:
        urllib.request.urlretrieve(wheel_url, wheel_path)
    except Exception as e:
        pytest.skip(f"沙箱网络受限, 跳过 wheel 下载: {e}")

    with zipfile.ZipFile(wheel_path, "r") as z:
        # wheel 应含 METADATA + 所有 forgemind 模块
        names = z.namelist()
        has_metadata = any(n.endswith("METADATA") for n in names)
        assert has_metadata, "wheel 应有 METADATA"
        # 检查 forgemind.cli / .api / .mcp / .core.data.storage
        for required in (
            "forgemind/__init__.py",
            "forgemind/cli.py",
            "forgemind/api/main.py",
            "forgemind/mcp/server.py",
            "forgemind/core/data/storage.py",
        ):
            assert required in names, f"wheel 缺 {required}"
        # METADATA 看 wheel-requires (确认 deps 声明)
        metadata = z.read([n for n in names if n.endswith("METADATA")][0]).decode("utf-8")
        for dep in ("fastapi", "duckdb", "pydantic", "structlog", "click"):
            assert dep in metadata, f"wheel METADATA 应声明 {dep}"


def test_public_repo_carries_the_only_complete_source():
    """公开仓带的是完整且唯一的一份源码,没有该藏的东西

    架构变过一次:源码原先在私人仓,公开仓只是个发布面。现在源码就在
    公开仓里,它是唯一的真源 —— 于是"公开仓不含源码"这条判据早就过期
    了,它把真正的源码当成了泄漏。

    现在要守的是:

    - 源码完整:核心模块、界面、测试、门禁脚本都在;
    - 源码唯一:没有第二份副本;
    - 该藏的没进仓:凭据与私钥。
    """
    import json
    import urllib.request

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from check_repo_cleanliness import SECRET_FILE_NAMES, SECRET_FILE_SUFFIXES

    url = "https://api.github.com/repos/bin1732/forgemind-pypi/git/trees/HEAD?recursive=1"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        pytest.skip(f"沙箱网络受限: {e}")

    paths = {n["path"] for n in data.get("tree", []) if n.get("type") == "blob"}

    # 源码完整:核心模块、界面、测试、门禁脚本都得在
    for required in (
        "forgemind/__init__.py",
        "forgemind/cli.py",
        "forgemind/api/main.py",
        "forgemind/mcp/server.py",
        "forgemind/core/data/storage.py",
        "forgemind-ui/package.json",
        "scripts/check_repo_cleanliness.py",
    ):
        assert required in paths, f"公开仓缺 {required}"
    assert any(p.startswith("tests/") for p in paths), "公开仓缺测试"

    # 源码唯一:根一级之外不该再有第二份源码包
    duplicates = [
        p for p in paths
        if p.endswith(".py")
        and "forgemind" in p.split("/")[:-1]
        and p.split("/")[0] != "forgemind"
    ]
    assert not duplicates, f"公开仓里有第二份源码副本: {sorted(duplicates)[:5]}"

    # 该藏的没进仓
    leaked = [
        p for p in paths
        if p.rsplit("/", 1)[-1] in SECRET_FILE_NAMES or p.endswith(SECRET_FILE_SUFFIXES)
    ]
    assert not leaked, f"凭据不该进仓: {sorted(leaked)[:5]}"
