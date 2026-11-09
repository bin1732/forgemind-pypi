# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import numpy as np
import pandas as pd

from forgemind.core.events.types import SignalEvent
from forgemind.core.strategies.base import MovingAverageCrossStrategy, Strategy


class MeanReversionStrategy(Strategy):
    """均值回归 — 价格偏离 N 日均线超过阈值时反向"""

    def validate_parameters(self) -> None:
        if "lookback" not in self.parameters:
            self.parameters["lookback"] = 20
        if "threshold" not in self.parameters:
            self.parameters["threshold"] = 2.0  # 2 个标准差

    def generate_signals(self, price_df: pd.DataFrame) -> pd.DataFrame:
        lookback = self.parameters["lookback"]
        threshold = self.parameters["threshold"]

        ma = price_df["close"].rolling(lookback).mean()
        std = price_df["close"].rolling(lookback).std()
        z_score = (price_df["close"] - ma) / std

        # Z-score > threshold → 价格过高 → sell
        # Z-score < -threshold → 价格过低 → buy
        entries = z_score < -threshold
        exits = z_score > threshold

        return pd.DataFrame(
            {
                "entries": entries.fillna(False).astype(bool),
                "exits": exits.fillna(False).astype(bool),
            }
        )

    def on_bar(self, bar_dict: dict) -> SignalEvent | None:
        if not hasattr(self, "_prices"):
            self._prices = []
        self._prices.append(bar_dict["close"])

        lookback = self.parameters["lookback"]
        threshold = self.parameters["threshold"]

        if len(self._prices) < lookback:
            return None

        prices = np.array(self._prices[-lookback:])
        ma = prices.mean()
        std = prices.std()
        z_score = (bar_dict["close"] - ma) / std if std > 0 else 0

        if z_score < -threshold:
            return SignalEvent(
                symbol=bar_dict.get("symbol"),
                direction="buy",
                strength=min(1.0, abs(z_score) / 4.0),
                confidence=0.7,
                rationale=f"均值回归 Z={z_score:.2f} < -{threshold}",
            )
        elif z_score > threshold:
            return SignalEvent(
                symbol=bar_dict.get("symbol"),
                direction="sell",
                strength=min(1.0, abs(z_score) / 4.0),
                confidence=0.7,
                rationale=f"均值回归 Z={z_score:.2f} > {threshold}",
            )
        return None


class MomentumStrategy(Strategy):
    """动量 — 过去 N 日收益率为正则买入"""

    def validate_parameters(self) -> None:
        if "lookback" not in self.parameters:
            self.parameters["lookback"] = 60
        if "top_quantile" not in self.parameters:
            self.parameters["top_quantile"] = 0.7  # 涨幅超过 70% 才入场

    def generate_signals(self, price_df: pd.DataFrame) -> pd.DataFrame:
        lookback = self.parameters["lookback"]

        # N 日收益率
        returns = price_df["close"].pct_change(lookback)
        # 用 1 年滚动分位数确定阈值
        rolling_threshold = returns.rolling(252, min_periods=60).quantile(
            self.parameters["top_quantile"]
        )

        entries = returns > rolling_threshold
        exits = returns < 0  # 收益为正 → 出场

        return pd.DataFrame(
            {
                "entries": entries.fillna(False).astype(bool),
                "exits": exits.fillna(False).astype(bool),
            }
        )

    def on_bar(self, bar_dict: dict) -> SignalEvent | None:
        if not hasattr(self, "_prices"):
            self._prices = []
        self._prices.append(bar_dict["close"])

        lookback = self.parameters["lookback"]
        if len(self._prices) < lookback + 252:
            return None

        recent_return = (bar_dict["close"] - self._prices[-lookback]) / self._prices[-lookback]
        # 简化:固定阈值 5%
        if recent_return > 0.05:
            return SignalEvent(
                symbol=bar_dict.get("symbol"),
                direction="buy",
                strength=min(1.0, recent_return * 10),
                confidence=0.6,
                rationale=f"动量收益={recent_return:.2%}",
            )
        return None


