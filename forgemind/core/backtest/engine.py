# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from forgemind.core.observability.logging import get_logger
from forgemind.core.strategies.base import Strategy

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


def _as_bool_signals(series) -> np.ndarray:
    """把一列信号变成严格的布尔数组。

    缺失(NaN/None)按"没有信号"处理 —— 缺一个信号不等于要买入。
    """
    import pandas as pd

    if not isinstance(series, pd.Series):
        series = pd.Series(series)
    if series.dtype == bool:
        return series.to_numpy()
    try:
        # 可空布尔:缺失变成 NA,再填 False —— NaN 不会被当成真
        return series.astype("boolean").fillna(False).to_numpy(dtype=bool)
    except (TypeError, ValueError):
        # 0/1 这类数值列:非零即真
        return (series.fillna(0) != 0).to_numpy(dtype=bool)


def sortino_ratio(returns, periods: int = 252) -> float:
    """Sortino:分母是**下行偏差**而非负收益子集的标准差

    dd = sqrt( mean( min(r, 0)^2 ) )  对全部周期求均方根。

    BacktestReport.compute_metrics 与本函数统一调用此实现,避免与 empyrical
    计算口径分化。
    """
    r = np.asarray(getattr(returns, "to_numpy", lambda: returns)(), dtype=float)
    if r.size < 2:
        return 0.0
    downside = np.minimum(r, 0.0)
    dd = float(np.sqrt(np.mean(np.square(downside))))
    if dd <= 0:
        return 0.0
    return float(r.mean() / dd * np.sqrt(periods))


