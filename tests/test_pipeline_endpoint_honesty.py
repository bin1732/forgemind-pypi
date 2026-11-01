# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`/api/pipeline/run` 必须真的跑研究流水线,并如实标注数据来源

桌面端的 `run_pipeline` 命令调的就是这个端点,而这个端点
**从头到尾没跑过研究流水线** —— 它生成确定性 GBM 随机价格,在上面算
动量,返回一组 LONG/SHORT 和自算的 confidence。

外加一层:端点声明的 `SignalOutput` 是另一套自造字段
(symbol/date/direction/confidence/signal),与 pipeline 真正产出的
signal_id/side/rationale/timestamp 毫无关系;response_model 遇到缺失字段
就填默认值 0.0,于是 confidence 恒为 0.0 —— 看起来完全正常,实际是编的。

桌面端 signal-table 面板正因为拿不到真实信号,才长期显示硬编码数据。
"""

import pytest


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from forgemind.api.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def run_result(client):
    r = client.post("/api/pipeline/run", json={
        "symbols": ["600519.SH"], "start": "2024-01-01", "end": "2024-03-01",
    })
    assert r.status_code == 200, r.text
    return r.json()


class TestSignalsComeFromTheRealPipeline:
    def test_signals_carry_the_pipelines_own_fields(self, run_result):
        """真实信号带 signal_id / side / rationale / timestamp"""
        sigs = run_result.get("signals") or []
        assert sigs, "研究流水线没有产出任何信号"
        s = sigs[0]
        for f in ("signal_id", "symbol", "side", "confidence", "rationale",
                  "timestamp"):
            assert f in s, f"信号缺少 {f}: {s}"
        assert s["rationale"], "rationale 不能是空字符串"
        assert 0.0 <= s["confidence"] <= 1.0, s["confidence"]

    def test_uses_the_full_frontend_signal_shape(self):
        """桌面端 Signal 接口就是这六个字段,必须对得上

        对不上就得在前端做映射,而映射本身就是编造的机会。
        """
        import re
        from pathlib import Path

        store = (Path(__file__).resolve().parent.parent
                 / "forgemind-ui" / "lib" / "store.ts").read_text(encoding="utf-8")
        m = re.search(r"interface Signal \{(.*?)\}", store, re.S)
        assert m, "store.ts 里找不到 Signal 接口"
        fields = set(re.findall(r"(\w+)\??:", m.group(1)))
        assert {"signal_id", "symbol", "side", "confidence", "rationale",
                "timestamp"} <= fields, f"前端 Signal 字段变了: {sorted(fields)}"


class TestDataSourceIsDeclared:
    def test_response_says_the_data_is_synthetic(self, run_result):
        assert run_result.get("data_source") == "synthetic_gbm"
        w = run_result.get("warning") or ""
        assert w, "用模拟价格就必须带警告,不能让用户以为是真实行情"
        assert "模拟" in w or "synthetic" in w.lower()

    def test_sharpe_and_drawdown_are_still_labelled(self, run_result):
        """sharpe / max_drawdown 依然来自模拟数据 —— 警告里必须提到"""
        w = run_result.get("warning") or ""
        assert "sharpe" in w.lower() and "max_drawdown" in w.lower()
