# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import threading as _threading
from pathlib import Path

import duckdb

from forgemind.core.config.settings import get_settings
from forgemind.core.observability.logging import get_logger

logger = get_logger("forgemind.storage")


class LocalStoreLockedError(RuntimeError):
    """本地库正被另一个进程占着。

    DuckDB 的文件锁是**独占**的:同一个库文件,同一时间只能一个进程打开
    (只读模式也不行 —— 实测过,read_only=True 一样被锁挡)。于是"桌面端
    开着"的时候,终端里的命令连不上那个库。

    这件事必须单独认出来:连不上与"库里没有数据"是两回事,说成后者会把
    用户引到一条同样跑不通的路上(他会去拉数据,而拉数据同样连不上)。
    """

    def __init__(self, path: str | None = None):
        self.path = path
        super().__init__(
            "本地库正被另一个进程占用 —— 桌面端开着时它会占着同一个库。"
            "关掉那个进程再试,或用 FORGEMIND_DATA_DIR 换个目录。"
        )


class LocalStoreWriteError(RuntimeError):
    """存储写不进去(磁盘满、配额满、权限不足)。

    与 LocalStoreLockedError 是两回事:那是"读不到",这个是"写不进去"。
    两者都归资源类,但用户要做的事不一样 —— 一个要关掉占着库的进程,
    一个要清磁盘或改权限。

    原始报错里有本机路径,不往外带。
    """

    def __init__(self, path: str | None = None):
        self.path = path
        super().__init__(
            "存储写不进去 —— 磁盘满了、配额用完了,或没有写权限。"
            "清出空间或改好权限后重试;也可以用 FORGEMIND_DATA_DIR 换个目录。"
        )


def is_lock_conflict(exc: BaseException) -> bool:
    """这个异常是不是"库被另一个进程占着"。

    认的是 DuckDB 的报错文本里那句锁冲突 —— 没有别的信号:它没有自己的
    异常类型,也不带错误码。
    """
    text = str(exc).lower()
    return "conflicting lock" in text or "could not set lock" in text


#: 写不进去的样子。DuckDB 的写失败**不带 errno** —— 异常对象上没有,
#: 只能看报错文本。这些措辞是 DuckDB 与操作系统给出来的。
WRITE_FAILURE_MARKERS = (
    "file too large",  # errno 27:超出文件大小上限(配额)
    "no space left",  # errno 28:磁盘满
    "disk full",
    "permission denied",  # errno 13:权限不足
    "errno 27",
    "errno 28",
    "errno 13",
)


def is_write_failure(exc: BaseException) -> bool:
    """这个异常是不是"写不进去"(磁盘满、配额满、权限不足)。

    判定只看报错文本:上一层的异常没有 errno,底层可能包着带 errno
    的 OSError —— 所以要顺着 cause 链找下去。
    """
    if any(marker in str(exc).lower() for marker in WRITE_FAILURE_MARKERS):
        return True
    cause = exc.__cause__
    if cause is not None and cause is not exc:
        return is_write_failure(cause)
    return False


def is_resource_error(exc: BaseException) -> bool:
    """这个异常是不是"资源类"(库被占着 / 存储写不进去)。

    这两类都是"环境暂时用不了":用户做完对应的动作就能继续 —— 关掉
    占着库的进程,或清出磁盘空间。命令行的退出码表把这一类归到 4。
    """
    return isinstance(exc, (LocalStoreLockedError, LocalStoreWriteError))


def bare_symbol(symbol: str) -> str:
    """把 '600519.SH' / 'sh600519' / 'SH600519' 统一成 DuckDB 里存的 '600519'

    ETL 落库用的是 6 位代码,而 CLI / API / MCP 的入参常常带交易所后缀
    (README 与 `forgemind agent --symbol` 的默认值就是 '600519.SH')。
    不归一化的后果:用户照文档先跑 etl 再跑 agent,后者查不到任何 K 线,
    然后如实报"本地没有行情数据" —— 看起来像数据没拉,其实是格式不匹配。

    归一化必须放在**查询前**,而不是要求每个调用方自己记得剥后缀。
    """
    s = str(symbol).strip().upper()
    for sep in (".", "-", "_"):
        if sep in s:
            s = s.split(sep)[0]
    for pre in ("SH", "SZ", "BJ"):
        if s.startswith(pre) and s[2:].isdigit():
            s = s[2:]
    return s.strip()


