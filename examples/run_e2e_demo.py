# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

#!/usr/bin/env python3
"""
ForgeMind 端到端流水线 Demo

跑真数据流,展示:
- 数据拉取
- 166 因子计算
- IC 评估
- LightGBM 模型训练
- Walk-Forward OOS 验证
- Monte Carlo 稳健性
- 完整回测
- 交易信号输出

用法:
    python examples/run_e2e_demo.py                      # 默认规模
    python examples/run_e2e_demo.py --scale small        # 小规模(快速)
    python examples/run_e2e_demo.py --scale large        # 大规模(慢)
    python examples/run_e2e_demo.py --data akshare      # AKShare 真数据(需网络)
"""
import argparse
import os
import sys
from pathlib import Path


def setup_path():
    """设置 Python path"""
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(description="ForgeMind 端到端流水线 Demo")
    parser.add_argument(
        "--scale",
        choices=["tiny", "small", "medium", "large", "xlarge", "mega"],
        default="medium",
        help=(
            "数据规模:"
            "tiny=10票×6月(3s) / "
            "small=20票×1年(5s) / "
            "medium=50票×1年(20s) / "
            "large=100票×半年(40s) / "
            "xlarge=500票×1年(3min) / "
            "mega=1000票×2年(10min,极限)"
        ),
    )
    parser.add_argument(
        "--data",
        choices=["mock", "akshare", "csv"],
        default="mock",
        help="数据源",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="CSV 文件路径(当 --data=csv 时使用)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="保存结果 JSON 路径(可选)",
    )
    parser.add_argument(
        "--no-wfo",
        action="store_true",
        help="关闭 Walk-Forward(加速)",
    )
    parser.add_argument(
        "--no-mc",
        action="store_true",
        help="关闭 Monte Carlo(加速)",
    )
    args = parser.parse_args()
    
    setup_path()
    
    # 确保 API key
    if "FORGEMIND_API_SECRET_KEY" not in os.environ:
        os.environ["FORGEMIND_API_SECRET_KEY"] = "a" * 32
    
    from forgemind.core.pipeline import EndToEndPipeline
    
    # 规模映射
    scale_configs = {
        "tiny":   {"symbols": 10,  "months": 6,   "expect_time": "3s"},
        "small":  {"symbols": 20,  "months": 12,  "expect_time": "5s"},
        "medium": {"symbols": 50,  "months": 12,  "expect_time": "20s"},
        "large":  {"symbols": 100, "months": 6,   "expect_time": "40s"},
        "xlarge": {"symbols": 500, "months": 12,  "expect_time": "3min"},
        "mega":   {"symbols": 1000, "months": 24,  "expect_time": "10min"},
    }
    
    cfg = scale_configs[args.scale]
    symbols = [f"S{i:05d}" for i in range(cfg["symbols"])]
    
    start_date = "2024-01-01"
    # 计算 end_date
    from datetime import datetime, timedelta
    end_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=30 * cfg["months"])).strftime("%Y-%m-%d")
    
    print(f"\n🚀 ForgeMind 端到端 Demo")
    print(f"   规模:  {args.scale} ({cfg['symbols']} 票 × {cfg['months']} 月)")
    print(f"   数据:  {args.data}")
    print(f"   区间:  {start_date} → {end_date}")
    print(f"   WFO:   {'关闭' if args.no_wfo else '开启(3 folds)'}")
    print(f"   MC:    {'关闭' if args.no_mc else '开启(30 模拟)'}")
    print()
    
    # 创建 pipeline
    pipeline = EndToEndPipeline(
        symbols=symbols,
        start=start_date,
        end=end_date,
        data_source=args.data,
        data_path=args.csv,
        top_n_signals=min(20, cfg["symbols"] // 2),
        wfo_enabled=not args.no_wfo,
        mc_enabled=not args.no_mc,
        wfo_n_folds=3,
        mc_n_simulations=30,
    )
    
    # 跑
    import time
    t0 = time.time()
    result = pipeline.run()
    elapsed = time.time() - t0
    
    # 打印结果
    print(result.summary())
    print(f"\n⏱️  端到端总耗时(含 CLI 开销): {elapsed:.2f}s")
    
    # 保存
    if args.output:
        import json
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False, default=str)
        print(f"\n💾 结果已保存到: {args.output}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())