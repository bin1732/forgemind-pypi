# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""OTLP 导出的时间单位必须是纳秒

TraceExporter.to_otlp 把 startTime 写成
`int(start_time * 1_000_000)`(微秒)、duration 写成 `int(duration_ms * 1_000)`。
OTLP / OpenTelemetry 规范要求两者都是**纳秒**,于是导出的 trace 比真实时间
小 1000 倍 —— 导入 Jaeger / Tempo / Datadog 后时间轴完全错位,
而没有任何测试断言过单位,所以一直没被发现。
"""

import json

from forgemind.core.observability.trace_exporter import TraceExporter
from forgemind.core.observability.tracing import get_tracer
from forgemind.core.observability.tracing import span as _span

NS_PER_SEC = 1_000_000_000
NS_PER_MS = 1_000_000


class TestOtlpTimeUnits:
    def _one_span(self, tmp_path):
        tracer = get_tracer()
        tracer.clear()
        # 带上属性:AnyValue 包装的断言需要非空的 attributes 才有效
        with _span("unit-probe", attributes={"probe_int": 1, "probe_str": "x",
                                            "probe_float": 1.5}):
            pass
        exp = TraceExporter(tracer)
        path = tmp_path / "otlp.json"
        exp.to_otlp(str(path))
        return json.loads(path.read_text())["resourceSpans"][0]["scopeSpans"][0]["spans"][0]

    def test_start_time_is_nanoseconds(self, tmp_path):
        import time

        before = time.time()
        span = self._one_span(tmp_path)
        after = time.time()
        # startTime 应落在 [before, after] 的纳秒区间内
        assert before * NS_PER_SEC <= span["startTime"] <= after * NS_PER_SEC, (
            f"startTime={span['startTime']} 不在纳秒区间 "
            f"[{before * NS_PER_SEC:.0f}, {after * NS_PER_SEC:.0f}]"
        )

    def test_duration_is_nanoseconds(self, tmp_path):
        """一个 sleep 20ms 的 span,duration 应约 2×10^7 纳秒,而不是 2×10^4 微秒数"""
        import time

        tracer = get_tracer()
        tracer.clear()
        with _span("dur-probe"):
            time.sleep(0.02)
        exp = TraceExporter(tracer)
        path = tmp_path / "d.json"
        exp.to_otlp(str(path))
        span = json.loads(path.read_text())["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        d = span["duration"]
        # 20ms → 约 2.0e7 ns
        assert 1.0e7 < d < 5.0e7, f"duration={d} 不像纳秒(20ms 应约 2e7)"
        # 若误用微秒则约 2e4;若误用毫秒则约 20
        assert d > 1.0e5, f"duration={d} 像是微秒/毫秒而非纳秒"

    def test_span_carries_real_otlp_shape(self, tmp_path):
        """必须是**真** OTLP 字段,不是 Jaeger 的

        这个断言原先写的是 operationName / tags / logs —— 那是 Jaeger 的
        字段名,却被称作"OTLP 字段"。于是导出的载荷外层是 OTLP 封装
        (resourceSpans/scopeSpans)、内层是 Jaeger 字段,既不是合法 OTLP
        也不是合法 Jaeger,没有任何 Collector 能正确解析。
        """
        import re

        span = self._one_span(tmp_path)
        for k in ("traceId", "spanId", "name", "startTime", "duration",
                  "kind", "attributes", "status"):
            assert k in span, f"缺少 OTLP 字段 {k}"
        # Jaeger 字段不应出现在 OTLP 载荷里
        for k in ("operationName", "tags", "logs"):
            assert k not in span, f"{k} 是 Jaeger 字段,不是 OTLP 的"

        # traceId 32 个 hex(16 字节),spanId 16 个 hex(8 字节)
        assert re.fullmatch(r"[0-9a-f]{32}", span["traceId"]), span["traceId"]
        assert re.fullmatch(r"[0-9a-f]{16}", span["spanId"]), span["spanId"]

        # status 必须是 {"code": int, "message": str},不是裸字符串
        assert isinstance(span["status"], dict), span["status"]
        assert isinstance(span["status"].get("code"), int)
        assert isinstance(span["status"].get("message"), str)

        # attributes 的值必须是 AnyValue 包装。
        # 这个 span 本身带一个探针属性,保证断言不是空转 ——
        # 上一版对空列表 for 循环直接放过,注入"裸字符串属性"完全测不出来。
        attrs = span.get("attributes", [])
        assert attrs, "探针 span 应至少带一个属性,否则本测试形同虚设"
        for a in attrs:
            assert isinstance(a.get("value"), dict), (
                f"attribute 值必须是 AnyValue 包装,实际 {a}")
            assert set(a["value"]) & {"stringValue", "intValue",
                                      "doubleValue", "boolValue"}, a