def sharpe_ratio(returns, periods: int = 252) -> float:
    """年化 Sharpe(与 empyrical 对齐,便于交叉验证)"""
    r = np.asarray(getattr(returns, "to_numpy", lambda: returns)(), dtype=float)
    if r.size < 2:
        return 0.0
    # ddof=1(样本标准差),与 pandas Series.std() 及 empyrical 口径一致。
    # 统一用 pandas Series.std() 的 ddof=1, 与 advanced 报数一致。
    sd = float(r.std(ddof=1))
    if sd <= 0:
        return 0.0
    return float(r.mean() / sd * np.sqrt(periods))


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
        slippage_model: str = "fixed",
        adv_shares: float = 0.0,
    ):
        """滑点模型:`"fixed" | "linear" | "sqrt"`

        `linear` 与 `sqrt` 需要 `adv_shares` 估冲击;未提供时
        自动退化为 `fixed`,并通过 `slippage_degraded_to_fixed` 属性留痕。
        """
        self.initial_capital = initial_capital
        self.fees = fees
        self.slippage_bps = slippage_bps
        self.use_next_open = use_next_open
        if slippage_model not in ("fixed", "linear", "sqrt"):
            raise ValueError(f"未知的滑点模型 {slippage_model!r};可用:fixed / linear / sqrt")
        self.slippage_model = slippage_model
        self.adv_shares = float(adv_shares or 0.0)
        self._equity_now = initial_capital
        self.slippage_degraded_to_fixed = slippage_model != "fixed" and self.adv_shares <= 0

    def _order_size(self, raw_price: float) -> int:
        """本次下单的股数 = 名义金额 / 价格

        冲击模型(linear / sqrt)的整个意义就是按**下单规模**估冲击,
        而满仓回测的名义金额就是当前权益。size 来自 cash / price,
        冲击项小到可以忽略,两个模型算出来几乎一样 —— 等于模型接了、
        但不起作用。
        """
        if raw_price <= 0:
            return 0
        notional = float(getattr(self, "_equity_now", self.initial_capital))
        return max(1, int(notional / raw_price))

    def _slip_price(self, raw_price: float, size: int, is_buy: bool) -> float:
        """按所选模型算成交价"""
        from .advanced import SlippageModel

        model = self.slippage_model
        if model != "fixed" and self.adv_shares > 0:
            fn = (
                SlippageModel.linear_slippage
                if model == "linear"
                else SlippageModel.square_root_slippage
            )
            try:
                filled = fn(raw_price, size, int(self.adv_shares), self.slippage_bps)
                return float(filled)
            except Exception:  # noqa: BLE001 — 冲击模型失败时退回固定滑点
                pass
        # 固定 bps:买入加、卖出减
        adj = self.slippage_bps / 10000
        return raw_price * (1 + adj if is_buy else 1 - adj)

    def run(
        self,
        strategy: Strategy,
        price_df: pd.DataFrame,
        symbol: str | None = None,
    ) -> BacktestResult:
        """
        跑单次回测

        Args:
            strategy: 策略实例(有 generate_signals 方法)
            price_df: K 线(OHLCV)
            symbol: 可选日志 tag
        """
        # 事件类策略在缺少基本面列时若静默返回全 0,回测只显示"0 笔交易",
        # 用户分不清是"没有此类事件"还是"你没提供所需数据"。策略通过
        # required_columns 声明依赖,这里提前拦下,给出缺哪列、现在有什么列。
        _required = tuple(getattr(strategy, "required_columns", ()) or ())
        _missing = [c for c in _required if c not in price_df.columns]
        if _missing:
            raise ValueError(
                f"策略 {strategy.name} 需要以下列,而输入数据里没有: "
                f"{', '.join(_missing)}。当前可用列: {', '.join(map(str, price_df.columns))}。"
                "这类策略依赖额外数据源,补齐后再回测 —— 不要把全 0 信号当成结论。"
            )

        logger.info(
            "backtest_started",
            strategy=strategy.name,
            params=strategy.parameters,
            symbol=symbol or "ALL",
            n_bars=len(price_df),
        )

        signals = strategy.generate_signals(price_df)
        if "entries" not in signals.columns or "exits" not in signals.columns:
            raise ValueError(
                f"Strategy {strategy.name}.generate_signals must return DataFrame with "
                "'entries' and 'exits' boolean columns"
            )
        # 信号在这里统一处理成严格布尔,后面模拟成交与提取交易都用这一份。
        # 早先两处各自读原始列,于是模拟按 NaN 当真、提取交易按另一套口径,
        # 两边对不上 —— 指标算成垃圾,交易数也是错的。
        signals = signals.copy()
        signals["entries"] = _as_bool_signals(signals["entries"])
        signals["exits"] = _as_bool_signals(signals["exits"])

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

        fee = self.fees

        # 成交价:next open 或 current close
        if self.use_next_open and "open" in price_df.columns:
            prices_open = price_df["open"].values
        else:
            prices_open = price_df["close"].values

        closes = price_df["close"].values
        # 信号在 run() 里已经统一处理成严格布尔,这里直接取用。
        entries = signals["entries"].values
        exits = signals["exits"].values

        self._equity_now = self.initial_capital
        for i in range(1, n):
            # 判断进场 / 出场 — 用上一根信号(避免 look-ahead)
            if position == 0 and entries[i - 1]:
                # 买入:成交于 open[i],当日就经历了 open[i] → close[i] 的波动。
                #
                # 进出两端对称: 买入用 close[i] (含当日涨幅), 卖出用 close[j] (含当日涨幅)。
                # 100 买、130 卖(同日)时引擎报 0% 收益,正确是 +30%。
                entry_price = self._slip_price(
                    prices_open[i], self._order_size(prices_open[i]), True
                )
                position = 1
                day_ret = (closes[i] / entry_price) - 1 if entry_price else 0.0
                equity[i] = equity[i - 1] * (1 - fee) * (1 + day_ret)
            elif position == 1 and exits[i - 1]:
                # 卖出:只补上"昨日收盘 → 今日卖出价"这一段
                exit_price = self._slip_price(
                    prices_open[i], self._order_size(prices_open[i]), False
                )
                #
                # 持仓期间的 [entry, i-1] 已经逐日按 close 复利,此处仅补
                # `close[i-1] → exit_price` 增量,避免整段涨幅被重复计入。
                # 例 100 买 → 105 持有一日 → 110 卖,正确 1.10,而非 1.155。
                prev_close = closes[i - 1]
                step_ret = (exit_price / prev_close) - 1 if prev_close else 0.0
                equity[i] = equity[i - 1] * (1 + step_ret) * (1 - fee)
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
    ) -> list[dict[str, Any]]:
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
                entry_price = self._slip_price(opens[i], self._order_size(opens[i]), True)
                entry_idx = i
            elif in_trade and exits[i]:
                exit_price = self._slip_price(opens[i], self._order_size(opens[i]), False)
                ret = (exit_price / entry_price) - 1
                pnl_pct = ret - 2 * self.fees
                trades.append(
                    {
                        "entry_idx": entry_idx,
                        "exit_idx": i,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "return": ret,
                        "pnl_pct": pnl_pct,
                        "win": pnl_pct > 0,
                    }
                )
                in_trade = False

        # 强制平掉回测结束时仍持有的仓位
        #
        # signals 只给 entry 不给 exit 时, 期末按 close 强制平仓,
        # 把未实现盈亏计入 trade 列表。
        if in_trade:
            last = len(closes) - 1
            exit_price = closes[last]
            ret = (exit_price / entry_price) - 1 if entry_price else 0.0
            pnl_pct = ret - 2 * self.fees
            trades.append(
                {
                    "entry_idx": entry_idx,
                    "exit_idx": last,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "return": ret,
                    "pnl_pct": pnl_pct,
                    "win": pnl_pct > 0,
                    "forced_close": True,  # 标记为期末强平,便于区分
                }
            )

        return trades

    def _compute_metrics(
        self,
        equity_curve: pd.Series,
        trades: list[dict],
        signals: pd.DataFrame,
        params: dict,
    ) -> BacktestResult:
        """计算所有回测指标"""
        # 权益曲线为空:策略在这段数据里没有产生任何可成交的点。
        # 这不是错误,而是一个合法结论(比如均线在这段行情里没有交叉)。
        # 早先这里直接取 iloc[-1],空曲线会抛 IndexError —— 用户看到的是
        # 一整段 Python 栈回溯,而不是"这段时间没有产生交易"。
        if equity_curve is None or len(equity_curve) == 0:
            return BacktestResult(
                total_return=0.0,
                sharpe=0.0,
                sortino=0.0,
                max_drawdown=0.0,
                calmar=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                expectancy=0.0,
                n_trades=len(trades or []),
                equity_curve=(equity_curve if equity_curve is not None else pd.Series(dtype=float)),
                signals=signals,
                params=dict(params or {}),
                extra={"no_tradable_signal": True},
            )

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

            # Sortino:分母是**下行偏差**(downside deviation),
            #   dd = sqrt( mean( min(r - target, 0)^2 ) )  对**全部**周期求均方根
            # Sortino 分母用全部周期收益的均方根, 跟 empyrical 一致。
            #   (对拍 empyrical.sortino_ratio 发现:1.0599 vs 1.2471)
            downside = np.minimum(returns.to_numpy(), 0.0)
            dd = float(np.sqrt(np.mean(np.square(downside))))
            sortino = (mean_ret / dd * np.sqrt(252)) if dd > 0 else 0.0

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
        strategy_class: type[Strategy],
        price_df: pd.DataFrame,
        param_grid: dict[str, list[Any]],
    ) -> list[BacktestResult]:
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