def market_data_unavailable_reason(symbol: str) -> str:
    """本地库里没有这个标的的行情 —— 对用户说的一句话。

    命令行、接口、MCP 三条通道说的是同一件事,文案也只在这里写一份:
    抄三遍就会漂,漂了以后三个地方对不上,谁也说不清哪句是对的。
    """
    return f"本地库里没有 {symbol} 的 K 线"


def market_data_unreadable_reason() -> str:
    """本地行情读不了(表还没建或 schema 不对)—— 对用户说的一句话。

    **不写异常类型名。** "CatalogException" 是内部实现:它出现在响应
    里,读的人只会以为程序坏了 —— 而程序没坏,只是还没拉数据。真正
    的原因(表没建)用一句话说清楚,类型名留给日志。
    """
    return "本地行情库还读不了(表可能还没建,先跑 forgemind etl 拉数据)"


def data_freshness(last_date: str | None, today=None) -> str:
    """把"数据最新日期"变成一句人能直接判断的话

    量化工具最容易被忽视的误导:计算完全正确,但依据的是几周前的
    收盘价。用户看到"均线空头排列"却不知道那是上个月的形态。
    这里只做陈述,不做判断 —— 多久算过期取决于策略,不替用户决定。
    """
    import datetime as _dt

    if not last_date:
        return "未知(没有数据)"
    try:
        d = _dt.date.fromisoformat(str(last_date)[:10])
    except ValueError:
        return f"未知(无法解析日期 {last_date!r})"
    today = today or _dt.date.today()
    days = (today - d).days
    if days < 0:
        return f"{d}(未来日期,请检查数据源)"
    if days == 0:
        return f"{d}(今天)"
    if days == 1:
        return f"{d}(昨天)"
    if days <= 7:
        return f"{d}({days} 天前)"
    if days <= 60:
        return f"{d}(**{days} 天前,已明显滞后**)"
    return f"{d}(**{days} 天前,严重过期,请重跑 forgemind etl**)"


# DuckDB 是嵌入式 OLAP, connect() 内部走 mmap, 启动 < 1ms。
# 但每次 with DuckDBStorage() 仍要 allocate 连接对象 + 解析 schema cache。
# 同进程同 path 多次连接是浪费(典型场景: queryPortfolio 后紧跟 getKline),
# 加轻量级连接缓存。
#
# 但**缓存的是"根连接",不是给每个线程同一个连接**:
# DuckDB 的连接上,"最后一次查询的结果"只有一个槽位。多个线程共用一个
# 连接时,一个线程的 execute 会把另一个线程还没取的结果顶掉 ——
# fetchdf 取不到就返回 None,上层 .empty / .iterrows() 直接炸
# ("'NoneType' object has no attribute 'iterrows'")。更糟的是它可能
# 静默返回**别人的行**。
#
# 实测(16 线程 × 30 次参数化查询):共用一个连接 4 次拿到 None;
# 每人一个 cursor() 0 次 —— cursor 共享同一个数据库实例,但结果槽独立,
# 这正是 DuckDB 官方给多线程用的姿势。
#
# 另外首次连接要加锁:缓存冷的时候多个线程会同时 duckdb.connect(同一
# path),DuckDB 会回 "Unique file handle conflict" / "Could not set
# lock on file"。
_DUCKDB_CONN_CACHE: dict[str, "duckdb.DuckDBPyConnection"] = {}
_DUCKDB_CONN_LOCK = _threading.RLock()


