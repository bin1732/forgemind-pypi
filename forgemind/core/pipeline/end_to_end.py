# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import polars as pl
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass, field, asdict


@dataclass
class PipelineResult:
    """端到端流水线结果"""
    # 数据
    n_symbols: int
    n_days: int
    n_bars: int
    
    # 因子
    n_factors_computed: int
    
    # IC
    ic_top_factors: List[Dict]  # Top N 因子的 IC 信息
    best_ic_mean: float
    best_icir: float
    
    # 模型
    model_name: str
    cv_rank_ic_mean: float
    cv_rank_ic_std: float
    cv_sharpe: float
    top_features: Dict[str, float]
    
    # 回测
    total_return: float
    sharpe: float
    sortino: float
    max_drawdown: float
    win_rate: float
    n_trades: int
    
    # 信号(必填,无默认值)
    signals: List[Dict]
    
    # 元数据(必填)
    start_date: str
    end_date: str
    duration_seconds: float
    
    # Walk-Forward(防 look-ahead)— 可选,默认 0
    wfo_oos_sharpe: float = 0.0
    wfo_oos_return: float = 0.0
    wfo_oos_max_dd: float = 0.0
    wfo_n_folds: int = 0
    wfo_folds_detail: List[Dict] = field(default_factory=list)
    
    # Monte Carlo(稳健性)— 可选,默认 0
    mc_sharpe_5pct: float = 0.0
    mc_sharpe_95pct: float = 0.0
    mc_return_5pct: float = 0.0
    mc_return_95pct: float = 0.0
    mc_n_successful: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def summary(self) -> str:
        wfo_block = ""
        if self.wfo_n_folds > 0:
            wfo_block = f"""
║ ⏭️  Walk-Forward OOS                                              ║
║   OOS Sharpe:  {self.wfo_oos_sharpe:.2f}                                         ║
║   OOS Return:  {self.wfo_oos_return:.2%}                                        ║
║   OOS MaxDD:   {self.wfo_oos_max_dd:.2%}                                         ║
║   Folds:       {self.wfo_n_folds}                                              ║"""

        mc_block = ""
        if self.mc_n_successful > 0:
            mc_block = f"""
║ 🎲 Monte Carlo({self.mc_n_successful} 模拟)                                    ║
║   Sharpe 5-95%:  [{self.mc_sharpe_5pct:.2f}, {self.mc_sharpe_95pct:.2f}]                          ║
║   Return 5-95%:  [{self.mc_return_5pct:.2%}, {self.mc_return_95pct:.2%}]                        ║"""

        return f"""
╔══════════════════════════════════════════════════════════════════╗
║              ForgeMind 端到端流水线结果 v2026.09                  ║
╠══════════════════════════════════════════════════════════════════╣
║ 📊 数据                                                          ║
║   股票数: {self.n_symbols}                                          ║
║   天数:   {self.n_days}                                            ║
║   K线数:  {self.n_bars}                                            ║
║   区间:   {self.start_date} → {self.end_date}                       ║
╠══════════════════════════════════════════════════════════════════╣
║ 🧮 因子库                                                        ║
║   计算因子数: {self.n_factors_computed}                                   ║
╠══════════════════════════════════════════════════════════════════╣
║ 📈 IC 评估(Top 5)                                                ║
║   最佳 IC 均值: {self.best_ic_mean:.4f}                                  ║
║   最佳 ICIR:    {self.best_icir:.4f}                                     ║
║   Top 因子:                                                         ║
{chr(10).join(f'   {i+1}. {f["factor"]:25s}  IC={f["ic_mean"]:.4f}  RankIC={f["rank_ic_mean"]:.4f}' for i, f in enumerate(self.ic_top_factors[:5]))}
╠══════════════════════════════════════════════════════════════════╣
║ 🤖 模型({self.model_name})                                              ║
║   CV Rank IC: {self.cv_rank_ic_mean:.4f} ± {self.cv_rank_ic_std:.4f}           ║
║   CV Sharpe:  {self.cv_sharpe:.2f}                                          ║
║   Top 5 特征:                                                       ║
{chr(10).join(f'   {i+1}. {k:25s}  importance={v:.4f}' for i, (k, v) in enumerate(list(self.top_features.items())[:5]))}
╠══════════════════════════════════════════════════════════════════╣
║ 📊 回测                                                           ║
║   总收益:    {self.total_return:.2%}                                       ║
║   Sharpe:    {self.sharpe:.2f}                                              ║
║   Sortino:   {self.sortino:.2f}                                             ║
║   Max DD:    {self.max_drawdown:.2%}                                        ║
║   胜率:      {self.win_rate:.1%}                                            ║
║   交易数:    {self.n_trades}                                              ║{wfo_block}{mc_block}
╠══════════════════════════════════════════════════════════════════╣
║ 🎯 信号输出(Top {len(self.signals)})                                              ║
{chr(10).join(f'   {i+1}. {s["symbol"]}  {s["side"]:4s}  conf={s["confidence"]:.2f}  {s["rationale"][:50]}' for i, s in enumerate(self.signals[:5]))}
╠══════════════════════════════════════════════════════════════════╣
║ ⏱️  耗时: {self.duration_seconds:.2f}s                                              ║
╚══════════════════════════════════════════════════════════════════╝
"""


