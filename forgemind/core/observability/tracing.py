# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import time
import uuid
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json


@dataclass
class SpanRecord:
    """单个 span 记录"""
    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "OK"  # OK / ERROR
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "status": self.status,
            "error_message": self.error_message,
        }


class Tracer:
    """追踪器 — 记录所有 span"""
    
    def __init__(self, max_spans: int = 10000):
        self.spans: List[SpanRecord] = []
        self.max_spans = max_spans
        self._active_spans: List[SpanRecord] = []
    
    def start_span(
        self,
        name: str,
        attributes: Optional[Dict] = None,
        parent_span_id: Optional[str] = None,
    ) -> SpanRecord:
        """开始一个 span"""
        # 决定 trace_id
        if self._active_spans:
            trace_id = self._active_spans[-1].trace_id
            parent = self._active_spans[-1].span_id
        else:
            trace_id = str(uuid.uuid4())
            parent = None
        
        if parent_span_id:
            parent = parent_span_id
        
        span = SpanRecord(
            name=name,
            trace_id=trace_id,
            span_id=str(uuid.uuid4())[:16],
            parent_span_id=parent,
            start_time=time.time(),
            attributes=attributes or {},
        )
        self._active_spans.append(span)
        return span
    
    def end_span(self, span: SpanRecord, error: Optional[Exception] = None):
        """结束一个 span"""
        span.end_time = time.time()
        span.duration_ms = (span.end_time - span.start_time) * 1000
        if error:
            span.status = "ERROR"
            span.error_message = str(error)
        # 弹出
        if span in self._active_spans:
            self._active_spans.remove(span)
        # 记录
        self.spans.append(span)
        if len(self.spans) > self.max_spans:
            self.spans.pop(0)
    
    def get_trace(self, trace_id: str) -> List[SpanRecord]:
        """获取一个 trace 的所有 span"""
        return [s for s in self.spans if s.trace_id == trace_id]
    
    def clear(self):
        """清空 span 记录"""
        self.spans.clear()
        self._active_spans.clear()
    
    def stats(self) -> Dict:
        """统计信息"""
        if not self.spans:
            return {"n_spans": 0}
        
        by_status = {}
        for s in self.spans:
            by_status[s.status] = by_status.get(s.status, 0) + 1
        
        durations = [s.duration_ms for s in self.spans]
        return {
            "n_spans": len(self.spans),
            "by_status": by_status,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "n_traces": len(set(s.trace_id for s in self.spans)),
        }


# 全局追踪器
_global_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    """获取全局追踪器"""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = Tracer()
    return _global_tracer


def reset_tracer():
    """重置追踪器"""
    global _global_tracer
    _global_tracer = Tracer()


@contextmanager
def span(name: str, **attributes):
    """span 上下文管理器
    
    用法:
        with span("compute_factors", symbols=10):
            ...
    """
    tracer = get_tracer()
    span_record = tracer.start_span(name, attributes)
    try:
        yield span_record
    except Exception as e:
        tracer.end_span(span_record, error=e)
        raise
    else:
        tracer.end_span(span_record)


def span_decorator(name: Optional[str] = None):
    """span 装饰器
    
    用法:
        @span_decorator("compute_factors")
        def my_func(...):
            ...
    """
    def decorator(func):
        span_name = name or func.__name__
        def wrapper(*args, **kwargs):
            with span(span_name, **{"func_args": str(args)[:100], "func_kwargs": str(kwargs)[:100]}):
                return func(*args, **kwargs)
        return wrapper
    return decorator


