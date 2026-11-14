# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, Field  # noqa: E402

if TYPE_CHECKING:
    import pandas as pd

from forgemind.core.data.storage import (
    DuckDBStorage,
    LocalStoreLockedError,
    LocalStoreWriteError,
    bare_symbol,
)  # noqa: E402
from forgemind.core.observability.logging import get_logger  # noqa: E402

logger = get_logger("forgemind.stock_picker")

# 因子权重(所有因子均已归一化到 [0,1],统一"越大越好")
WEIGHTS = {
    "momentum": 0.30,
    "trend": 0.30,
    "volume_price": 0.20,
    "volatility": 0.10,
    "mean_reversion": 0.10,
}


class StockPick(BaseModel):
    """选股结果"""

    symbol: str
    score: float  # 综合评分 0-1
    direction: str  # "buy" / "hold" / "sell"
    confidence: float  # 0-1
    rationale: str  # 自然语言解释
    factors: dict[str, float] = Field(default_factory=dict)  # 各因子得分


#: 查询失败时对用户说的话。
#:
#: 为什么不给更具体的原因:异常文本里有 DuckDB 的报错原文,连着内部表名
#: 与整条 SQL。要说清的是"这是读不到,不是没有数据",以及下一步该做什么。
QUERY_FAILED_REASON = "读不到本地行情"


