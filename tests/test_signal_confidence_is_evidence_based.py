# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""信号的置信度必须由证据决定,不能是分数绝对值的换算

已验证:一次回测 total_return=-10.23% / Sharpe=-1.75 的运行,
对 5 只股票**全部**发出 BUY,置信度 0.61~0.95 —— 其中得分 -1.5015
(全场最差)的那只拿到 0.65。两个原因:

  1. side 硬编码 "BUY" —— 没有 SELL/HOLD 路径
  2. confidence = min(0.95, 0.5 + abs(score)/10) —— 用**绝对值**,
     与因子预测力、样本外表现都无关;|score| > 4.5 就封顶 0.95

现在:方向取得分符号;置信度由因子平均 |Rank IC| 与样本外 Sharpe 共同决定,
样本外 Sharpe ≤ 0 时封顶并写明"信号未经验证"。
"""

import pandas as pd


def _fake_ic(rank_ic):
    class R:
        def __init__(self, f, ic):
            self.factor, self.rank_ic_mean = f, ic
    return [R("F1", rank_ic), R("F2", rank_ic)]


def _panel(n=6, ndays=40):
    import datetime as dt
    import numpy as np
    rng = np.random.default_rng(1)
    rows = []
    for s in range(n):
        px = 100 + s
        for d in range(ndays):
            # date 必须是真日期:信号生成里会 last_date.strftime(...)
            rows.append({"symbol": f"S{s:02d}",
                         "date": (dt.date(2024, 1, 1) + dt.timedelta(days=d)),
                         "F1": rng.normal(0, 1), "F2": rng.normal(0, 1),
                         "close": px})
    return pd.DataFrame(rows)


class TestSignalSideFollowsScore:
    def test_negative_score_is_not_a_buy(self, monkeypatch):
        import polars as pl

        from forgemind.core.pipeline.end_to_end import EndToEndPipeline

        pipe = EndToEndPipeline(symbols=["S00", "S01"], start="2024-01-01",
                               end="2024-02-01", data_source="mock")
        df = pl.DataFrame(_panel(n=2, ndays=30))
        # 构造:F1/F2 在最后一天全部为负
        last = df["date"].max()
        df = df.with_columns(
            pl.when(pl.col("date") == last)
            .then(-5.0).otherwise(pl.col("F1")).alias("F1"),
            pl.when(pl.col("date") == last)
            .then(-5.0).otherwise(pl.col("F2")).alias("F2"))
        sigs = pipe._generate_signals(df.lazy(), {}, {"F1": 1, "F2": 1},
                                      _fake_ic(0.01), oos_sharpe=1.0)
        assert sigs, "应当产出信号"
        for s in sigs:
            assert s["side"] == "HOLD", (
                f"得分为负却发 {s['side']}: {s['rationale']}")

    def test_positive_score_keeps_buy(self):
        import polars as pl

        from forgemind.core.pipeline.end_to_end import EndToEndPipeline

        pipe = EndToEndPipeline(symbols=["S00", "S01"], start="2024-01-01",
                               end="2024-02-01", data_source="mock")
        df = pl.DataFrame(_panel(n=2, ndays=30))
        last = df["date"].max()
        # 每股给**不同**的正分:横截面全部相同的话 std=0,归一化后恒为 0,
        # 得分就落到随机列上了(我第一版就是这么写错的)
        df = df.with_columns(
            pl.when(pl.col("date") == last)
            .then(pl.col("symbol").str.extract(r"(\d+)", 1).cast(pl.Int64))
            .otherwise(pl.col("F1")).alias("F1"))
        sigs = pipe._generate_signals(df.lazy(), {}, {"F1": 1}, _fake_ic(0.05),
                                      oos_sharpe=1.5)
        # S00 的 F1=0 → 得分恰为 0 → HOLD;只有 S01(F1=1)应为 BUY。
        # 一度写成 all(side == "BUY"),那要求零分也买入 —— 本身就是错的。
        by_symbol = {s["symbol"]: s["side"] for s in sigs}
        assert by_symbol.get("S01") == "BUY", by_symbol
        assert by_symbol.get("S00") == "HOLD", by_symbol


class TestConfidenceTracksEvidence:
    def _run(self, rank_ic, oos_sharpe):
        import polars as pl

        from forgemind.core.pipeline.end_to_end import EndToEndPipeline

        pipe = EndToEndPipeline(symbols=["S00", "S01"], start="2024-01-01",
                               end="2024-02-01", data_source="mock")
        df = pl.DataFrame(_panel(n=2, ndays=30))
        last = df["date"].max()
        df = df.with_columns(
            pl.when(pl.col("date") == last)
            .then(5.0).otherwise(pl.col("F1")).alias("F1"))
        sigs = pipe._generate_signals(df.lazy(), {}, {"F1": 1}, _fake_ic(rank_ic),
                                      oos_sharpe=oos_sharpe)
        return sigs[0]

    def test_bad_oos_caps_confidence_and_says_so(self):
        s = self._run(rank_ic=0.05, oos_sharpe=-1.0)
        assert s["confidence"] <= 0.4, s
        assert "未经验证" in s["rationale"], s["rationale"]

    def test_good_evidence_raises_confidence(self):
        good = self._run(rank_ic=0.05, oos_sharpe=2.0)
        bad = self._run(rank_ic=0.0, oos_sharpe=0.0)
        assert good["confidence"] > bad["confidence"], (good, bad)
        assert "Rank IC" in good["rationale"]

    def test_weak_factor_lowers_confidence_at_same_oos(self):
        strong = self._run(rank_ic=0.05, oos_sharpe=1.0)
        weak = self._run(rank_ic=0.0, oos_sharpe=1.0)
        assert strong["confidence"] > weak["confidence"]


class TestNoAbsoluteValueInConfidence:
    def test_source_does_not_use_abs_of_score_for_confidence(self):
        """回归:防止有人把 abs(score) 又写回置信度公式"""
        import inspect

        from forgemind.core.pipeline.end_to_end import EndToEndPipeline

        src = inspect.getsource(EndToEndPipeline._generate_signals)
        assert "abs(row[\"score\"])" not in src
        assert "abs(row['score'])" not in src
        assert 'side = "BUY"' in src
        assert '"side": side' in src, "side 必须是变量,不能硬编码"
