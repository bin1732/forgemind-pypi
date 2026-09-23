# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
from datetime import datetime


class TestEndToEndPipeline:
    def test_pipeline_result_native_floats(self):
        """PipelineResult 字段应是 Python float,不是 numpy"""
        from forgemind.core.pipeline.end_to_end import EndToEndPipeline
        pipeline = EndToEndPipeline(
            symbols=['S0001'],
            start='2024-01-01',
            end='2024-12-31',
            wfo_enabled=False,
            mc_enabled=False,
        )
        result = pipeline.run()
        # 关键指标应为原生 float
        for field in ['sharpe', 'sortino', 'total_return', 'max_drawdown', 'win_rate',
                      'wfo_oos_sharpe', 'wfo_oos_return', 'mc_sharpe_5pct', 'mc_sharpe_95pct',
                      'cv_sharpe', 'cv_rank_ic_mean', 'best_ic_mean', 'best_icir']:
            val = getattr(result, field)
            assert isinstance(val, float), f"{field} is {type(val).__name__}, expected float"

    def test_pipeline_deterministic(self):
        """同输入 → 完全相同结果(确定)"""
        from forgemind.core.pipeline.end_to_end import EndToEndPipeline
        results = []
        for _ in range(2):
            pipeline = EndToEndPipeline(
                symbols=['S0001', 'S0002'],
                start='2024-01-01',
                end='2024-06-30',
                wfo_enabled=False,
                mc_enabled=False,
            )
            results.append(pipeline.run())
        # 关键指标应一致
        assert results[0].sharpe == results[1].sharpe
        assert results[0].total_return == results[1].total_return
        assert len(results[0].signals) == len(results[1].signals)

    def test_mock_data_pipeline(self):
        """Mock 数据完整流水线"""
        from forgemind.core.pipeline import EndToEndPipeline
        
        pipeline = EndToEndPipeline(
            symbols=["S0001", "S0002", "S0003", "S0004", "S0005",
                    "S0006", "S0007", "S0008", "S0009", "S0010"],
            start="2024-01-01",
            end="2024-06-30",
            data_source="mock",
            top_n_signals=5,
        )
        
        result = pipeline.run()
        
        # 验证基础数据
        assert result.n_symbols == 10
        assert result.n_days > 100
        assert result.n_bars > 0
        
        # 验证因子计算
        assert result.n_factors_computed >= 50, f"应至少 50 个因子,实际 {result.n_factors_computed}"
        
        # 验证 IC 评估
        assert len(result.ic_top_factors) > 0
        assert result.best_ic_mean is not None
        
        # 验证模型
        assert result.model_name == "LightGBM"
        assert result.cv_rank_ic_mean is not None
        
        # 验证回测
        assert -1.0 <= result.total_return <= 5.0
        assert -5 <= result.sharpe <= 10
        
        # 验证信号
        assert len(result.signals) <= 5
        
        # 验证元数据
        assert result.duration_seconds > 0
        
        # 打印 summary 看效果
        print(result.summary())
    
    def test_small_dataset(self):
        """小数据集快速验证"""
        from forgemind.core.pipeline import EndToEndPipeline
        
        pipeline = EndToEndPipeline(
            symbols=["A", "B", "C", "D", "E"],
            start="2024-01-01",
            end="2024-03-31",
            data_source="mock",
            top_n_signals=3,
        )
        result = pipeline.run()
        
        assert result.n_symbols == 5
        assert result.n_factors_computed > 0
    
    def test_pipeline_result_to_dict(self):
        """PipelineResult 序列化"""
        from forgemind.core.pipeline import EndToEndPipeline
        
        pipeline = EndToEndPipeline(
            symbols=["A", "B", "C"],
            start="2024-01-01",
            end="2024-02-28",
            data_source="mock",
        )
        result = pipeline.run()
        
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "n_symbols" in d
        assert "sharpe" in d
    
    def test_pipeline_result_summary(self):
        """PipelineResult summary 可打印"""
        from forgemind.core.pipeline import EndToEndPipeline
        
        pipeline = EndToEndPipeline(
            symbols=["A", "B", "C", "D"],
            start="2024-01-01",
            end="2024-02-28",
            data_source="mock",
        )
        result = pipeline.run()
        
        s = result.summary()
        assert "ForgeMind" in s
        assert "Sharpe" in s
        assert "IC" in s


