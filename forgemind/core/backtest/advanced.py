# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import numpy as np
import pandas as pd
from typing import Callable, Dict, List, Tuple, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class BacktestMetrics:
    """完整回测指标 — 对标 Riskfolio / QuantStats"""
    # 收益指标
    total_return: float
    cagr: float  # 复合年增长率
    # 风险指标
    volatility: float
    max_drawdown: float
    max_drawdown_duration_days: int
    # 风险调整收益
    sharpe: float
    sortino: float
    calmar: float
    # 交易指标
    win_rate: float
    profit_factor: float
    n_trades: int
    avg_win: float
    avg_loss: float
    expectancy: float  # 期望收益 = win_rate * avg_win - (1 - win_rate) * |avg_loss|
    # 信息比率
    information_ratio: float
    # 其他
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def summary(self) -> str:
        return (
            f"  Total Return:    {self.total_return:.2%}\n"
            f"  CAGR:            {self.cagr:.2%}\n"
            f"  Sharpe:          {self.sharpe:.2f}\n"
            f"  Sortino:         {self.sortino:.2f}\n"
            f"  Calmar:          {self.calmar:.2f}\n"
            f"  Max DD:          {self.max_drawdown:.2%} ({self.max_drawdown_duration_days}d)\n"
            f"  Win Rate:        {self.win_rate:.1%}\n"
            f"  Profit Factor:   {self.profit_factor:.2f}\n"
            f"  Expectancy:      {self.expectancy:.4f}\n"
            f"  N Trades:        {self.n_trades}\n"
            f"  Information Ratio: {self.information_ratio:.2f}"
        )


class BacktestReport:
    """回测报告生成器"""
    
    @staticmethod
    def compute_metrics(
        returns: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
        trades: Optional[pd.DataFrame] = None,
    ) -> BacktestMetrics:
        """从日度收益序列计算完整指标"""
        returns = returns.dropna()
        if len(returns) == 0:
            return BacktestMetrics(
                total_return=0, cagr=0, volatility=0, max_drawdown=0,
                max_drawdown_duration_days=0, sharpe=0, sortino=0, calmar=0,
                win_rate=0, profit_factor=0, n_trades=0, avg_win=0,
                avg_loss=0, expectancy=0, information_ratio=0,
            )
        
        # 总收益 + CAGR
        total_return = float((1 + returns).prod() - 1)
        n_days = len(returns)
        cagr = float((1 + total_return) ** (252 / n_days) - 1) if n_days > 0 else 0.0

        # 波动率
        volatility = float(returns.std() * np.sqrt(252))

        # 最大回撤
        cum = (1 + returns).cumprod()
        running_max = cum.cummax()
        drawdown = cum / running_max - 1
        max_drawdown = float(drawdown.min())

        # 最大回撤持续期
        dd_dur = 0
        max_dd_dur = 0
        for dd in drawdown:
            if dd < 0:
                dd_dur += 1
                max_dd_dur = max(max_dd_dur, dd_dur)
            else:
                dd_dur = 0

        # Sharpe (无风险利率 = 0 简化)
        sharpe = float(returns.mean() / (returns.std() + 1e-9) * np.sqrt(252))

        # Sortino(下行风险)
        downside = returns[returns < 0]
        sortino = float(returns.mean() / (downside.std() + 1e-9) * np.sqrt(252)) if len(downside) > 0 else 0.0

        # Calmar
        calmar = float(cagr / (abs(max_drawdown) + 1e-9))
        
        # 交易指标(从 returns 序列推断)
        win_rate = float((returns > 0).sum() / len(returns))
        wins = returns[returns > 0]
        losses = returns[returns < 0]
        avg_win = float(wins.mean()) if len(wins) > 0 else 0.0
        avg_loss = float(losses.mean()) if len(losses) > 0 else 0.0
        profit_factor = float(wins.sum() / abs(losses.sum())) if len(losses) > 0 and losses.sum() != 0 else float('inf')
        expectancy = float(win_rate * avg_win - (1 - win_rate) * abs(avg_loss))
        
        # Information Ratio
        info_ratio = 0.0
        if benchmark_returns is not None:
            benchmark_returns = benchmark_returns.reindex(returns.index).fillna(0)
            excess = returns - benchmark_returns
            info_ratio = float(excess.mean() / (excess.std() + 1e-9) * np.sqrt(252))
        
        return BacktestMetrics(
            total_return=total_return,
            cagr=cagr,
            volatility=volatility,
            max_drawdown=max_drawdown,
            max_drawdown_duration_days=max_dd_dur,
            sharpe=sharpe,
            sortino=sortino,
            calmar=calmar,
            win_rate=win_rate,
            profit_factor=profit_factor,
            n_trades=len(trades) if trades is not None else (returns != 0).sum(),
            avg_win=avg_win,
            avg_loss=avg_loss,
            expectancy=expectancy,
            information_ratio=info_ratio,
            start_date=str(returns.index[0]) if hasattr(returns.index[0], 'isoformat') else None,
            end_date=str(returns.index[-1]) if hasattr(returns.index[-1], 'isoformat') else None,
        )


