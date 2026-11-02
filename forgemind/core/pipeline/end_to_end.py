# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import polars as pl

from forgemind import __version__
from forgemind.core.observability.logging import get_logger

logger = get_logger("forgemind.pipeline")


def _display_width(text: str) -> int:
    """按终端列宽计算字符串宽度。

    中日韩文字与多数表情占两列,变体选择符不占列。手数出来的空格对不上
    是因为宽度按字符数算的,中文和表情都是两列。
    """
    width = 0
    for char in text:
        if char == "\ufe0f":
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


def _render_box(rows: list[str | None]) -> str:
    """把若干行内容渲染成对齐的方框。

    框宽按内容算,每行单独补齐,于是不管字段多长、几个字,右边框都在同
    一列。行内容为 None 表示画一条分隔线。
    """
    width = max(_display_width(row) for row in rows if row is not None)
    border = "═" * (width + 2)
    lines = ["╔" + border + "╗"]
    for row in rows:
        if row is None:
            lines.append("╠" + border + "╣")
            continue
        lines.append("║ " + row + " " * (width - _display_width(row)) + " ║")
    lines.append("╚" + border + "╝")
    return "\n".join(lines)


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
    ic_top_factors: list[dict]  # Top N 因子的 IC 信息
    best_ic_mean: float
    best_icir: float

    # 模型
    model_name: str
    cv_rank_ic_mean: float
    cv_rank_ic_std: float
    cv_sharpe: float
    top_features: dict[str, float]

    # 回测
    total_return: float
    sharpe: float
    sortino: float
    max_drawdown: float
    win_rate: float
    n_trades: int

    # 信号(必填,无默认值)
    signals: list[dict]

    # 元数据(必填)
    start_date: str
    end_date: str
    duration_seconds: float

    # Walk-Forward(防 look-ahead)— 可选,默认 0
    #: 实际训练用的后端。模型名写 LightGBM 不代表真跑的是 LightGBM ——
    #: 缺包时会静默降级到 sklearn,不记录的话用户无从分辨
    model_backend: str = "unknown"
    wfo_oos_sharpe: float = 0.0
    wfo_oos_return: float = 0.0
    wfo_oos_max_dd: float = 0.0
    wfo_n_folds: int = 0
    wfo_folds_detail: list[dict] = field(default_factory=list)

    # Monte Carlo(稳健性)— 可选,默认 0
    mc_sharpe_5pct: float = 0.0
    mc_sharpe_95pct: float = 0.0
    mc_return_5pct: float = 0.0
    mc_return_95pct: float = 0.0
    #: 数据来源。mock = 确定性 GBM 模拟行情,不代表任何真实标的
    data_source: str = "unknown"
    data_warning: str = ""
    #: 模型在训练集上学不到任何信号(cv≈0)。与"训练失败"必须区分开:
    #: 随机游走型的模拟行情本来就没有可预测性,这是正确结果而非故障
    model_found_signal: bool | None = None

    #: 5% 与 95% 分位相同 = 模拟分布退化,**不能**据此判断稳健性
    mc_degenerate: bool = False
    mc_note: str = ""
    #: WFO / MC 跑挂时的原因(原先静默吞掉,看起来像"绩效为零")
    risk_warning: str = ""
    mc_n_successful: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        """把结果渲染成一张对齐的表格。"""
        rows: list[str | None] = []

        rows.append(f"ForgeMind 端到端流水线结果 v{__version__}")
        rows.append(None)
        rows.append("📊 数据")
        rows.append(f"  股票数: {self.n_symbols}")
        rows.append(f"  天数:   {self.n_days}")
        rows.append(f"  K线数:  {self.n_bars}")
        rows.append(f"  区间:   {self.start_date} → {self.end_date}")
        rows.append(None)
        rows.append("🧮 因子库")
        rows.append(f"  计算因子数: {self.n_factors_computed}")
        rows.append(None)
        rows.append("📈 IC 评估(Top 5)")
        rows.append(f"  最佳 IC 均值: {self.best_ic_mean:.4f}")
        rows.append(f"  最佳 ICIR:    {self.best_icir:.4f}")
        rows.append("  Top 因子:")
        for i, f in enumerate(self.ic_top_factors[:5]):
            rows.append(
                f"  {i + 1}. {f['factor']:25s}  IC={f['ic_mean']:.4f}  "
                f"RankIC={f['rank_ic_mean']:.4f}"
            )
        rows.append(None)
        rows.append(f"🤖 模型({self.model_name} / 后端 {self.model_backend})")
        rows.append(f"  CV Rank IC: {self.cv_rank_ic_mean:.4f} ± {self.cv_rank_ic_std:.4f}")
        rows.append(f"  CV Sharpe:  {self.cv_sharpe:.2f}")

        # 只在实际成立时才印这两行 —— 无条件打印"未学到信号"本身也是一句假话
        caveats = []
        if self.data_source == "mock":
            caveats.append("数据来源: mock(模拟行情,非真实市场)")
        if self.model_found_signal is False:
            caveats.append("模型未学到可预测信号(随机行情下属正常,非故障)")
        for caveat in caveats:
            rows.append(f"  ⚠️  {caveat}")

        rows.append("  Top 5 特征:")
        for i, (name, value) in enumerate(list(self.top_features.items())[:5]):
            rows.append(f"  {i + 1}. {name:25s}  importance={value:.4f}")
        rows.append(None)
        rows.append("📊 回测")
        rows.append(f"  总收益:    {self.total_return:.2%}")
        rows.append(f"  Sharpe:    {self.sharpe:.2f}")
        rows.append(f"  Sortino:   {self.sortino:.2f}")
        rows.append(f"  Max DD:    {self.max_drawdown:.2%}")
        rows.append(f"  胜率:      {self.win_rate:.1%}")
        rows.append(f"  交易数:    {self.n_trades}")

        if self.wfo_n_folds > 0:
            rows.append("⏭️  Walk-Forward OOS")
            rows.append(f"  OOS Sharpe:  {self.wfo_oos_sharpe:.2f}")
            rows.append(f"  OOS Return:  {self.wfo_oos_return:.2%}")
            rows.append(f"  OOS MaxDD:   {self.wfo_oos_max_dd:.2%}")
            rows.append(f"  Folds:       {self.wfo_n_folds}")

        if self.mc_n_successful > 0:
            rows.append(f"🎲 Monte Carlo({self.mc_n_successful} 模拟)")
            rows.append(f"  Sharpe 5-95%:  [{self.mc_sharpe_5pct:.2f}, {self.mc_sharpe_95pct:.2f}]")
            rows.append(f"  Return 5-95%:  [{self.mc_return_5pct:.2%}, {self.mc_return_95pct:.2%}]")
            if self.mc_degenerate:
                rows.append("  ⚠️  5%/95% 分位相同 = 分布退化,不能据此判断稳健性")

        rows.append(None)
        rows.append(f"🎯 信号输出(Top {len(self.signals)})")
        for i, signal in enumerate(self.signals[:5]):
            rows.append(
                f"  {i + 1}. {signal['symbol']}  {signal['side']:4s}  "
                f"conf={signal['confidence']:.2f}  {signal['rationale'][:50]}"
            )
        rows.append(None)
        rows.append(f"⏱️  耗时: {self.duration_seconds:.2f}s")
        return _render_box(rows)


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
        symbols: list[str],
        start: str = "2024-01-01",
        end: str = "2024-12-31",
        data_source: str = "mock",  # "mock" / "akshare" / "csv"
        data_path: str | None = None,
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
        from forgemind.core.observability import PipelineTracker, get_metrics, span

        tracker = PipelineTracker("e2e")
        tracker.start(
            n_symbols=len(self.symbols),
            data_source=self.data_source,
        )
        metrics = get_metrics()

        try:
            # === Step 1: 拉数据 ===
            with span("fetch_data", source=self.data_source):
                df_polars = self._fetch_data()
                n_bars = df_polars.select(pl.len()).collect().item()
                n_days = df_polars.select(pl.col("date").n_unique()).collect().item()
                metrics.inc("data.bars_loaded", n_bars)
                tracker.step("fetch_data", n_bars=n_bars, n_days=n_days)

            # === Step 2: 算因子 ===
            with span("compute_factors"):
                df_with_factors = self._compute_factors(df_polars)
                n_factors = len(
                    [
                        c
                        for c in df_with_factors.collect_schema().names()
                        if c
                        not in [
                            "date",
                            "symbol",
                            "open",
                            "high",
                            "low",
                            "close",
                            "volume",
                            "industry",
                            "returns",
                        ]
                    ]
                )
                metrics.set_gauge("factors.count", n_factors)
                tracker.step("compute_factors", n_factors=n_factors)

            # === Step 3: IC 评估 ===
            with span("evaluate_ic"):
                ic_results = self._evaluate_ic(df_with_factors)
                best = max(ic_results, key=lambda r: abs(r.rank_ic_mean)) if ic_results else None
                metrics.inc("ic.factors_evaluated", len(ic_results))
                tracker.step("evaluate_ic", n_ic=len(ic_results))

            # === Step 4: LightGBM 训练 ===
            with span("train_model"):
                model_result, top_features = self._train_model(df_with_factors, ic_results)
                tracker.step("train_model", cv_sharpe=model_result.get("cv_sharpe", 0.0))

            # === Step 5: 回测 ===
            with span("backtest"):
                backtest_metrics = self._backtest(df_with_factors, ic_results)
                metrics.observe("backtest.sharpe", backtest_metrics.get("sharpe", 0.0))
                tracker.step("backtest", sharpe=backtest_metrics.get("sharpe", 0.0))

            # === Step 5b: Walk-Forward Optimization(OOS 验证) ===
            with span("walk_forward"):
                wfo_result = (
                    self._walk_forward(df_with_factors, ic_results)
                    if self.wfo_enabled
                    else {
                        "oos_sharpe": 0.0,
                        "oos_return": 0.0,
                        "oos_max_dd": 0.0,
                        "n_folds": 0,
                        "folds_detail": [],
                    }
                )
                metrics.observe("wfo.oos_sharpe", wfo_result.get("oos_sharpe", 0.0))
                tracker.step("walk_forward", oos_sharpe=wfo_result.get("oos_sharpe", 0.0))

            # === Step 5c: Monte Carlo 稳健性 ===
            with span("monte_carlo"):
                mc_result = (
                    self._monte_carlo(df_with_factors, ic_results)
                    if self.mc_enabled
                    else {
                        "sharpe_5pct": 0.0,
                        "sharpe_95pct": 0.0,
                        "return_5pct": 0.0,
                        "return_95pct": 0.0,
                        "n_successful": 0,
                    }
                )
                metrics.inc("mc.simulations", mc_result.get("n_successful", 0))
                tracker.step("monte_carlo", n_sims=mc_result.get("n_successful", 0))

            # === Step 6: 信号输出 ===
            with span("generate_signals"):
                signals = self._generate_signals(
                    df_with_factors,
                    model_result,
                    top_features,
                    ic_results,
                    oos_sharpe=wfo_result.get("oos_sharpe", 0.0),
                )
                metrics.inc("signals.generated", len(signals))
                tracker.step("generate_signals", n_signals=len(signals))

            tracker.end()
        except Exception as e:
            tracker.end(error=e)
            raise

        end_time = datetime.now()

        return PipelineResult(
            n_symbols=len(self.symbols),
            n_days=int(n_days),
            n_bars=int(n_bars),
            n_factors_computed=int(n_factors),
            ic_top_factors=[
                {
                    "factor": r.factor,
                    "ic_mean": float(r.ic_mean),
                    "rank_ic_mean": float(r.rank_ic_mean),
                }
                for r in sorted(ic_results, key=lambda r: abs(r.rank_ic_mean), reverse=True)[:10]
            ]
            if ic_results
            else [],
            best_ic_mean=float(best.ic_mean) if best else 0.0,
            best_icir=float(best.icir) if best else 0.0,
            model_name="LightGBM",
            model_backend=str(model_result.get("model_backend", "unknown")),
            data_source=self.data_source,
            data_warning=(
                "本次使用确定性 GBM 模拟行情(非真实市场)。随机游走型价格"
                "本就没有可预测性,因而 CV IC / Sharpe 接近 0 属正常,"
                "不代表模型故障,也不代表任何真实标的的表现。"
                if self.data_source == "mock"
                else ""
            ),
            model_found_signal=model_result.get("model_found_signal"),
            cv_rank_ic_mean=float(model_result.get("cv_rank_ic_mean", 0.0) or 0.0),
            cv_rank_ic_std=float(model_result.get("cv_rank_ic_std", 0.0) or 0.0),
            cv_sharpe=float(model_result.get("cv_sharpe", 0.0) or 0.0),
            top_features={k: float(v) for k, v in top_features.items()},
            total_return=float(backtest_metrics.get("total_return", 0.0) or 0.0),
            sharpe=float(backtest_metrics.get("sharpe", 0.0) or 0.0),
            sortino=float(backtest_metrics.get("sortino", 0.0) or 0.0),
            max_drawdown=float(backtest_metrics.get("max_drawdown", 0.0) or 0.0),
            win_rate=float(backtest_metrics.get("win_rate", 0.0) or 0.0),
            n_trades=int(backtest_metrics.get("n_trades", 0) or 0),
            wfo_oos_sharpe=float(wfo_result.get("oos_sharpe", 0.0) or 0.0),
            wfo_oos_return=float(wfo_result.get("oos_return", 0.0) or 0.0),
            wfo_oos_max_dd=float(wfo_result.get("oos_max_dd", 0.0) or 0.0),
            wfo_n_folds=int(wfo_result.get("n_folds", 0) or 0),
            wfo_folds_detail=list(wfo_result.get("folds_detail", [])),
            mc_degenerate=bool(mc_result.get("degenerate", False)),
            mc_note=str(mc_result.get("spread_note", "")),
            mc_sharpe_5pct=float(mc_result.get("sharpe_5pct", 0.0) or 0.0),
            mc_sharpe_95pct=float(mc_result.get("sharpe_95pct", 0.0) or 0.0),
            mc_return_5pct=float(mc_result.get("return_5pct", 0.0) or 0.0),
            mc_return_95pct=float(mc_result.get("return_95pct", 0.0) or 0.0),
            mc_n_successful=int(mc_result.get("n_successful", 0) or 0),
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
        dates = [
            datetime.strptime(self.start, "%Y-%m-%d") + timedelta(days=i)
            for i in range(
                (
                    datetime.strptime(self.end, "%Y-%m-%d")
                    - datetime.strptime(self.start, "%Y-%m-%d")
                ).days
                + 1
            )
        ]

        np.random.seed(42)
        rows = []
        for sym in self.symbols:
            price = 100.0
            for date in dates:
                # 让不同股票有不同的 drift 和 vol(真实市场)
                sym_idx = self.symbols.index(sym)
                drift = 0.0005 + 0.0001 * (sym_idx % 5 - 2)
                vol = 0.015 + 0.005 * (sym_idx % 7 - 3)
                price *= 1 + drift + np.random.randn() * vol

                high = price * (1 + abs(np.random.randn() * 0.008))
                low = price * (1 - abs(np.random.randn() * 0.008))
                open_ = price * (1 + np.random.randn() * 0.003)
                volume = int(np.random.lognormal(15, 1))

                rows.append(
                    {
                        "symbol": sym,
                        "date": date,
                        "open": open_,
                        "high": high,
                        "low": low,
                        "close": price,
                        "volume": volume,
                    }
                )

        df = (
            pl.LazyFrame(rows)
            .sort(["symbol", "date"])
            .with_columns(
                [
                    pl.col("close").pct_change().over("symbol").alias("returns"),
                ]
            )
        )
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
        from forgemind.core.factors import Alpha158Config, compute_alpha158

        config = Alpha158Config()
        # Alpha158(主力)
        df = compute_alpha158(df, config)
        return df

    def _evaluate_ic(self, df: pl.LazyFrame) -> list:
        """Step 3: IC 评估"""
        from forgemind.core.factors import (
            batch_compute_ic,
            compute_forward_returns,
        )

        df_with_returns = compute_forward_returns(df, [1, 5])

        # 收集所有因子名(排除非因子列)
        non_factor_cols = {
            "date",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "returns",
            "industry",
            "fwd_return_1",
            "fwd_return_5",
            "fwd_return_10",
            "fwd_return_20",
        }
        df_cols = df_with_returns.collect_schema().names()
        factor_cols = [c for c in df_cols if c not in non_factor_cols][:30]  # 限制 30 个因子加速

        results = batch_compute_ic(
            df_with_returns, factor_cols, decay_cols=["fwd_return_1", "fwd_return_5"]
        )
        return results

    def _train_model(self, df: pl.LazyFrame, ic_results: list) -> tuple:
        """Step 4: LightGBM 训练"""
        from forgemind.core.factors import compute_forward_returns
        from forgemind.core.models import LightGBMModel

        df_with_returns = compute_forward_returns(df, [1])
        df_collected = df_with_returns.collect().to_pandas()

        # 选 Top 因子
        top_factor_names = [
            r.factor
            for r in sorted(ic_results, key=lambda r: abs(r.rank_ic_mean), reverse=True)[:15]
        ]
        feature_cols = [c for c in top_factor_names if c in df_collected.columns]

        if not feature_cols:
            return {
                "cv_rank_ic_mean": 0.0,
                "cv_rank_ic_std": 0.0,
                "cv_sharpe": 0.0,
                "model_found_signal": None,
                "model_backend": "not_trained",
            }, {}

        X = df_collected[feature_cols].fillna(0)
        y = df_collected["fwd_return_1"].fillna(0)

        model = LightGBMModel()
        result = model.train(X, y, use_cv=True)

        top_features = dict(sorted(result.feature_importance.items(), key=lambda x: -x[1])[:5])

        # cv≈0 有两种可能:模型没训成,或者**数据里本来就没有可预测性**。
        # 随机游走型的模拟行情属于后者 —— 这是正确结果,但必须说出来,
        # 否则报告里的 "CV Rank IC: 0.0000" 会被读成"模型坏了"。
        found_signal = abs(result.cv_mean) > 1e-3
        if not found_signal:
            logger.info(
                "pipeline_model_no_signal",
                cv_mean=result.cv_mean,
                n_features=X.shape[1],
                n_samples=X.shape[0],
            )
        return {
            "cv_rank_ic_mean": result.cv_mean,
            "cv_rank_ic_std": result.cv_std,
            "cv_sharpe": result.cv_mean * np.sqrt(252) if abs(result.cv_mean) > 0 else 0.0,
            "model_found_signal": found_signal,
            "model_backend": getattr(model, "backend", "unknown"),
        }, top_features

    def _backtest(self, df: pl.LazyFrame, ic_results: list) -> dict:
        """Step 5: 回测"""
        from forgemind.core.backtest import BacktestReport

        df_with_returns = df.with_columns(
            [
                (pl.col("close").shift(-1) / pl.col("close") - 1).alias("fwd_ret"),
            ]
        )
        df_collected = df_with_returns.collect().to_pandas()

        # 简单多空回测: 用综合 IC 分数排序, top 1/3 做多, bottom 1/3 做空
        if not ic_results:
            return {
                "total_return": 0.0,
                "sharpe": 0.0,
                "sortino": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "n_trades": 0,
            }

        # 用 top 因子 daily cross-sectional rank 做策略
        top_factor_names = [
            r.factor
            for r in sorted(ic_results, key=lambda r: abs(r.rank_ic_mean), reverse=True)[:5]
        ]
        factor_cols = [c for c in top_factor_names if c in df_collected.columns]

        if not factor_cols:
            return {
                "total_return": 0.0,
                "sharpe": 0.0,
                "sortino": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "n_trades": 0,
            }

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
        ic_results: list,
        n_folds: int = 3,
    ) -> dict:
        """Step 5b: Walk-Forward Optimization(防 look-ahead)

        把数据按时间切成 N 个 fold,每个 fold 用前面的数据"训练"IC 权重,
        评估在后续数据上的 OOS 表现。这是判断策略真实性的黄金标准。
        """
        from forgemind.core.backtest import WalkForwardOptimizer

        if not ic_results:
            return {
                "oos_sharpe": 0.0,
                "oos_return": 0.0,
                "oos_max_dd": 0.0,
                "n_folds": 0,
                "folds_detail": [],
            }

        df_collected = df.collect().to_pandas()
        top_factor_names = [
            r.factor
            for r in sorted(ic_results, key=lambda r: abs(r.rank_ic_mean), reverse=True)[:5]
        ]
        factor_cols = [c for c in top_factor_names if c in df_collected.columns]
        if not factor_cols:
            return {
                "oos_sharpe": 0.0,
                "oos_return": 0.0,
                "oos_max_dd": 0.0,
                "n_folds": 0,
                "folds_detail": [],
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
        except Exception as exc:
            # 显式记录失败原因,返回结构化错误字段
            logger.error("walk_forward_failed", error=str(exc), error_type=type(exc).__name__)
            return {
                "oos_sharpe": 0.0,
                "oos_return": 0.0,
                "oos_max_dd": 0.0,
                "n_folds": 0,
                "folds_detail": [],
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _monte_carlo(
        self,
        df: pl.LazyFrame,
        ic_results: list,
        n_simulations: int = 30,
    ) -> dict:
        """Step 5c: Monte Carlo 稳健性

        对 IC 排序做参数扰动,看 Sharpe 分布
        """
        from forgemind.core.backtest import MonteCarloSimulator

        if not ic_results:
            return {
                "sharpe_5pct": 0.0,
                "sharpe_95pct": 0.0,
                "return_5pct": 0.0,
                "return_95pct": 0.0,
                "n_successful": 0,
            }

        df_collected = df.collect().to_pandas()
        top_factor_names = [
            r.factor
            for r in sorted(ic_results, key=lambda r: abs(r.rank_ic_mean), reverse=True)[:5]
        ]
        factor_cols = [c for c in top_factor_names if c in df_collected.columns]
        if not factor_cols:
            return {
                "sharpe_5pct": 0.0,
                "sharpe_95pct": 0.0,
                "return_5pct": 0.0,
                "return_95pct": 0.0,
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
                # 5% == 95% 说明模拟没有方差,不是"策略稳健"。
                # 标的太少时 rank 量化严重(5 只票只有 5 个 rank 档位),
                # 参数扰动跨越不了档位边界,每次模拟选出同一批票。
                # 这种情况必须说出来,否则会被读成风险极低。
                "degenerate": bool(
                    result["n_successful"] > 1
                    and abs(result["sharpe_95th_pct"] - result["sharpe_5th_pct"]) < 1e-9
                ),
                "spread_note": (
                    "5% 与 95% 分位相同:本次模拟分布退化(通常是标的数过少,"
                    "横截面 rank 档位不足以让参数扰动改变选股结果),"
                    "不能据此判断策略稳健性。"
                ),
            }
        except Exception as exc:
            # 静默返回 0 会让"跑挂了"和"没有数据"长得一模一样
            logger.error("monte_carlo_failed", error=str(exc), error_type=type(exc).__name__)
            return {
                "sharpe_5pct": 0.0,
                "sharpe_95pct": 0.0,
                "return_5pct": 0.0,
                "return_95pct": 0.0,
                "n_successful": 0,
                "degenerate": True,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _generate_signals(
        self,
        df: pl.LazyFrame,
        model_result: dict,
        top_features: dict,
        ic_results: list | None = None,
        oos_sharpe: float = 0.0,
    ) -> list[dict]:
        """Step 6: 信号输出

        方向与置信度必须由**证据**决定,而不是恒为 BUY + 分数绝对值:

        - 方向取综合得分的符号。原来 side 硬编码 "BUY",于是得分 -1.50
          (全场最差)照样发 BUY。
        - 置信度取决于 (a) 入选因子的历史 Rank IC,(b) 策略自身的样本外
          Sharpe。min(0.95, 0.5 + |score|/10) 的形式用绝对值,与
          预测力无关,回测亏 10% 也照样满屏 0.6~0.95 的高置信 BUY。
        """
        ic_by_factor = {r.factor: r.rank_ic_mean for r in (ic_results or [])}
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
                normalized = (last_data[factor] - last_data[factor].mean()) / (
                    last_data[factor].std() + 1e-9
                )
                score = score.add(normalized.fillna(0), fill_value=0)

        # 排名
        last_data["score"] = score
        top_stocks = last_data.nlargest(self.top_n_signals, "score")

        # 证据强度:入选因子的平均 |Rank IC| 是"这些因子过去有没有预测力"
        ics = [abs(ic_by_factor.get(f, 0.0)) for f in top_features]
        mean_ic = float(np.mean(ics)) if ics else 0.0
        # 样本外表现是最终裁判:OOS Sharpe <= 0 时,任何信号都不该是高置信买入
        oos_ok = oos_sharpe > 0

        signals = []
        for _, row in top_stocks.iterrows():
            score = float(row["score"])
            side = "BUY" if score > 0 else "HOLD"

            # 置信度 = 因子预测力 × 样本外验证,两者都弱就是低置信
            conf = 0.5 * min(1.0, mean_ic / 0.03) + 0.5 * min(1.0, max(oos_sharpe, 0) / 1.0)
            if not oos_ok:
                conf = min(conf, 0.4)
                conf_note = f"样本外 Sharpe {oos_sharpe:+.2f} ≤ 0,信号未经验证"
            else:
                conf_note = f"因子平均 |Rank IC| {mean_ic:.4f},样本外 Sharpe {oos_sharpe:+.2f}"

            rationale = (
                f"综合因子得分 {score:+.4f}(>0 看多 / <0 观望);"
                f"依据 {', '.join(list(top_features.keys())[:3])};"
                f"{conf_note}"
            )
            signals.append(
                {
                    "signal_id": f"sig_{last_date.strftime('%Y%m%d')}_{row['symbol']}",
                    "symbol": row["symbol"],
                    "side": side,
                    "confidence": round(float(conf), 3),
                    "rationale": rationale,
                    "timestamp": str(datetime.now()),
                }
            )

        return signals
