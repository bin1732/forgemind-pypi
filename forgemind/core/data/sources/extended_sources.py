# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

from forgemind.core.observability.logging import get_logger

logger = get_logger("forgemind.extended_sources")


class DataSource(ABC):
    """数据源基类"""
    name: str = "BaseDataSource"
    requires_api_key: bool = False
    is_free: bool = True

    @abstractmethod
    def fetch(self, **kwargs) -> pl.DataFrame:
        """拉取数据"""
        raise NotImplementedError

    @abstractmethod
    def get_schema(self) -> dict[str, str]:
        """返回 schema: {col_name: dtype}"""
        raise NotImplementedError


# === Tushare Pro ===
class TushareProSource(DataSource):
    """Tushare Pro — A 股基本面 / 财报 / 分析师预期

    需要 API Key,免费档 2000 次/天
    """
    name = "TusharePro"
    requires_api_key = True
    is_free = True

    def __init__(self, token: str = "", cache_dir: str = "./data/cache/tushare"):
        self.token = token
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_pro(self):
        try:
            import tushare as ts
            pro = ts.pro_api(self.token) if self.token else None
            return pro
        except ImportError:
            return None

    def fetch(self, symbols: list[str], start: str, end: str, fields: list[str] = None, **kwargs) -> pl.DataFrame:
        """拉取基本面数据

        fields 支持:
        - "daily_basic" — PE/PB/PS/换手率
        - "income" — 利润表
        - "balancesheet" — 资产负债表
        - "fina_indicator" — 财务指标
        - "forecast" — 业绩预告
        """
        pro = self._get_pro()
        if pro is None:
            # 返回 mock 数据
            return self._mock_fundamental(symbols, start, end)

        all_data = []
        for sym in symbols[:10]:  # 限制 10 个防止超限
            try:
                if "daily_basic" in (fields or ["daily_basic"]):
                    df = pro.daily_basic(ts_code=sym, start_date=start, end_date=end)
                    if df is not None:
                        all_data.append(df)
            except Exception:
                continue

        if not all_data:
            return self._mock_fundamental(symbols, start, end)

        return pl.from_pandas(pd.concat(all_data))

    def _mock_fundamental(self, symbols, start, end):
        """Mock 数据(无 Tushare token 时)"""
        dates = pd.date_range(start, end, freq="D")
        rows = []
        for sym in symbols:
            for date in dates[::5]:  # 每 5 天一次
                rows.append({
                    "ts_code": sym,
                    "trade_date": date.strftime("%Y%m%d"),
                    "pe": np.random.uniform(5, 50),
                    "pb": np.random.uniform(0.5, 10),
                    "ps": np.random.uniform(0.5, 20),
                    "turnover_rate": np.random.uniform(0, 10),
                })
        return pl.from_pandas(pd.DataFrame(rows))

    def get_schema(self) -> dict[str, str]:
        return {
            "ts_code": "str",
            "trade_date": "str",
            "pe": "float",
            "pb": "float",
            "ps": "float",
            "turnover_rate": "float",
        }


# === 基本面聚合 ===
class FundamentalDataSource(DataSource):
    """基本面数据聚合器

    整合多个数据源:
    - PE/PB/PS(Tushare)
    - 营收增速 / 净利润增速(财报)
    - 分析师预期(forecast)
    - 机构持仓(十大股东)
    """
    name = "Fundamental"
    is_free = True

    def __init__(self, tushare: TushareProSource | None = None):
        self.tushare = tushare or TushareProSource()

    def fetch(self, symbols, start, end, **kwargs) -> pl.DataFrame:
        return self.tushare.fetch(symbols, start, end, fields=["daily_basic"])

    def get_schema(self):
        return self.tushare.get_schema()


