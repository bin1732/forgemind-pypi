# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import argparse  # noqa: E402
import asyncio  # noqa: E402
import io  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402

from forgemind.core.config.settings import get_settings  # noqa: E402
from forgemind.core.observability.logging import get_logger, setup_logging  # noqa: E402

logger = get_logger("forgemind.cli")


def _force_utf8_stdio() -> None:
    """Windows 控制台默认是 GBK/cp1252,打印中文与 emoji 会直接崩

    真实故障:Windows 上跑 `forgemind signal` 抛
    UnicodeEncodeError: 'charmap' codec can't encode characters
    —— 一个中文 Windows 用户装完就用不了。

    这里不依赖 `reconfigure`:部分环境(含 PyInstaller 冻结包)拿不到它,
    因此直接用 TextIOWrapper 包一层 buffer 替换 sys.stdout / sys.stderr。
    """
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        buffer = getattr(stream, "buffer", None)
        if buffer is None:  # 已被替换过
            continue
        encoding = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
        if encoding in ("utf8", "utf_8"):
            continue
        try:
            wrapped = io.TextIOWrapper(
                buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
            setattr(sys, name, wrapped)
        except (ValueError, OSError):  # pragma: no cover
            pass


_force_utf8_stdio()


def refuse_unusable_strategy(name: str) -> None:
    """这个策略在这个命令里跑不出有意义的结果 —— 明确拒绝,并说清怎么走得通。

    三种情况,消息不能混:

    - 名字根本不存在:就是不存在,别装懂。
    - 存在但这个命令喂不了它:说清缺什么、怎么自己用。把这种说成"未知
      策略"是骗人 —— 同一个命令的策略清单里明明列着它,用户照着清单挑
      一个却被告知没听说过,两处说法自相矛盾。
    - 能跑:放行。

    拒绝要发生在动手取数之前:让用户先等一轮取数、再被告知跑不了,是在
    浪费他的时间。
    """
    from forgemind.core.strategies.library import (
        available_strategies,
        cli_runnable_strategies,
        strategy_unusable_reason,
        strategy_usage_hint,
    )

    runnable = cli_runnable_strategies()
    if name in runnable:
        return

    if name not in available_strategies():
        print(f"❌ 未知策略 {name}")
        print(f"   这个命令能跑的:{', '.join(sorted(runnable))}")
        print("   想看全部可用策略:forgemind backtest --list-strategies")
        raise SystemExit(2)

    reason = strategy_unusable_reason(name) or "这个命令喂不了它"
    print(f"⚠️  {name} 这个命令跑不了:{reason}")
    usage = strategy_usage_hint(name)
    if usage:
        print(f"   自己用:{usage}")
    else:
        print("   自己准备多支标的的行情表,用引擎直接跑:")
        print("     from forgemind.core.backtest.engine import SimpleBacktestEngine")
        print("     SimpleBacktestEngine().run(MyStrategy(), 多标的的行情表)")
    raise SystemExit(2)


def cmd_demo(args):
    """一条命令看到真实结果:取数 → 回测 → 落库

    给第一次用的人的第一条命令:不需要密钥、不需要配置文件、不需要先
    准备数据,装好就能跑。

    数据只有三种来源,全都是真实行情:

    - 免费数据源实时拉取(装了 [cn] 额外依赖时可用)
    - 本地库里已经存好的真实行情
    - 包内置的真实历史行情(见 forgemind/data/README.md)

    这里没有"用随机数凑一份数据"那条路 —— 跑出来的收益、夏普、回撤
    全部来自真实价格,赚是赚,亏是亏。
    """
    import importlib.util

    import pandas as pd

    from forgemind.core.backtest.engine import SimpleBacktestEngine
    from forgemind.core.data.storage import DuckDBStorage, bare_symbol
    from forgemind.core.strategies.library import STRATEGY_REGISTRY

    symbol = args.symbol
    start, end = args.start, args.end
    db_symbol = bare_symbol(symbol)

    # 先看这个策略在这个命令里跑不跑得起来,再动手取数
    refuse_unusable_strategy(args.strategy)

    print("ForgeMind 演示 —— 一条命令看到结果")
    print(f"  标的 {symbol} · 区间 {start} → {end} · 策略 {args.strategy}")

    price_df = None
    data_note = ""
    extra_hint = ""

    # 取数:实时行情 → 本地库 → 包内置的真实历史行情
    if importlib.util.find_spec("akshare") is not None:
        try:
            from forgemind.core.data.akshare_etl import AKShareETL

            etl = AKShareETL()
            prev_level = os.environ.get("FORGEMIND_LOG_LEVEL")
            os.environ["FORGEMIND_LOG_LEVEL"] = "ERROR"
            try:
                stats = asyncio.run(etl.run(symbols=[db_symbol], start=start, end=end))
            finally:
                if prev_level is None:
                    os.environ.pop("FORGEMIND_LOG_LEVEL", None)
                else:
                    os.environ["FORGEMIND_LOG_LEVEL"] = prev_level
            n_klines = (stats or {}).get("klines", 0) or 0
            if n_klines:
                print(f"1/3 取数 · ✅ 实时行情:{n_klines} 根日线(免费数据源)")
                data_note = "实时行情"
        except Exception as exc:  # noqa: BLE001 — 取不到数不该让整条命令失败
            extra_hint = f"免费数据源这次没取到({type(exc).__name__}),先用手头的数据"
    else:
        extra_hint = "想拉实时行情就装:pip install 'forgemind[cn]'"

    if not data_note:
        try:
            with DuckDBStorage() as db:
                price_df = db.query_df(
                    "SELECT date, open, high, low, close, volume FROM kline_daily "
                    "WHERE symbol = ? AND date BETWEEN ? AND ? ORDER BY date ASC",
                    [db_symbol, start, end],
                )
        except Exception:  # noqa: BLE001 — 库还没建好是常见情况
            price_df = None
        if price_df is not None and not price_df.empty:
            price_df["date"] = pd.to_datetime(price_df["date"])
            price_df = price_df.set_index("date").sort_index()
            data_note = f"本地库里的真实行情({len(price_df)} 根日线)"

    if not data_note:
        price_df = _bundled_real_prices(start, end)
        data_note = (
            f"包内置的真实历史行情({len(price_df)} 根日线,"
            f"{price_df.index[0].date()} → {price_df.index[-1].date()})"
        )

    if not data_note.startswith("实时行情"):
        print(f"1/3 取数 · ✅ {data_note}")
        if extra_hint:
            print(f"      {extra_hint}")

    # 用之前先体检:列序写错这类问题读得出来、日期也对,只有策略在上面
    # 算出离谱结果时才暴露。这里先挡住,别把坏数据算成好结果。
    from forgemind.core.data.ohlc import assert_ohlc

    assert_ohlc(price_df, "演示用的行情数据")

    # 回测:按名字真的选策略(能不能跑已经在开头拒过了)
    strategy = STRATEGY_REGISTRY[args.strategy]()
    strategy.validate_parameters()

    engine = SimpleBacktestEngine(initial_capital=100_000)
    result = engine.run(strategy, price_df)
    total = float(getattr(result, "total_return", 0.0) or 0.0)
    sharpe = float(getattr(result, "sharpe", 0.0) or 0.0)
    mdd = float(getattr(result, "max_drawdown", 0.0) or 0.0)
    n_trades = int(getattr(result, "n_trades", 0) or 0)
    print(f"2/3 回测 · 策略 {args.strategy}")
    if n_trades:
        print(
            f"3/3 结果 · 总收益 {total:+.2%} · 夏普 {sharpe:.2f} · "
            f"最大回撤 {mdd:.2%} · 进出 {n_trades} 次"
        )
    else:
        print("3/3 结果 · 这段区间里策略没有产生任何进出(总收益与夏普都是 0)")
    print(f"      (数据来源:{data_note} —— 真实价格,不是模拟数据)")
    if n_trades and total < 0:
        # 不粉饰:这段行情里这个策略亏了,就说它亏了。策略不是万能的,
        # 换个标的或换段区间结果会不一样 —— 让用户自己跑一次比较。
        print("      提示:这一段行情里这个策略是亏的。换标的、换区间或换策略,")
        print("           结果会不同 —— 下面几条命令就是给你试的。")

    print("\n下一步:")
    print(f"  forgemind pick --symbol {symbol}      多因子选股")
    print(f"  forgemind backtest --strategy {args.strategy} --symbol {symbol}   再跑一次回测")
    print("  forgemind mcp                          接入 MCP 客户端(Claude Desktop / Cursor)")
    print("  forgemind info                         版本、数据源与连接状态")
    return 0


def _bundled_real_prices(start: str, end: str):
    """读包内置的真实历史行情。

    内置的是历史事实,不是模拟数据。区间与文件里的数据对不上时,按文件里
    实际有的那段来 —— 少给几根总比给一段编造的强。
    """
    import pandas as pd

    from forgemind.core.data import bundled_sample_path

    path = bundled_sample_path()
    df = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    lo, hi = pd.Timestamp(start), pd.Timestamp(end)
    window = df[(df.index >= lo) & (df.index <= hi)]
    if window.empty:
        window = df
    return window


def cmd_backtest(args):
    """跑一个示例回测"""
    import numpy as np
    import pandas as pd

    from forgemind.core.backtest.engine import SimpleBacktestEngine
    from forgemind.core.strategies.base import MovingAverageCrossStrategy  # noqa: F401

    if getattr(args, "list_strategies", False):
        from forgemind.core.strategies.library import (
            available_strategies,
            cli_runnable_strategies,
            strategy_unusable_reason,
        )

        # 清单是一份承诺:列出来的就要能跑。跑不了的另列一节,写明原因 ——
        # 混在一起列,用户照着挑一个,得到的是"未知策略"。
        # 第二节的理由与拒绝时说的话取自同一处(strategy_unusable_reason),
        # 两边不会各说各话。
        runnable = cli_runnable_strategies()
        print("=== 这个命令能跑的策略 ===")
        for name in sorted(runnable):
            print(f"  {name:26} {runnable[name]}")
        others = [n for n in sorted(available_strategies()) if n not in runnable]
        if others:
            print("\n=== 存在但这个命令跑不了的 ===")
            for name in others:
                why = strategy_unusable_reason(name) or available_strategies()[name]
                print(f"  {name:26} {why}")
        return

    # 先看这个策略在这个命令里跑不跑得起来,再动手取数:让用户先等一轮
    # 取数、然后才被告知跑不了,是在浪费他的时间。
    refuse_unusable_strategy(args.strategy)

    # 参数只有一部分策略用得上(fast/slow 是双均线的),别把不相关的参数
    # 印在命令行里 —— 那会让读的人以为这个策略用了它们。
    _takes_ma_params = args.strategy in ("ma_cross", "mean_reversion")
    _params_note = f" fast={args.fast} slow={args.slow}" if _takes_ma_params else ""
    print(f"Running backtest: {args.strategy}{_params_note}")

    # 优先查 DuckDB 真实数据;指定 --symbol 后查到就用,查不到降级
    price_df = None
    real_data_note = ""
    if args.symbol:
        from forgemind.core.data.storage import DuckDBStorage, bare_symbol

        # ETL 落库用 6 位代码,CLI / MCP 入参常带交易所后缀(.SH / .SZ)。
        # 不归一化就查不到真数据,然后被静默降级到模拟 —— 用户以为自己跑通了
        # 真实回测,实际得到的是一组 np.random。归一化放在查询参数里,
        # 任何上游(CLI / API / MCP)传 '600519.SH' / 'SH600519' 都能命中。
        symbol_db = bare_symbol(args.symbol)
        try:
            with DuckDBStorage() as _db:
                price_df = _db.query_df(
                    "SELECT date, open, high, low, close, volume "
                    "FROM kline_daily WHERE symbol = ? "
                    "AND date BETWEEN ? AND ? ORDER BY date ASC",
                    [symbol_db, args.start, args.end],
                )
        except Exception as _db_err:
            # 可能是表不存在(init_duckdb 没跑)或 schema 异常 —— 不强求,
            # 走降级路径并明确告知,免得用户被 DuckDB 问题挡在门外
            print(f"⚠️  查 DuckDB 真数据失败({type(_db_err).__name__}: {str(_db_err)[:80]})")
            price_df = None
        if price_df is not None and not price_df.empty:
            price_df["date"] = pd.to_datetime(price_df["date"])
            price_df = price_df.set_index("date").sort_index()
            price_df.index.name = "date"
            price_df["symbol"] = args.symbol  # 保留入参形式(带后缀)给用户看
            real_data_note = f"(真数据:DuckDB {len(price_df)} 根 K 线)"
        elif price_df is not None and price_df.empty:
            # 表存在但查不到 — 用户可能还没跑 etl
            print(f"⚠️  DuckDB 中没有 {args.symbol} 在 {args.start}~{args.end} 的 K 线")
            print(
                "   提示: forgemind etl --symbols "
                + args.symbol
                + f" --start {args.start} --end {args.end}"
            )
            price_df = None

    if price_df is None:
        # 降级:没给标的、或者给了但库里没有 → 用 np.random 模拟。
        # 话术要跟着实际情况走:用户明明给了 --symbol,却说"未指定
        # --symbol",等于骗他,后面再跟一条"去拉这个标的"的提示,更矛盾。
        if args.symbol:
            print(f"⚠️  {args.symbol} 在库里没有 K 线,使用 np.random 合成行情(非真实市场)")
            print(
                "   提示: forgemind etl --symbols "
                + args.symbol
                + f" --start {args.start} --end {args.end}"
            )
        else:
            print("⚠️  未指定 --symbol 且 DuckDB 无数据,使用 np.random 合成行情(非真实市场)")
            print("   提示: forgemind etl --symbols 600519 --start 2024-01-01 --end 2024-12-31")
            print("   然后 forgemind backtest --symbol 600519 --start 2024-01-01 --end 2024-12-31")
        dates = pd.date_range(args.start, args.end, freq="D")
        n = len(dates)
        np.random.seed(42)
        close = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, n)))
        price_df = pd.DataFrame(
            {
                "open": close * (1 + np.random.normal(0, 0.005, n)),
                "high": close * (1 + np.abs(np.random.normal(0, 0.01, n))),
                "low": close * (1 - np.abs(np.random.normal(0, 0.01, n))),
                "close": close,
                "volume": np.random.randint(1_000_000, 10_000_000, n),
                "symbol": "DEMO",
            },
            index=dates,
        )
        price_df.index.name = "date"
        real_data_note = "(模拟数据,非真实市场)"
    from forgemind.core.strategies.extended_library import list_strategies

    extended = list_strategies()
    if args.strategy in extended:
        # 批量策略:经 adapter 适配成引擎接口
        from forgemind.core.strategies.library import (
            _EXTENDED_STRATEGY_PARAMS,
            get_extended_strategy,
        )

        hint = _EXTENDED_STRATEGY_PARAMS.get(args.strategy)
        if hint:
            print(f"⚠️  {args.strategy} 需要额外参数,无法直接回测: {hint}")
            sys.exit(1)
        strategy = get_extended_strategy(args.strategy)

        # 事件类策略依赖基本面/事件数据,而 CLI 的演示数据只有 OHLCV。
        # 以前这类策略静默返回全 0 信号,回测打印 "Trades: 0" ——
        # 看着像"跑了但没信号",实际是数据根本不够。必须在这里说清楚。
        _req = tuple(getattr(strategy, "required_columns", ()) or ())
        if _req:
            print(f"⚠️  {args.strategy} 是事件类策略,需要额外数据,无法在演示数据上回测。")
            print(f"   缺少的列: {', '.join(_req)}")
            print("   演示数据只有: " + ", ".join(price_df.columns))
            print("   这些列来自基本面/事件数据源(财报、指数成分调整等),")
            print("   请用真实数据调用:")
            print("     forgemind pick / etl 后自行构造,或直接用 Python API:")
            print("     from forgemind.core.backtest.engine import SimpleBacktestEngine")
            print(f"     SimpleBacktestEngine().run(MyStrategy(), df_with_{_req[0]})")
            sys.exit(1)
    else:
        from forgemind.core.strategies.library import get_strategy_class

        strategy_class = get_strategy_class(args.strategy)
        strategy = strategy_class(
            parameters={
                "fast_period": args.fast,
                "slow_period": args.slow,
            }
        )

    engine = SimpleBacktestEngine(
        initial_capital=args.capital,
        slippage_model=args.slippage_model,
        adv_shares=args.adv,
    )
    result = engine.run(strategy, price_df)
    # 反映数据来源:真数据 vs 模拟数据,避免 "Total Return: 12.34%" 被误读
    if "真数据" in real_data_note:
        print(f"\n=== Result {real_data_note} ===")
    else:
        print(f"\n=== Result {real_data_note} ===")
        print("   ⚠️  本次使用随机生成的合成行情,以下数字只用于验证流程能跑通,")
        print(_plain("       **不是真实回测结果**。要真实结果请先 `forgemind etl` 拉数据。"))
    print(f"  Total Return: {result.total_return:.2%}")
    print(f"  Sharpe: {result.sharpe:.2f}")
    print(f"  Max Drawdown: {result.max_drawdown:.2%}")
    print(f"  Trades: {result.n_trades}")

    # 把本次回测的真实指标落 backtest_run 表,给桌面风险指标面板用
    # 优先用 result 自带;Sortino / win_rate 没有就用 numpy/pandas 算;
    # 算不出来就 None,绝不编造。
    try:
        from forgemind.core.data.storage import save_backtest_run

        metrics = {
            "total_return": float(result.total_return),
            "sharpe": float(result.sharpe),
            "max_drawdown": float(result.max_drawdown),
            "n_trades": int(result.n_trades),
        }
        # BacktestResult 已含 sortino / win_rate 字段(BacktestReport 是更细的
        # 在 result 不带 equity_curve 时 AttributeError 退化成 None,反而漏了
        # BacktestResult 自己算出来的真值。直接读 result 自带字段。
        metrics["sortino"] = (
            float(result.sortino) if getattr(result, "sortino", None) is not None else None
        )
        metrics["win_rate"] = (
            float(result.win_rate) if getattr(result, "win_rate", None) is not None else None
        )

        symbol_label = str(price_df["symbol"].iloc[0]) if "symbol" in price_df.columns else "?"

        run_id = save_backtest_run(
            symbol=symbol_label,
            strategy=args.strategy,
            metrics=metrics,
        )
        print(f"\n  Backtest run saved: {run_id}")
    except Exception as e:
        # 落盘失败不阻断 backtest 主体流程
        print(f"\n  ⚠️  回测结果落盘失败({type(e).__name__})")