class BollingerBandsStrategy(Strategy):
    """布林带策略 — 价格触及上下轨时反向"""

    def validate_parameters(self) -> None:
        if "period" not in self.parameters:
            self.parameters["period"] = 20
        if "std_multiplier" not in self.parameters:
            self.parameters["std_multiplier"] = 2.0

    def generate_signals(self, price_df: pd.DataFrame) -> pd.DataFrame:
        period = self.parameters["period"]
        std_mult = self.parameters["std_multiplier"]

        ma = price_df["close"].rolling(period).mean()
        std = price_df["close"].rolling(period).std()
        lower = ma - std_mult * std

        # 触及下轨 → 买入(预期反弹)
        entries = price_df["close"] <= lower
        # 触及中轨或上轨 → 卖出
        exits = price_df["close"] >= ma

        return pd.DataFrame(
            {
                "entries": entries.fillna(False).astype(bool),
                "exits": exits.fillna(False).astype(bool),
            }
        )

    def on_bar(self, bar_dict: dict) -> SignalEvent | None:
        if not hasattr(self, "_prices"):
            self._prices = []
        self._prices.append(bar_dict["close"])

        period = self.parameters["period"]
        std_mult = self.parameters["std_multiplier"]

        if len(self._prices) < period:
            return None

        prices = np.array(self._prices[-period:])
        ma = prices.mean()
        std = prices.std()
        lower = ma - std_mult * std
        upper = ma + std_mult * std

        if bar_dict["close"] <= lower:
            return SignalEvent(
                symbol=bar_dict.get("symbol"),
                direction="buy",
                strength=0.8,
                confidence=0.7,
                rationale=f"触及布林下轨 {lower:.2f}",
            )
        elif bar_dict["close"] >= upper:
            return SignalEvent(
                symbol=bar_dict.get("symbol"),
                direction="sell",
                strength=0.8,
                confidence=0.7,
                rationale=f"触及布林上轨 {upper:.2f}",
            )
        return None


class BuyAndHoldStrategy(Strategy):
    """买入持有 — 基准策略,用于对比"""

    def validate_parameters(self) -> None:
        pass

    def generate_signals(self, price_df: pd.DataFrame) -> pd.DataFrame:
        entries = pd.Series(False, index=price_df.index)
        exits = pd.Series(False, index=price_df.index)
        # 第一天买入,最后一天卖出
        if len(price_df) > 0:
            entries.iloc[0] = True
            exits.iloc[-1] = True
        return pd.DataFrame({"entries": entries, "exits": exits})

    def on_bar(self, bar_dict: dict) -> SignalEvent | None:
        if not hasattr(self, "_bought"):
            self._bought = False

        if not self._bought:
            self._bought = True
            return SignalEvent(
                symbol=bar_dict.get("symbol"),
                direction="buy",
                strength=1.0,
                confidence=1.0,
                rationale="买入持有",
            )
        return None


# 策略注册表
# 键 = CLI `--strategy` 可用的名字
# 前 5 个是 on_bar 逐根策略(Strategy 子类),后 12 个是批量策略
# (extended_library),经 adapter.SignalSeriesAdapter 包装后同样可回测。
STRATEGY_REGISTRY = {
    "ma_cross": MovingAverageCrossStrategy,
    "mean_reversion": MeanReversionStrategy,
    "momentum": MomentumStrategy,
    "bollinger": BollingerBandsStrategy,
    "buy_hold": BuyAndHoldStrategy,
}

# 这些策略的构造参数就缺东西 —— 不是行情数据的问题,是调用方要自己准备。
# 每条写两件事:缺什么(理由)、怎么自己用(用法)。命令的拒绝消息、策略清单
# 的说明、能不能跑的判定,三处都从这里取 —— 分开写三遍,必然会有一处先漂掉。
_EXTENDED_STRATEGY_PARAMS = {
    "LightGBMStrategy": {
        "reason": "需要先训练好的模型",
        "usage": "LightGBMStrategy(model=<已训练模型>)",
    },
    "OnlineLearningStrategy": {
        "reason": "需要模型工厂",
        "usage": "OnlineLearningStrategy(model_factory=<callable>)",
    },
    "PairsTrading": {
        "reason": "需要两个标的",
        "usage": "PairsTrading().generate_signal(df_a, df_b)",
    },
}


__all__ = [
    "MovingAverageCrossStrategy",
    "MeanReversionStrategy",
    "MomentumStrategy",
    "BollingerBandsStrategy",
    "BuyAndHoldStrategy",
    "STRATEGY_REGISTRY",
    "get_strategy_class",
    "get_extended_strategy",
    "available_strategies",
    "cli_runnable_strategies",
    "strategy_unusable_reason",
    "strategy_usage_hint",
]


