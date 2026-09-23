# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import tempfile
from pathlib import Path


class TestTracer:
    def test_create_tracer(self):
        from forgemind.core.observability import get_tracer
        tracer = get_tracer()
        assert tracer is not None
    
    def test_start_end_span(self):
        from forgemind.core.observability import get_tracer
        tracer = get_tracer()
        tracer.clear()
        
        span = tracer.start_span("test", attributes={"x": 1})
        assert span.name == "test"
        assert span.attributes["x"] == 1
        assert span.duration_ms == 0  # not ended yet
        
        tracer.end_span(span)
        assert span.duration_ms > 0
        assert span.status == "OK"
    
    def test_span_with_error(self):
        from forgemind.core.observability import get_tracer
        tracer = get_tracer()
        tracer.clear()
        
        span = tracer.start_span("failing")
        try:
            raise ValueError("test error")
        except ValueError as e:
            tracer.end_span(span, error=e)
        
        assert span.status == "ERROR"
        assert "test error" in span.error_message


class TestSpanContextManager:
    def test_span_context(self):
        from forgemind.core.observability import span, get_tracer
        tracer = get_tracer()
        tracer.clear()
        
        with span("test", x=1) as s:
            assert s.name == "test"
            assert s.attributes["x"] == 1
        
        # 应已结束
        assert s.duration_ms >= 0
        assert s.status == "OK"
    
    def test_span_context_error(self):
        from forgemind.core.observability import span, get_tracer
        tracer = get_tracer()
        tracer.clear()
        
        with pytest.raises(ValueError):
            with span("fail") as s:
                raise ValueError("boom")
        
        assert s.status == "ERROR"
        assert "boom" in s.error_message


class TestSpanDecorator:
    def test_decorator_basic(self):
        from forgemind.core.observability import span_decorator, get_tracer
        tracer = get_tracer()
        tracer.clear()
        
        @span_decorator()
        def my_func(x, y):
            return x + y
        
        result = my_func(1, 2)
        assert result == 3
        
        # 应记录了 1 个 span
        spans = [s for s in tracer.spans if s.name == "my_func"]
        assert len(spans) == 1


class TestMetricsRecorder:
    def test_counter(self):
        from forgemind.core.observability import MetricsRecorder
        m = MetricsRecorder()
        m.inc("requests")
        m.inc("requests")
        m.inc("requests", value=5)
        assert m.counters["requests"] == 7
    
    def test_gauge(self):
        from forgemind.core.observability import MetricsRecorder
        m = MetricsRecorder()
        m.set_gauge("temperature", 25.5)
        m.set_gauge("temperature", 30.0)
        assert m.gauges["temperature"] == 30.0
    
    def test_histogram(self):
        from forgemind.core.observability import MetricsRecorder
        m = MetricsRecorder()
        for v in [1, 2, 3, 4, 5]:
            m.observe("latency_ms", v)
        snap = m.snapshot()
        assert snap["histograms"]["latency_ms"]["count"] == 5
        assert snap["histograms"]["latency_ms"]["avg"] == 3.0
    
    def test_prometheus_export(self):
        from forgemind.core.observability import MetricsRecorder
        m = MetricsRecorder()
        m.inc("requests", labels={"endpoint": "/api"})
        m.observe("latency", 100, labels={"endpoint": "/api"})
        
        text = m.export_prometheus()
        assert "requests" in text
        assert "latency" in text


class TestPipelineTracker:
    def test_pipeline_tracker(self):
        from forgemind.core.observability import PipelineTracker, get_tracer
        tracer = get_tracer()
        tracer.clear()
        
        tracker = PipelineTracker("e2e")
        tracker.start(symbols=10, start="2024-01-01")
        tracker.step("fetch_data", n_bars=1000)
        tracker.step("compute_factors", n_factors=149)
        tracker.step("train_model")
        tracker.end()
        
        # 至少 4 个 span(1 个 pipeline + 3 个 step)
        assert len(tracer.spans) >= 4
    
    def test_pipeline_with_error(self):
        from forgemind.core.observability import PipelineTracker, get_metrics
        get_metrics()
        
        tracker = PipelineTracker("failing")
        tracker.start()
        tracker.step("step1")
        tracker.end(error=ValueError("test"))
        
        # metrics 应该记了 error
        snap = get_metrics().snapshot()
        # pipeline.error counter 应该 +1
        error_count = sum(
            v for k, v in snap["counters"].items()
            if "pipeline.error" in k
        )
        assert error_count >= 1
    
    def test_save_trace(self):
        from forgemind.core.observability import PipelineTracker, get_tracer
        tracer = get_tracer()
        tracer.clear()
        
        tracker = PipelineTracker("test")
        tracker.start(x=1)
        tracker.step("s1")
        tracker.end()
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
            tracker.save_trace(path)
            content = Path(path).read_text()
            assert "test" in content
            assert "trace_id" in content


class TestIntegration:
    def test_traced_pipeline(self):
        """完整链路追踪 + metrics"""
        from forgemind.core.observability import (
            span, span_decorator, get_tracer, get_metrics
        )
        
        tracer = get_tracer()
        metrics = get_metrics()
        tracer.clear()
        metrics.counters.clear()
        metrics.gauges.clear()
        metrics.histograms.clear()
        
        @span_decorator("load_data")
        def load_data():
            metrics.inc("data.loaded")
            return [1, 2, 3]
        
        @span_decorator("compute")
        def compute(data):
            metrics.observe("compute.size", len(data))
            return sum(data)
        
        with span("pipeline", items=3) as p:
            data = load_data()
            result = compute(data)
        
        assert result == 6
        
        # 应有 3 个 span
        assert len(tracer.spans) >= 3
        # metrics 应记录了 1 次 data.loaded
        assert metrics.counters.get("data.loaded", 0) >= 1