# === Walk-Forward Optimization ===
@dataclass
class WFOResult:
    """Walk-Forward 结果"""
    folds: List[Dict]  # 每个 fold 的结果
    oos_returns: pd.Series  # OOS 拼接收益
    combined_sharpe: float
    combined_metrics: BacktestMetrics


class WalkForwardOptimizer:
    """Walk-Forward 优化(防 look-ahead 偏差)
    
    流程(AFML Ch.11):
    1. 划分数据为 N 个连续 fold
    2. 每个 fold: 在 train 上找最优参数, 在 test 上评估
    3. 拼接所有 test 段 → 得到 OOS 收益序列
    
    这是判断策略真实性的黄金标准。
    """
    
    def __init__(
        self,
        strategy_factory: Callable,  # 接受 params 返回策略实例
        backtest_fn: Callable,  # 接受 (strategy, data) 返回 returns Series
        n_folds: int = 5,
        anchored: bool = False,  # True = anchored(累积), False = rolling
    ):
        self.strategy_factory = strategy_factory
        self.backtest_fn = backtest_fn
        self.n_folds = n_folds
        self.anchored = anchored
    
    def _split_folds(self, n: int) -> List[Tuple[int, int, int, int]]:
        """划分 folds: 返回 (train_start, train_end, test_start, test_end)"""
        fold_size = n // (self.n_folds + 1)  # 留 1/n 给 test
        test_size = fold_size
        result = []
        for i in range(self.n_folds):
            if self.anchored:
                train_start = 0
            else:
                train_start = i * fold_size
            
            train_end = (i + 1) * fold_size
            test_start = train_end
            test_end = test_start + test_size
            
            if test_end > n:
                test_end = n
            
            result.append((train_start, train_end, test_start, test_end))
        return result
    
    def run(
        self,
        df: pd.DataFrame,
        param_grid: Dict[str, List],
        primary_metric: str = "sharpe",
    ) -> WFOResult:
        """执行 Walk-Forward
        
        Args:
            df: 数据(按时间排序)
            param_grid: 参数网格 {"lookback": [10, 20, 30], "threshold": [0.5, 1.0]}
            primary_metric: 用什么指标选最优("sharpe" / "calmar" / "total_return")
        
        Returns:
            WFOResult
        """
        n = len(df)
        folds = self._split_folds(n)
        all_oos_returns = []
        fold_results = []
        
        for fold_idx, (train_start, train_end, test_start, test_end) in enumerate(folds):
            train_df = df.iloc[train_start:train_end]
            test_df = df.iloc[test_start:test_end]
            
            # 在 train 上网格搜索
            best_params = None
            best_metric = -np.inf
            
            from itertools import product
            param_keys = list(param_grid.keys())
            param_values = list(param_grid.values())
            
            for combo in product(*param_values):
                params = dict(zip(param_keys, combo))
                try:
                    strategy = self.strategy_factory(**params)
                    train_returns = self.backtest_fn(strategy, train_df)
                    metrics = BacktestReport.compute_metrics(train_returns)
                    metric_value = getattr(metrics, primary_metric, 0)
                    if metric_value > best_metric:
                        best_metric = metric_value
                        best_params = params
                except Exception:
                    continue
            
            # 用最优参数在 test 上跑
            if best_params:
                strategy = self.strategy_factory(**best_params)
                test_returns = self.backtest_fn(strategy, test_df)
                all_oos_returns.append(test_returns)
                
                fold_metrics = BacktestReport.compute_metrics(test_returns)
                fold_results.append({
                    "fold": fold_idx,
                    "train_start": train_start,
                    "train_end": train_end,
                    "test_start": test_start,
                    "test_end": test_end,
                    "best_params": best_params,
                    "test_sharpe": fold_metrics.sharpe,
                    "test_return": fold_metrics.total_return,
                })
        
        oos_returns = pd.concat(all_oos_returns) if all_oos_returns else pd.Series()
        combined_metrics = BacktestReport.compute_metrics(oos_returns)
        
        return WFOResult(
            folds=fold_results,
            oos_returns=oos_returns,
            combined_sharpe=combined_metrics.sharpe,
            combined_metrics=combined_metrics,
        )