def get_strategy_class(name: str) -> type:
    """按名取策略类(仅 5 个 on_bar 策略)"""
    if name not in STRATEGY_REGISTRY:
        raise ValueError(
            f"Unknown strategy: {name}. "
            f"Available: {sorted(STRATEGY_REGISTRY)}. "
            "(批量策略请用 build_extended_strategy)"
        )
    return STRATEGY_REGISTRY[name]


def get_extended_strategy(name: str, **params):
    """按名取扩展策略(12 个批量策略),自动套 adapter 适配回测引擎"""
    from forgemind.core.strategies.adapter import build_extended_strategy

    return build_extended_strategy(name, **params)


# 策略类别的说法。这是给用户看的:命令行的策略清单、报错信息都用它。
# 原来的 "on_bar 策略" / "批量策略" 是内部叫法,读的人看不出这些策略
# 到底在做什么,更看不出哪些当前跑不了。
CATEGORY_LABELS = {
    "on_bar": "单标的策略:在一支标的的 K 线上产生买卖信号",
    "momentum": "动量类:按过去一段时间的涨跌幅排序或择时",
    "stat_arb": "统计套利类:用价差关系找机会",
    "portfolio": "组合类:在多支标的上分配权重(当前命令只喂一支标的,跑不了)",
    "event": "事件类:需要基本面或事件数据",
    "ml": "机器学习类:需要训练好的模型",
    "mean_reversion": "均值回复类:价格偏离均值后回归",
}

# 需要多支标的的类别:命令一次只喂一支,这些策略在那种输入下算出来的
# 权重没有意义 —— 实测有两个组合策略在单标的上给出逐位相同的结果,
# 看着像结论,其实是退化了。
MULTI_SYMBOL_CATEGORIES = ("portfolio",)


def strategy_category(name: str) -> str:
    """策略的类别。查不到就返回空串。"""
    from forgemind.core.strategies.extended_library import list_strategies

    if name in STRATEGY_REGISTRY:
        return "on_bar"
    cls = list_strategies().get(name)
    return getattr(cls, "category", "") if cls is not None else ""


def strategy_unusable_reason(name: str) -> str | None:
    """这个策略在这个命令里跑不了的原因;跑得了的返回 None。

    这是唯一的判据来源。命令的拒绝消息、策略清单里的说明、能不能跑的
    判定,三处都从这里取 —— 分开写三遍,必然会有一处先漂掉,而漂掉的那处
    会直接变成一句骗人的话(把"存在但跑不了"说成"未知策略")。

    跑不了有四种,每一种都要说清是哪一种:

    - 名字根本不存在:不是"跑不了",是没这个策略 —— 这里返回 None,
      由调用方按"未知策略"处理。
    - 需要多支标的:横截面与组合类策略要在多支标的之间比较,命令一次只喂
      一支,算出来的权重没有意义。
    - 构造参数就缺东西:模型、模型工厂、第二个标的 —— 不是行情数据的问题。
    - 需要行情表里没有的数据列:事件类策略要基本面字段,日线表里没有。
    """
    if name in STRATEGY_REGISTRY:
        return None

    from forgemind.core.strategies.extended_library import list_strategies

    cls = list_strategies().get(name)
    if cls is None:
        return None

    if needs_multiple_symbols(name):
        return "多标的策略需要多支标的的行情,当前命令一次只喂一支标的"

    extra = _EXTENDED_STRATEGY_PARAMS.get(name)
    if extra:
        return extra["reason"]

    required = getattr(cls, "required_columns", ())
    if required:
        return "需要行情表里没有的数据列:" + ", ".join(required)

    return None


def strategy_usage_hint(name: str) -> str:
    """这个策略怎么自己用。命令跑不了时,得给用户一条走得通的路。"""
    extra = _EXTENDED_STRATEGY_PARAMS.get(name)
    if extra:
        return extra["usage"]
    return ""