class StockPickerAgent:
    #: 计算 60 日动量 / 20 日均线至少需要这么多根 K 线
    MIN_BARS = 60
    #: 上一次 pick() 中因数据不足被跳过的标的 -> 实际 K 线根数
    last_insufficient: dict[str, int] = {}
    #: 上一次 pick() 中**读不到**行情的标的 -> 原因。
    #:
    #: "读不到"与"没有数据"是两回事,混为一谈会把用户引到错的路上:
    #: 桌面端开着时它占着同一个库,终端里的查询直接失败 —— 这时候告诉
    #: 用户"库里没有该标的",他会去跑 etl,而 etl 同样读不到那个库。
    last_query_errors: dict[str, str] = {}
    #: 上一次 pick() 中撞上**资源类**故障的标的 -> 原因。
    #:
    #: 资源类(库被另一个进程占着、存储写不进去)与"没有数据"要分开:
    #: 前者命令是失败的,退出码 4;后者是正常的"没有候选"。这个属性
    #: 就是给上层判断这一点的 —— 只看文字会漏判,因为两者的提示长得
    #: 不一样但都能读成"没选出来"。
    last_resource_errors: dict[str, str] = {}

    """
    选股 Agent — 不需要 LLM,纯规则 + 多策略投票

    多策略:
    1. 动量策略(过去 20/60 日收益)
    2. 均值回归(偏离均线)
    3. 趋势跟踪(MA 交叉)
    4. 量价配合(放量上涨)

    综合评分 → Top N
    """

    def __init__(self, db: DuckDBStorage | None = None):
        self.db = db or DuckDBStorage()
        self.lookbacks = [5, 20, 60]  # 多窗口
        #: 本次选股所依据的行情最新日期(由 pick() 填充)。
        #: 结论的时效性必须能被调用方读出来 —— 计算正确不代表依据新鲜。
        self.last_data_date: str | None = None
        #: 读不到行情的标的(实例级:不留在类上,免得跨次调用串味)。
        self.last_query_errors: dict[str, str] = {}
        logger.info("stock_picker_init")

    async def pick(
        self,
        universe: list[str],
        top_n: int = 10,
        as_of: str | None = None,
    ) -> list[StockPick]:
        """
        从 universe 选 top N 个

        Args:
            universe: 候选股票代码列表("600519" 格式,不带交易所后缀)
            top_n: 返回 top N
            as_of: 截至日期(None = 最新)

        Returns:
            StockPick 列表,按 score 降序
        """
        picks = []
        # 记录这批行情的最新日期 —— 用户可能是拿一周前的 etl 结果
        # 在做今天的决策,计算没错,但依据已经过时,必须让他知道。
        self.last_data_date: str | None = None

        raw: list[tuple[str, pd.DataFrame, dict[str, float]]] = []
        # 数据不足的标的必须显式登记,便于上层提示用户
        # 该先跑 `forgemind etl` 拉更长的区间,而不是只看到 "Top 0 picks"。
        insufficient: dict[str, int] = {}
        self.last_insufficient = insufficient
        query_errors: dict[str, str] = {}
        self.last_query_errors = query_errors
        resource_errors: dict[str, str] = {}
        self.last_resource_errors = resource_errors

        for symbol in universe:
            df = self._get_kline(symbol, as_of)
            if df is None:
                # 查询失败与"确实没有数据"分开记 —— 前者要告诉用户
                # "读不到",后者才是"去拉数据"。
                if symbol in self.last_query_errors:
                    continue
                insufficient[symbol] = 0
                continue
            if len(df) < self.MIN_BARS:
                insufficient[symbol] = len(df)
                continue
            raw.append((symbol, df, self._compute_raw_factors(df)))

        if raw:
            newest = max(df["date"].iloc[-1] for _, df, _ in raw)
            self.last_data_date = str(newest)

        # 横截面排名归一化:
        # 因子值在**当期横截面内**取百分位排名,而不是固定 ±5% scale
        # 的线性归一化 —— 后者把超出区间的动量压成 0/1,丧失区分度。
        norm = self._cross_sectional_normalize([r[2] for r in raw])

        for (symbol, _df, raw_factors), nf in zip(raw, norm):
            score = sum(nf[k] * WEIGHTS[k] for k in nf)
            # 原始绝对值必须一路带下去:横截面百分位只是"池内相对位置",
            # 拿它陈述"多头排列""动量强劲"这类**关于个股的事实**是错的。
            # 已验证:全员 -0.5%/日 的池子里,榜首仍拿到 0.85 分 / buy / 0.70 置信,
            # 并被告知"多头排列,趋势向上""动量强劲"——三句全是假的。
            pick = self._build_pick(symbol, score, nf, raw_factors)
            if pick:
                picks.append(pick)

        picks.sort(key=lambda p: p.score, reverse=True)
        top = picks[:top_n]

        logger.info(
            "stock_picker_complete",
            universe_size=len(universe),
            top_n=len(top),
            top_score=top[0].score if top else 0,
        )
        return top

    async def _evaluate_symbol(self, symbol: str, as_of: str | None) -> StockPick | None:
        """评估一个 symbol(兼容入口:单标的时横截面退化为常量 0.5)"""
        df = self._get_kline(symbol, as_of)
        if df is None or len(df) < 60:
            return None
        raw = self._compute_raw_factors(df)
        # 单标的没有横截面可比,统一给中性 0.5
        return self._build_pick(symbol, 0.5, dict.fromkeys(raw, 0.5), raw)

    def _compute_raw_factors(self, df) -> dict[str, float]:
        """计算**未归一化**的原始因子值

        归一化交给 _cross_sectional_normalize 在整个 universe 上做,
        这里只负责把真实数据变成可比较的数值。
        """
        close = df["close"]
        volume = df["volume"]

        # === 因子 1:动量(20/60 日混合)===
        mom_20 = float(close.iloc[-1] / close.iloc[-20] - 1) if len(close) >= 20 else 0.0
        mom_60 = float(close.iloc[-1] / close.iloc[-60] - 1) if len(close) >= 60 else 0.0
        momentum = mom_20 * 0.6 + mom_60 * 0.4

        # === 因子 2:趋势(MA 排列,取连续值而非三档)===
        ma5 = float(close.rolling(5).mean().iloc[-1])
        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma60 = float(close.rolling(60).mean().iloc[-1])
        # 排列强度:多头排列为正、空头为负,连续
        trend = ((ma5 - ma20) / (ma20 + 1e-9)) * 0.5 + ((ma20 - ma60) / (ma60 + 1e-9)) * 0.5

        # === 因子 3:量价配合(带量的涨跌)===
        recent_vol = float(volume.iloc[-5:].mean())
        avg_vol = float(volume.iloc[-60:].mean())
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0
        px_chg = float(close.iloc[-1] / close.iloc[-5:].mean() - 1)
        volume_price = px_chg * min(vol_ratio, 3.0) / 3.0

        # === 因子 4:波动率(越低越好 → 取负号统一为"越大越好")===
        returns = close.pct_change().dropna()
        vol = float(returns.std()) if len(returns) > 1 else 0.0
        volatility = -vol

        # === 因子 5:均值回归(相对 20 日均线的 z 值,越负越加分)===
        sd20 = float(close.rolling(20).std().iloc[-1])
        z = (float(close.iloc[-1]) - float(ma20)) / sd20 if sd20 > 0 else 0.0
        mean_reversion = -z

        return {
            "momentum": momentum,
            "trend": trend,
            "volume_price": volume_price,
            "volatility": volatility,
            "mean_reversion": mean_reversion,
        }

    @staticmethod
    def _cross_sectional_normalize(
        raws: list[dict[str, float]],
    ) -> list[dict[str, float]]:
        """横截面百分位归一化:每个因子在当期 universe 内取排名 → [0,1]

        保证任何分布下都保留区分度,不再出现"±5% 之外全压成 0/1"。
        全部相等时返回 0.5(无法区分)。
        """
        if not raws:
            return []
        keys = list(raws[0])
        out = [dict.fromkeys(keys, 0.5) for _ in raws]
        n = len(raws)
        for k in keys:
            values = [r[k] for r in raws]
            lo, hi = min(values), max(values)
            if hi - lo < 1e-12:
                continue  # 全同 → 保持 0.5
            for i, v in enumerate(values):
                # 严格小于的个数 / (n-1) → 百分位,单调且铺满 [0,1]
                rank = sum(1 for w in values if w < v)
                out[i][k] = rank / (n - 1)
        return out

    def _build_pick(
        self,
        symbol: str,
        _fallback: float,
        factors: dict[str, float],
        raw_factors: dict[str, float] | None = None,
    ) -> "StockPick | None":
        """由归一化因子构造最终推荐

        factors 是**池内百分位**,只回答"在候选池里排第几";
        raw_factors 是**真实值**,回答"这只股票本身处于什么状态"。
        两者必须分开用:

        - 排序 / 选 top_n  → 用百分位
        - 方向、置信、以及 rationale 里的事实陈述 → 必须用真实值

        否则一个正在暴跌的池子,榜首会被贴上 "buy / 0.70 置信 /
        多头排列,趋势向上",而这三句没有一句是真的。
        """
        weights = WEIGHTS
        score = sum(factors[k] * weights[k] for k in factors)
        raw_factors = raw_factors or {}

        raw_mom = float(raw_factors.get("momentum", 0.0))
        raw_trend = float(raw_factors.get("trend", 0.0))

        # 绝对闸门:真实趋势与动量不支持多头时,不允许仅凭池内排名喊 buy。
        # 阈值取保守值:趋势排列强度 ≤ 0(非多头)或动量 ≤ 0(近 20/60 日在跌)
        # 都不足以支撑"买入"。
        abs_support_buy = raw_trend > 0 and raw_mom > 0

        if score >= 0.65 and abs_support_buy:
            direction = "buy"
        elif score <= 0.40:
            direction = "sell"
        else:
            direction = "hold"

        confidence = abs(score - 0.5) * 2
        if direction == "buy" and not abs_support_buy:
            # 池内领先但绝对面不支持 —— 置信必须反映这个折扣
            confidence *= 0.5
        if raw_mom < -0.10 or raw_trend < -0.02:
            # 自身明显走弱:进一步压低
            confidence = min(confidence, 0.35)

        rationale = self._make_rationale(symbol, factors, weights, score, raw_factors)

        return StockPick(
            symbol=symbol,
            score=round(score, 3),
            direction=direction,
            confidence=round(confidence, 3),
            rationale=rationale,
            factors={k: round(v, 4) for k, v in factors.items()},
        )

    def _make_rationale(
        self,
        symbol: str,
        factors: dict[str, float],
        weights: dict[str, float],
        score: float,
        raw_factors: dict[str, float] | None = None,
    ) -> str:
        """自然语言解释

        **关键约束:凡是陈述"这只股票怎么样"的句子,必须由 raw_factors 支撑,
        不能用横截面百分位。**

        百分位只说明"在本次候选池里排第几"。全员下跌的池子里,每只票的
        动量百分位都有高有低,最高的那个照样 >= 0.7 —— 但它的真实动量是负的。
        照旧写法会输出"动量强劲,过去 20/60 日涨幅明显",这是一句事实错误,
        而且带着 0.7 的置信度推给用户。

        相对位置用中性措辞表述("在本次候选池中相对领先"),事实判断只给真实值。
        """
        raw = raw_factors or {}
        raw_mom = float(raw.get("momentum", 0.0))
        raw_trend = float(raw.get("trend", 0.0))
        raw_vp = float(raw.get("volume_price", 0.0))

        sorted_factors = sorted(factors.items(), key=lambda x: x[1], reverse=True)
        top_factor = sorted_factors[0]
        bottom_factor = sorted_factors[-1]

        lines = [f"📊 {symbol} 池内综合评分 {score:.2f} / 1.00"]
        lines.append("  ℹ️  该分数是**本次候选池内的相对排名**,不等于股票本身的质地。")
        lines.append(
            f"  ✅ 池内最强项: {top_factor[0]}={top_factor[1]:.2f} "
            f"(权重{weights[top_factor[0]]:.0%})"
        )
        lines.append(
            f"  ⚠️  池内最弱项: {bottom_factor[0]}={bottom_factor[1]:.2f} "
            f"(权重{weights[bottom_factor[0]]:.0%})"
        )

        if raw:
            lines.append(
                f"  📐 真实值: 动量 {raw_mom:+.1%} / 趋势 {raw_trend:+.3f} / 量价 {raw_vp:+.3f}"
            )
            # ↓ 事实陈述,由真实值决定
            if raw_trend > 0.01:
                lines.append("  📈 均线多头排列(MA5 > MA20 > MA60)")
            elif raw_trend < -0.01:
                lines.append("  📉 均线空头排列(MA5 < MA20 < MA60)")
            else:
                lines.append("  ➖ 均线缠绕,无明确方向")

            if raw_mom > 0.05:
                lines.append(f"  🚀 20/60 日混合动量 {raw_mom:+.1%},确实在涨")
            elif raw_mom < -0.05:
                lines.append(f"  🐌 20/60 日混合动量 {raw_mom:+.1%},实际在跌")
            else:
                lines.append("  ➖ 动量平淡,20/60 日涨跌互现")

            if raw_vp > 0.02:
                lines.append("  💰 近期放量上涨")
            elif raw_vp < -0.02:
                lines.append("  ⚠️  近期放量下跌,资金流出")
            else:
                lines.append("  ➖ 量价配合平淡")

        return "\n".join(lines)

    def _get_kline(self, symbol: str, as_of: str | None) -> Optional["pd.DataFrame"]:
        """从 DuckDB 拉 K 线,按时间正序返回最新 100 根。

        实现:`ORDER BY date DESC LIMIT 100` 取最新段,再翻回正序;
        因子按 `iloc[-1]` 视为最新一根。若直接 `ORDER BY date ASC LIMIT`
        会取到最早 100 根,而 `DESC` 后不翻序会让所有因子错位约 100 根 K 线。
        """
        try:
            with self.db as db:
                # 先问表在不在:第一次跑的人库里还没有这张表,那是正常情况,
                # 不是故障 —— 用异常问问题会留下一条带内部表名与 SQL 的告警。
                if not db.table_exists("kline_daily"):
                    return None
                if as_of:
                    df = db.query_df(
                        "SELECT * FROM kline_daily WHERE symbol = ? AND date <= ? "
                        "ORDER BY date DESC LIMIT 100",
                        [bare_symbol(symbol), as_of],
                    )
                else:
                    df = db.query_df(
                        "SELECT * FROM kline_daily WHERE symbol = ? ORDER BY date DESC LIMIT 100",
                        [bare_symbol(symbol)],
                    )
                if df.empty:
                    return None
                # 翻回时间正序:iloc[-1] 必须是最新一根
                df = df.sort_values("date", ascending=True).reset_index(drop=True)
                return df
        except LocalStoreLockedError as exc:
            # 库被别的进程占着(桌面端开着时它就占着)。这句话是给用户看的,
            # 直接说"本地库正被另一个进程占用" —— 说成"库里没有该标的"
            # 会让他去拉数据,而拉数据同样连不上那个库。
            logger.warning("kline_query_failed", symbol=symbol, reason="store_locked")
            self.last_query_errors[symbol] = str(exc)
            self.last_resource_errors[symbol] = str(exc)
            return None
        except LocalStoreWriteError as exc:
            # 存储写不进去(磁盘满、配额满、权限不足)。同样是资源类:
            # 命令是失败的,不是"这个标的数据不足"。
            logger.warning("kline_query_failed", symbol=symbol, reason="store_write_failed")
            self.last_query_errors[symbol] = str(exc)
            self.last_resource_errors[symbol] = str(exc)
            return None
        except Exception as e:
            # 告警里只放异常类型:原始文本里有 DuckDB 的报错原文,连着内部
            # 表名与整条 SQL。选股失败要说清是"取不到数据",不是把内部
            # 实现摊给用户。完整文本留在 debug 里。
            logger.warning("kline_query_failed", symbol=symbol, error_type=type(e).__name__)
            logger.debug("kline_query_failed_detail", symbol=symbol, error=str(e))
            # 记下来:这次是"读不到",不是"没有数据"。上层要把两者分开说。
            self.last_query_errors[symbol] = QUERY_FAILED_REASON
            return None