def cmd_agent(args):
    """跑一个 AI 决策 — 真的人工审批 gating

    两步:
      1. prepare: 跑 sub-agent,卡在 PM 节点前,显示 bull/bear 让你审批
      2. 真拍板: y/n/y-yes 才走 approve、resume PM;其它路径全部不落 pm_decision,
         也不更新 portfolio snapshot(否则"决策"就漏到了持仓里)
    """
    import os
    from datetime import datetime

    from forgemind.core.agents.portfolio_context import (
        PortfolioContext,
        PortfolioPosition,
        resume_decision,
        run_decision,
    )

    print(f"Running AI decision: {args.symbol}")

    portfolio = PortfolioContext(
        cash=args.cash,
        total_equity=args.equity,
        positions=[
            PortfolioPosition(
                symbol=args.symbol,
                quantity=args.position_qty,
                avg_price=args.position_price,
            )
        ]
        if args.position_qty > 0
        else [],
    )

    state = asyncio.run(
        run_decision(
            symbol=args.symbol,
            as_of=datetime.now(),
            portfolio=portfolio,
        )
    )

    thread_id = state.get("thread_id", "")
    bull = state.get("bull_case", {}) or {}
    bear = state.get("bear_case", {}) or {}

    print("\n=== Pending Human Review ===")
    print(f"  thread_id: {thread_id}")
    print(f"  bull: {bull.get('thesis', '')}")
    print(f"  bear: {bear.get('thesis', '')}")
    print(f"  confidence: {state.get('confidence', 0):.2%}")

    pm = state.get("pm_decision")
    if pm is not None:
        # 通常 ainvoke 第一次不会到这里;只是防御。
        print("\n  ⚠️  PM 节点意外已跑(未审批),仍按 gating 拒绝落盘")
        return 1

    # 真审批:非交互模式(--yes)直接 y,否则显式 y/n
    if getattr(args, "yes", False):
        answer = "y"
    else:
        if not sys.stdin.isatty() or os.environ.get("FORGEMIND_NONINTERACTIVE"):
            print("  非交互模式未传 --yes,拒绝自动审批")
            return 2
        try:
            answer = input("\nApprove this decision? [y/N] ").strip().lower()
        except EOFError:
            print("  无输入,拒绝自动审批")
            return 2

    if answer != "y":
        asyncio.run(
            resume_decision(
                thread_id,
                approved=False,
                reviewer=os.environ.get("USER", "cli"),
                notes="rejected at prompt",
            )
        )
        print("\n  ❌ 已拒绝 — pm_decision 不会落盘,组合快照不动")
        return 0

    reviewer = os.environ.get("USER", "cli")
    final = asyncio.run(
        resume_decision(thread_id, approved=True, reviewer=reviewer, notes="approved at prompt")
    )
    pm = final.get("pm_decision") or {}
    print("\n=== Approved Decision ===")
    print(f"  approved_by: {reviewer}")
    print(f"  Direction: {pm.get('direction')}")
    print(f"  Quantity: {pm.get('quantity')}")
    print(f"  Final Weight: {pm.get('final_weight', 0):.2%}")
    print(f"  Current Weight: {pm.get('current_weight', 0):.2%}")
    print(f"  Confidence: {pm.get('confidence', 0):.2%}")
    print(f"  Rationale: {pm.get('rationale')}")

    # 落库在共用层做(resume_decision 内部):CLI 与 API 的审批是同一件事,
    # 两边都要落 portfolio snapshot 与 6 条决策明细 —— 桌面端的"组合概览"
    # 与"多 Agent 决策"面板读的就是这两张表。
    persisted = final.get("persisted") or {}
    if persisted.get("error"):
        print(f"\n  ⚠️  组合快照落盘失败({persisted['error']}),MCP query_portfolio 将读到旧组合")
    else:
        print(f"\n  Portfolio snapshot saved: {persisted.get('snapshot_id')}")
        print(f"  Agent decisions saved: {persisted.get('decisions_written', 0)}/6")