def cli_runnable_strategies() -> dict[str, str]:
    """这个命令行真正跑得起来的策略 → 说明。

    判据是"这条命令能不能把它喂出结果",不是"它在不在基础注册表里":
    扩展策略里有单标的的那些,经适配器一样能跑(实测 TimeSeriesMomentum、
    MomentumRotation、OrnsteinUhlenbeck、RSIReversion 都能跑出结果),
    把它们划进"跑不了"同样是虚报。

    判据本身在 strategy_unusable_reason 里 —— 那里是唯一解释"为什么跑不了"
    的地方。
    """
    from forgemind.core.strategies.extended_library import list_strategies

    out: dict[str, str] = {}
    for name in STRATEGY_REGISTRY:
        out[name] = CATEGORY_LABELS["on_bar"]
    for name, cls in list_strategies().items():
        if name in out:
            continue
        if strategy_unusable_reason(name) is not None:
            continue
        out[name] = CATEGORY_LABELS.get(getattr(cls, "category", ""), "策略")
    return out


def needs_multiple_symbols(name: str) -> bool:
    """这个策略是不是必须有多支标的。

    先看策略自己打的标记,再看类别 —— 横截面动量归在"动量类",但它同样
    要跨标的比较。靠类别猜会漏掉这一类,而这类策略在单标的上算出来的
    结果看着像结论,其实是退化了(实测有两个策略在单标的上给出逐位相同
    的结果)。
    """
    from forgemind.core.strategies.extended_library import list_strategies

    cls = list_strategies().get(name)
    if cls is not None and getattr(cls, "requires_multiple_symbols", False):
        return True
    return strategy_category(name) in MULTI_SYMBOL_CATEGORIES


def resolve_backtest_strategy(
    name: str, fast: int = 5, slow: int = 20, params: dict | None = None
) -> tuple[Any | None, dict | None]:
    """把策略名解析成能喂给回测引擎的对象;跑不了就说清为什么。

    解析只有一份,在命令行与 MCP 共用 —— 分开写两遍,必然有一处先漂掉。
    实测漂掉的那处:命令能跑 9 个策略,MCP 只认 5 个,而且把存在但跑不了
    的说成"未知策略"。模型照着资源里的清单挑一个,工具回一句它没听过
    —— 两处说法自相矛盾。

    返回 (策略对象, None) 或 (None, 拒绝理由)。拒绝理由是一份可以直接
    给人看的说明:

        {"kind": "unknown"|"unusable", "error": ..., "usage": ...}

    kind 区分"根本没这个策略"与"有,但这个命令喂不了它" —— 这两件事
    对读者的下一步完全不同。
    """
    from forgemind.core.strategies.extended_library import list_strategies

    runnable = cli_runnable_strategies()

    if name in STRATEGY_REGISTRY:
        # params 是调用方给的策略参数;不给就用这条命令的默认快慢线。
        return (
            STRATEGY_REGISTRY[name](
                parameters=(
                    params if params is not None else {"fast_period": fast, "slow_period": slow}
                )
            ),
            None,
        )

    extended = list_strategies()
    if name not in extended:
        return None, {
            "kind": "unknown",
            "error": f"未知策略 {name}",
            "runnable": sorted(runnable),
            "usage": "完整的策略清单:读 forgemind://strategies",
        }

    # 有这个策略,但这个命令喂不了它 —— 说清缺什么、怎么自己用。
    # "存在但跑不了"说成"未知策略"是骗人:同一个接口的清单里列着它。
    reason = strategy_unusable_reason(name)
    if reason:
        return None, {
            "kind": "unusable",
            "error": f"{name} 这个命令跑不了:{reason}",
            "usage": strategy_usage_hint(name),
            "runnable": sorted(runnable),
        }

    # 扩展策略:经 adapter 适配成引擎接口
    from forgemind.core.strategies.library import get_extended_strategy

    extra = _EXTENDED_STRATEGY_PARAMS.get(name)
    if extra:
        return None, {
            "kind": "unusable",
            "error": f"{name} 需要额外参数,这个命令喂不了它:{extra}",
            "usage": strategy_usage_hint(name),
            "runnable": sorted(runnable),
        }
    return get_extended_strategy(name), None


def available_strategies() -> dict:
    """全部可用策略名 → 说明(CLI --help / 报错都用它)

    跑不了的那些,说明写的就是跑不了的原因 —— 与命令拒绝时说的话是同一
    句(都取自 strategy_unusable_reason)。
    """
    from forgemind.core.strategies.extended_library import list_strategies

    out = {}
    for k in STRATEGY_REGISTRY:
        out[k] = CATEGORY_LABELS["on_bar"]
    for k in list_strategies():
        reason = strategy_unusable_reason(k)
        if reason:
            out[k] = reason
        else:
            out[k] = CATEGORY_LABELS.get(strategy_category(k), "策略")
    return out