# === Monte Carlo Simulator ===
class MonteCarloSimulator:
    """蒙特卡洛模拟 — 参数扰动评估策略稳健性"""
    
    def __init__(
        self,
        strategy_factory: Callable,
        backtest_fn: Callable,
        n_simulations: int = 100,
        param_noise_pct: float = 0.1,  # 参数 ±10% 扰动
    ):
        self.strategy_factory = strategy_factory
        self.backtest_fn = backtest_fn
        self.n_simulations = n_simulations
        self.param_noise_pct = param_noise_pct
    
    def run(self, df: pd.DataFrame, base_params: Dict) -> Dict:
        """运行蒙特卡洛
        
        Returns:
            {metric_name: distribution array}
        """
        sharpes = []
        returns = []
        max_dds = []
        
        for _ in range(self.n_simulations):
            # 扰动参数
            perturbed = {}
            for k, v in base_params.items():
                if isinstance(v, (int, float)):
                    noise = np.random.uniform(-self.param_noise_pct, self.param_noise_pct)
                    perturbed[k] = v * (1 + noise)
                    if isinstance(v, int):
                        perturbed[k] = int(perturbed[k])
                else:
                    perturbed[k] = v
            
            try:
                strategy = self.strategy_factory(**perturbed)
                rets = self.backtest_fn(strategy, df)
                metrics = BacktestReport.compute_metrics(rets)
                sharpes.append(metrics.sharpe)
                returns.append(metrics.total_return)
                max_dds.append(metrics.max_drawdown)
            except Exception:
                continue
        
        return {
            "sharpe_distribution": np.array(sharpes),
            "return_distribution": np.array(returns),
            "max_dd_distribution": np.array(max_dds),
            "sharpe_5th_pct": float(np.percentile(sharpes, 5)) if sharpes else 0,
            "sharpe_95th_pct": float(np.percentile(sharpes, 95)) if sharpes else 0,
            "return_5th_pct": float(np.percentile(returns, 5)) if returns else 0,
            "return_95th_pct": float(np.percentile(returns, 95)) if returns else 0,
            "n_successful": len(sharpes),
        }


# === Slippage Models ===
class SlippageModel:
    """滑点模型 — 三种: Fixed / Linear / Square-Root
    
    对标 Zipline / Nautilus Trader slippage
    """
    
    @staticmethod
    def fixed_slippage(price: float, size: int, bps: float = 5.0) -> float:
        """固定 bps 滑点"""
        slippage = price * bps / 10000
        return price + slippage  # 买入多付
    
    @staticmethod
    def linear_slippage(price: float, size: int, adv: int, impact_bps: float = 10.0) -> float:
        """线性冲击: impact = adv_pct * impact_bps"""
        if adv <= 0:
            return price
        adv_pct = size / adv
        slippage = price * adv_pct * impact_bps / 10000
        return price + slippage
    
    @staticmethod
    def square_root_slippage(price: float, size: int, adv: int, impact_bps: float = 10.0) -> float:
        """平方根冲击(对标 Almgren-Chriss):
        slippage = σ * √(size / adv) * impact_bps
        
        更真实: 大单冲击比线性模型低
        """
        if adv <= 0:
            return price
        adv_pct = size / adv
        slippage = price * np.sqrt(adv_pct) * impact_bps / 10000
        return price + slippage


# === Multi-Asset Portfolio Backtest ===
class PortfolioBacktest:
    """多资产组合回测"""
    
    def __init__(
        self,
        weights: pd.DataFrame,  # date x symbol 权重
        prices: pd.DataFrame,  # date x symbol 价格
        rebalance_freq: int = 5,  # 每 5 天调仓
        transaction_cost_bps: float = 5.0,
    ):
        self.weights = weights
        self.prices = prices
        self.rebalance_freq = rebalance_freq
        self.transaction_cost_bps = transaction_cost_bps
    
    def run(self) -> pd.Series:
        """返回组合日度收益"""
        # 对齐
        common_dates = self.weights.index.intersection(self.prices.index)
        weights = self.weights.loc[common_dates].fillna(0)
        prices = self.prices.loc[common_dates]
        returns = prices.pct_change().fillna(0)
        
        # 调仓
        portfolio_returns = []
        prev_weights = pd.Series(0, index=weights.columns)
        rebalance_count = 0
        
        for date in common_dates[1:]:
            current_weights = weights.loc[date] if date in weights.index else prev_weights
            
            # 调仓成本
            if rebalance_count % self.rebalance_freq == 0:
                turnover = (current_weights - prev_weights).abs().sum()
                cost = turnover * self.transaction_cost_bps / 10000
                rebalance_count = 0
            else:
                cost = 0
            rebalance_count += 1
            
            # 漂移权重(因价格变动)
            drift_weights = prev_weights * (1 + returns.loc[date])
            drift_weights = drift_weights / (drift_weights.sum() + 1e-9)
            
            # 当日收益(用漂移权重 × 资产收益)
            day_return = (drift_weights * returns.loc[date]).sum() - cost
            
            portfolio_returns.append(day_return)
            prev_weights = current_weights
        
        return pd.Series(portfolio_returns, index=common_dates[1:])