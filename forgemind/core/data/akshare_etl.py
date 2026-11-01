# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import time

import pandas as pd

from forgemind.core.data.fetch_guard import call_with_timeout
from forgemind.core.data.storage import DuckDBStorage, create_market_tables
from forgemind.core.observability.logging import get_logger

logger = get_logger("forgemind.akshare_etl")


def _classify_fetch_error(exc: Exception) -> str:
    """把取数异常归类成用户可行动的几种原因

    必须是**模块级**函数:AKShareETL.run 在初始化阶段也要用它,
    只挂在 AKShareDataSource 上的话会 AttributeError —— 保护代码自己
    抛错比不保护更糟。
    """
    msg = str(exc).lower()
    etype = type(exc).__name__
    # 类型比消息可靠:ConnectionError("reset") 的消息里根本没有
    # "connection" 字样,只看文本会把它误判成 unclassified
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return "network_unreachable"
    if isinstance(exc, PermissionError) or "permission" in msg or "errno 13" in msg:
        return "storage_permission_denied"
    if "no space" in msg or "disk full" in msg or "errno 28" in msg:
        return "storage_full"
    # DuckDB 并发写分类:
    # ConstraintException → 只有 PK/UNIQUE 冲突是并发,其它(NOT NULL / CHECK)
    #   不归 storage_locked(可能是数据 bug,不是锁的问题)
    # TransactionException → 几乎总是 commit 时的并发冲突
    # IOException → 只有消息里含 lock/flock 字样才算锁;
    #   "Cannot read from file" / "disk full" 这种不算
    if etype == "ConstraintException":
        if "primary key" in msg or "unique constraint" in msg or "duplicate key" in msg:
            return (
                "storage_locked(另一个进程或线程正占用 DuckDB 文件,"
                "多半是 API 服务、另一个 ETL、pick、agent 同时在写;"
                "先停掉其它进程再重试,或用 FORGEMIND_DATA_DIR "
                "指向另一个目录)"
            )
    if etype == "TransactionException":
        return (
            "storage_locked(并发事务提交失败 —— 另一个进程或线程正"
            "在写同一 DuckDB 文件;先停掉其它进程再重试,或用 "
            "FORGEMIND_DATA_DIR 指向另一个目录)"
        )
    if etype == "IOException" and (
        "lock" in msg or "could not set lock" in msg or "conflict" in msg
    ):
        return (
            "storage_locked(DuckDB 文件级 flock 失败 —— 另一进程正在"
            "读或写;用 FORGEMIND_DATA_DIR 指向另一个目录)"
        )
    if "ioexception" in etype.lower() or isinstance(exc, OSError):
        if "lock" in msg or "could not set lock" in msg or "conflict" in msg:
            return (
                "storage_locked(另一个进程正占用 data/duckdb/main.db,"
                "多半是 API 服务或另一个 CLI 还在运行;关掉它,或用 "
                "FORGEMIND_DATA_DIR 指向另一个目录)"
            )
    if any(
        k in msg
        for k in (
            "connection",
            "timed out",
            "timeout",
            "resolve",
            "ssl",
            "max retries",
            "reset by peer",
            "aborted",
        )
    ):
        return "network_unreachable"
    if any(k in msg for k in ("json", "decode", "expecting value")):
        return "upstream_returned_non_json(可能限流或被拦截)"
    if isinstance(exc, ModuleNotFoundError):
        return "akshare_not_installed"
    if "invalid" in msg and "symbol" in msg:
        return "invalid_symbol_format"
    if any(k in msg for k in ("too many", "rate", "频繁")):
        return "rate_limited"
    return f"unclassified:{type(exc).__name__}"


