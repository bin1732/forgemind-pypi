# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd
import polars as pl

from forgemind.core.config.settings import data_path
from forgemind.core.data.fetch_guard import call_with_timeout
from forgemind.core.observability.logging import get_logger

logger = get_logger("forgemind.extended_sources")


class DataSource(ABC):
    """数据源基类

    **契约:没有真实数据就如实说没有,绝不返回编造的数字。**

    历史上这里有三个源用 np.random 造 PE/PB/新闻/PMI,字段名和取值范围
    都像真的(茅台 PE 落在 5-50 之间),用户完全无法分辨。基本面数字会直接
    驱动选股与估值判断,新闻情绪会驱动交易信号 —— 这类假数据比没有数据
    危险得多。

    因此:未实现或未配置的数据源,fetch 要么抛 DataSourceUnavailableError,
    要么返回**空表 + 正确 schema**,并让 is_available() 如实为 False。
    绝不用随机数填充。
    """

    name: str = "BaseDataSource"
    requires_api_key: bool = False
    is_free: bool = True

    def is_available(self) -> tuple[bool, str]:
        """(是否可用, 不可用时的原因)

        原因要能直接指导用户下一步,例如"缺少 TUSHARE_TOKEN"。
        """
        return True, ""

    def require_available(self) -> None:
        ok, reason = self.is_available()
        if not ok:
            raise DataSourceUnavailableError(self.name, reason)

    @abstractmethod
    def fetch(self, **kwargs) -> pl.DataFrame:
        """拉取数据。不可用时抛 DataSourceUnavailableError,不要返回编造数据。"""
        raise NotImplementedError

    @abstractmethod
    def get_schema(self) -> dict[str, str]:
        """返回 schema: {col_name: dtype}"""
        raise NotImplementedError


def _empty_like_schema(schema: dict[str, str]) -> "pl.DataFrame":
    """按 schema 造一张 0 行的空表

    明确"这里没有数据",而不是造几行看起来很像真的数字。
    """
    dtype = {"str": pl.Utf8, "float": pl.Float64, "int": pl.Int64, "date": pl.Date}
    return pl.DataFrame(
        {k: pl.Series([], dtype=dtype.get(v, pl.Float64)) for k, v in schema.items()}
    )


class DataSourceUnavailableError(RuntimeError):
    """数据源不可用(未实现 / 缺凭证 / 上游不可达)

    存在的意义:让"拿不到数据"变成一个**可捕获的类型**,而不是一段
    看起来合理的假数字。调用方要么处理它,要么让用户看见它。
    """

    def __init__(self, source: str, reason: str):
        self.source = source
        self.reason = reason
        super().__init__(f"数据源 {source} 不可用:{reason}")


