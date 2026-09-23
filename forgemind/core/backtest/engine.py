# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Type, Any
import pandas as pd
import numpy as np

from forgemind.core.strategies.base import Strategy
from forgemind.core.observability.logging import get_logger

logger = get_logger("forgemind.backtest")


@dataclass
class BacktestResult:
    """回测结果"""
    total_return: float
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float
    win_rate: float
    profit_factor: float
    expectancy: float
    n_trades: int
    equity_curve: pd.Series
    signals: pd.DataFrame
    params: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)


class SimpleBacktestEngine:
    """简化回测引擎 — 自实现,不依赖 vectorbt
    
    工作流:
    1. 策略生成信号(entries/exits)
    2. 模拟成交(下一根 bar open 成交)
    3. 计算 equity curve
    4. 计算所有指标
    """
    
    def __init__(
        self,
        initial_capital: float = 100_000.0,
        fees: float = 0.001,  # 0.1% 单边
        slippage_bps: float = 5.0,  # 5 bps
        use_next_open: bool = True,  # True = 次日开盘成交(更真实)
    ):
        self.initial_capital = initial_capital
        self.fees = fees
        self.slippage_bps = slippage_bps
        self.use_next_open = use_next_open
    
    def run(
        self,
        strategy: Strategy,
        price_df: pd.DataFrame,
        symbol: Optional[str] = None,
    ) -> BacktestResult:
        """
        跑单次回测
        
        Args:
            strategy: 策略实例(有 generate_signals 方法)
            price_df: K 线(OHLCV)
            symbol: 可选日志 tag
        """
        logger.info(
            "backtest_started",
            strategy=strategy.name,
            params=strategy.parameters,
            symbol=symbol or "ALL",
            n_bars=len(price_df),
        )
        
        # 1. 生成信号
        signals = strategy.generate_signals(price_df)
        if "entries" not in signals.columns or "exits" not in signals.columns:
            raise ValueError(
                f"Strategy {strategy.name}.generate_signals must return DataFrame with "
                "'entries' and 'exits' boolean columns"
            )
        
        # 2. 模拟成交 + equity curve
        equity_curve = self._simulate_equity(price_df, signals)
        
        # 3. 提取交易
        trades = self._extract_trades(price_df, signals, equity_curve)
        
        # 4. 计算指标
        result = self._compute_metrics(equity_curve, trades, signals, strategy.parameters)
        
        logger.info(
            "backtest_completed",
            strategy=strategy.name,
            total_return=result.total_return,
            sharpe=result.sharpe,
            max_drawdown=result.max_drawdown,
            n_trades=result.n_trades,
        )
        
        return result
    
    def _simulate_equity(
        self,
        price_df: pd.DataFrame,
        signals: pd.DataFrame,
    ) -> pd.Series:
        """模拟 equity curve — 含手续费 + 滑点"""
        n = len(price_df)
        equity = np.full(n, self.initial_capital, dtype=np.float64)
        position = 0  # 0 = 空仓, 1 = 满仓
        entry_price = 0.0
        
        slip = self.slippage_bps / 10000
        fee = self.fees
        
        # 成交价:next open 或 current close
        if self.use_next_open and "open" in price_df.columns:
            prices_open = price_df["open"].values
        else:
            prices_open = price_df["close"].values
        
        closes = price_df["close"].values
        entries = signals["entries"].values
        exits = signals["exits"].values
        
        for i in range(1, n):
            # 判断进场 / 出场 — 用上一根信号(避免 look-ahead)
            if position == 0 and entries[i - 1]:
                # 买入
                entry_price = prices_open[i] * (1 + slip)
                position = 1
                equity[i] = equity[i - 1] * (1 - fee)
            elif position == 1 and exits[i - 1]:
                # 卖出
                exit_price = prices_open[i] * (1 - slip)
                ret = (exit_price / entry_price) - 1
                equity[i] = equity[i - 1] * (1 + ret) * (1 - fee)
                position = 0
            else:
                # 持仓不动
                if position == 1:
                    ret = (closes[i] / closes[i - 1]) - 1
                    equity[i] = equity[i - 1] * (1 + ret)
                else:
                    equity[i] = equity[i - 1]
        
        return pd.Series(equity, index=price_df.index)
    
    def _extract_trades(
        self,
        price_df: pd.DataFrame,
        signals: pd.DataFrame,
        equity_curve: pd.Series,
    ) -> List[Dict[str, Any]]:
        """提取每笔交易 — entry/exit 时间 + 价格 + PnL"""
        entries = signals["entries"].values
        exits = signals["exits"].values
        closes = price_df["close"].values
        opens = price_df["open"].values if "open" in price_df.columns else closes
        
        trades = []
        in_trade = False
        entry_price = 0.0
        entry_idx = 0
        
        for i in range(len(entries)):
            if not in_trade and entries[i]:
                in_trade = True
                entry_price = opens[i] * (1 + self.slippage_bps / 10000)
                entry_idx = i
            elif in_trade and exits[i]:
                exit_price = opens[i] * (1 - self.slippage_bps / 10000)
                ret = (exit_price / entry_price) - 1
                pnl_pct = ret - 2 * self.fees
                trades.append({
                    "entry_idx": entry_idx,
                    "exit_idx": i,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "return": ret,
                    "pnl_pct": pnl_pct,
                    "win": pnl_pct > 0,
                })
                in_trade = False
        
        return trades
    
    def _compute_metrics(
        self,
        equity_curve: pd.Series,
        trades: List[Dict],
        signals: pd.DataFrame,
        params: dict,
    ) -> BacktestResult:
        """计算所有回测指标"""
        # 总收益
        total_return = float((equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1)
        
        # 日收益
        returns = equity_curve.pct_change().dropna()
        if len(returns) < 2:
            sharpe = 0.0
            sortino = 0.0
            max_dd = 0.0
            calmar = 0.0
        else:
            # Sharpe(年化, 252)
            mean_ret = float(returns.mean())
            std_ret = float(returns.std())
            sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0.0

            # Sortino(只算下行波动)
            downside = returns[returns < 0]
            dd_std = float(downside.std()) if len(downside) > 0 else std_ret
            sortino = (mean_ret / dd_std * np.sqrt(252)) if dd_std > 0 else 0.0
            
            # Max Drawdown
            running_max = equity_curve.cummax()
            drawdown = (equity_curve - running_max) / running_max
            max_dd = float(drawdown.min())

            # Calmar
            years = len(returns) / 252
            annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
            calmar = annual_return / abs(max_dd) if max_dd < 0 else 0.0

        # 交易统计
        n_trades = len(trades)
        if n_trades > 0:
            wins = sum(1 for t in trades if t["win"])
            win_rate = wins / n_trades
            pnls = [t["pnl_pct"] for t in trades]
            avg_pnl = float(np.mean(pnls))
            gross_profit = sum(p for p in pnls if p > 0)
            gross_loss = abs(sum(p for p in pnls if p < 0))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
            expectancy = avg_pnl
        else:
            win_rate = 0.0
            profit_factor = 0.0
            expectancy = 0.0
        
        return BacktestResult(
            total_return=total_return,
            sharpe=sharpe,
            sortino=sortino,
            max_drawdown=max_dd,
            calmar=calmar,
            win_rate=win_rate,
            profit_factor=profit_factor,
            expectancy=expectancy,
            n_trades=n_trades,
            equity_curve=equity_curve,
            signals=signals,
            params=params,
        )
    
    def grid_search(
        self,
        strategy_class: Type[Strategy],
        price_df: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
    ) -> List[BacktestResult]:
        """参数网格扫描 — 按 Sharpe 排序返回所有结果
        
        Args:
            strategy_class: 策略类(不是实例)
            price_df: K 线
            param_grid: {"fast_period": [3, 5, 10], "slow_period": [10, 20, 30]}
        
        Returns:
            BacktestResult 列表,按 Sharpe 降序
        """
        from itertools import product
        
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(product(*values))
        
        logger.info(
            "grid_search_started",
            n_combinations=len(combinations),
            strategy=strategy_class.__name__,
        )
        
        results = []
        for combo in combinations:
            params = dict(zip(keys, combo))
            try:
                # 策略 init 用 parameters 字段(对 library 里的策略)
                strategy = strategy_class(parameters=params)
                result = self.run(strategy, price_df)
                results.append(result)
            except Exception as e:
                logger.warning(
                    "grid_search_combo_failed",
                    params=params,
                    error=str(e),
                    error_type=type(e).__name__,
                )
        
        results.sort(key=lambda r: r.sharpe, reverse=True)
        
        logger.info(
            "grid_search_completed",
            n_results=len(results),
            best_sharpe=results[0].sharpe if results else 0,
        )
        return results