class MetricsRecorder:
    """Prometheus 风格 metrics 记录"""
    
    def __init__(self):
        self.counters: Dict[str, int] = {}
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = {}
    
    def inc(self, name: str, value: int = 1, labels: Optional[Dict] = None):
        """增加 counter"""
        key = self._make_key(name, labels)
        self.counters[key] = self.counters.get(key, 0) + value
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict] = None):
        """设置 gauge"""
        key = self._make_key(name, labels)
        self.gauges[key] = value
    
    def observe(self, name: str, value: float, labels: Optional[Dict] = None):
        """记录 histogram"""
        key = self._make_key(name, labels)
        if key not in self.histograms:
            self.histograms[key] = []
        self.histograms[key].append(value)
    
    def _make_key(self, name: str, labels: Optional[Dict]) -> str:
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def export_prometheus(self) -> str:
        """导出为 Prometheus 文本格式"""
        lines = []
        for key, value in self.counters.items():
            lines.append(f"# TYPE {key} counter")
            lines.append(f"{key} {value}")
        for key, value in self.gauges.items():
            lines.append(f"# TYPE {key} gauge")
            lines.append(f"{key} {value}")
        for key, values in self.histograms.items():
            lines.append(f"# TYPE {key} summary")
            if values:
                lines.append(f"{key}_sum {sum(values)}")
                lines.append(f"{key}_count {len(values)}")
                lines.append(f"{key}_avg {sum(values) / len(values)}")
                lines.append(f"{key}_max {max(values)}")
                lines.append(f"{key}_min {min(values)}")
        return "\n".join(lines)
    
    def snapshot(self) -> Dict:
        """获取快照"""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {
                k: {
                    "count": len(v),
                    "sum": sum(v),
                    "avg": sum(v) / len(v) if v else 0,
                    "max": max(v) if v else 0,
                    "min": min(v) if v else 0,
                }
                for k, v in self.histograms.items()
            },
        }


# 全局 metrics
_global_metrics: Optional[MetricsRecorder] = None


def get_metrics() -> MetricsRecorder:
    """获取全局 metrics 记录器"""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MetricsRecorder()
    return _global_metrics


def reset_metrics():
    """重置 metrics"""
    global _global_metrics
    _global_metrics = MetricsRecorder()


class PipelineTracker:
    """流水线追踪器 — 跟踪整个 pipeline 的执行"""
    
    def __init__(self, pipeline_name: str):
        self.pipeline_name = pipeline_name
        self.tracer = get_tracer()
        self.metrics = get_metrics()
        self.pipeline_span: Optional[SpanRecord] = None
    
    def start(self, **attributes):
        """开始 pipeline"""
        self.pipeline_span = self.tracer.start_span(
            f"pipeline.{self.pipeline_name}",
            attributes={"pipeline_name": self.pipeline_name, **attributes},
        )
        self.metrics.inc(f"pipeline.start", labels={"name": self.pipeline_name})
    
    def step(self, name: str, **attributes):
        """记录一个 step"""
        if not self.pipeline_span:
            return
        step_span = self.tracer.start_span(
            f"pipeline.{self.pipeline_name}.{name}",
            attributes=attributes,
            parent_span_id=self.pipeline_span.span_id,
        )
        # 立即结束(用于 mark 完成)
        self.tracer.end_span(step_span)
        self.metrics.inc(f"pipeline.step", labels={"pipeline": self.pipeline_name, "step": name})
    
    def end(self, error: Optional[Exception] = None):
        """结束 pipeline"""
        if self.pipeline_span:
            self.tracer.end_span(self.pipeline_span, error)
            if not error:
                self.metrics.inc(f"pipeline.success", labels={"name": self.pipeline_name})
            else:
                self.metrics.inc(f"pipeline.error", labels={"name": self.pipeline_name})
    
    def save_trace(self, path: str):
        """保存 trace 到 JSON 文件"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        # 保存这个 pipeline 的所有 span
        if not self.pipeline_span:
            return
        
        trace_id = self.pipeline_span.trace_id
        spans = self.tracer.get_trace(trace_id)
        output = {
            "pipeline_name": self.pipeline_name,
            "trace_id": trace_id,
            "spans": [s.to_dict() for s in spans],
            "metrics": self.metrics.snapshot(),
        }
        Path(path).write_text(json.dumps(output, indent=2, default=str))