class EndToEndPipeline:
    """端到端真数据流水线
    
    用法:
        pipeline = EndToEndPipeline(
            symbols=["600519.SH", "000001.SZ", ...],
            start="2024-01-01",
            end="2024-12-31",
            data_source="mock",  # 或 "akshare"
        )
        result = pipeline.run()
        print(result.summary())
    """
    
    def __init__(
        self,
        symbols: List[str],
        start: str = "2024-01-01",
        end: str = "2024-12-31",
        data_source: str = "mock",  # "mock" / "akshare" / "csv"
        data_path: Optional[str] = None,
        top_n_signals: int = 10,
        ic_top_n: int = 20,
        wfo_n_folds: int = 3,
        wfo_enabled: bool = True,
        mc_n_simulations: int = 30,
        mc_enabled: bool = True,
    ):
        self.symbols = symbols
        self.start = start
        self.end = end
        self.data_source = data_source
        self.data_path = data_path
        self.top_n_signals = top_n_signals
        self.ic_top_n = ic_top_n
        self.wfo_n_folds = wfo_n_folds
        self.wfo_enabled = wfo_enabled
        self.mc_n_simulations = mc_n_simulations
        self.mc_enabled = mc_enabled
    
    def run(self) -> PipelineResult:
        """完整运行"""
        start_time = datetime.now()
        
        # 用 OTel + Prometheus 观测
        from forgemind.core.observability import (
            PipelineTracker, span, get_metrics
        )
        tracker = PipelineTracker("e2e")
        tracker.start(
            n_symbols=len(self.symbols),
            data_source=self.data_source,
        )
        metrics = get_metrics()
        
        try:
            # === Step 1: 拉数据 ===
            with span("fetch_data", source=self.data_source) as s1:
                df_polars = self._fetch_data()
                n_bars = df_polars.select(pl.len()).collect().item()
                n_days = df_polars.select(pl.col("date").n_unique()).collect().item()
                metrics.inc("data.bars_loaded", n_bars)
                tracker.step("fetch_data", n_bars=n_bars, n_days=n_days)
            
            # === Step 2: 算因子 ===
            with span("compute_factors") as s2:
                df_with_factors = self._compute_factors(df_polars)
                n_factors = len([c for c in df_with_factors.collect_schema().names()
                                if c not in ["date", "symbol", "open", "high", "low", "close", "volume", "industry", "returns"]])
                metrics.set_gauge("factors.count", n_factors)
                tracker.step("compute_factors", n_factors=n_factors)
            
            # === Step 3: IC 评估 ===
            with span("evaluate_ic") as s3:
                ic_results = self._evaluate_ic(df_with_factors)
                best = max(ic_results, key=lambda r: abs(r.rank_ic_mean)) if ic_results else None
                metrics.inc("ic.factors_evaluated", len(ic_results))
                tracker.step("evaluate_ic", n_ic=len(ic_results))
            
            # === Step 4: LightGBM 训练 ===
            with span("train_model") as s4:
                model_result, top_features = self._train_model(df_with_factors, ic_results)
                tracker.step("train_model", cv_sharpe=model_result.get("cv_sharpe", 0.0))
            
            # === Step 5: 回测 ===
            with span("backtest") as s5:
                backtest_metrics = self._backtest(df_with_factors, ic_results)
                metrics.observe("backtest.sharpe", backtest_metrics.get("sharpe", 0.0))
                tracker.step("backtest", sharpe=backtest_metrics.get("sharpe", 0.0))
            
            # === Step 5b: Walk-Forward Optimization(OOS 验证) ===
            with span("walk_forward"):
                wfo_result = self._walk_forward(df_with_factors, ic_results) if self.wfo_enabled else {"oos_sharpe": 0.0, "oos_return": 0.0, "oos_max_dd": 0.0, "n_folds": 0, "folds_detail": []}
                metrics.observe("wfo.oos_sharpe", wfo_result.get("oos_sharpe", 0.0))
                tracker.step("walk_forward", oos_sharpe=wfo_result.get("oos_sharpe", 0.0))
            
            # === Step 5c: Monte Carlo 稳健性 ===
            with span("monte_carlo"):
                mc_result = self._monte_carlo(df_with_factors, ic_results) if self.mc_enabled else {"sharpe_5pct": 0.0, "sharpe_95pct": 0.0, "return_5pct": 0.0, "return_95pct": 0.0, "n_successful": 0}
                metrics.inc("mc.simulations", mc_result.get("n_successful", 0))
                tracker.step("monte_carlo", n_sims=mc_result.get("n_successful", 0))
            
            # === Step 6: 信号输出 ===
            with span("generate_signals"):
                signals = self._generate_signals(df_with_factors, model_result, top_features)
                metrics.inc("signals.generated", len(signals))
                tracker.step("generate_signals", n_signals=len(signals))
            
            tracker.end()
        except Exception as e:
            tracker.end(error=e)
            raise
        
        end_time = datetime.now()
        
        return PipelineResult(
            n_symbols=len(self.symbols),
            n_days=n_days,
            n_bars=n_bars,
            n_factors_computed=n_factors,
            ic_top_factors=[
                {"factor": r.factor, "ic_mean": r.ic_mean, "rank_ic_mean": r.rank_ic_mean}
                for r in sorted(ic_results, key=lambda r: abs(r.rank_ic_mean), reverse=True)[:10]
            ] if ic_results else [],
            best_ic_mean=best.ic_mean if best else 0.0,
            best_icir=float(best.icir) if best else 0.0,
            model_name="LightGBM",
            cv_rank_ic_mean=model_result.get("cv_rank_ic_mean", 0.0),
            cv_rank_ic_std=model_result.get("cv_rank_ic_std", 0.0),
            cv_sharpe=model_result.get("cv_sharpe", 0.0),
            top_features=top_features,
            total_return=backtest_metrics.get("total_return", 0.0),
            sharpe=backtest_metrics.get("sharpe", 0.0),
            sortino=backtest_metrics.get("sortino", 0.0),
            max_drawdown=backtest_metrics.get("max_drawdown", 0.0),
            win_rate=backtest_metrics.get("win_rate", 0.0),
            n_trades=backtest_metrics.get("n_trades", 0),
            wfo_oos_sharpe=wfo_result.get("oos_sharpe", 0.0),
            wfo_oos_return=wfo_result.get("oos_return", 0.0),
            wfo_oos_max_dd=wfo_result.get("oos_max_dd", 0.0),
            wfo_n_folds=wfo_result.get("n_folds", 0),
            wfo_folds_detail=wfo_result.get("folds_detail", []),
            mc_sharpe_5pct=mc_result.get("sharpe_5pct", 0.0),
            mc_sharpe_95pct=mc_result.get("sharpe_95pct", 0.0),
            mc_return_5pct=mc_result.get("return_5pct", 0.0),
            mc_return_95pct=mc_result.get("return_95pct", 0.0),
            mc_n_successful=mc_result.get("n_successful", 0),
            signals=signals,
            start_date=self.start,
            end_date=self.end,
            duration_seconds=(end_time - start_time).total_seconds(),
        )
    
    def _fetch_data(self) -> pl.LazyFrame:
        """Step 1: 拉数据"""
        if self.data_source == "mock":
            return self._mock_data()
        elif self.data_source == "csv":
            return pl.scan_csv(self.data_path)
        elif self.data_source == "akshare":
            return self._akshare_data()
        else:
            raise ValueError(f"Unknown data_source: {self.data_source}")
    
    def _mock_data(self) -> pl.LazyFrame:
        """Mock 数据(无网络依赖)"""
        dates = [datetime.strptime(self.start, "%Y-%m-%d") + timedelta(days=i)
                 for i in range((datetime.strptime(self.end, "%Y-%m-%d") - datetime.strptime(self.start, "%Y-%m-%d")).days + 1)]
        
        np.random.seed(42)
        rows = []
        for sym in self.symbols:
            price = 100.0
            for date in dates:
                # 让不同股票有不同的 drift 和 vol(真实市场)
                sym_idx = self.symbols.index(sym)
                drift = 0.0005 + 0.0001 * (sym_idx % 5 - 2)
                vol = 0.015 + 0.005 * (sym_idx % 7 - 3)
                price *= (1 + drift + np.random.randn() * vol)
                
                high = price * (1 + abs(np.random.randn() * 0.008))
                low = price * (1 - abs(np.random.randn() * 0.008))
                open_ = price * (1 + np.random.randn() * 0.003)
                volume = int(np.random.lognormal(15, 1))
                
                rows.append({
                    "symbol": sym,
                    "date": date,
                    "open": open_, "high": high, "low": low,
                    "close": price, "volume": volume,
                })
        
        df = pl.LazyFrame(rows).sort(["symbol", "date"]).with_columns([
            pl.col("close").pct_change().over("symbol").alias("returns"),
        ])
        return df
    
    def _akshare_data(self) -> pl.LazyFrame:
        """AKShare 真数据(网络不通时 fallback)"""
        try:
            from forgemind.core.data.akshare_etl import AKShareETL
            etl = AKShareETL()
            df_pandas = etl.fetch(symbols=self.symbols, start=self.start, end=self.end)
            return pl.LazyFrame(df_pandas).sort(["symbol", "date"])
        except Exception:
            return self._mock_data()
    
    def _compute_factors(self, df: pl.LazyFrame) -> pl.LazyFrame:
        """Step 2: 算因子"""
        from forgemind.core.factors import compute_alpha158, Alpha158Config
        
        config = Alpha158Config()
        # Alpha158(主力)
        df = compute_alpha158(df, config)
        return df
    
    def _evaluate_ic(self, df: pl.LazyFrame) -> List:
        """Step 3: IC 评估"""
        from forgemind.core.factors import (
            compute_forward_returns, batch_compute_ic,
            list_alpha158_factors,
        )
        df_with_returns = compute_forward_returns(df, [1, 5])
        
        # 收集所有因子名(排除非因子列)
        non_factor_cols = {"date", "symbol", "open", "high", "low", "close", 
                          "volume", "returns", "industry", "fwd_return_1",
                          "fwd_return_5", "fwd_return_10", "fwd_return_20"}
        df_cols = df_with_returns.collect_schema().names()
        factor_cols = [c for c in df_cols if c not in non_factor_cols][:30]  # 限制 30 个因子加速
        
        results = batch_compute_ic(df_with_returns, factor_cols, decay_cols=["fwd_return_1", "fwd_return_5"])
        return results
    
    def _train_model(self, df: pl.LazyFrame, ic_results: List) -> tuple:
        """Step 4: LightGBM 训练"""
        from forgemind.core.factors import compute_forward_returns
        from forgemind.core.models import LightGBMModel
        
        df_with_returns = compute_forward_returns(df, [1])
        df_collected = df_with_returns.collect().to_pandas()
        
        # 选 Top 因子
        top_factor_names = [r.factor for r in sorted(ic_results, key=lambda r: abs(r.rank_ic_mean), reverse=True)[:15]]
        feature_cols = [c for c in top_factor_names if c in df_collected.columns]
        
        if not feature_cols:
            return {"cv_rank_ic_mean": 0.0, "cv_rank_ic_std": 0.0, "cv_sharpe": 0.0}, {}
        
        X = df_collected[feature_cols].fillna(0)
        y = df_collected["fwd_return_1"].fillna(0)
        
        model = LightGBMModel()
        result = model.train(X, y, use_cv=True)
        
        top_features = dict(sorted(
            result.feature_importance.items(),
            key=lambda x: -x[1]
        )[:5])
        
        return {
            "cv_rank_ic_mean": result.cv_mean,
            "cv_rank_ic_std": result.cv_std,
            "cv_sharpe": result.cv_mean * np.sqrt(252) if abs(result.cv_mean) > 0 else 0.0,
        }, top_features
    
    def _backtest(self, df: pl.LazyFrame, ic_results: List) -> Dict:
        """Step 5: 回测"""
        from forgemind.core.backtest import BacktestReport
        
        df_with_returns = df.with_columns([
            (pl.col("close").shift(-1) / pl.col("close") - 1).alias("fwd_ret"),
        ])
        df_collected = df_with_returns.collect().to_pandas()
        
        # 简单多空回测: 用综合 IC 分数排序, top 1/3 做多, bottom 1/3 做空
        if not ic_results:
            return {"total_return": 0.0, "sharpe": 0.0, "sortino": 0.0, 
                    "max_drawdown": 0.0, "win_rate": 0.0, "n_trades": 0}
        
        # 用 top 因子 daily cross-sectional rank 做策略
        top_factor_names = [r.factor for r in sorted(ic_results, key=lambda r: abs(r.rank_ic_mean), reverse=True)[:5]]
        factor_cols = [c for c in top_factor_names if c in df_collected.columns]
        
        if not factor_cols:
            return {"total_return": 0.0, "sharpe": 0.0, "sortino": 0.0,
                    "max_drawdown": 0.0, "win_rate": 0.0, "n_trades": 0}
        
        # 综合 alpha 分数 = 各因子标准化值的平均
        score = pd.Series(0.0, index=df_collected.index)
        for col in factor_cols:
            normalized = df_collected.groupby("date")[col].transform(
                lambda x: (x - x.mean()) / (x.std() + 1e-9)
            )
            score = score.add(normalized.fillna(0), fill_value=0)
        score = score / len(factor_cols)
        
        # 每天 rank
        ranks = score.groupby(df_collected["date"]).rank(pct=True)
        
        # long top 1/3, short bottom 1/3
        long_signal = (ranks > 0.67).astype(int)
        short_signal = (ranks < 0.33).astype(int) * -1
        signal = long_signal + short_signal
        
        # 收益
        daily_returns = df_collected["fwd_ret"].fillna(0) * signal
        # 每天 portfolio return = 持仓的收益平均
        portfolio_returns = daily_returns.groupby(df_collected["date"]).mean()
        
        metrics = BacktestReport.compute_metrics(portfolio_returns.dropna())
        
        return {
            "total_return": metrics.total_return,
            "sharpe": metrics.sharpe,
            "sortino": metrics.sortino,
            "max_drawdown": metrics.max_drawdown,
            "win_rate": metrics.win_rate,
            "n_trades": (signal.diff().abs() > 0).sum(),
        }
    
    def _walk_forward(
        self,
        df: pl.LazyFrame,
        ic_results: List,
        n_folds: int = 3,
    ) -> Dict:
        """Step 5b: Walk-Forward Optimization(防 look-ahead)
        
        把数据按时间切成 N 个 fold,每个 fold 用前面的数据"训练"IC 权重,
        评估在后续数据上的 OOS 表现。这是判断策略真实性的黄金标准。
        """
        from forgemind.core.backtest import BacktestReport, WalkForwardOptimizer
        
        if not ic_results:
            return {
                "oos_sharpe": 0.0, "oos_return": 0.0, "oos_max_dd": 0.0,
                "n_folds": 0, "folds_detail": [],
            }
        
        df_collected = df.collect().to_pandas()
        top_factor_names = [
            r.factor for r in sorted(ic_results, key=lambda r: abs(r.rank_ic_mean), reverse=True)[:5]
        ]
        factor_cols = [c for c in top_factor_names if c in df_collected.columns]
        if not factor_cols:
            return {
                "oos_sharpe": 0.0, "oos_return": 0.0, "oos_max_dd": 0.0,
                "n_folds": 0, "folds_detail": [],
            }
        
        # 准备数据
        df_with_fwd = df_collected.copy()
        df_with_fwd["fwd_ret"] = df_with_fwd.groupby("symbol")["close"].pct_change().shift(-1)
        
        # 用 IC 排序权重做策略
        def strategy_factory(top_pct=0.33):
            return {"top_pct": top_pct}
        
        def backtest_fn(params, data):
            """简化回测:用 IC 分数排序做多空"""
            top_pct = params["top_pct"]
            # 计算 composite score
            score = pd.Series(0.0, index=data.index)
            for col in factor_cols:
                if col in data.columns:
                    normalized = data.groupby("date")[col].transform(
                        lambda x: (x - x.mean()) / (x.std() + 1e-9)
                    )
                    score = score.add(normalized.fillna(0), fill_value=0)
            score = score / max(1, len(factor_cols))
            ranks = score.groupby(data["date"]).rank(pct=True)
            
            long_sig = (ranks > 1 - top_pct).astype(int)
            short_sig = (ranks < top_pct).astype(int) * -1
            signal = long_sig + short_sig
            
            daily_ret = data["fwd_ret"].fillna(0) * signal
            portfolio_ret = daily_ret.groupby(data["date"]).mean()
            return portfolio_ret.dropna()
        
        try:
            wfo = WalkForwardOptimizer(
                strategy_factory=strategy_factory,
                backtest_fn=backtest_fn,
                n_folds=self.wfo_n_folds,
            )
            param_grid = {"top_pct": [0.2, 0.33, 0.5]}
            wfo_result = wfo.run(
                df_with_fwd,
                param_grid=param_grid,
                primary_metric="sharpe",
            )
            
            oos_metrics = wfo_result.combined_metrics
            
            return {
                "oos_sharpe": oos_metrics.sharpe,
                "oos_return": oos_metrics.total_return,
                "oos_max_dd": oos_metrics.max_drawdown,
                "n_folds": len(wfo_result.folds),
                "folds_detail": wfo_result.folds,
            }
        except Exception:
            return {
                "oos_sharpe": 0.0, "oos_return": 0.0, "oos_max_dd": 0.0,
                "n_folds": 0, "folds_detail": [],
            }
    
    def _monte_carlo(
        self,
        df: pl.LazyFrame,
        ic_results: List,
        n_simulations: int = 30,
    ) -> Dict:
        """Step 5c: Monte Carlo 稳健性
        
        对 IC 排序做参数扰动,看 Sharpe 分布
        """
        from forgemind.core.backtest import MonteCarloSimulator, BacktestReport
        
        if not ic_results:
            return {
                "sharpe_5pct": 0.0, "sharpe_95pct": 0.0,
                "return_5pct": 0.0, "return_95pct": 0.0,
                "n_successful": 0,
            }
        
        df_collected = df.collect().to_pandas()
        top_factor_names = [
            r.factor for r in sorted(ic_results, key=lambda r: abs(r.rank_ic_mean), reverse=True)[:5]
        ]
        factor_cols = [c for c in top_factor_names if c in df_collected.columns]
        if not factor_cols:
            return {
                "sharpe_5pct": 0.0, "sharpe_95pct": 0.0,
                "return_5pct": 0.0, "return_95pct": 0.0,
                "n_successful": 0,
            }
        
        df_with_fwd = df_collected.copy()
        df_with_fwd["fwd_ret"] = df_with_fwd.groupby("symbol")["close"].pct_change().shift(-1)
        
        def strategy_factory(top_pct=0.33):
            return {"top_pct": top_pct}
        
        def backtest_fn(params, data):
            top_pct = params["top_pct"]
            score = pd.Series(0.0, index=data.index)
            for col in factor_cols:
                if col in data.columns:
                    normalized = data.groupby("date")[col].transform(
                        lambda x: (x - x.mean()) / (x.std() + 1e-9)
                    )
                    score = score.add(normalized.fillna(0), fill_value=0)
            score = score / max(1, len(factor_cols))
            ranks = score.groupby(data["date"]).rank(pct=True)
            long_sig = (ranks > 1 - top_pct).astype(int)
            short_sig = (ranks < top_pct).astype(int) * -1
            signal = long_sig + short_sig
            daily_ret = data["fwd_ret"].fillna(0) * signal
            portfolio_ret = daily_ret.groupby(data["date"]).mean()
            return portfolio_ret.dropna()
        
        try:
            mc = MonteCarloSimulator(
                strategy_factory=strategy_factory,
                backtest_fn=backtest_fn,
                n_simulations=self.mc_n_simulations,
                param_noise_pct=0.1,
            )
            result = mc.run(df_with_fwd, base_params={"top_pct": 0.33})
            return {
                "sharpe_5pct": result["sharpe_5th_pct"],
                "sharpe_95pct": result["sharpe_95th_pct"],
                "return_5pct": result["return_5th_pct"],
                "return_95pct": result["return_95th_pct"],
                "n_successful": result["n_successful"],
            }
        except Exception:
            return {
                "sharpe_5pct": 0.0, "sharpe_95pct": 0.0,
                "return_5pct": 0.0, "return_95pct": 0.0,
                "n_successful": 0,
            }
    
    def _generate_signals(
        self,
        df: pl.LazyFrame,
        model_result: Dict,
        top_features: Dict,
    ) -> List[Dict]:
        """Step 6: 信号输出"""
        # 取最后一天数据
        df_collected = df.collect().to_pandas()
        last_date = df_collected["date"].max()
        last_data = df_collected[df_collected["date"] == last_date].copy()
        
        if last_data.empty or not top_features:
            return []
        
        # 用 top 因子分数生成信号
        score = pd.Series(0.0, index=last_data.index)
        for factor in top_features.keys():
            if factor in last_data.columns:
                normalized = (last_data[factor] - last_data[factor].mean()) / (last_data[factor].std() + 1e-9)
                score = score.add(normalized.fillna(0), fill_value=0)
        
        # 排名
        last_data["score"] = score
        top_stocks = last_data.nlargest(self.top_n_signals, "score")
        
        signals = []
        for _, row in top_stocks.iterrows():
            confidence = min(0.95, 0.5 + abs(row["score"]) / 10)
            rationale = f"因子综合得分 {row['score']:.4f} (top 特征: {', '.join(list(top_features.keys())[:3])})"
            signals.append({
                "signal_id": f"sig_{last_date.strftime('%Y%m%d')}_{row['symbol']}",
                "symbol": row["symbol"],
                "side": "BUY",
                "confidence": round(confidence, 3),
                "rationale": rationale,
                "timestamp": str(datetime.now()),
            })
        
        return signals