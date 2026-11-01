# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""json 模块的真实行为验证

覆盖模块:json(标准库)

真实测试项(共 18 个):
   1. dumps(sort_keys=True) 按键名字典序输出确切文本
   2. dumps(indent=2) 输出确切的多行缩进文本
   3. dumps(separators=(",", ":")) 输出确切紧凑文本
   4. dumps(ensure_ascii=True/False) 对同一段中文给出确切的两套文本
   5. dumps(default=...) 真的回调,并把 Decimal 序列化成字符串
   6. dumps 遇到 Decimal 且没有 default 时抛 TypeError,消息确切
   7. loads 解析嵌套文档得到确切的结构
   8. loads(object_hook=...) 对每一个 JSON 对象各回调一次
   9. loads(parse_float=Decimal) 得到 Decimal 数值而非 float
  10. loads(parse_int=...) 按回调结果改写整数值
  11. loads 非法 JSON 时 JSONDecodeError 给出确切的 msg/pos/lineno/colno
  12. loads 文档之后有多余内容时,错误位置指向第二段内容
  13. dumps 对 NaN/Infinity 输出非标准字面量,allow_nan=False 抛 ValueError
  14. loads(parse_constant=...) 收到 NaN/Infinity 字面量
  15. JSONDecoder.raw_decode 返回确切的值与结束下标
  16. dumps(cls=自定义编码器) 走自定义 default 分支
  17. loads(object_pairs_hook=...) 保留重复键与键序
  18. dump 写进真实文件,文件文本与 dumps 的结果逐字符一致