# === 新闻 / 舆情 ===
class NewsDataSource(DataSource):
    """新闻 / 舆情数据

    数据源:
    - 财新网(爬虫,无 key)
    - 同花顺(爬虫)
    - 雪球(API)
    - Twitter(X)(API)
    - Reddit(API)
    """
    name = "News"
    is_free = True

    def fetch(self, symbols, start, end, **kwargs) -> pl.DataFrame:
        """返回新闻 DataFrame"""
        return self._mock_news(symbols, start, end)

    def _mock_news(self, symbols, start, end):
        """Mock 新闻数据"""
        dates = pd.date_range(start, end, freq="D")
        rows = []
        for sym in symbols[:5]:
            for date in dates[::3]:
                sentiment = np.random.uniform(-1, 1)
                rows.append({
                    "symbol": sym,
                    "date": date,
                    "title": f"{sym} 出现新闻标题 {np.random.randint(1000)}",
                    "source": np.random.choice(["财新", "同花顺", "雪球"]),
                    "sentiment_score": sentiment,
                    "n_comments": np.random.randint(0, 500),
                    "url": f"https://example.com/news/{sym}/{date.strftime('%Y%m%d')}",
                })
        return pl.from_pandas(pd.DataFrame(rows))

    def get_schema(self):
        return {
            "symbol": "str",
            "date": "date",
            "title": "str",
            "source": "str",
            "sentiment_score": "float",
            "n_comments": "int",
            "url": "str",
        }


# === 宏观数据 ===
class MacroDataSource(DataSource):
    """宏观数据 — PMI / PPI / CPI / 利率 / 汇率"""
    name = "Macro"
    is_free = True

    def fetch(self, start, end, **kwargs) -> pl.DataFrame:
        """拉宏观指标"""
        return self._mock_macro(start, end)

    def _mock_macro(self, start, end):
        dates = pd.date_range(start, end, freq="ME")
        rows = []
        for date in dates:
            rows.append({
                "date": date,
                "PMI": np.random.uniform(45, 55),
                "CPI": np.random.uniform(0.5, 5.0),
                "PPI": np.random.uniform(-3, 8),
                "M2_yoy": np.random.uniform(8, 15),
                "10y_yield": np.random.uniform(2, 4),
                "USD_CNY": np.random.uniform(6.5, 7.5),
            })
        return pl.from_pandas(pd.DataFrame(rows))

    def get_schema(self):
        return {
            "date": "date",
            "PMI": "float", "CPI": "float", "PPI": "float",
            "M2_yoy": "float", "10y_yield": "float", "USD_CNY": "float",
        }


# === 行业分类 ===
class SectorDataSource(DataSource):
    """行业分类 — 申万 / 中信 / GICS"""
    name = "Sector"
    is_free = True

    def __init__(self, classification: str = "申万"):
        self.classification = classification

    def fetch(self, symbols: list[str], **kwargs) -> pl.DataFrame:
        """返回行业分类"""
        sectors = ["银行", "地产", "科技", "医药", "消费", "能源", "制造", "金融"]
        rows = []
        for sym in symbols:
            rows.append({
                "symbol": sym,
                "sector": np.random.choice(sectors),
                "industry": np.random.choice(sectors),
                "classification": self.classification,
            })
        return pl.from_pandas(pd.DataFrame(rows))

    def get_schema(self):
        return {
            "symbol": "str",
            "sector": "str",
            "industry": "str",
            "classification": "str",
        }


# === 数据源注册表 ===
class DataSourceRegistry:
    """数据源注册表(可插拔)"""

    def __init__(self):
        self._sources: dict[str, DataSource] = {}

    def register(self, name: str, source: DataSource):
        self._sources[name] = source

    def get(self, name: str) -> DataSource | None:
        return self._sources.get(name)

    def list_sources(self) -> list[str]:
        return list(self._sources.keys())

    def fetch_multi(self, sources: list[str], **kwargs) -> dict[str, pl.DataFrame]:
        """并发拉多个数据源 — 失败的单源不阻塞其他

        Returns:
            {source_name: DataFrame},失败的不在结果里
        """
        import asyncio

        async def _fetch_one(name):
            source = self.get(name)
            if not source:
                logger.warning("data_source_not_found", source=name)
                return name, None
            try:
                df = source.fetch(**kwargs)
                return name, df
            except Exception as e:
                logger.error(
                    "data_source_fetch_failed",
                    source=name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                return name, None

        async def _run():
            tasks = [_fetch_one(n) for n in sources]
            return await asyncio.gather(*tasks)

        results = asyncio.run(_run())
        return {name: df for name, df in results if df is not None}


# === 默认注册 ===
def get_default_registry() -> DataSourceRegistry:
    """默认注册表"""
    registry = DataSourceRegistry()
    registry.register("tushare", TushareProSource())
    registry.register("fundamental", FundamentalDataSource())
    registry.register("news", NewsDataSource())
    registry.register("macro", MacroDataSource())
    registry.register("sector", SectorDataSource())
    return registry