def cmd_mcp(args):
    """启动 MCP server"""
    from forgemind.mcp.server import main as mcp_main

    mcp_main()


def cmd_pick(args):
    """选股 Agent — 选 top N"""
    from forgemind.core.agents.stock_picker import StockPickerAgent

    symbols = args.symbols.split(",") if args.symbols else None
    if not symbols:
        symbols = [
            "600519",
            "000001",
            "601318",
            "600036",
            "000333",
            "601398",
            "601988",
            "600028",
            "601857",
            "600585",
        ]

    print(f"Selecting top {args.top_n} from {len(symbols)} symbols...")
    picker = StockPickerAgent()
    picks = asyncio.run(picker.pick(universe=symbols, top_n=args.top_n))

    # 结论的时效性:计算没错,但依据可能已经是几周前的收盘价。
    # 不说的话,用户会把"上周的形态"当成"今天的形态"。
    from forgemind.core.data.storage import data_freshness

    fresh = data_freshness(getattr(picker, "last_data_date", None))
    print(f"  依据的行情最新日期: {fresh}")

    # 没有结果时必须说清原因,而不是只留一句 "Top 0 picks"
    short = dict(getattr(picker, "last_insufficient", {}) or {})
    if not picks and short:
        print("\n=== Top 0 picks ===\n")
        print(
            f"  {len(short)} 个标的因 K 线数据不足被跳过 (至少需要 {StockPickerAgent.MIN_BARS} 根):"
        )
        for sym, n in list(short.items())[:6]:
            got = f"仅 {n} 根" if n else "库里没有该标的"
            print(f"    {sym:12} {got}")
        print("\n  先拉更长的历史区间再试,例如:")
        print(
            f"    forgemind etl --symbols {','.join(list(short)[:3])} "
            f"--start 2022-01-01 --end 2024-12-31"
        )
        return
    if not picks:
        print("\n=== Top 0 picks ===\n")
        print("  候选标的都没有 K 线数据。先跑 `forgemind etl` 拉取数据。")
        return

    print(f"\n=== Top {len(picks)} picks ===\n")
    for i, p in enumerate(picks, 1):
        print(
            f"#{i} {p.symbol} | {p.direction.upper()} | score={p.score:.3f} | conf={p.confidence:.2%}"
        )
        print(f"   {p.rationale}\n")
    if short:
        print(f"  (另有 {len(short)} 个标的因数据不足被跳过)")