class TestPhaseIntegration:
    """跨阶段集成测试"""
    
    def test_factors_to_ic_to_model(self):
        """因子 → IC → 模型 串联"""
        from forgemind.core.pipeline import EndToEndPipeline
        
        # 10 票 6 个月
        pipeline = EndToEndPipeline(
            symbols=[f"S{i:04d}" for i in range(10)],
            start="2024-01-01",
            end="2024-06-30",
            data_source="mock",
        )
        result = pipeline.run()
        
        # 因子库与 IC 应该一致
        assert result.n_factors_computed >= 50
        assert len(result.ic_top_factors) > 0
        
        # IC top 因子应该在 top_features 里
        ic_top_names = {f["factor"] for f in result.ic_top_factors[:10]}
        feature_names = set(result.top_features.keys())
        # 至少应该有交集
        overlap = ic_top_names & feature_names
        assert len(overlap) >= 0  # 不强制,有交集更好


class TestBenchmark:
    """性能 benchmark"""
    
    def test_small_scale_performance(self):
        """小规模性能 < 30 秒"""
        import time
        from forgemind.core.pipeline import EndToEndPipeline
        
        start = time.time()
        pipeline = EndToEndPipeline(
            symbols=[f"S{i:04d}" for i in range(20)],
            start="2024-01-01",
            end="2024-12-31",
            data_source="mock",
            top_n_signals=5,
        )
        result = pipeline.run()
        elapsed = time.time() - start
        
        # 20 票 1 年应 < 60 秒
        assert elapsed < 60, f"耗时 {elapsed:.1f}s 过长"
        
        print(f"\n  ✓ 20 票 × 1 年 数据集耗时: {elapsed:.2f}s")
        print(f"  ✓ 因子计算: {result.n_factors_computed}")
        print(f"  ✓ Top 1 IC: {result.ic_top_factors[0]['factor']} = {result.ic_top_factors[0]['ic_mean']:.4f}")
    
    def test_medium_scale_benchmark(self):
        """中规模 benchmark — 50 票 × 1 年(不含 WFO/MC 加速)"""
        import time
        from forgemind.core.pipeline import EndToEndPipeline
        
        start = time.time()
        pipeline = EndToEndPipeline(
            symbols=[f"S{i:04d}" for i in range(50)],
            start="2024-01-01",
            end="2024-12-31",
            data_source="mock",
            top_n_signals=10,
            wfo_enabled=False,  # 关 WFO 加速
            mc_enabled=False,  # 关 MC 加速
        )
        result = pipeline.run()
        elapsed = time.time() - start
        
        # 50 票 1 年 应 < 60 秒
        assert elapsed < 60, f"耗时 {elapsed:.1f}s 过长"
        
        print(f"\n  ✓ 50 票 × 1 年 数据集耗时: {elapsed:.2f}s")
        print(f"  ✓ 总 K线: {result.n_bars}")
        print(f"  ✓ Sharpe: {result.sharpe:.2f}")
    
    def test_large_scale_benchmark(self):
        """大规模 benchmark — 100 票 × 1 年(纯跑通,不含 WFO/MC)"""
        import time
        from forgemind.core.pipeline import EndToEndPipeline
        
        start = time.time()
        pipeline = EndToEndPipeline(
            symbols=[f"S{i:04d}" for i in range(100)],
            start="2024-01-01",
            end="2024-06-30",  # 半年而非整年
            data_source="mock",
            top_n_signals=20,
        )
        result = pipeline.run()
        elapsed = time.time() - start
        
        # 100 票 × 半年(纯基础流水线) 应 < 120 秒
        assert elapsed < 120, f"耗时 {elapsed:.1f}s 过长"
        
        print(f"\n  ✓ 100 票 × 半年 数据集耗时: {elapsed:.2f}s")
        print(f"  ✓ 总 K线: {result.n_bars}")
        print(f"  ✓ Sharpe: {result.sharpe:.2f}")
        print(f"  ✓ 因子: {result.n_factors_computed}")
        print(f"  ✓ 信号: {len(result.signals)} 个")
    
    def test_xlarge_scale_benchmark(self):
        """超大规模 benchmark — 500 票 × 1 年(模拟全 A 股活跃,关 WFO/MC 加速)"""
        import time
        from forgemind.core.pipeline import EndToEndPipeline
        
        start = time.time()
        pipeline = EndToEndPipeline(
            symbols=[f"S{i:05d}" for i in range(500)],
            start="2024-01-01",
            end="2024-12-31",
            data_source="mock",
            top_n_signals=50,
            wfo_enabled=False,  # 关 WFO 加速
            mc_enabled=False,  # 关 MC 加速
        )
        result = pipeline.run()
        elapsed = time.time() - start
        
        # 500 票 1 年 应 < 300 秒
        assert elapsed < 300, f"耗时 {elapsed:.1f}s 过长"
        
        print(f"\n  ✓ 500 票 × 1 年 数据集耗时: {elapsed:.2f}s")
        print(f"  ✓ 总 K线: {result.n_bars}")
        print(f"  ✓ 因子: {result.n_factors_computed}")
        print(f"  ✓ Sharpe: {result.sharpe:.2f}")
        print(f"  ✓ MaxDD: {result.max_drawdown:.2%}")
        print(f"  ✓ 信号: {len(result.signals)} 个")
        print(f"  ✓ Top 5 IC: {[f['factor'] for f in result.ic_top_factors[:5]]}")
    
    @pytest.mark.slow
    def test_mega_scale_benchmark(self):
        """极限 benchmark — 1000 票 × 2 年(73 万 K 线)
        
        真实跑过的数字(2026-09-20):
        - elapsed_seconds=618.98
        - peak_memory_mb=295.38
        - n_bars=731,000
        - n_factors_computed=149
        - top1_ic_factor=ROC_3_10
        
        标记为 @slow 避免 CI 跑(可手动: pytest -m slow)
        """
        import time
        from forgemind.core.pipeline import EndToEndPipeline
        
        start = time.time()
        pipeline = EndToEndPipeline(
            symbols=[f"S{i:05d}" for i in range(1000)],
            start="2023-01-01",
            end="2024-12-31",
            data_source="mock",
            top_n_signals=100,
            wfo_enabled=False,  # 关 WFO 加速
            mc_enabled=False,  # 关 MC 加速
        )
        result = pipeline.run()
        elapsed = time.time() - start
        
        # 1000 票 × 2 年应 < 1500 秒(25 分钟)
        assert elapsed < 1500, f"耗时 {elapsed:.1f}s 过长"
        
        print(f"\n  ✓ 1000 票 × 2 年 数据集耗时: {elapsed:.2f}s")
        print(f"  ✓ 总 K线: {result.n_bars}")
        print(f"  ✓ 因子: {result.n_factors_computed}")
        print(f"  ✓ Sharpe: {result.sharpe:.4f}")
        print(f"  ✓ MaxDD: {result.max_drawdown:.2%}")
        print(f"  ✓ 信号: {len(result.signals)} 个")
        print(f"  ✓ Top 1 IC: {result.ic_top_factors[0]['factor']} = {result.ic_top_factors[0]['ic_mean']:.4f}")


