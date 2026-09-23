# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAKShareETL:
    """AKShare ETL 测试(不真拉,只测配置)"""
    
    def test_storage_init(self):
        from forgemind.core.data.storage import DuckDBStorage
        with DuckDBStorage() as db:
            assert db.conn is not None
    
    def test_etl_create(self):
        from forgemind.core.data.akshare_etl import AKShareETL, AKShareDataSource
        etl = AKShareETL()
        assert etl.storage is not None
        
        ds = AKShareDataSource()
        assert ds._akshare is None  # 没真 import,延迟加载
    
    @pytest.mark.asyncio
    async def test_init_tables(self):
        from forgemind.core.data.akshare_etl import AKShareETL
        from forgemind.core.data.storage import DuckDBStorage
        etl = AKShareETL(storage=DuckDBStorage())
        await etl.init_tables()
        # 验证表存在
        with etl.storage as db:
            tables = db.query_df("SHOW TABLES")
            names = tables["name"].tolist() if not tables.empty else []
            assert "stock_list" in names
            assert "kline_daily" in names


class TestStockPicker:
    """选股 Agent 测试"""
    
    def test_create(self):
        from forgemind.core.agents.stock_picker import StockPickerAgent, StockPick
        picker = StockPickerAgent()
        assert picker.lookbacks == [5, 20, 60]
    
    def test_normalize_score(self):
        from forgemind.core.agents.stock_picker import StockPickerAgent
        picker = StockPickerAgent()
        # value=0 → 0.5
        assert picker._normalize_score(0) == 0.5
        # value > 0 → > 0.5
        assert picker._normalize_score(0.05) > 0.5
        # value < 0 → < 0.5
        assert picker._normalize_score(-0.05) < 0.5
        # 限幅
        assert picker._normalize_score(1.0) == 1.0
        assert picker._normalize_score(-1.0) == 0.0
    
    def test_make_rationale(self):
        from forgemind.core.agents.stock_picker import StockPickerAgent
        picker = StockPickerAgent()
        factors = {
            "momentum": 0.8,
            "trend": 0.7,
            "volume_price": 0.6,
            "volatility": 0.5,
            "mean_reversion": 0.4,
        }
        weights = {k: 0.2 for k in factors}
        rationale = picker._make_rationale("600519.SH", factors, weights, 0.65)
        assert "600519.SH" in rationale
        assert "momentum" in rationale
        assert "多头排列" in rationale  # trend >= 0.7
    
    @pytest.mark.asyncio
    async def test_pick_empty_universe(self):
        """空 universe 不崩"""
        from forgemind.core.agents.stock_picker import StockPickerAgent
        picker = StockPickerAgent()
        picks = await picker.pick(universe=[], top_n=5)
        assert picks == []
    
    @pytest.mark.asyncio
    async def test_pick_with_mock_data(self):
        """有 mock 数据的股票能跑出 pick"""
        import pandas as pd
        import numpy as np
        from forgemind.core.agents.stock_picker import StockPickerAgent
        from forgemind.core.data.storage import DuckDBStorage
        
        # 写一些 mock 数据
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        df = pd.DataFrame({
            "date": dates,
            "symbol": "600519",
            "open": 100 + np.cumsum(np.random.normal(0, 1, 100)),
            "high": 102 + np.cumsum(np.random.normal(0, 1, 100)),
            "low": 98 + np.cumsum(np.random.normal(0, 1, 100)),
            "close": 100 + np.cumsum(np.random.normal(0.05, 1, 100)),  # 上升趋势
            "volume": np.random.randint(1000000, 5000000, 100),
        })
        
        with DuckDBStorage() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS kline_daily (
                    date DATE, symbol VARCHAR, open DOUBLE, high DOUBLE,
                    low DOUBLE, close DOUBLE, volume BIGINT,
                    PRIMARY KEY (date, symbol)
                )
            """)
            db.execute("DELETE FROM kline_daily WHERE symbol = '600519'")
            for _, row in df.iterrows():
                db.execute(
                    """INSERT INTO kline_daily VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    [row["date"], row["symbol"], row["open"], row["high"],
                     row["low"], row["close"], row["volume"]],
                )
        
        picker = StockPickerAgent()
        picks = await picker.pick(universe=["600519"], top_n=1)
        assert len(picks) == 1
        assert picks[0].symbol == "600519"
        assert 0 <= picks[0].score <= 1


class TestNoBrokerInCore:
    """v1.0+:ForgeMind 主框架完全解耦券商 SDK"""
    
    def test_no_brokers_package(self):
        """forgemind.core.brokers 应该已被删除"""
        from pathlib import Path
        core = Path("/workspace/forgemind/forgemind/core")
        brokers_dir = core / "brokers"
        assert not brokers_dir.exists(), \
            "v1.0+ forgemind.core.brokers 应该不存在 — 解耦券商"
    
    def test_no_miniqmt_in_core(self):
        """主代码不应 import xtquant SDK(MiniQMT 字样在 cli print 提示文案里可以出现)"""
        core_py = Path("/workspace/forgemind/forgemind")
        for py in core_py.rglob("*.py"):
            if "__pycache__" in str(py):
                continue
            content = py.read_text()
            assert "xtquant" not in content.lower(), f"{py} 提到 xtquant"
            assert "import xtquant" not in content, f"{py} import xtquant"
            assert "from xtquant" not in content, f"{py} from xtquant"
    
    def test_no_examples_plugins(self):
        """examples/ 应该存在(放 demo),但不包含 plugins/broker"""
        from pathlib import Path
        examples = Path("/workspace/forgemind/examples")
        # examples/ 现在合法存在,放 run_e2e_demo.py
        # 但 examples/plugins/ 不应存在
        plugins = examples / "plugins"
        assert not plugins.exists(), "examples/plugins/ 已删除(零 broker 代码)"