def cmd_etl(args):
    """AKShare 数据 ETL"""
    from forgemind.core.data.akshare_etl import AKShareETL

    symbols = args.symbols.split(",") if args.symbols else ["600519", "000001"]
    print(f"Running AKShare ETL for {len(symbols)} symbols ({args.start} → {args.end})...")

    etl = AKShareETL()
    try:
        stats = asyncio.run(etl.run(symbols=symbols, start=args.start, end=args.end))
    except MemoryError:
        # 小内存机器上一次性装下全市场日线是真实场景(笔记本 8G、
        # 容器 2G)。裸 MemoryError 堆栈对用户毫无指导意义。
        print("❌ 内存不足,ETL 中断。")
        print(f"   已请求 {len(symbols)} 个标的 × {args.start} → {args.end} —— 一次装不进来。")
        print("   建议:缩小标的范围或日期区间,分批执行,例如:")
        print(f"     forgemind etl --symbols 600519,000001 --start {args.start} --end {args.end}")
        # 退出码 2: 资源类 (memory/disk),与网络/数据类区分
        raise SystemExit(2) from None
    except TimeoutError:
        # 用户只看到一句 asyncio 内部错误,既没有上下文也不知道该不该重试。
        print("❌ 取数超时,ETL 中断。")
        print(f"   标的:{', '.join(symbols[:5])}{' …' if len(symbols) > 5 else ''}")
        print("   上游行情源无响应。重试,或缩小标的范围 / 日期区间:")
        print(
            f"     forgemind etl --symbols {','.join(symbols[:3])} "
            f"--start {args.start} --end {args.end}"
        )
        # 退出码 3: 网络/上游类 (timeout/connect refused/DNS)
        raise SystemExit(3) from None
    except OSError as exc:
        if getattr(exc, "errno", None) == 28:  # ENOSPC
            print("❌ 磁盘空间不足,ETL 中断。")
            print(f"   写入位置:{os.getcwd()}/data — 清理后重试。")
            # 退出码 4: 磁盘类
            raise SystemExit(4) from None
        raise
    n_klines = (stats or {}).get("klines", 0)
    failures = (stats or {}).get("failures") or {}
    ok_syms = (stats or {}).get("ok_symbols", 0)
    n_stocks = (stats or {}).get("stocks", 0)
    stock_list_provider = (stats or {}).get("stock_list_provider", "unknown")
    if n_klines:
        print(f"✅ ETL complete — 本次写入 {n_klines} 根 K 线,来自 {ok_syms} 个标的")
        if n_stocks:
            print(f"   代码表:本次取到 {n_stocks} 只(源:{stock_list_provider})")
        else:
            print("   代码表:本次没取到(不影响已指定标的的 K 线)")
        print("   Next: forgemind pick --symbol 600519.SH")
        if failures:
            total_fail = sum(failures.values())
            print(f"   ⚠️  {total_fail} 个标的取数失败:")
            for reason, cnt in failures.items():
                print(f"        {cnt}× {reason}")
    else:
        # init 阶段失败时**根本没开始取数** —— 说"拉到 0 条"是假的,
        # 会让用户以为区间/代码有问题,实际上是数据库没打开
        init_failed = any(k.startswith("init:") for k in failures)
        if init_failed:
            print("⚠️  ETL 未能开始取数(初始化阶段就失败了),没有写入任何 K 线。")
        else:
            print("⚠️  ETL 拉到 0 条数据,没有写入任何 K 线。")
        if failures:
            print("   失败原因分类:")
            for reason, cnt in failures.items():
                print(f"        {cnt}× {reason}")
            # 退出码 3: 数据/上游类错误 (失败但非资源问题)
            # 退出码 4: 资源类 (init 失败是 db 文件路径/权限)
            rc = 4 if init_failed else 3
            print(f"\n   exit code: {rc} (3=数据, 4=资源)")
            # 依赖类建议(在 exit 之前给)
            if "akshare_not_installed" in " ".join(failures):
                print("   安装带 A 股数据源的 extra 后重试:")
                print("     pip install 'forgemind[cn]'")
            raise SystemExit(rc)
        else:
            try:
                import akshare  # noqa: F401

                print("   akshare 已安装但未取到数据,请检查网络或日期区间。")
            except ImportError:
                print("   akshare 未安装 → pip install 'forgemind[cn]'")
        # 每条建议只对**它对应的那类原因**给,别的一律不提。
        # 而那跟数据库被占用毫无关系。
        if "akshare_not_installed" in " ".join(failures):
            print("   安装带 A 股数据源的 extra 后重试:")
            print("     pip install 'forgemind[cn]'")
        elif not init_failed:
            # 取数跑了、只是没数据 → 才有可能是代码格式或区间的问题
            print("   代码格式应为 6 位(如 600519),而非 600519.SH")
        sys.exit(1)


