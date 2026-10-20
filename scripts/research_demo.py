#!/usr/bin/env python3
# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""研究示例:对着**已安装的** ForgeMind 包跑一次完整研究流程。

流程:真实取数 → 多因子 IC 评估 → 选股 → 回测 → 打印可分析的结果。

    python scripts/research_demo.py
    python scripts/research_demo.py --symbols 600519,000001 --start 2024-01-01

需要能访问公网行情源。用的是真实数据,不使用编造的数值。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ForgeMind 研究示例")
    parser.add_argument("--symbols", default="600519,000001",
                        help="逗号分隔的标的代码")
    parser.add_argument("--start", default="2024-01-01", help="起始日期")
    parser.add_argument("--end", default="2024-12-31", help="结束日期")
    parser.add_argument("--data-source", default="akshare",
                        choices=["akshare", "csv", "mock"],
                        help="数据来源;akshare 为真实取数")
    parser.add_argument("--top-n", type=int, default=5, help="选股数量")
    parser.add_argument("--no-wfo", action="store_true", help="跳过滚动前向优化")
    parser.add_argument("--no-mc", action="store_true", help="跳过蒙特卡洛稳健性检验")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        print("没有给出任何标的", file=sys.stderr)
        return 2

    try:
        from forgemind.core.pipeline.end_to_end import EndToEndPipeline
    except ImportError as exc:
        print(f"未装好 ForgeMind,先按 README 的安装说明安装: {exc}", file=sys.stderr)
        return 2

    pipeline = EndToEndPipeline(
        symbols=symbols,
        start=args.start,
        end=args.end,
        data_source=args.data_source,
        top_n_signals=args.top_n,
        wfo_enabled=not args.no_wfo,
        mc_enabled=not args.no_mc,
    )

    result = pipeline.run()

    summary = {
        "数据": {
            "标的数": result.n_symbols,
            "交易日数": result.n_days,
            "K 线数": result.n_bars,
            "来源": args.data_source,
        },
        "因子": {
            "计算因子数": result.n_factors_computed,
            "最优因子平均 IC": round(result.best_ic_mean, 6),
            "最优因子 ICIR": round(result.best_icir, 6),
            "交叉验证 Rank IC 均值": round(result.cv_rank_ic_mean, 6),
            "交叉验证 Rank IC 标准差": round(result.cv_rank_ic_std, 6),
        },
        "模型": {
            "名称": result.model_name,
            "Top 特征数": len(result.top_features),
        },
        "回测": {
            "总收益": round(result.total_return, 6),
            "夏普": round(result.sharpe, 6),
            "索提诺": round(result.sortino, 6),
            "最大回撤": round(result.max_drawdown, 6),
            "胜率": round(result.win_rate, 6),
            "交易次数": result.n_trades,
        },
        "信号数": len(result.signals),
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print("=== 数据 ===")
    for k, v in summary["数据"].items():
        print(f"  {k}: {v}")
    print("=== 因子 ===")
    for k, v in summary["因子"].items():
        print(f"  {k}: {v}")
    if result.ic_top_factors:
        print("  IC 排名靠前的因子:")
        for item in result.ic_top_factors[:5]:
            print(f"    {item.get('factor')}: IC={item.get('ic_mean')} ICIR={item.get('icir')}")
    print("=== 模型 ===")
    for k, v in summary["模型"].items():
        print(f"  {k}: {v}")
    print("=== 回测 ===")
    for k, v in summary["回测"].items():
        print(f"  {k}: {v}")
    if result.signals:
        print("=== 信号 ===")
        for sig in result.signals[: args.top_n]:
            print(f"  {sig.get('symbol')} {sig.get('side')} "
                  f"置信度={sig.get('confidence')} 理由={sig.get('rationale', '')[:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
