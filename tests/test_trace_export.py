# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import pytest
import tempfile
from pathlib import Path


class TestTraceExporter:
    def test_export_to_json(self):
        from forgemind.core.observability import (
            span, get_tracer, reset_tracer, TraceExporter
        )
        reset_tracer()
        
        with span("test1"):
            pass
        with span("test2", x=1):
            pass
        
        tracer = get_tracer()
        exporter = TraceExporter(tracer)
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
            exporter.to_json(path)
            content = Path(path).read_text()
            assert "test1" in content
            assert "test2" in content
            assert "spans" in content
    
    def test_export_to_otlp(self):
        from forgemind.core.observability import (
            span, get_tracer, reset_tracer, TraceExporter
        )
        reset_tracer()
        
        with span("otlp_test"):
            pass
        
        tracer = get_tracer()
        exporter = TraceExporter(tracer)
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
            exporter.to_otlp(path)
            content = Path(path).read_text()
            assert "resourceSpans" in content
            assert "scopeSpans" in content
            assert "operationName" in content
            assert "otlp_test" in content


class TestTraceAnalyzer:
    def test_find_bottlenecks(self):
        from forgemind.core.observability import (
            span, get_tracer, reset_tracer, TraceAnalyzer
        )
        reset_tracer()
        
        with span("fast"):
            pass
        with span("slow"):
            import time
            time.sleep(0.1)
            pass
        
        analyzer = TraceAnalyzer(get_tracer())
        bottlenecks = analyzer.find_bottlenecks(top_n=2)
        assert len(bottlenecks) >= 1
        # "slow" 应该在 bottleneck 列表里
        names = [b["name"] for b in bottlenecks]
        assert "slow" in names
    
    def test_group_by_name(self):
        from forgemind.core.observability import (
            span, get_tracer, reset_tracer, TraceAnalyzer
        )
        reset_tracer()
        
        for _ in range(3):
            with span("repeated"):
                pass
        
        analyzer = TraceAnalyzer(get_tracer())
        groups = analyzer.group_by_name()
        assert "repeated" in groups
        assert groups["repeated"]["count"] == 3
    
    def test_error_rate(self):
        from forgemind.core.observability import (
            span, get_tracer, reset_tracer, TraceAnalyzer
        )
        reset_tracer()
        
        with span("ok"):
            pass
        try:
            with span("error"):
                raise ValueError("test")
        except ValueError:
            pass
        
        analyzer = TraceAnalyzer(get_tracer())
        rate = analyzer.error_rate()
        assert 0 < rate <= 1
    
    def test_report(self):
        from forgemind.core.observability import (
            span, get_tracer, reset_tracer, TraceAnalyzer
        )
        reset_tracer()
        
        with span("op_a"):
            pass
        with span("op_b"):
            pass
        
        report = TraceAnalyzer(get_tracer()).report()
        assert "ForgeMind Trace" in report
        assert "Spans:" in report
        assert "op_a" in report


class TestTraceVisualizer:
    def test_to_html(self):
        from forgemind.core.observability import (
            span, get_tracer, reset_tracer, TraceVisualizer
        )
        reset_tracer()
        
        with span("html_test"):
            pass
        
        visualizer = TraceVisualizer(get_tracer())
        
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            path = f.name
            visualizer.to_html(path)
            content = Path(path).read_text()
            assert "<!DOCTYPE html>" in content
            assert "html_test" in content
            assert "span-bar" in content


class TestIntegration:
    def test_export_pipeline_trace(self):
        """端到端流水线 trace 导出 + 分析 + 可视化"""
        from forgemind.core.observability import (
            PipelineTracker, get_tracer, reset_tracer,
            TraceExporter, TraceAnalyzer, TraceVisualizer,
        )
        reset_tracer()
        
        tracker = PipelineTracker("demo")
        tracker.start()
        tracker.step("step1")
        tracker.step("step2")
        tracker.end()
        
        tracer = get_tracer()
        
        # Export
        with tempfile.TemporaryDirectory() as tmp:
            json_path = f"{tmp}/trace.json"
            otlp_path = f"{tmp}/trace_otlp.json"
            html_path = f"{tmp}/trace.html"
            
            TraceExporter(tracer).to_json(json_path)
            TraceExporter(tracer).to_otlp(otlp_path)
            TraceVisualizer(tracer).to_html(html_path)
            
            assert Path(json_path).exists()
            assert Path(otlp_path).exists()
            assert Path(html_path).exists()
            
            # Analyze
            analyzer = TraceAnalyzer(tracer)
            report = analyzer.report()
            assert "demo" in report or "step1" in report