def cmd_broker_test(args):
    """生成一个示例信号 + 落 DuckDB signal_history

    这里只 print broker stub, signal 没落盘, 桌面 signal-table 看不到。
    修:真调 save_signal 落 signal_history,跟 MCP output_signal 同一路径。
    用户跑 forgemind signal 之后,桌面 signal-table 会真显示这条信号。
    """
    from forgemind.core.data.storage import bare_symbol, save_signal

    symbol = getattr(args, "symbol", None) or "600519.SH"
    side = getattr(args, "side", None) or "BUY"
    confidence = float(getattr(args, "confidence", None) or 0.5)
    rationale = (
        getattr(args, "rationale", None) or "示例信号:从 CLI 生成,等 LLM 接管后会被真分析替换"
    )

    from datetime import datetime

    sym_db = bare_symbol(symbol)
    sig_id = save_signal(
        signal_id=f"sig_cli_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}_{sym_db}",
        symbol=sym_db,
        side=side,
        confidence=confidence,
        rationale=rationale,
        source="forgemind_signal_cli",
    )
    print("ℹ️  ForgeMind 是研究层 Agent (research-layer, no broker),不直接对接券商 SDK。")
    print("    信号已落 DuckDB signal_history:")
    print(f"      signal_id: {sig_id}")
    print(f"      symbol:    {symbol}")
    print(f"      side:      {side}")
    print(f"      confidence: {confidence:.0%}")
    print(f"      rationale: {rationale[:80]}")
    print()
    print("    执行请用:")
    print("      • vnpy (CTP / MiniQMT)")
    print("      • nautilus_trader (多券商)")
    print("      • 你的券商 SDK (ccxt / ib_insync 等)")
    print()
    print("    桌面端信号表格会自动显示这条信号 (signal-table 拉 forgemind://signals resource)")