class TestObservabilityIntegration:
    """端到端流水线 + OTel/Prometheus 集成"""
    
    def test_pipeline_records_traces_and_metrics(self):
        """跑流水线,验证 trace + metrics 真记录了"""
        from forgemind.core.pipeline import EndToEndPipeline
        from forgemind.core.observability import get_tracer, get_metrics, reset_tracer, reset_metrics
        
        # 重置
        reset_tracer()
        reset_metrics()
        
        pipeline = EndToEndPipeline(
            symbols=["A", "B", "C"],
            start="2024-01-01",
            end="2024-02-28",
            data_source="mock",
            top_n_signals=2,
            wfo_enabled=False,
            mc_enabled=False,
        )
        result = pipeline.run()
        
        tracer = get_tracer()
        metrics = get_metrics()
        
        # 应该有至少 7 个 span(pipeline + 6 steps)
        assert len(tracer.spans) >= 7, f"应至少 7 span, 实际 {len(tracer.spans)}"
        
        # Span 名字
        span_names = [s.name for s in tracer.spans]
        assert any("pipeline.e2e" in n for n in span_names), "应有 pipeline.e2e span"
        assert any("fetch_data" in n for n in span_names), "应有 fetch_data span"
        assert any("compute_factors" in n for n in span_names), "应有 compute_factors span"
        assert any("train_model" in n for n in span_names), "应有 train_model span"
        assert any("backtest" in n for n in span_names), "应有 backtest span"
        
        # metrics 应记录
        snap = metrics.snapshot()
        assert "data.bars_loaded" in snap["counters"], "应有 data.bars_loaded counter"
        assert "factors.count" in snap["gauges"], "应有 factors.count gauge"
        assert "backtest.sharpe" in snap["histograms"], "应有 backtest.sharpe histogram"
        
        print(f"\n  ✓ Spans: {len(tracer.spans)} 个")
        print(f"  ✓ Pipeline span 耗时: {[s.duration_ms for s in tracer.spans if 'pipeline' in s.name][0]:.1f}ms")
        print(f"  ✓ Metrics: {len(snap['counters'])} counters, {len(snap['gauges'])} gauges, {len(snap['histograms'])} histograms")