所有断言都比对确切字符串、确切结构或确切异常信息,不做任何伪造。
"""

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest


def test_json_dumps_sort_keys_orders_keys_ascending() -> None:
    """sort_keys=True 时键按字典序排列,输出文本为 '{"a": 1, "b": 2, "c": 3}'。"""
    payload = {"c": 3, "a": 1, "b": 2}
    assert json.dumps(payload, sort_keys=True) == '{"a": 1, "b": 2, "c": 3}'
    assert json.dumps(payload) == '{"c": 3, "a": 1, "b": 2}'


def test_json_dumps_indent_two_prints_nested_structure() -> None:
    """indent=2 时每个层级缩进两格,输出与预期多行文本逐字符一致。"""
    payload = {"a": 1, "b": [1, 2]}
    expected = '{\n  "a": 1,\n  "b": [\n    1,\n    2\n  ]\n}'
    assert json.dumps(payload, indent=2) == expected


def test_json_dumps_separators_removes_whitespace() -> None:
    """separators=(",", ":") 去掉键值两侧空格,输出 '{"a":1,"b":2}'。"""
    payload = {"a": 1, "b": 2}
    assert json.dumps(payload, separators=(",", ":")) == '{"a":1,"b":2}'
    assert json.dumps(payload, separators=(", ", ": ")) == '{"a": 1, "b": 2}'


def test_json_dumps_ensure_ascii_controls_chinese_escaping() -> None:
    """ensure_ascii=False 保留中文原字符,True 时转成 \\uXXXX 转义。"""
    payload = {"k": "中文"}
    assert json.dumps(payload, ensure_ascii=False) == '{"k": "中文"}'
    assert json.dumps(payload, ensure_ascii=True) == '{"k": "\\u4e2d\\u6587"}'


def test_json_dumps_default_callback_handles_decimal() -> None:
    """default 回调真的被调用两次,并把两个 Decimal 都转成字符串写进结果。"""
    calls: list[str] = []

    def to_text(obj: object) -> str:
        calls.append(str(obj))
        return str(obj)

    text = json.dumps({"p": Decimal("1.25"), "q": Decimal("2.5")}, default=to_text)
    assert text == '{"p": "1.25", "q": "2.5"}'
    assert calls == ["1.25", "2.5"]


def test_json_dumps_decimal_without_default_raises_type_error() -> None:
    """没有 default 时 Decimal 不可序列化,TypeError 消息指名 Decimal。"""
    with pytest.raises(
        TypeError,
        match=re.escape("Object of type Decimal is not JSON serializable"),
    ):
        json.dumps(Decimal("1"))


def test_json_loads_parses_nested_document_to_exact_structure() -> None:
    """loads 解析嵌套文档,得到键序、类型与取值都确切的结构。"""
    document = '{"name": "forge", "tags": ["a", "b"], "meta": {"n": 3, "ok": true}}'
    parsed = json.loads(document)
    assert parsed == {
        "name": "forge",
        "tags": ["a", "b"],
        "meta": {"n": 3, "ok": True},
    }
    assert list(parsed) == ["name", "tags", "meta"]
    assert parsed["meta"]["n"] == 3


def test_json_loads_object_hook_is_called_for_every_object() -> None:
    """object_hook 对内层与外层对象各回调一次,收到的键集合确切。"""
    seen: list[list[str]] = []

    def hook(obj: dict) -> dict:
        seen.append(sorted(obj))
        obj["_hooked"] = True
        return obj

    parsed = json.loads('{"a": {"b": 1}, "c": 2}', object_hook=hook)
    assert seen == [["b"], ["a", "c"]]
    assert parsed == {"a": {"b": 1, "_hooked": True}, "c": 2, "_hooked": True}


def test_json_loads_parse_float_returns_decimal_values() -> None:
    """parse_float=Decimal 时浮点字面量被解析成 Decimal,取值与字符串都确切。"""
    parsed = json.loads("[1.10, 2.5]", parse_float=Decimal)
    assert [str(value) for value in parsed] == ["1.10", "2.5"]
    assert parsed[0] == Decimal("1.10")
    assert parsed[1] == Decimal("2.5")


def test_json_loads_parse_int_rewrites_integer_values() -> None:
    """parse_int 回调的结果直接成为解析出的整数值,文本内容也随之变化。"""
    parsed = json.loads("[1, 20]", parse_int=lambda raw: int(raw) * 2)
    assert parsed == [2, 40]
    assert json.dumps(parsed) == "[2, 40]"


def test_json_decode_error_reports_exact_position_information() -> None:
    """非法 JSON 抛出的 JSONDecodeError 带有确切的 msg/pos/lineno/colno。"""
    with pytest.raises(json.JSONDecodeError) as excinfo:
        json.loads('{"a": 1,}')
    error = excinfo.value
    assert error.msg == "Expecting property name enclosed in double quotes"
    assert (error.pos, error.lineno, error.colno) == (8, 1, 9)
    assert str(error) == ("Expecting property name enclosed in double quotes: line 1 column 9 (char 8)")

    with pytest.raises(json.JSONDecodeError) as excinfo:
        json.loads("")
    error = excinfo.value
    assert error.msg == "Expecting value"
    assert (error.pos, error.lineno, error.colno) == (0, 1, 1)


def test_json_decode_error_extra_data_points_at_second_document() -> None:
    """一段 JSON 之后还有内容时,错误信息是 Extra data,位置指向第二段。"""
    with pytest.raises(json.JSONDecodeError) as excinfo:
        json.loads('  {"a": 1}\n  {"b": 2}')
    error = excinfo.value
    assert error.msg == "Extra data"
    assert (error.pos, error.lineno, error.colno) == (13, 2, 3)


def test_json_dumps_writes_non_standard_nan_literals() -> None:
    """NaN 与 Infinity 被写成非标准字面量,allow_nan=False 时抛 ValueError。"""
    assert json.dumps(float("nan")) == "NaN"
    assert json.dumps([float("inf"), float("-inf")]) == "[Infinity, -Infinity]"
    with pytest.raises(
        ValueError,
        match=re.escape("Out of range float values are not JSON compliant"),
    ):
        json.dumps(float("nan"), allow_nan=False)


def test_json_loads_parse_constant_receives_nan_literals() -> None:
    """parse_constant 回调收到 NaN/Infinity/-Infinity 三个确切字面量。"""
    seen: list[str] = []

    def capture(constant: str) -> str:
        seen.append(constant)
        return constant

    parsed = json.loads("[NaN, Infinity, -Infinity]", parse_constant=capture)
    assert seen == ["NaN", "Infinity", "-Infinity"]
    assert parsed == ["NaN", "Infinity", "-Infinity"]


def test_json_raw_decode_returns_value_and_end_index() -> None:
    """raw_decode 只解析第一个文档,返回值与结束下标都确切。"""
    decoder = json.JSONDecoder()
    value, end = decoder.raw_decode('{"a": 1} trailing')
    assert value == {"a": 1}
    assert end == 8
    assert '{"a": 1} trailing'[end:] == " trailing"


def test_json_dumps_custom_encoder_class_handles_unknown_type() -> None:
    """cls 指定自定义编码器时,未识别类型走自定义 default 分支。"""
    import decimal

    class TextEncoder(json.JSONEncoder):
        def default(self, o: object) -> str:
            return "E:" + str(o)

    text = json.dumps({"x": decimal.Decimal("2")}, cls=TextEncoder)
    assert text == '{"x": "E:2"}'


def test_json_loads_object_pairs_hook_keeps_duplicate_keys() -> None:
    """object_pairs_hook 收到原始键值对序列,重复键与先后顺序都保留。"""
    pairs = json.loads('{"b": 1, "a": 2, "b": 3}', object_pairs_hook=lambda items: items)
    assert pairs == [("b", 1), ("a", 2), ("b", 3)]


def test_json_dump_writes_exact_text_into_real_file(tmp_path: Path) -> None:
    """dump 写进真实文件后,文件文本与 dumps 的结果逐字符相同。"""
    target = tmp_path / "payload.json"
    payload = {"名称": "锻造", "数值": [1, 2]}
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    expected = json.dumps(payload, ensure_ascii=False, indent=2)
    assert target.read_text(encoding="utf-8") == expected
    assert target.read_text(encoding="utf-8") == '{\n  "名称": "锻造",\n  "数值": [\n    1,\n    2\n  ]\n}'
    assert json.loads(target.read_text(encoding="utf-8")) == payload