def cmd_router_demo(args):
    """Model Router demo"""
    from forgemind.core.ai.router import quick_route_demo

    quick_route_demo()


def cmd_info(args):
    """显示配置"""
    import os

    settings = get_settings()
    print("=== ForgeMind Config ===")
    print(f"  Env: {settings.env}")
    print(f"  Mode: {settings.mode}")
    print(f"  Version: {settings.version}")
    print(f"  API: {settings.api_host}:{settings.api_port}")
    print(f"  PG: {settings.pg_host}:{settings.pg_port}")
    print(f"  ClickHouse: {settings.ch_host}:{settings.ch_port}")
    print(f"  Data dir: {settings.data_dir}")
    # US 数据源状态:让用户一眼看到「我现在能不能拉美股」
    us_token = os.environ.get("FORGEMIND_US_TOKEN", "").strip()
    if us_token:
        masked = us_token[:4] + "***" + us_token[-2:] if len(us_token) > 6 else "***"
        print(f"  US source: {os.environ.get('FORGEMIND_US_PROVIDER', 'polygon')}, token={masked}")
    else:
        print(
            "  US source: NOT configured (设 FORGEMIND_US_TOKEN=... 启用;免费 tier 见 polygon.io / tiingo.com)"
        )


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 解析器

    单独抽出来是为了让"功能清单"能从运行时提取真实命令集合 ——
    手写清单会随实现漂移,而"全绿"建立在漂移的清单上就没有意义。
    """
    parser = argparse.ArgumentParser(prog="forgemind", description="ForgeMind CLI")
    subparsers = parser.add_subparsers(dest="command")

    # info
    subparsers.add_parser("info", help="Show config")

    # backtest
    parser_bt = subparsers.add_parser("backtest", help="Run backtest")
    parser_bt.add_argument(
        "--strategy",
        default="ma_cross",
        help=(
            "策略名。可选:ma_cross / mean_reversion / momentum / bollinger / buy_hold "
            "(on_bar 策略),以及 TimeSeriesMomentum / CrossSectionalMomentum / "
            "MomentumRotation / OrnsteinUhlenbeck / RSIReversion / MaxSharpe / "
            "RiskParity 等扩展策略。`forgemind backtest --list-strategies` 看全部。"
        ),
    )
    parser_bt.add_argument(
        "--list-strategies",
        action="store_true",
        help="列出全部可用策略后退出",
    )
    parser_bt.add_argument(
        "--symbol",
        default=None,
        help=(
            "标的代码(6 位,如 600519)。指定后从 DuckDB kline_daily "
            "读真实行情回测;不指定则无 DuckDB 数据时降级为模拟行情。"
            "`forgemind etl --symbols ...` 拉数据后即可回测真行情。"
        ),
    )
    parser_bt.add_argument("--fast", type=int, default=5)
    parser_bt.add_argument("--slow", type=int, default=20)
    parser_bt.add_argument(
        "--slippage-model",
        default="fixed",
        choices=["fixed", "linear", "sqrt"],
        help="滑点模型:fixed=固定 bps;linear/sqrt=按成交量估冲击(需 --adv)",
    )
    parser_bt.add_argument(
        "--adv",
        type=float,
        default=0.0,
        help="平均日成交量(股)。linear/sqrt 冲击模型需要它,否则退化为 fixed",
    )
    parser_bt.add_argument("--start", default="2024-01-01")
    parser_bt.add_argument("--end", default="2024-12-31")
    parser_bt.add_argument("--capital", type=float, default=100_000)
    parser_bt.set_defaults(func=cmd_backtest)

    # agent
    parser_agent = subparsers.add_parser("agent", help="Run AI decision")
    parser_agent.add_argument("--symbol", default="600519.SH")
    parser_agent.add_argument("--cash", type=float, default=80_000)
    parser_agent.add_argument("--equity", type=float, default=200_000)
    parser_agent.add_argument("--position-qty", type=int, default=100)
    parser_agent.add_argument("--position-price", type=float, default=1500)
    parser_agent.add_argument(
        "--yes", action="store_true", help="非交互模式直接批准(默认会真等你按 y)"
    )
    parser_agent.set_defaults(func=cmd_agent)

    # mcp
    parser_mcp = subparsers.add_parser("mcp", help="Start MCP server")
    parser_mcp.set_defaults(func=cmd_mcp)

    # router-demo
    parser_router = subparsers.add_parser("router-demo", help="Demo model router")
    parser_router.set_defaults(func=cmd_router_demo)

    # pick
    parser_pick = subparsers.add_parser("pick", help="Stock picker agent — 选股")
    parser_pick.add_argument("--symbols", help="Comma-separated symbols")
    parser_pick.add_argument("--top-n", type=int, default=5)
    parser_pick.set_defaults(func=cmd_pick)

    # etl
    parser_etl = subparsers.add_parser("etl", help="AKShare 数据 ETL(免费拉 A 股)")
    parser_etl.add_argument("--symbols", help="Comma-separated")
    parser_etl.add_argument("--start", default="2024-01-01")
    parser_etl.add_argument("--end", default="2024-12-31")
    parser_etl.set_defaults(func=cmd_etl)

    # signal — 真落 DuckDB signal_history,让桌面 signal-table 显示
    parser_signal = subparsers.add_parser("signal", help="生成示例信号 + 落 DuckDB(无券商 SDK)")
    parser_signal.add_argument("--symbol", default="600519.SH", help="6 位代码,可选 .SH/.SZ")
    parser_signal.add_argument("--side", default="BUY", choices=["BUY", "SELL", "HOLD"])
    parser_signal.add_argument("--confidence", type=float, default=0.5, help="0-1")
    parser_signal.add_argument("--rationale", default=None, help="信号理由")
    parser_signal.set_defaults(func=cmd_broker_test)

    # demo — 新手的第一条命令:零配置、零密钥,跑完就看到结果
    parser_demo = subparsers.add_parser(
        "demo", help="一条命令看到真实结果:取数 → 回测 → 落库(无需密钥或配置)"
    )
    parser_demo.add_argument("--symbol", default="600519", help="6 位代码,可选 .SH/.SZ")
    parser_demo.add_argument("--start", default="2024-01-01")
    parser_demo.add_argument("--end", default="2024-12-31")
    parser_demo.add_argument("--strategy", default="ma_cross", help="策略名")
    parser_demo.set_defaults(func=cmd_demo)

    return parser


def _plain(s: str) -> str:
    """把 markdown 强调标记换成终端里看得见的强调

    终端不渲染 `**`, 直接打印出来就是一堆星号。现在
    "**830 天前,严重过期**" 这种文案在终端里是
        2024-06-28(**830 天前,严重过期**)
    —— 看起来像渲染坏了,反而削弱了它本该有的警示作用。
    用 ANSI 粗体替代;非 TTY(重定向到文件)则原样保留 markdown。
    """
    if not s:
        return s
    if not sys.stdout.isatty():
        return s
    return re.sub(r"\*\*(.+?)\*\*", lambda m: f"\033[1m{m.group(1)}\033[0m", s)


class _PlainPrinter:
    """把 print 里的 markdown 强调标记转成终端可见的强调

    终端不渲染 `**`,直接印出来是一堆星号 ——
    "**830 天前,严重过期**" 在终端里看着像渲染坏了,反而削弱了它本该有
    的警示作用。逐个 print 改造太啰嗦(跨行 f-string 尤其麻烦),这里
    统一在 main() 里换掉 builtins.print。
    """

    def __init__(self):
        self._orig = print

    def __call__(self, *args, **kw):
        kw.pop("file", None)
        kw.pop("flush", None)
        args = tuple(_plain(str(a)) for a in args)
        self._orig(*args, flush=True, **kw)


def main():
    parser = build_parser()
    # TTY 下把 markdown 强调转成 ANSI 粗体;重定向到文件时保持原样
    if sys.stdout.isatty():
        import builtins as _b

        _b.print = _PlainPrinter()

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # CLI 默认把内部事件日志压到 WARNING:否则 `forgemind agent` 的输出里
    # 会混进十几行事件日志,真正的决策结果被淹没。
    # 需要排查时用 FORGEMIND_LOG_LEVEL=info 打开(大小写均可)。
    if not os.environ.get("FORGEMIND_LOG_LEVEL"):
        os.environ["FORGEMIND_LOG_LEVEL"] = "WARNING"
    setup_logging()

    if args.command == "info":
        cmd_info(args)
    else:
        rc = args.func(args)
        if rc is not None and rc != 0:
            sys.exit(rc)


if __name__ == "__main__":
    main()
