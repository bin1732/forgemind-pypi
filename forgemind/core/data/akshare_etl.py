# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import asyncio

import pandas as pd

from forgemind.core.data.storage import DuckDBStorage
from forgemind.core.observability.logging import get_logger

logger = get_logger("forgemind.akshare_etl")


class AKShareDataSource:
    """
    AKShare 免费数据源

    用法:
        async with AKShareDataSource() as ds:
            df = await ds.get_history("600519.SH", start="2024-01-01", end="2024-12-31")
    """

    def __init__(self):
        self._akshare = None
        logger.info("akshare_init")

    async def __aenter__(self):
        try:
            import akshare as ak
            self._akshare = ak
            logger.info("akshare_loaded")
        except ImportError:
            logger.warning(
                "akshare_not_installed",
                hint="pip install 'forgemind[cn]'",
            )
            self._akshare = None
        return self

    async def __aexit__(self, *args):
        pass

    async def get_stock_list(self) -> pd.DataFrame:
        """拉 A 股全列表"""
        if not self._akshare:
            return pd.DataFrame()
        try:
            # stock_info_a_code_name — A 股代码 + 名称
            df = self._akshare.stock_info_a_code_name()
            df = df.rename(columns={
                "code": "symbol",
                "name": "name",
            })
            logger.info("akshare_stock_list_loaded", count=len(df))
            return df
        except Exception as e:
            logger.error("akshare_stock_list_failed", error=str(e))
            return pd.DataFrame()

    async def get_history(
        self,
        symbol: str,
        start: str = "2024-01-01",
        end: str = "2024-12-31",
        adjust: str = "qfq",  # 前复权
        period: str = "daily",
    ) -> pd.DataFrame:
        """
        拉历史 K 线

        Args:
            symbol: 股票代码(6 位数字,如 "600519")
            start: 开始日期
            end: 结束日期
            adjust: qfq 前复权 / hfq 后复权 / "" 不复权
            period: daily / weekly / monthly

        Returns:
            DataFrame(date, symbol, open, high, low, close, volume)
        """
        if not self._akshare:
            return pd.DataFrame()
        try:
            # stock_zh_a_hist — 历史行情
            # akshare 要求日期格式 YYYYMMDD
            start_fmt = start.replace("-", "")
            end_fmt = end.replace("-", "")
            df = self._akshare.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_fmt,
                end_date=end_fmt,
                adjust=adjust,
            )

            if df.empty:
                return df

            # 标准化列名
            df = df.rename(columns={
                "日期": "date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",
            })
            df["symbol"] = symbol
            df["date"] = pd.to_datetime(df["date"])

            logger.info(
                "akshare_history_loaded",
                symbol=symbol,
                start=start,
                end=end,
                n=len(df),
            )
            return df[["date", "symbol", "open", "high", "low", "close", "volume"]]
        except Exception as e:
            logger.error("akshare_history_failed", symbol=symbol, error=str(e))
            return pd.DataFrame()


class AKShareETL:
    """
    AKShare ETL — 把数据落到 DuckDB

    用法:
        etl = AKShareETL()
        await etl.run(symbols=["600519", "000001"], days=365)
    """

    def __init__(self, storage: DuckDBStorage | None = None):
        self.storage = storage or DuckDBStorage()
        logger.info("akshare_etl_init")

    async def init_tables(self):
        """初始化 DuckDB 表"""
        with self.storage as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS stock_list (
                    symbol VARCHAR PRIMARY KEY,
                    name VARCHAR
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS kline_daily (
                    date DATE,
                    symbol VARCHAR,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume BIGINT,
                    PRIMARY KEY (date, symbol)
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_kline_symbol ON kline_daily(symbol, date)")
            logger.info("akshare_etl_tables_created")

    async def run(
        self,
        symbols: list[str],
        start: str = "2024-01-01",
        end: str = "2024-12-31",
        batch_size: int = 10,
    ) -> dict[str, int]:
        """
        跑 ETL

        Args:
            symbols: 股票代码列表(6 位数字)
            start: 开始日期
            end: 结束日期
            batch_size: 每批多少(防限流)
        """
        await self.init_tables()

        async with AKShareDataSource() as ds:
            # 1. 股票列表
            stock_list = await ds.get_stock_list()
            if not stock_list.empty:
                with self.storage as db:
                    for _, row in stock_list.iterrows():
                        db.execute(
                            "INSERT OR REPLACE INTO stock_list VALUES (?, ?)",
                            [row["symbol"], row["name"]],
                        )

            # 2. 历史 K 线
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i : i + batch_size]
                logger.info(
                    "akshare_etl_batch",
                    batch=i // batch_size + 1,
                    n=len(batch),
                )

                for symbol in batch:
                    df = await ds.get_history(symbol, start, end)
                    if df.empty:
                        continue

                    with self.storage as db:
                        for _, row in df.iterrows():
                            db.execute(
                                """INSERT OR REPLACE INTO kline_daily
                                (date, symbol, open, high, low, close, volume)
                                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                [
                                    row["date"],
                                    row["symbol"],
                                    row["open"],
                                    row["high"],
                                    row["low"],
                                    row["close"],
                                    row["volume"],
                                ],
                            )

                    # 防限流
                    await asyncio.sleep(0.5)

            # 3. 统计
            with self.storage as db:
                n_stocks = db.query_scalar("SELECT COUNT(*) FROM stock_list")
                n_klines = db.query_scalar("SELECT COUNT(*) FROM kline_daily")
                logger.info(
                    "akshare_etl_complete",
                    stocks=n_stocks,
                    klines=n_klines,
                )
                return {"stocks": n_stocks, "klines": n_klines}
