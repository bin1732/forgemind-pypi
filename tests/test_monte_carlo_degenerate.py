# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""Monte Carlo 的 5%–95% 分位相同 = 分布退化,不是"策略稳健"

已验证:标的只有 5 只时,`mc_sharpe_5pct` 与 `mc_sharpe_95pct` **完全相等**
(Sharpe +2.6544,Return +13.77%)。参数扰动只让 top_pct 在 ±10% 内浮动,
而 5 只股票的横截面 rank 只有 {0.2,0.4,0.6,0.8,1.0} 五个档位 ——
阈值跨越不了档位边界,30 次模拟选出的股票完全相同,方差为零。

这在报告里长得和"策略非常稳健"一模一样。必须自己说出来。

另外 WFO 与 MC 的 except 分支原先静默返回 0,跑挂了和"没有数据"无法区分。
"""

import pytest


@pytest.mark.slow
class TestMonteCarloReportsDegeneracy:
    def _run(self, n_symbols):
        import warnings

        warnings.filterwarnings("ignore")
        from forgemind.core.pipeline import EndToEndPipeline

        p = EndToEndPipeline(
            symbols=[f"S{i:04d}" for i in range(n_symbols)],
            start="2024-01-01", end="2024-06-30",
            data_source="mock", top_n_signals=5)
        return p.run()

    def test_few_symbols_flags_degenerate(self):
        r = self._run(5)
        assert abs(r.mc_sharpe_5pct - r.mc_sharpe_95pct) < 1e-9, (
            "本用例依赖 5 只标的时分布退化;若已修复请更新本测试")
        assert r.mc_degenerate is True
        assert "退化" in r.mc_note and "稳健" in r.mc_note

    def test_enough_symbols_gives_real_spread(self):
        r = self._run(30)
        assert r.mc_n_successful > 1
        assert abs(r.mc_sharpe_95pct - r.mc_sharpe_5pct) > 1e-6, (
            "30 只标的时扰动应能改变选股结果,分布应有宽度")
        assert r.mc_degenerate is False


class TestRiskFailuresAreNotSilent:
    """跑挂了要说跑挂了,不能返回一组看起来正常的零"""

    def test_walk_forward_except_reports_the_error(self):
        import inspect

        import forgemind.core.pipeline.end_to_end as mod

        seg = inspect.getsource(mod.EndToEndPipeline._walk_forward)
        assert "except Exception as exc" in seg, "WFO 仍在静默吞异常"
        assert '"error"' in seg, "WFO 失败时应带上原因"
        assert "logger.error" in seg, "WFO 失败必须记日志"

    def test_monte_carlo_except_reports_the_error(self):
        import inspect

        import forgemind.core.pipeline.end_to_end as mod

        seg = inspect.getsource(mod.EndToEndPipeline._monte_carlo)
        assert "except Exception as exc" in seg
        assert '"error"' in seg
        assert "logger.error" in seg

    def test_degenerate_flag_is_exposed_on_the_result(self):
        import dataclasses

        from forgemind.core.pipeline.end_to_end import PipelineResult

        names = {f.name for f in dataclasses.fields(PipelineResult)}
        assert "mc_degenerate" in names, "退化标记没进结果对象"
        assert "mc_note" in names
        assert "risk_warning" in names


class TestWalkForwardIsActuallyRun:
    def test_folds_have_distinct_sharpes(self):
        """每个 fold 的样本外 Sharpe 应当各不相同 —— 全相等同样是退化"""
        import warnings

        warnings.filterwarnings("ignore")
        from forgemind.core.pipeline import EndToEndPipeline

        r = EndToEndPipeline(
            symbols=[f"S{i:04d}" for i in range(12)],
            start="2024-01-01", end="2024-09-30",
            data_source="mock", top_n_signals=5).run()
        assert r.wfo_n_folds >= 2
        sharpes = [f.get("test_sharpe") for f in r.wfo_folds_detail
                   if f.get("test_sharpe") is not None]
        assert len(sharpes) >= 2
        assert len(set(round(s, 9) for s in sharpes)) > 1, (
            f"各 fold 样本外 Sharpe 完全相同:{sharpes} —— WFO 疑似退化")


class TestPipelineDeclaresItsDataSource:
    """流水线结果必须自己说清数据是不是模拟的

    `EndToEndPipeline(data_source="mock")` 生成的是确定性 GBM 随机游走。
    而随机游走本来就没有可预测性,所以 CV IC / Sharpe 接近 0 是**正确结果**,
    不是模型坏了 —— 但报告里一个光秃秃的 "CV Rank IC: 0.0000" 会被读成故障。
    """

    @pytest.mark.slow
    def test_result_carries_source_and_warning(self):
        import warnings

        warnings.filterwarnings("ignore")
        from forgemind.core.pipeline import EndToEndPipeline

        r = EndToEndPipeline(
            symbols=[f"S{i:04d}" for i in range(8)],
            start="2024-01-01", end="2024-06-30",
            data_source="mock", top_n_signals=5).run()
        assert r.data_source == "mock"
        assert "模拟" in r.data_warning, "必须说明这份数据不是真实行情"
        # model_found_signal 必须是三态而不是默认 None,否则无法区分
        # "没学到信号" 与 "根本没训练"
        assert r.model_found_signal in (True, False), r.model_found_signal

    @pytest.mark.slow
    def test_summary_prints_the_caveat_only_when_true(self):
        """caveat 必须按实际条件出现,不能无条件印 —— 那本身也是一句假话"""
        import warnings

        warnings.filterwarnings("ignore")
        from forgemind.core.pipeline import EndToEndPipeline

        r = EndToEndPipeline(
            symbols=[f"S{i:04d}" for i in range(8)],
            start="2024-01-01", end="2024-06-30",
            data_source="mock", top_n_signals=5).run()
        s = r.summary()
        if r.data_source == "mock":
            assert "数据来源" in s, "用模拟数据时摘要必须标注"
        if r.model_found_signal is False:
            assert "未学到" in s
        else:
            assert "未学到可预测信号" not in s, (
                "模型实际学到了信号,却印了'未学到' —— 又是一句假话")

    def test_fields_exist_on_the_result(self):
        import dataclasses

        from forgemind.core.pipeline.end_to_end import PipelineResult

        names = {f.name for f in dataclasses.fields(PipelineResult)}
        assert {"data_source", "data_warning", "model_found_signal"} <= names