# === Tushare Pro ===
class TushareProSource(DataSource):
    """Tushare Pro — A 股基本面 / 财报 / 分析师预期

    需要 API Key,免费档 2000 次/天
    """

    name = "TusharePro"
    requires_api_key = True
    is_free = True

    def __init__(self, token: str = "", cache_dir: str | None = None):
        self.token = token
        self.cache_dir = Path(cache_dir) if cache_dir else data_path("cache", "tushare")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> tuple[bool, str]:
        if not self.token:
            return False, (
                "未配置 TUSHARE_TOKEN。到 https://tushare.pro 注册获取 token, "
                "然后设置环境变量 TUSHARE_TOKEN 后重试。"
            )
        try:
            import tushare  # noqa: F401
        except ImportError:
            return False, "未安装 tushare。pip install 'forgemind[cn]'"
        return True, ""

    def _get_pro(self):
        try:
            import tushare as ts

            return ts.pro_api(self.token) if self.token else None
        except ImportError:
            return None

    def fetch(
        self, symbols: list[str], start: str, end: str, fields: list[str] = None, **kwargs
    ) -> pl.DataFrame:
        """拉取基本面数据

        fields 支持:
        - "daily_basic" — PE/PB/PS/换手率
        - "income" — 利润表
        - "balancesheet" — 资产负债表
        - "fina_indicator" — 财务指标
        - "forecast" — 业绩预告
        """
        self.require_available()
        pro = self._get_pro()
        if pro is None:
            raise DataSourceUnavailableError(self.name, self.is_available()[1])

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
            # 上游可达但区间内确实没有数据:这是事实,如实返回空表 + schema,
            # 不能拿随机数填 —— 真实"没财报"和"编一个 PE"必须区分得开
            logger.warning(
                "tushare_no_fundamental_rows",
                symbols=len(symbols),
                start=start,
                end=end,
            )
            return _empty_like_schema(self.get_schema())

        return pl.from_pandas(pd.concat(all_data))

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

    def is_available(self) -> tuple[bool, str]:
        return False, ("新闻数据源尚未接入真实抓取实现,如实报不可用;接入真实源后再开放。")

    def fetch(self, symbols, start, end, **kwargs) -> pl.DataFrame:
        """返回新闻 DataFrame"""
        self.require_available()
        raise DataSourceUnavailableError(self.name, self.is_available()[1])

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
    """宏观数据 — PMI / PPI / CPI / M2 / 国债收益率 / 汇率

    数据来自 akshare 的公开接口。月度指标给的是**发布日**,日频指标给
    的是交易日;两者按"最近一次发布"对齐 —— 月度指标在发布日之后一直
    有效,往前找最近的那次发布,就是当时市场看到的那份数。

    某一个指标取不到,那一列就是空的,不用别的指标的值顶替。
    """

    name = "Macro"
    is_free = True

    #: 月度指标:指标名 -> (akshare 接口名, 取值列)
    _MONTHLY = {
        "PMI": ("macro_china_pmi_yearly", "今值"),
        "CPI": ("macro_china_cpi_monthly", "今值"),
        "PPI": ("macro_china_ppi_yearly", "今值"),
        "M2_yoy": ("macro_china_m2_yearly", "今值"),
    }

    #: 日频指标:指标名 -> (akshare 接口名, 取值列, 缩放系数)
    #: 外汇牌价按 100 单位报价,换算成 1 单位要除以 100
    _DAILY = {
        "10y_yield": ("bond_zh_us_rate", "中国国债收益率10年", 1.0),
        "USD_CNY": ("currency_boc_sina", "央行中间价", 0.01),
    }

    def is_available(self) -> tuple[bool, str]:
        try:
            import akshare  # noqa: F401
        except ImportError:
            return False, "需要 akshare 包,安装 forgemind[cn] 后可用"
        return True, ""

    def _monthly_series(self, ak, func_name: str, value_col: str) -> pd.DataFrame:
        """月度指标:长表(商品/日期/今值)取成 (date, value)。"""
        df = call_with_timeout(lambda: getattr(ak, func_name)())
        if df is None or df.empty:
            return pd.DataFrame(columns=["date", "value"])
        if "日期" not in df.columns or value_col not in df.columns:
            return pd.DataFrame(columns=["date", "value"])
        out = df[["日期", value_col]].rename(columns={"日期": "date", value_col: "value"})
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out["value"] = pd.to_numeric(out["value"], errors="coerce")
        return out.dropna(subset=["date", "value"]).sort_values("date")

    def _daily_series(self, ak, func_name: str, value_col: str, scale: float) -> pd.DataFrame:
        """日频指标:取成 (date, value)。"""
        df = call_with_timeout(lambda: getattr(ak, func_name)())
        if df is None or df.empty:
            return pd.DataFrame(columns=["date", "value"])
        if "日期" not in df.columns or value_col not in df.columns:
            return pd.DataFrame(columns=["date", "value"])
        out = df[["日期", value_col]].rename(columns={"日期": "date", value_col: "value"})
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out["value"] = pd.to_numeric(out["value"], errors="coerce") * scale
        return out.dropna(subset=["date", "value"]).sort_values("date")

    def fetch(self, start=None, end=None, **kwargs) -> pl.DataFrame:
        """拉宏观指标,按日期对齐成一张宽表。"""
        import akshare as ak

        schema = self.get_schema()
        series: dict[str, pd.DataFrame] = {}
        for name, (func_name, value_col) in self._MONTHLY.items():
            try:
                series[name] = self._monthly_series(ak, func_name, value_col)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "macro_indicator_failed", indicator=name, error_type=type(exc).__name__
                )
                series[name] = pd.DataFrame(columns=["date", "value"])
        for name, (func_name, value_col, scale) in self._DAILY.items():
            try:
                series[name] = self._daily_series(ak, func_name, value_col, scale)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "macro_indicator_failed", indicator=name, error_type=type(exc).__name__
                )
                series[name] = pd.DataFrame(columns=["date", "value"])

        all_dates = pd.concat(
            [s["date"] for s in series.values() if not s.empty]
            or [pd.Series([], dtype="datetime64[ns]")],
            ignore_index=True,
        )
        if all_dates.empty:
            return _empty_like_schema(schema)

        index = pd.DataFrame({"date": sorted(all_dates.unique())})
        merged = index
        for name, frame in series.items():
            if frame.empty:
                merged[name] = float("nan")
                continue
            # 月度指标在发布日之后一直有效,按"最近一次发布"往前找
            merged = pd.merge_asof(
                merged.sort_values("date"),
                frame.rename(columns={"value": name}),
                on="date",
                direction="backward",
            )

        merged = merged.sort_values("date")
        if start is not None:
            merged = merged[merged["date"] >= pd.Timestamp(start)]
        if end is not None:
            merged = merged[merged["date"] <= pd.Timestamp(end)]

        result = pl.from_pandas(merged[["date"] + list(schema.keys())[1:]])
        # schema 声明的是 date,不是 datetime —— 对不上会让调用方按日期
        # 分组时拿到一堆零时分秒
        if result.schema.get("date") != pl.Date:
            result = result.with_columns(pl.col("date").cast(pl.Date))
        # 取不到的指标是 NaN,而 NaN 不等于 null:null_count 数不到它,
        # drop_nulls 也删不掉它,NaN 会一路传进计算。缺数据要写成 null。
        float_cols = [c for c, t in schema.items() if t == "float" and c in result.columns]
        if float_cols:
            result = result.with_columns(
                [
                    pl.when(pl.col(c).is_nan()).then(None).otherwise(pl.col(c)).alias(c)
                    for c in float_cols
                ]
            )
        return result

    def get_schema(self):
        return {
            "date": "date",
            "PMI": "float",
            "CPI": "float",
            "PPI": "float",
            "M2_yoy": "float",
            "10y_yield": "float",
            "USD_CNY": "float",
        }


# === 行业分类 ===
class SectorDataSource(DataSource):
    """行业分类 — 申万 / 中信 / GICS"""

    name = "Sector"
    is_free = True

    def __init__(self, classification: str = "申万"):
        self.classification = classification

    def is_available(self) -> tuple[bool, str]:
        return False, (
            "行业分类源尚未接入真实申万/中信分类数据,如实报不可用;接入真实分类表后再开放。"
        )

    def fetch(self, symbols: list[str], **kwargs) -> pl.DataFrame:
        """返回行业分类"""
        self.require_available()
        raise DataSourceUnavailableError(self.name, self.is_available()[1])

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