class DuckDBStorage:
    """
    DuckDB 单节点 OLAP — 给 Agent / Notebook 用

    用法:
        with DuckDBStorage() as db:
            df = db.query_df("SELECT * FROM market_data WHERE symbol = '600519.SH'")

    同进程同 path 多次 with DuckDBStorage() 默认复用同一个数据库实例
    (每次拿一个游标, 各自的结果槽独立), 减少 connect() 开销。
    要写时显式 force_new=True 拿独占连接。
    """

    def __init__(self, path: str | None = None, force_new: bool = False):
        settings = get_settings()
        self.path = path or settings.duckdb_path
        self.force_new = force_new
        try:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            # 建目录就写不进去(没权限/磁盘满)—— 与后面的写失败是同一件
            # 事,归到同一个错上,用户清一次磁盘或改一次权限就够。
            if getattr(exc, "errno", None) in (13, 27, 28) or is_write_failure(exc):
                raise LocalStoreWriteError(self.path) from None
            raise
        self.conn: duckdb.DuckDBPyConnection | None = None
        logger.info("duckdb_storage_init", path=self.path, force_new=force_new)

    def __enter__(self):
        # force_new 显式绕过缓存: 上层需要独占连接做 init / 迁移时
        # 不写 cache, 让下个 with 继续用原 cached conn
        force_new = getattr(self, "force_new", False)
        with _DUCKDB_CONN_LOCK:
            root = _DUCKDB_CONN_CACHE.get(self.path) if not force_new else None
            if root is None:
                # 首次连接要加锁: 缓存冷的时候多个线程会同时 connect 同一个
                # path, DuckDB 会回 "Unique file handle conflict"
                try:
                    root = duckdb.connect(self.path)
                except Exception as exc:
                    # 库被别的进程占着 → 一件可识别的事,不是"连不上"。
                    # 原始报错里有本机路径,不往外带。
                    if is_lock_conflict(exc):
                        raise LocalStoreLockedError(self.path) from None
                    # 写不进去:连接本身就要写文件(建库文件与 WAL),磁盘满
                    # 或配额用完时,失败发生在**连接**这一步,还没走到
                    # 执行 SQL。不认它的话,上层只能笼统地说"连不上"。
                    if is_write_failure(exc):
                        raise LocalStoreWriteError(self.path) from None
                    raise
                if not force_new:
                    _DUCKDB_CONN_CACHE[self.path] = root
            # 每次拿一个游标: 同一个数据库实例, 但结果槽各自独立。
            # 直接共用根连接的话, 多线程并发查询会互相顶掉结果 ——
            # 见上面 _DUCKDB_CONN_CACHE 那段注释里的实测。
            self.conn = root if force_new else root.cursor()
        return self

    def __exit__(self, exc_type, exc_val, _exc_tb):
        if self.conn:
            if exc_type is not None:
                # 只在告警里放异常类型,不放原始异常文本:那里面有内部表名
                # 与整条 SQL(DuckDB 的报错会把查询原文带回来)。命令行的
                # 用户看到的是自己终端里的一行字,不该在这里读到内部实现。
                # 完整文本留在 debug 里 —— 要排查的人自己把级别打开。
                logger.warning(
                    "duckdb_context_exit_with_error",
                    exc_type=exc_type.__name__,
                )
                logger.debug(
                    "duckdb_context_exit_detail",
                    exc_type=exc_type.__name__,
                    exc_msg=str(exc_val) if exc_val else None,
                )
            # 不真关: 下次 with 同 path 自动复用 (连接缓存)
            # 写异常时回滚事务但不关 conn
            if exc_type is not None:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            self.conn = None  # 本次 instance 解引用, cached 仍持有底层连接

    def execute(self, sql: str, params: list | None = None):
        """执行 SQL(insert/update/ddl)"""
        if not self.conn:
            raise RuntimeError("Use within 'with' block")
        try:
            if params:
                self.conn.execute(sql, params)
            else:
                self.conn.execute(sql)
        except Exception as exc:
            # 写不进去要说清楚 —— 不然上层只能笼统地说"落盘失败",
            # 用户不知道要去清磁盘还是要改权限。原始报错里有本机路径,
            # 不往外带。
            if is_write_failure(exc):
                raise LocalStoreWriteError(self.path) from None
            raise

    def query_df(self, sql: str, params: list | None = None):
        """查询 → DataFrame"""
        if not self.conn:
            raise RuntimeError("Use within 'with' block")
        try:
            if params:
                return self.conn.execute(sql, params).df()
            return self.conn.execute(sql).df()
        except Exception as exc:
            # 读也会写(DuckDB 的 WAL),所以磁盘满的时候"读"也会失败。
            # 归到同一个错上 —— 用户清磁盘就够,不该分两种说法。
            if is_write_failure(exc):
                raise LocalStoreWriteError(self.path) from None
            raise

    def query_scalar(self, sql: str, params: list | None = None):
        """查询 → 单值"""
        df = self.query_df(sql, params)
        if df.empty:
            return None
        return df.iloc[0, 0]

    def table_exists(self, table_name: str) -> bool:
        """这张表在不在?

        **用异常问"表在不在"是反的**:第一次跑的人库里还没有这些表,那是
        正常情况,不是故障 —— 而异常会在存储层留下一条带内部表名与 SQL 的
        告警,命令行的用户看到的是一串 JSON,像坏了。

        表名是调用方给的内部名,这里不接受外部输入拼接(参数化查询)。
        """
        if not self.conn:
            raise RuntimeError("Use within 'with' block")
        n = self.conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
            [str(table_name)],
        ).fetchone()
        return bool(n and n[0])