class AKShareDataSource:
    """
    AKShare 免费数据源

    用法:
        async with AKShareDataSource() as ds:
            df = await ds.get_history("600519.SH", start="2024-01-01", end="2024-12-31")
    """

    def __init__(self):
        self._akshare = None
        #: 最近一次取数失败的原因分类(None = 尚无失败)
        self._last_error: str | None = None
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

    #: A 股全列表的取数源。聚合接口在部分网络下会被拒,交易所自己的名单
    #: 接口是另一条路 —— 拿不到全市场代码表,依赖全市场的功能就只剩用户
    #: 给的那些标的。
    _STOCK_LIST_SOURCES = {
        "eastmoney": "stock_info_a_code_name",
        "sse": "stock_info_sh_name_code",
        "szse": "stock_info_sz_name_code",
    }

    #: 各源的列名不一样,统一成 symbol / name
    _STOCK_LIST_COLUMNS = {
        "eastmoney": ("code", "name"),
        "sse": ("证券代码", "证券简称"),
        "szse": ("A股代码", "A股简称"),
    }

    async def get_stock_list(self) -> pd.DataFrame:
        """拉 A 股全列表。

        聚合接口给的是全市场,拿得到就用它。拿不到就退到各交易所自己的
        名单接口 —— 能取到的交易所都要合并:只取到一个交易所的名单,那
        不是全市场,是那一个交易所。用了哪些源会一并报出来。
        """
        if not self._akshare:
            return pd.DataFrame()

        aggregate = self._fetch_stock_list("eastmoney")
        if aggregate is not None:
            return aggregate

        frames = []
        providers = []
        for source in ("sse", "szse"):
            df = self._fetch_stock_list(source)
            if df is None:
                continue
            frames.append(df)
            providers.append(source)
        if not frames:
            logger.error("akshare_stock_list_failed", error="所有取数源都不可用")
            return pd.DataFrame()
        merged = pd.concat(frames, ignore_index=True).drop_duplicates(
            subset=["symbol"], keep="first"
        )
        merged.attrs["provider"] = "+".join(providers)
        logger.info(
            "akshare_stock_list_loaded", count=len(merged), provider=merged.attrs["provider"]
        )
        return merged

    #: 取数调用的超时秒数。这些接口在受限网络下可能连接建起来却不回
    #: 数据,没有超时的取数会把整条 ETL 挂住 —— 卡住比取不到更难排查。
    _FETCH_TIMEOUT = 25.0

    @staticmethod
    def _call_with_timeout(func, timeout: float = 25.0):
        """带超时的调用。

        第三方接口不暴露超时参数,socket 的默认超时是这里唯一能抓的
        手柄:连接建起来却不回数据时,它会变成一次超时失败,而不是无限
        期地等下去。调用期间这个默认值是进程级的,调用结束立刻还原。
        """
        return call_with_timeout(func, timeout)

    def _fetch_stock_list(self, source: str) -> pd.DataFrame | None:
        """从指定源取 A 股名单,归一成 symbol / name。取不到返回 None。

        这些接口在受限网络下会间歇性失败 —— 同一个源上一分钟通、这一
        分钟就断。连接层面的失败重试几次再放弃,免得一次抖动就少了半个
        市场的代码表。
        """
        func_name = self._STOCK_LIST_SOURCES[source]
        # 两次就够:一次重试加一次换源。再多只是把卡住的时间拉长。
        for attempt in range(2):
            try:
                df = self._call_with_timeout(
                    lambda: getattr(self._akshare, func_name)(),
                    self._FETCH_TIMEOUT,
                )
                code_col, name_col = self._STOCK_LIST_COLUMNS[source]
                if code_col not in df.columns or name_col not in df.columns:
                    raise KeyError(f"{source} 的列名与预期不符: {list(df.columns)[:6]}")
                df = df[[code_col, name_col]].rename(columns={code_col: "symbol", name_col: "name"})
                df = df.dropna(subset=["symbol", "name"])
                df["symbol"] = df["symbol"].astype(str).str.strip()
                df.attrs["provider"] = source
                return df
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "akshare_stock_list_source_failed", provider=source, error_type=type(e).__name__
                )
                if attempt < 1:
                    time.sleep(1.5 * (attempt + 1))
        return None

    # 类内路径与模块级共用同一份分类逻辑。早期这里另写了一份只按消息文本
    # 匹配的简化版本,会把 DuckDB 的并发锁、权限、磁盘满都误报成网络问题,
    # 用户看不到"另一个进程正占用数据库文件"这类可行动指引。
    _classify_fetch_error = staticmethod(_classify_fetch_error)

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
            self._last_error = "akshare_not_installed"
            return pd.DataFrame()

        start_fmt = start.replace("-", "")
        end_fmt = end.replace("-", "")

        # 多源回退
        #
        # 多源回退: 任一可达即用, 单一数据源不应作为可用性前提。
        last_err: Exception | None = None
        for provider, fetch in self._history_providers(symbol, start_fmt, end_fmt, adjust, period):
            try:
                df = self._call_with_timeout(fetch, self._FETCH_TIMEOUT)
            except Exception as exc:
                last_err = exc
                logger.warning(
                    "akshare_provider_failed",
                    symbol=symbol,
                    provider=provider,
                    error_type=type(exc).__name__,
                )
                continue
            if df is None or df.empty:
                last_err = None  # 该源可用但区间内无数据,不必换源
                break
            df = self._normalize_history(df, symbol)
            # 标记数据来源,便于追溯同一标的跨源的前复权口径差异
            df.attrs["provider"] = provider
            df.attrs["provider"] = provider
            logger.info(
                "akshare_history_loaded",
                symbol=symbol,
                provider=provider,
                start=start,
                end=end,
                n=len(df),
            )
            return df

        reason = (
            _classify_fetch_error(last_err)
            if last_err
            else "empty_result(所有源均返回空,可能是代码无数据或日期区间为空)"
        )
        self._last_error = reason
        logger.error(
            "akshare_history_failed",
            symbol=symbol,
            error_type=type(last_err).__name__ if last_err else "EmptyData",
            reason=reason,
        )
        return pd.DataFrame()

    def _history_providers(self, symbol, start_fmt, end_fmt, adjust, period):
        """按可用性排序的取数源:(名称, 调用)"""
        ak = self._akshare
        ak_name = self._exchange_prefixed(symbol)
        return [
            (
                "eastmoney",
                lambda: ak.stock_zh_a_hist(
                    symbol=symbol,
                    period=period,
                    start_date=start_fmt,
                    end_date=end_fmt,
                    adjust=adjust,
                ),
            ),
            (
                "tencent",
                lambda: ak.stock_zh_a_hist_tx(
                    symbol=ak_name, start_date=start_fmt, end_date=end_fmt, adjust=adjust
                ),
            ),
            (
                "sina",
                lambda: ak.stock_zh_a_daily(
                    symbol=ak_name, start_date=start_fmt, end_date=end_fmt, adjust=adjust
                ),
            ),
        ]

    @staticmethod
    def _exchange_prefixed(symbol: str) -> str:
        """600519 -> sh600519 / 000001 -> sz000001(新浪/腾讯的代码格式)"""
        s = str(symbol).strip().lower()
        if s.startswith(("sh", "sz", "bj")):
            return s
        head = s[:1]
        if symbol.isdigit() and len(s) == 6:
            prefix = "sh" if head in "5679" else "sz"
            return prefix + s
        return s

    @staticmethod
    def _normalize_history(df: "pd.DataFrame", symbol: str) -> "pd.DataFrame":
        """把不同源的列名统一成 date/open/high/low/close/volume"""
        import pandas as _pd

        df = df.rename(
            columns={
                "日期": "date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",
            }
        )
        # 腾讯/新浪用英文列名时做一次兜底
        df.columns = [str(c).lower() for c in df.columns]
        if "date" in df.columns:
            df["date"] = _pd.to_datetime(df["date"]).dt.date
        df["symbol"] = symbol
        want = ["date", "symbol", "open", "high", "low", "close", "volume"]
        for c in want:
            if c not in df.columns:
                df[c] = None
        df = df[want]
        if df["date"].isna().any():
            df = df.dropna(subset=["date"])
        return df


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
            # 行情表的 DDL 与索引由 storage.create_market_tables 单一定义。
            # 两处各写一遍时索引名会对不上,同一个索引会被建出两个名字,
            # 写放大一倍,库里到底有几个索引还取决于哪条路径先跑。
            create_market_tables(db)
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
        # 建表/初始化也可能因磁盘、上游握手等失败,必须一并纳入失败分类,
        # 否则用户看到的是裸堆栈而不是可行动的提示
        try:
            await self.init_tables()
        except Exception as exc:
            reason = _classify_fetch_error(exc)
            logger.error("akshare_etl_init_failed", reason=reason, error_type=type(exc).__name__)
            return {
                "stocks": 0,
                "klines": 0,
                "ok_symbols": 0,
                "stocks_in_db": 0,
                "klines_in_db": 0,
                "failures": {f"init:{reason}": 1},
            }

        report: dict[str, int] = {}
        failures: dict[str, int] = {}

        async with AKShareDataSource() as ds:
            # 1. 股票列表
            try:
                stock_list = await ds.get_stock_list()
            except Exception as exc:
                # 拿不到代码表不该中断:历史 K 线仍可拉
                logger.warning("akshare_stock_list_failed", error_type=type(exc).__name__)
                stock_list = pd.DataFrame()
            #: 本次取到的代码表条数。与库里的累计条数分开 —— 表里已经有
            #: 历史数据时,报累计数会让人以为这次也取到了那么多。
            n_stocks_fetched = len(stock_list)
            stock_list_provider = stock_list.attrs.get("provider", "unknown")
            if not stock_list.empty:
                with self.storage as db:
                    for _, row in stock_list.iterrows():
                        db.execute(
                            "INSERT OR REPLACE INTO stock_list (symbol, name) VALUES (?, ?)",
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
                        # 记录该标的失败数与原因,不再静默跳过
                        reason = ds._last_error or "empty_result(可能是代码无数据或日期区间为空)"
                        failures[reason] = failures.get(reason, 0) + 1
                        continue
                    report[symbol] = len(df)

                    provider = df.attrs.get("provider", "unknown")
                    n_inserted = 0
                    n_failed = 0
                    last_insert_err: Exception | None = None
                    with self.storage as db:
                        for _, row in df.iterrows():
                            # INSERT 必包 try/except:并发或磁盘异常不应
                            # 让整个 ETL 静默丢数据。ConstraintException /
                            # TransactionException 都被 _classify_fetch_error
                            # 转成 actionable 的 storage_locked。
                            try:
                                db.execute(
                                    """INSERT OR REPLACE INTO kline_daily
                                    (date, symbol, open, high, low, close, volume, provider)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                                    [
                                        row["date"],
                                        row["symbol"],
                                        row["open"],
                                        row["high"],
                                        row["low"],
                                        row["close"],
                                        row["volume"],
                                        provider,
                                    ],
                                )
                                n_inserted += 1
                            except Exception as insert_exc:  # noqa: BLE001
                                n_failed += 1
                                last_insert_err = insert_exc

                    if n_failed:
                        reason = (
                            _classify_fetch_error(last_insert_err) if last_insert_err else "unknown"
                        )
                        failures[reason] = failures.get(reason, 0) + n_failed
                        # 报告里只记「真成功写入的」条数,免得用户看 len(df)
                        # 以为全成功
                        report[symbol] = n_inserted
                        logger.warning(
                            "akshare_etl_partial_insert",
                            symbol=symbol,
                            n_inserted=n_inserted,
                            n_failed=n_failed,
                            reason=reason,
                        )
                    else:
                        report[symbol] = n_inserted

                    # 防限流
                    await asyncio.sleep(0.5)

            # 3. 统计
            with self.storage as db:
                n_stocks_in_db = db.query_scalar("SELECT COUNT(*) FROM stock_list")
                n_klines_in_db = db.query_scalar("SELECT COUNT(*) FROM kline_daily")
                #: 本次真正写入的行数。库里有多少行是另一回事 ——
                #: 那是历次累计,拿它当本次成果报,用户看到的数字是虚的。
                n_klines = sum(report.values())
                logger.info(
                    "akshare_etl_complete",
                    stocks=n_stocks_fetched,
                    klines=n_klines,
                    stocks_in_db=n_stocks_in_db,
                    klines_in_db=n_klines_in_db,
                    stock_list_provider=stock_list_provider,
                    ok_symbols=len(report),
                    failed_symbols=len(failures),
                )
                if failures:
                    logger.warning(
                        "akshare_etl_partial_failure",
                        failures=failures,
                        ok_symbols=len(report),
                    )
                return {
                    "stocks": n_stocks_fetched,
                    "klines": n_klines,
                    "stocks_in_db": n_stocks_in_db,
                    "klines_in_db": n_klines_in_db,
                    "stock_list_provider": stock_list_provider,
                    "ok_symbols": len(report),
                    "failures": failures,
                }
