# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""工具输出必须是 JavaScript 能解析的 JSON

当初的岔子:pandas 从带 NULL 的列里取出来的空值是 NaN,`json.dumps` 默认
把它写成 `NaN` —— 那不是合法 JSON。Python 自己的 `json.loads` 会容忍它,
**JavaScript 的 JSON.parse 直接抛错**。于是桌面端拿到的是一段好数据,
却报"组合数据不是可解析的 JSON",界面上写着"取数失败"。

这个错在纯 Python 侧永远测不出来:自己读自己写的东西,永远读得回来。
所以这里按 JavaScript 的规则来判 —— `json.loads` 带 `parse_constant`
钩子,遇到 NaN / Infinity 直接报错,和 JSON.parse 一个脾气。
"""

from __future__ import annotations

import json
import math

import pytest

from forgemind.core.data.storage import DuckDBStorage, load_latest_decisions
from forgemind.mcp.server import _dumps, _json_safe


def _parse_like_javascript(text: str):
    """按 JavaScript 的 JSON.parse 规则解析:NaN / Infinity 一律算错。"""
    def _reject(constant: str):
        raise ValueError(f"JSON.parse 不接受 {constant}")

    return json.loads(text, parse_constant=_reject)


class TestJsonSafe:
    def test_nan_becomes_null(self):
        assert _json_safe(float("nan")) is None
        assert _json_safe(float("inf")) is None
        assert _json_safe(float("-inf")) is None

    def test_normal_numbers_untouched(self):
        assert _json_safe(1.5) == 1.5
        assert _json_safe(0) == 0

    def test_nested_structures_are_cleaned(self):
        payload = {"a": [float("nan"), {"b": float("inf")}], "c": {"d": [1.0, float("nan")]}}
        cleaned = _json_safe(payload)
        assert cleaned["a"][0] is None
        assert cleaned["a"][1]["b"] is None
        assert cleaned["c"]["d"] == [1.0, None]

    def test_dumps_output_is_parsable_by_javascript_rules(self):
        text = _dumps({"x": float("nan"), "y": [float("inf")]})
        parsed = _parse_like_javascript(text)
        assert parsed == {"x": None, "y": [None]}


class TestDecisionVoteMissing:
    """空 vote(数据源没接上)必须是 None,不能是 NaN"""

    @pytest.fixture
    def seeded(self) -> None:
        with DuckDBStorage() as db:
            db.execute(
                "CREATE TABLE portfolio_decision ("
                "snapshot_id VARCHAR, agent VARCHAR, vote VARCHAR, score DOUBLE, "
                "confidence DOUBLE, thesis VARCHAR, evidence VARCHAR)"
            )
            db.execute(
                "INSERT INTO portfolio_decision VALUES "
                "('snap_x', 'Fundamentals', NULL, 0, 0, 'unavailable | 未接入基本面数据源', NULL),"
                "('snap_x', 'Technical', 'buy', 3.62, 0.725, 'MA5 上穿 MA20', NULL)"
            )

    def test_missing_vote_reads_back_as_none(self, seeded: None):
        rows = load_latest_decisions()
        by_agent = {r["agent"]: r for r in rows}
        assert by_agent["Fundamentals"]["vote"] is None
        assert by_agent["Technical"]["vote"] == "buy"

    def test_missing_vote_is_not_a_float_nan(self, seeded: None):
        """pandas 会把带 NULL 的 VARCHAR 列变成 float64,空值就是 NaN"""
        rows = load_latest_decisions()
        for row in rows:
            vote = row["vote"]
            if vote is not None:
                assert not (isinstance(vote, float) and math.isnan(vote))

    def test_decisions_serialize_to_javascript_parsable_json(self, seeded: None):
        rows = load_latest_decisions()
        text = _dumps({"decisions": rows})
        parsed = _parse_like_javascript(text)
        votes = {d["agent"]: d["vote"] for d in parsed["decisions"]}
        assert votes["Fundamentals"] is None
        assert votes["Technical"] == "buy"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