def create_market_tables(db) -> None:
    """建行情表与索引 —— 单一真源。

    初始化与 ETL 都走这里。同一张表在两处各写一遍 DDL 时,索引名与列
    迟早对不上:两个名字的同一个索引会一起建出来,写放大一倍,而库里
    到底有几个索引还取决于哪条路径先跑。

    Args:
        db: 已进入 with 块的 DuckDBStorage。
    """
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
            provider VARCHAR,
            PRIMARY KEY (date, symbol)
        )
    """)
    # 老库没有 provider 列,补上;补不上的要报出来,不能静默
    cols = set(db.query_df("SELECT * FROM kline_daily LIMIT 0").columns)
    if "provider" not in cols:
        db.execute("ALTER TABLE kline_daily ADD COLUMN provider VARCHAR")
        logger.info("kline_daily_provider_column_added")
    # 老版本建的索引名是 idx_kline_symbol,列与现在的一模一样。老库升级
    # 之后会多出一个同列的索引,写入放大一倍 —— 而且没人会注意到。
    # 只删自己这个旧名字,不动用户自己建的索引。
    stale = db.query_df(
        "SELECT COUNT(*) AS n FROM duckdb_indexes() "
        "WHERE index_name = 'idx_kline_symbol' AND table_name = 'kline_daily'"
    )
    if not stale.empty and int(stale["n"].iloc[0]) > 0:
        db.execute("DROP INDEX IF EXISTS idx_kline_symbol")
        logger.info("kline_daily_stale_index_dropped")
    db.execute("CREATE INDEX IF NOT EXISTS idx_kline_symbol_date ON kline_daily(symbol, date)")


_init_lock = _threading.Lock()
_init_done_for: set[str] = set()


def init_duckdb(wait_for_lock: bool = False):
    """初始化 DuckDB — 创建本地表

    进程内单次:同 (db path) 只跑一次 DDL,避免并发线程同时
    CREATE INDEX 触发 DuckDB catalog write-write conflict
    ("TransactionException: Catalog write-write conflict on create
    with ... idx_kline_symbol_date")。新 db path 重新初始化。

    跨进程并发: 多进程同时 init 同一 db path 会撞 DuckDB file lock。
    DuckDB 的进程间锁是**排他**的 —— 连只读连接都连不上。所以"抢着
    建表"只能靠等: 后来者等前一个建完、放开锁,再自己连上。

    **等不等,由调用方明确选择**(wait_for_lock):

    - False(默认)—— 锁冲突立刻抛。命令路径用这个。库被桌面端这类
      长驻进程占着时,锁不会自己放开,让用户对着一条命令干等几十秒
      才看到"库被占着",是白等。
    - True —— 等前一个建完。明确知道"有人正在建表"的地方用这个
      (并发建库的用例、ETL 建库)。

    抛出的错是 LocalStoreLockedError —— 它是"读不到",不是"没有数据"。
    说成后者会把用户引到一条同样跑不通的路上。
    """
    import random
    import time as _time

    settings = get_settings()
    with _init_lock:
        if settings.duckdb_path in _init_done_for:
            return
        last_err = None
        # 退避要**封顶**还要**带抖动**:
        #
        # 封顶 —— 指数退避最后会睡到 51 秒,等待者会正好睡过"锁刚被释放"
        # 那一刻,于是明明只差几秒也要再等一个 51 秒的整轮,最后超时失败。
        # 抖动 —— 多个进程等同一个锁时,退避节奏一致就会同时醒来再撞一次,
        # 一直撞到重试次数用完。错开几百毫秒就能错开。
        #
        # 每次最多等 2 秒,共 40 次:锁一释放,两三秒内就能轮到自己。
        for _attempt in range(40):
            try:
                _do_init_duckdb_ddl(settings.duckdb_path)
                _init_done_for.add(settings.duckdb_path)
                return
            except (LocalStoreLockedError, duckdb.IOException, duckdb.OperationalError) as e:
                last_err = e
                err_str = str(e).lower()
                is_lock = (
                    isinstance(e, LocalStoreLockedError)
                    or "lock" in err_str
                    or "could not set" in err_str
                    or "conflicting" in err_str
                )
                if not is_lock:
                    # 非锁错 — 不重试, 直接抛
                    raise
                if not wait_for_lock:
                    # 库被占着,而占着它的进程不会自己放开。立刻把这件事
                    # 说清楚,好过让用户干等。锁冲突只有一种含义:
                    # 读不到 —— 不是"库里没有数据"。
                    if isinstance(e, LocalStoreLockedError):
                        raise
                    raise LocalStoreLockedError(settings.duckdb_path) from None
                _time.sleep(random.uniform(0.05, min(2.0, 0.1 * (2 ** min(_attempt, 5)))))
                continue
        # 重试次数用尽仍因 lock 失败 — 抛最后错
        if last_err:
            raise last_err


def _do_init_duckdb_ddl(db_path: str) -> None:
    """实际跑 DDL — 供 init_duckdb 锁内调用, IOException 时抛给外层重试"""
    with DuckDBStorage() as db:
        # market_data / factor_cache / decision_cache 三张表已删除 (全代码库零读零写)
        # 的 CREATE,但全代码库零读零写。删掉,DROP IF EXISTS 兼容老 db。
        # 真要的因子缓存 / 行情缓存等真接代码时再加,别在 schema 里承诺
        # "会写但实际不写"的能力。
        for dead in ("market_data", "factor_cache", "decision_cache"):
            try:
                db.execute(f"DROP TABLE IF EXISTS {dead}")
            except Exception:  # noqa: BLE001
                # 老 db 上 DROP 偶发 catalog 错,不影响主流程
                pass

        # K 线 / 股票列表
        create_market_tables(db)

        # 组合快照
        db.execute("""
                        CREATE TABLE IF NOT EXISTS portfolio_snapshot (
                            snapshot_id VARCHAR,
                            taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            cash DOUBLE NOT NULL,
                            currency VARCHAR DEFAULT 'CNY',
                            total_equity DOUBLE,
                            PRIMARY KEY (snapshot_id)
                        )
                    """)
        db.execute("""
                        CREATE TABLE IF NOT EXISTS portfolio_position (
                            snapshot_id VARCHAR,
                            symbol VARCHAR NOT NULL,
                            quantity DOUBLE NOT NULL,
                            avg_price DOUBLE NOT NULL,
                            unrealized_pnl DOUBLE DEFAULT 0,
                            PRIMARY KEY (snapshot_id, symbol),
                            -- 持仓数量必须 > 0 (0 或负数无意义, 实际买卖是 +quantity / -quantity)
                            -- 均价必须 > 0 (0 均价除法会爆, 负价无意义)
                            -- 强制数据完整性: 落库前应用层应已校验, DB 层再保一道
                            CONSTRAINT chk_pos_qty CHECK (quantity > 0),
                            CONSTRAINT chk_pos_avg CHECK (avg_price > 0)
                        )
                    """)

        # === portfolio_decision ===
        # 每个 snapshot 落一组 6 Agent 决策明细,给桌面 UI 多 Agent 面板用
        # (不再让前端硬编码 vote / score / reasoning)
        db.execute("""
                        CREATE TABLE IF NOT EXISTS portfolio_decision (
                            snapshot_id VARCHAR,
                            agent VARCHAR NOT NULL,
                            vote VARCHAR,
                            score DOUBLE,
                            confidence DOUBLE,
                            thesis TEXT,
                            evidence TEXT,
                            PRIMARY KEY (snapshot_id, agent),
                            -- vote 必须是 buy/sell/hold,NULL 表示"无观点"(unavailable 源)
                            CONSTRAINT chk_dec_vote CHECK (vote IS NULL OR vote IN ('buy','sell','hold')),
                            -- score 0-5,confidence 0-1
                            CONSTRAINT chk_dec_score CHECK (score IS NULL OR (score >= 0 AND score <= 5)),
                            CONSTRAINT chk_dec_conf CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
                        )
                    """)

        # === signal_history ===
        # MCP output_signal 落盘 + 桌面 signal-table 读真信号
        db.execute("""
                        CREATE TABLE IF NOT EXISTS signal_history (
                            signal_id VARCHAR PRIMARY KEY,
                            emitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            symbol VARCHAR NOT NULL,
                            side VARCHAR NOT NULL,
                            confidence DOUBLE,
                            rationale TEXT,
                            source VARCHAR,
                            -- CHECK 约束:side 必须是 BUY/SELL/HOLD,confidence 0-1
                            -- 老 db 已存在无 CHECK 的表,下面用 ALTER 尝试加 (失败 ignore)
                            CONSTRAINT chk_signal_side CHECK (side IN ('BUY','SELL','HOLD')),
                            CONSTRAINT chk_signal_conf CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
                        )
                    """)
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_signal_history_emitted_at ON signal_history(emitted_at)"
        )

        # === backtest_run ===
        # 每次 forgemind backtest 落一行真实指标,给桌面 UI 风险指标面板用
        db.execute("""
                        CREATE TABLE IF NOT EXISTS backtest_run (
                            run_id VARCHAR PRIMARY KEY,
                            ran_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            symbol VARCHAR,
                            strategy VARCHAR,
                            total_return DOUBLE,
                            sharpe DOUBLE,
                            sortino DOUBLE,
                            max_drawdown DOUBLE,
                            win_rate DOUBLE,
                            n_trades INTEGER,
                            -- 风险指标在合理范围;允许 NULL (还没算), 失败时记录
                            CONSTRAINT chk_bt_drawdown CHECK (max_drawdown IS NULL OR (max_drawdown >= -1 AND max_drawdown <= 0)),
                            CONSTRAINT chk_bt_winrate CHECK (win_rate IS NULL OR (win_rate >= 0 AND win_rate <= 1)),
                            CONSTRAINT chk_bt_ntrades CHECK (n_trades IS NULL OR n_trades >= 0)
                        )
                    """)

        logger.info("duckdb_init_complete", path=db_path)


def save_portfolio_snapshot(portfolio) -> str:
    """把一次组合状态落盘,返回 snapshot_id

    Args:
        portfolio: PortfolioContext(或任何有 cash/positions/total_equity/currency 的对象)

    供 `forgemind agent` 在每次决策后调用,让 MCP 的 query_portfolio 读到真实数据。
    """
    import uuid

    init_duckdb()
    snap_id = f"snap_{uuid.uuid4().hex[:12]}"
    with DuckDBStorage() as db:
        db.execute(
            "INSERT INTO portfolio_snapshot (snapshot_id, cash, currency, total_equity) "
            "VALUES (?, ?, ?, ?)",
            [
                snap_id,
                float(portfolio.cash),
                getattr(portfolio, "currency", "CNY"),
                float(getattr(portfolio, "total_equity", 0.0)),
            ],
        )
        for p in portfolio.positions:
            db.execute(
                "INSERT INTO portfolio_position "
                "(snapshot_id, symbol, quantity, avg_price, unrealized_pnl) VALUES (?, ?, ?, ?, ?)",
                [
                    snap_id,
                    p.symbol,
                    float(p.quantity),
                    float(p.avg_price),
                    float(getattr(p, "unrealized_pnl", 0.0)),
                ],
            )
    logger.info(
        "portfolio_snapshot_saved", snapshot_id=snap_id, n_positions=len(portfolio.positions)
    )
    return snap_id


def save_portfolio_decisions(snapshot_id: str, decisions: list[dict]) -> int:
    """把一组 6 Agent 决策明细落盘,关联到指定 snapshot

    decisions 元素 shape:
        {"agent": "Fundamentals"|"Technical"|"News"|"Bull"|"Bear"|"PM",
         "vote": "buy"|"sell"|"hold",
         "score": float (0-5),
         "confidence": float (0-1),
         "thesis": str,
         "evidence": str (可选,默认空)}

    返回写入行数,缺字段的那条会被跳过但日志告警,不阻断其它 agent 入库。
    桌面 UI 6 Agent 面板读这个表, vote / score / confidence 全部从 snapshot 来。
    """
    init_duckdb()
    written = 0
    skipped: list[str] = []
    with DuckDBStorage() as db:
        for d in decisions or []:
            agent = (d.get("agent") or "").strip()
            if not agent:
                skipped.append("<no agent>")
                continue
            try:
                db.execute(
                    "INSERT INTO portfolio_decision "
                    "(snapshot_id, agent, vote, score, confidence, thesis, evidence) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [
                        snapshot_id,
                        agent,
                        d.get("vote"),
                        float(d.get("score", 0.0)) if d.get("score") is not None else None,
                        float(d.get("confidence", 0.0))
                        if d.get("confidence") is not None
                        else None,
                        d.get("thesis"),
                        d.get("evidence"),
                    ],
                )
                written += 1
            except Exception as exc:  # noqa: BLE001
                # 单条 agent 失败不阻断(可能 schema 没及时同步)
                skipped.append(f"{agent}({type(exc).__name__})")
    if skipped:
        logger.warning(
            "portfolio_decision_partial_save",
            snapshot_id=snapshot_id,
            written=written,
            skipped=skipped,
        )
    return written


def _is_missing(value) -> bool:
    """空值判定:None 与 NaN 都算空。

    DuckDB 的列带 NULL 时,pandas 会把整列变成 float64,空值取出来是 NaN。
    NaN 序列化出去写的是 NaN —— 那不是合法 JSON,JavaScript 的 JSON.parse
    直接报错,好数据就这么没了(桌面端表现为"组合数据不是可解析的 JSON")。
    """
    if value is None:
        return True
    try:
        return bool(value != value)  # NaN != NaN
    except Exception:  # noqa: BLE001
        return False


def load_latest_decisions(limit_snapshots: int = 1) -> list[dict]:
    """读最近一组 portfolio_decision(snapshot 维度),给桌面 6 Agent 面板用

    返回:
        [{"agent": "Fundamentals", "vote": "buy", "score": 4,
          "confidence": 0.85, "thesis": "...", "evidence": "..."}]
    没有时返回空列表(让 UI 显示空态而不是假数据)。
    """
    init_duckdb()
    with DuckDBStorage() as db:
        exists = db.query_scalar(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='portfolio_decision'"
        )
        if not exists:
            return []
        snap_ids = db.query_df(
            "SELECT DISTINCT snapshot_id FROM portfolio_decision ORDER BY snapshot_id DESC LIMIT ?",
            [int(max(1, limit_snapshots))],
        )
        if snap_ids.empty:
            return []
        # 拿最近一个 snapshot 的所有 agent
        latest_snap = snap_ids.iloc[0]["snapshot_id"]
        rows = db.query_df(
            "SELECT agent, vote, score, confidence, thesis, evidence "
            "FROM portfolio_decision WHERE snapshot_id = ? ORDER BY agent",
            [latest_snap],
        )
    return [
        {
            "agent": r["agent"],
            # 空 vote 表示"这个 Agent 没能给出票"(它的数据源没接上),
            # 报成 None,不报 NaN
            "vote": None if _is_missing(r["vote"]) else r["vote"],
            "score": float(r["score"]) if not _is_missing(r["score"]) else None,
            "confidence": float(r["confidence"]) if not _is_missing(r["confidence"]) else None,
            "thesis": r["thesis"],
            "evidence": r["evidence"],
        }
        for _, r in rows.iterrows()
    ]


def save_backtest_run(
    symbol: str,
    strategy: str,
    metrics: dict,
) -> str:
    """把一次 backtest 的真实指标落盘,给桌面风险指标面板用

    metrics 期望键(total_return / sharpe / sortino / max_drawdown / win_rate /
    n_trades), 缺字段置 None, 不抛错。
    """
    import uuid

    init_duckdb()
    run_id = f"bt_{uuid.uuid4().hex[:12]}"
    with DuckDBStorage() as db:
        db.execute(
            "INSERT INTO backtest_run "
            "(run_id, symbol, strategy, total_return, sharpe, sortino, "
            " max_drawdown, win_rate, n_trades) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                symbol,
                strategy,
                metrics.get("total_return"),
                metrics.get("sharpe"),
                metrics.get("sortino"),
                metrics.get("max_drawdown"),
                metrics.get("win_rate"),
                int(metrics["n_trades"]) if metrics.get("n_trades") is not None else None,
            ],
        )
    logger.info(
        "backtest_run_saved",
        run_id=run_id,
        symbol=symbol,
        strategy=strategy,
        sharpe=metrics.get("sharpe"),
    )
    return run_id


def save_signal(
    signal_id: str,
    symbol: str,
    side: str,
    confidence: float,
    rationale: str,
    source: str = "mcp_output_signal",
) -> str:
    """把 output_signal 工具的信号落盘

    output_signal 落盘到这张表, signal-table 读真信号
    terminal 跑了 forgemind signal 之后,桌面 signal-table 不显示。
    落 signal_history 表,桌面从 forgemind://signals resource 拉真信号。

    返回 signal_id(已传,直接回传),错误时抛 RuntimeError 让 MCP 端处理。
    """
    import uuid

    if not signal_id:
        signal_id = f"sig_{uuid.uuid4().hex[:12]}_{symbol}"
    # 应用层校验:失败要快、要明确,不让 DB CHECK 抛难懂的异常
    if side not in ("BUY", "SELL", "HOLD"):
        raise ValueError(f"side 必须是 BUY/SELL/HOLD,收到 {side!r}")
    if not (0.0 <= float(confidence) <= 1.0):
        raise ValueError(f"confidence 必须在 [0, 1],收到 {confidence}")
    init_duckdb()
    with DuckDBStorage() as db:
        db.execute(
            "INSERT INTO signal_history "
            "(signal_id, symbol, side, confidence, rationale, source) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [signal_id, symbol, side, float(confidence), rationale, source],
        )
    logger.info("signal_saved", signal_id=signal_id, symbol=symbol, side=side)
    return signal_id


def load_recent_signals(limit: int = 100) -> list[dict]:
    """读最近 N 条真信号,给桌面 signal-table 用

    signal-table 拉 forgemind://signals MCP resource 读真落盘信号
    永远是空。现在拉 DuckDB signal_history,按 emitted_at 倒序。
    """
    init_duckdb()
    with DuckDBStorage() as db:
        exists = db.query_scalar(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='signal_history'"
        )
        if not exists:
            return []
        df = db.query_df(
            "SELECT signal_id, emitted_at, symbol, side, confidence, "
            "rationale, source FROM signal_history "
            "ORDER BY emitted_at DESC LIMIT ?",
            [int(max(1, limit))],
        )
    return [
        {
            "signal_id": r["signal_id"],
            "emitted_at": str(r["emitted_at"]),
            "symbol": r["symbol"],
            "side": r["side"],
            "confidence": float(r["confidence"]) if r["confidence"] is not None else None,
            "rationale": r["rationale"],
            "source": r["source"],
        }
        for _, r in df.iterrows()
    ]


def load_latest_backtest_run(symbol: str | None = None) -> dict | None:
    """读最近一次 backtest_run 指标

    symbol 不传时返回任意最近一次(适合桌面"风险指标"展示整体);
    传 symbol 时返回该 symbol 最近一次(适合按标的展示)。

    返回 None 时桌面 UI 应显示 "—",绝不编造。
    """
    init_duckdb()
    with DuckDBStorage() as db:
        exists = db.query_scalar(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='backtest_run'"
        )
        if not exists:
            return None
        if symbol:
            df = db.query_df(
                "SELECT run_id, ran_at, symbol, strategy, total_return, sharpe, "
                "sortino, max_drawdown, win_rate, n_trades FROM backtest_run "
                "WHERE symbol = ? ORDER BY ran_at DESC LIMIT 1",
                [bare_symbol(symbol)],
            )
        else:
            df = db.query_df(
                "SELECT run_id, ran_at, symbol, strategy, total_return, sharpe, "
                "sortino, max_drawdown, win_rate, n_trades FROM backtest_run "
                "ORDER BY ran_at DESC LIMIT 1"
            )
    if df.empty:
        return None
    r = df.iloc[0]
    return {
        "run_id": r["run_id"],
        "ran_at": str(r["ran_at"]),
        "symbol": r["symbol"],
        "strategy": r["strategy"],
        "total_return": float(r["total_return"]) if r["total_return"] is not None else None,
        "sharpe": float(r["sharpe"]) if r["sharpe"] is not None else None,
        "sortino": float(r["sortino"]) if r["sortino"] is not None else None,
        "max_drawdown": float(r["max_drawdown"]) if r["max_drawdown"] is not None else None,
        "win_rate": float(r["win_rate"]) if r["win_rate"] is not None else None,
        "n_trades": int(r["n_trades"]) if r["n_trades"] is not None else None,
    }


def load_latest_portfolio() -> dict | None:
    """读回最新一次组合快照;没有任何快照时返回 None(绝不编造)"""
    init_duckdb()
    with DuckDBStorage() as db:
        exists = db.query_scalar(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='portfolio_snapshot'"
        )
        if not exists:
            return None
        latest = db.query_df(
            "SELECT snapshot_id, cash, currency, total_equity FROM portfolio_snapshot "
            "ORDER BY taken_at DESC LIMIT 1"
        )
        if latest.empty:
            return None
        row = latest.iloc[0]
        pos = db.query_df(
            "SELECT symbol, quantity, avg_price, unrealized_pnl FROM portfolio_position "
            "WHERE snapshot_id = ? ORDER BY symbol",
            [row["snapshot_id"]],
        )
    positions = [
        {
            "symbol": r["symbol"],
            "quantity": float(r["quantity"]),
            "avg_price": float(r["avg_price"]),
            "unrealized_pnl": float(r["unrealized_pnl"]),
        }
        for _, r in pos.iterrows()
    ]
    return {
        "snapshot_id": row["snapshot_id"],
        "cash": float(row["cash"]),
        "currency": row["currency"],
        "total_equity": float(row["total_equity"]),
        "positions": positions,
    }


if __name__ == "__main__":
    init_duckdb()
