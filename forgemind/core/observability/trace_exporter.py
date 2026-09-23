# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
from .tracing import Tracer, SpanRecord


class TraceExporter:
    """Trace 导出器"""
    
    def __init__(self, tracer: Tracer):
        self.tracer = tracer
    
    def to_json(self, path: str, trace_id: Optional[str] = None):
        """导出 trace 到 JSON"""
        if trace_id:
            spans = self.tracer.get_trace(trace_id)
        else:
            spans = self.tracer.spans
        
        output = {
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "n_spans": len(spans),
            "traces": list(set(s.trace_id for s in spans)),
            "spans": [s.to_dict() for s in spans],
        }
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(output, indent=2, default=str))
        return path
    
    def to_otlp(self, path: str):
        """导出为 OTLP JSON(OpenTelemetry 协议)
        
        兼容 Jaeger / Tempo / Honeycomb / Datadog
        """
        spans = []
        for s in self.tracer.spans:
            otlp_span = {
                "traceId": s.trace_id.replace("-", "")[:16],
                "spanId": s.span_id,
                "operationName": s.name,
                "startTime": int(s.start_time * 1_000_000),  # microseconds
                "duration": int(s.duration_ms * 1000),  # microseconds
                "tags": [{"key": k, "value": str(v)} for k, v in s.attributes.items()],
                "logs": [],
                "status": s.status,
                "parentSpanId": s.parent_span_id,
            }
            if s.error_message:
                otlp_span["tags"].append({
                    "key": "error.message",
                    "value": s.error_message,
                })
            spans.append(otlp_span)
        
        output = {
            "resourceSpans": [{
                "resource": {"attributes": [{"key": "service.name", "value": "forgemind"}]},
                "scopeSpans": [{
                    "scope": {"name": "forgemind.tracer"},
                    "spans": spans,
                }],
            }],
        }
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(output, indent=2, default=str))
        return path


class TraceAnalyzer:
    """Trace 分析器 — 找瓶颈"""
    
    def __init__(self, tracer: Tracer):
        self.tracer = tracer
    
    def find_bottlenecks(self, top_n: int = 5) -> List[Dict]:
        """找最慢的 span"""
        sorted_spans = sorted(self.tracer.spans, key=lambda s: -s.duration_ms)
        return [
            {
                "name": s.name,
                "duration_ms": s.duration_ms,
                "attributes": s.attributes,
                "status": s.status,
            }
            for s in sorted_spans[:top_n]
        ]
    
    def group_by_name(self) -> Dict[str, Dict]:
        """按名字聚合"""
        groups = defaultdict(lambda: {
            "count": 0,
            "total_ms": 0.0,
            "min_ms": float("inf"),
            "max_ms": 0.0,
            "errors": 0,
        })
        
        for s in self.tracer.spans:
            g = groups[s.name]
            g["count"] += 1
            g["total_ms"] += s.duration_ms
            g["min_ms"] = min(g["min_ms"], s.duration_ms)
            g["max_ms"] = max(g["max_ms"], s.duration_ms)
            if s.status == "ERROR":
                g["errors"] += 1
        
        for name, g in groups.items():
            g["avg_ms"] = g["total_ms"] / g["count"]
            g["min_ms"] = g["min_ms"] if g["min_ms"] != float("inf") else 0
        
        return dict(groups)
    
    def error_rate(self) -> float:
        """错误率"""
        if not self.tracer.spans:
            return 0.0
        errors = sum(1 for s in self.tracer.spans if s.status == "ERROR")
        return errors / len(self.tracer.spans)
    
    def report(self) -> str:
        """生成完整分析报告"""
        stats = self.tracer.stats()
        if not self.tracer.spans:
            return "无 trace 数据"
        
        lines = [
            "=" * 70,
            "ForgeMind Trace 分析报告",
            "=" * 70,
            f"Spans: {stats['n_spans']}",
            f"Traces: {stats['n_traces']}",
            f"Avg duration: {stats['avg_duration_ms']:.2f}ms",
            f"Max duration: {stats['max_duration_ms']:.2f}ms",
            f"Status: {stats['by_status']}",
            f"Error rate: {self.error_rate():.1%}",
            "",
            "Top 5 瓶颈(按耗时):",
        ]
        
        for i, b in enumerate(self.find_bottlenecks(5), 1):
            lines.append(f"  {i}. {b['name']} — {b['duration_ms']:.1f}ms")
        
        lines.extend(["", "按名字聚合:"])
        for name, g in self.group_by_name().items():
            lines.append(f"  {name}: count={g['count']}, avg={g['avg_ms']:.1f}ms, max={g['max_ms']:.1f}ms")
        
        lines.append("=" * 70)
        return "\n".join(lines)


class TraceVisualizer:
    """生成简单的 HTML 可视化(Trace 时间轴)"""
    
    def __init__(self, tracer: Tracer):
        self.tracer = tracer
    
    def to_html(self, path: str, trace_id: Optional[str] = None):
        """生成 trace 时间轴 HTML"""
        if trace_id:
            spans = self.tracer.get_trace(trace_id)
        else:
            spans = self.tracer.spans
        
        if not spans:
            return None
        
        # 计算时间范围
        min_ts = min(s.start_time for s in spans)
        max_ts = max(s.start_time + s.duration_ms / 1000 for s in spans)
        duration = max_ts - min_ts
        
        # 按 trace 分组
        traces = {}
        for s in spans:
            if s.trace_id not in traces:
                traces[s.trace_id] = []
            traces[s.trace_id].append(s)
        
        html = ["""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>ForgeMind Trace 可视化</title>
<style>
body { font-family: monospace; background: #0a0a0a; color: #e5e5e5; padding: 20px; }
.trace { background: #1a1a1a; padding: 16px; margin-bottom: 16px; border-radius: 8px; }
.trace-title { color: #22c55e; margin-bottom: 12px; }
.span-row { display: flex; align-items: center; height: 24px; margin-bottom: 4px; }
.span-label { width: 240px; font-size: 12px; }
.span-bar { height: 18px; border-radius: 3px; position: relative; }
.span-duration { font-size: 10px; color: #888; margin-left: 8px; }
.span-error { background: #ef4444 !important; }
.span-ok { background: #22c55e; }
</style>
</head>
<body>
<h1>📊 ForgeMind Trace 可视化</h1>"""]
        
        for tid, trace_spans in traces.items():
            html.append(f'<div class="trace">')
            html.append(f'<div class="trace-title">Trace: {tid[:16]} ({len(trace_spans)} spans)</div>')
            
            for s in sorted(trace_spans, key=lambda x: x.start_time):
                offset = ((s.start_time - min_ts) / duration * 100) if duration > 0 else 0
                width = (s.duration_ms / 1000 / duration * 100) if duration > 0 else 0
                status_class = "span-error" if s.status == "ERROR" else "span-ok"
                
                html.append(f'<div class="span-row">')
                html.append(f'<div class="span-label">{s.name}</div>')
                html.append(f'<div class="span-bar {status_class}" style="margin-left: {offset}%; width: {width}%;"></div>')
                html.append(f'<div class="span-duration">{s.duration_ms:.1f}ms</div>')
                html.append(f'</div>')
            
            html.append(f'</div>')
        
        html.append("</body></html>")
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text("\n".join(html))
        return path