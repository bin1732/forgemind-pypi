# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""真 json"""
import json
import pytest
import decimal
import datetime
import uuid
import base64
import tempfile
import os

def test_json_round_trip_basic():
    data = {"null": None, "bool": True, "int": 42, "float": 3.14, "string": "hello", "empty_list": [], "empty_dict": {}}
    s = json.dumps(data)
    assert json.loads(s) == data

def test_json_unicode_emoji():
    data = {"中文": "测试", "emoji": "🎉"}
    s1 = json.dumps(data)
    assert "\\u" in s1
    s2 = json.dumps(data, ensure_ascii=False)
    assert "中文" in s2
    assert json.loads(s2) == data

def test_json_indent_sort_keys():
    data = {"b": 2, "a": 1, "c": {"z": 26, "y": 25}}
    s = json.dumps(data, indent=2, sort_keys=True)
    assert s.index('"a"') < s.index('"b"') < s.index('"c"')
    assert s.index('"y"') < s.index('"z"')

def test_json_separators():
    data = {"a": 1, "b": [1, 2, 3]}
    s_compact = json.dumps(data, separators=(",", ":"))
    assert " " not in s_compact

def test_json_custom_encoder_datetime():
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime.datetime):
                return obj.isoformat()
            if isinstance(obj, decimal.Decimal):
                return float(obj)
            return super().default(obj)
    data = {"dt": datetime.datetime(2026, 10, 13, 15, 0, 0), "dec": decimal.Decimal("3.14")}
    s = json.dumps(data, cls=DateTimeEncoder)
    loaded = json.loads(s)
    assert loaded["dt"] == "2026-10-13T15:00:00"
    assert abs(loaded["dec"] - 3.14) < 0.001

def test_json_object_hook():
    def as_complex(d):
        if "__complex__" in d:
            return complex(d["real"], d["imag"])
        return d
    s = '{"real": 1, "imag": 2, "__complex__": true}'
    assert json.loads(s, object_hook=as_complex) == 1 + 2j

def test_json_object_pairs_hook():
    loaded = json.loads('{"a": 1, "b": 2}', object_pairs_hook=list)
    assert loaded == [("a", 1), ("b", 2)]

def test_json_parse_float_str():
    loaded = json.loads('{"price": 0.1}', parse_float=decimal.Decimal)
    assert loaded["price"] == decimal.Decimal("0.1")

def test_json_stream_dump_load():
    data = [{"id": i} for i in range(100)]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = f.name
        for item in data:
            json.dump(item, f)
            f.write("\n")
    try:
        loaded = []
        with open(path) as f:
            for line in f:
                loaded.append(json.loads(line))
        assert loaded == data
    finally:
        os.unlink(path)

def test_json_invalid_raises():
    with pytest.raises(json.JSONDecodeError):
        json.loads("{not valid}")

def test_json_nan_infinity_allowed():
    s = json.dumps({"x": float("inf")})
    assert json.loads(s)["x"] == float("inf")
    import math
    assert math.isnan(json.loads(json.dumps({"z": float("nan")}))["z"])

def test_json_allow_nan_false():
    with pytest.raises(ValueError):
        json.dumps(float("inf"), allow_nan=False)
    with pytest.raises(ValueError):
        json.dumps(float("nan"), allow_nan=False)

def test_json_nested_deep():
    data = {"a": {"b": {"c": {"d": {"e": {"f": {"g": "deep"}}}}}}}
    assert json.loads(json.dumps(data))["a"]["b"]["c"]["d"]["e"]["f"]["g"] == "deep"
