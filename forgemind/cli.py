# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import argparse
import asyncio
import sys

from forgemind.core.config.settings import get_settings
from forgemind.core.observability.logging import setup_logging, get_logger

logger = get_logger("forgemind.cli")


def cmd_backtest(args):
    """跑一个示例回测"""
    from forgemind.core.strategies.base import MovingAverageCrossStrategy
    from forgemind.core.backtest.engine import SimpleBacktestEngine
    import pandas as pd
    import numpy as np
    
    print(f"Running backtest: {args.strategy} fast={args.fast} slow={args.slow}")
    
    # Demo 数据
    dates = pd.date_range(args.start, args.end, freq="D")
    n = len(dates)
    np.random.seed(42)
    close = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, n)))
    price_df = pd.DataFrame({
        "open": close * (1 + np.random.normal(0, 0.005, n)),
        "high": close * (1 + np.abs(np.random.normal(0, 0.01, n))),
        "low": close * (1 - np.abs(np.random.normal(0, 0.01, n))),
        "close": close,
        "volume": np.random.randint(1_000_000, 10_000_000, n),
    }, index=dates)
    
    strategy_class = MovingAverageCrossStrategy
    if args.strategy != "ma_cross":
        from forgemind.core.strategies.library import get_strategy_class
        strategy_class = get_strategy_class(args.strategy)
    
    strategy = strategy_class(parameters={
        "fast_period": args.fast,
        "slow_period": args.slow,
    })
    
    engine = SimpleBacktestEngine(initial_capital=args.capital)
    result = engine.run(strategy, price_df)
    print(f"\n=== Result ===")
    print(f"  Total Return: {result.total_return:.2%}")
    print(f"  Sharpe: {result.sharpe:.2f}")
    print(f"  Max Drawdown: {result.max_drawdown:.2%}")
    print(f"  Trades: {result.n_trades}")


def cmd_agent(args):
    """跑一个 AI 决策"""
    from datetime import datetime
    from forgemind.core.agents.portfolio_context import (
        PortfolioContext, PortfolioPosition, run_decision
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
        ] if args.position_qty > 0 else [],
    )
    
    state = asyncio.run(run_decision(
        symbol=args.symbol,
        as_of=datetime.now(),
        portfolio=portfolio,
        thread_id=f"cli-{args.symbol}",
    ))
    
    pm = state.get("pm_decision")
    if pm:
        print(f"\n=== Decision ===")
        print(f"  Direction: {pm.get('direction')}")
        print(f"  Quantity: {pm.get('quantity')}")
        print(f"  Final Weight: {pm.get('final_weight'):.2%}")
        print(f"  Current Weight: {pm.get('current_weight'):.2%}")
        print(f"  Confidence: {pm.get('confidence'):.2%}")
        print(f"  Rationale: {pm.get('rationale')}")
    else:
        print("\n=== Pending Human Review ===")
        print(f"  requires_human_review: {state.get('requires_human_review')}")
        print(f"  bull: {state.get('bull_case', {}).get('thesis')}")
        print(f"  bear: {state.get('bear_case', {}).get('thesis')}")


def cmd_mcp(args):
    """启动 MCP server"""
    from forgemind.mcp.server import main as mcp_main
    mcp_main()


def cmd_pick(args):
    """选股 Agent — 选 top N"""
    from forgemind.core.agents.stock_picker import StockPickerAgent
    
    symbols = args.symbols.split(",") if args.symbols else None
    if not symbols:
        symbols = ["600519", "000001", "601318", "600036", "000333",
                   "601398", "601988", "600028", "601857", "600585"]
    
    print(f"Selecting top {args.top_n} from {len(symbols)} symbols...")
    picker = StockPickerAgent()
    picks = asyncio.run(picker.pick(universe=symbols, top_n=args.top_n))
    
    print(f"\n=== Top {len(picks)} picks ===\n")
    for i, p in enumerate(picks, 1):
        print(f"#{i} {p.symbol} | {p.direction.upper()} | score={p.score:.3f} | conf={p.confidence:.2%}")
        print(f"   {p.rationale}\n")


def cmd_etl(args):
    """AKShare 数据 ETL"""
    from forgemind.core.data.akshare_etl import AKShareETL
    
    symbols = args.symbols.split(",") if args.symbols else ["600519", "000001"]
    print(f"Running AKShare ETL for {len(symbols)} symbols ({args.start} → {args.end})...")
    
    etl = AKShareETL()
    asyncio.run(etl.run(symbols=symbols, start=args.start, end=args.end))
    print("✅ ETL complete")


def cmd_broker_test(args):
    """Stub: ForgeMind is research-layer, no broker dependency.
    For execution, use vnpy / nautilus_trader / your broker's SDK.
    """
    print("ℹ️  ForgeMind is a research-layer Agent framework.")
    print("    No broker SDK is bundled. We output signals via:")
    print("      • MCP output_signal tool")
    print("      • CLI forgemind signal")
    print("      • Natural-language decision log (Markdown)")
    print()
    print("    For execution, plug the signal into:")
    print("      • vnpy (CTP / MiniQMT)")
    print("      • nautilus_trader (multi-broker)")
    print("      • your broker's SDK (ccxt / ib_insync / etc)")


def cmd_router_demo(args):
    """Model Router demo"""
    from forgemind.core.ai.router import quick_route_demo
    quick_route_demo()


def cmd_info(args):
    """显示配置"""
    settings = get_settings()
    print(f"=== ForgeMind Config ===")
    print(f"  Env: {settings.env}")
    print(f"  Mode: {settings.mode}")
    print(f"  Version: {settings.version}")
    print(f"  API: {settings.api_host}:{settings.api_port}")
    print(f"  PG: {settings.pg_host}:{settings.pg_port}")
    print(f"  ClickHouse: {settings.ch_host}:{settings.ch_port}")
    print(f"  Data dir: {settings.data_dir}")


def main():
    parser = argparse.ArgumentParser(prog="forgemind", description="ForgeMind CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    # info
    parser_info = subparsers.add_parser("info", help="Show config")
    
    # backtest
    parser_bt = subparsers.add_parser("backtest", help="Run backtest")
    parser_bt.add_argument("--strategy", default="ma_cross")
    parser_bt.add_argument("--fast", type=int, default=5)
    parser_bt.add_argument("--slow", type=int, default=20)
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
    
    # broker-test
    parser_signal = subparsers.add_parser("signal", help="Show research-layer signal output interface(no broker bundled)")
    parser_signal.set_defaults(func=cmd_broker_test)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    setup_logging()
    
    if args.command == "info":
        cmd_info(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()