# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""dataclasses 方向的底层真实行为测试:字段声明、初始化钩子与转换工具。

覆盖模块:dataclasses(标准库数据类)。

真实测试项:
  - `field` 的 default 与 default_factory 真体现在 `fields()` 上
  - `default_factory` 真为每个实例造出独立对象
  - `field` 的 metadata 真以只读 mapping 形式暴露
  - `__post_init__` 真在初始化后被调用并能改写字段
  - `__post_init__` 真收到 InitVar 参数
  - `frozen=True` 真让字段赋值抛 FrozenInstanceError
  - `frozen=True` 的数据类真可哈希且按值相等
  - InitVar 真不出现在 `fields()` 里,但留在 `__dataclass_fields__` 里
  - `asdict` 真递归把嵌套数据类转成普通字典
  - `astuple` 真递归把嵌套数据类转成普通元组
  - `fields()` 真返回带 name/type/default 等属性的 Field 对象
  - `replace` 真产出改过字段的新实例且不动原实例
  - `replace` 真能在 frozen 数据类上工作
  - `dataclass(kw_only=...)` 真禁止位置传参
  - `field(kw_only=...)` 真只让单个字段变成仅限关键字
  - `__dataclass_params__` 真暴露生成时的配置
  - `order=True` 真让数据类支持大小比较
  - `dataclasses.MISSING` 真标记没有默认值的字段
"""

import dataclasses
import inspect
from dataclasses import InitVar, asdict, astuple, dataclass, field, fields, replace

import pytest

_HAS_DATACLASS_KW_ONLY = "kw_only" in inspect.signature(dataclasses.dataclass).parameters
_HAS_FIELD_KW_ONLY = "kw_only" in inspect.signature(dataclasses.field).parameters


@dataclass
class _Profile:
    """普通数据类:一个必填字段加两个带默认值的字段。"""

    name: str
    age: int = 0
    tags: list = field(default_factory=list)


@dataclass
class _Ratio:
    """带 metadata 的数据类。"""

    name: str
    value: float = field(default=1.0, metadata={"unit": "pct"})


@dataclass
class _PostInit:
    """`__post_init__` 会改写字段的数据类。"""

    value: int
    doubled: int = 0

    def __post_init__(self) -> None:
        self.doubled = self.value * 2


@dataclass
class _WithInitVar:
    """带 InitVar 的数据类,`__post_init__` 消费该参数。"""

    length: int = 0
    raw: InitVar[str] = ""

    def __post_init__(self, raw: str) -> None:
        self.length = len(raw)


@dataclass
class _Inner:
    """嵌套用的小数据类。"""

    value: int
    label: str = "in"


@dataclass
class _Outer:
    """包含嵌套数据类与数据类列表的数据类。"""

    inner: _Inner
    items: list
    name: str = "n"


@dataclass(frozen=True)
class _Frozen:
    """不可变数据类。"""

    x: int
    y: int = 0


@dataclass(order=True)
class _Ordered:
    """开启排序比较的数据类。"""

    a: int
    b: str


def test_field_default_is_reported_by_fields() -> None:
    """`fields()` 真把字段名、默认值与工厂函数逐项报出来。"""
    profile_fields = fields(_Profile)

    assert [f.name for f in profile_fields] == ["name", "age", "tags"]
    assert profile_fields[0].default is dataclasses.MISSING
    assert profile_fields[1].default == 0
    assert profile_fields[2].default is dataclasses.MISSING
    assert profile_fields[2].default_factory is list


def test_field_default_factory_builds_new_object_per_instance() -> None:
    """`default_factory` 真为每个实例造出独立列表,互不影响。"""
    first = _Profile("a")
    second = _Profile("b")

    assert first.tags == []
    assert second.tags == []
    assert first.tags is not second.tags
    first.tags.append("x")
    assert first.tags == ["x"]
    assert second.tags == []


def test_field_metadata_is_readonly_mapping() -> None:
    """`field` 的 metadata 真以只读 mapping 暴露,写入会抛 TypeError。"""
    meta = fields(_Ratio)[1].metadata

    assert dict(meta) == {"unit": "pct"}
    assert meta["unit"] == "pct"
    with pytest.raises(TypeError, match="does not support item assignment"):
        meta["unit"] = "other"


def test_post_init_runs_after_init_and_can_mutate_fields() -> None:
    """`__post_init__` 真在字段赋值后被调用,并能改写其它字段。"""
    obj = _PostInit(3)

    assert obj.value == 3
    assert obj.doubled == 6
    assert _PostInit(5).doubled == 10


def test_post_init_receives_initvar_argument() -> None:
    """`__post_init__` 真收到 InitVar 的值,并据此改写普通字段。"""
    obj = _WithInitVar(raw="abcd")

    assert obj.length == 4
    assert vars(obj) == {"length": 4}
    assert "raw" not in vars(obj)
    assert [f.name for f in fields(_WithInitVar)] == ["length"]


def test_frozen_dataclass_rejects_attribute_assignment() -> None:
    """`frozen=True` 真让字段赋值抛 FrozenInstanceError,并说明是哪个字段。"""
    obj = _Frozen(1)

    with pytest.raises(dataclasses.FrozenInstanceError, match="cannot assign to field 'x'"):
        obj.x = 2
    assert issubclass(dataclasses.FrozenInstanceError, AttributeError)
    assert obj.x == 1


def test_frozen_dataclass_is_hashable_and_comparable() -> None:
    """`frozen=True` 的数据类真生成哈希,同值实例互相相等。"""
    assert hash(_Frozen(1, 2)) == hash(_Frozen(1, 2))
    assert _Frozen(1, 2) == _Frozen(1, 2)
    assert _Frozen(1, 2) != _Frozen(1, 3)


def test_initvar_is_hidden_from_fields_but_kept_in_dataclass_fields() -> None:
    """InitVar 伪字段真不进 `fields()`,但留在 `__dataclass_fields__` 里。"""
    initvar_field = _WithInitVar.__dataclass_fields__["raw"]

    assert [f.name for f in fields(_WithInitVar)] == ["length"]
    assert "raw" in _WithInitVar.__dataclass_fields__
    assert isinstance(initvar_field.type, InitVar)
    assert repr(initvar_field.type) == "dataclasses.InitVar[str]"
    assert initvar_field._field_type is dataclasses._FIELD_INITVAR


def test_asdict_recurses_into_nested_dataclasses() -> None:
    """`asdict` 真把嵌套数据类与列表里的数据类都转成普通字典。"""
    outer = _Outer(_Inner(1, "in"), [_Inner(2, "two")])

    assert asdict(outer) == {
        "inner": {"value": 1, "label": "in"},
        "items": [{"value": 2, "label": "two"}],
        "name": "n",
    }
    assert type(asdict(outer)["inner"]) is dict


def test_astuple_recurses_into_nested_dataclasses() -> None:
    """`astuple` 真把嵌套数据类与列表里的数据类都转成普通元组。"""
    outer = _Outer(_Inner(1, "in"), [_Inner(2, "two")])

    assert astuple(outer) == ((1, "in"), [(2, "two")], "n")
    assert type(astuple(outer)[0]) is tuple


def test_fields_exposes_field_objects_with_expected_attributes() -> None:
    """`fields()` 返回的 Field 真带 name/type/default/init/repr/compare 等属性。"""
    age_field = fields(_Profile)[1]

    assert age_field.name == "age"
    assert age_field.type is int
    assert age_field.default == 0
    assert age_field.default_factory is dataclasses.MISSING
    assert age_field.init is True
    assert age_field.repr is True
    assert age_field.compare is True


def test_replace_returns_new_instance_with_overridden_value() -> None:
    """`replace` 真产出改过字段的新实例,原实例保持不变。"""
    original = _Profile("a", 3)
    updated = replace(original, age=7)

    assert updated == _Profile("a", 7)
    assert updated is not original
    assert original.age == 3
    assert updated.name == "a"


def test_replace_works_on_frozen_dataclass() -> None:
    """`replace` 真能在 frozen 数据类上产出新实例,原实例不变。"""
    original = _Frozen(1, 2)
    updated = replace(original, x=9)

    assert updated == _Frozen(9, 2)
    assert original.x == 1
    assert updated.y == 2


@pytest.mark.skipif(
    not _HAS_DATACLASS_KW_ONLY,
    reason="dataclass(kw_only=...) 需要 Python 3.10+",
)
def test_dataclass_kw_only_forbids_positional_arguments() -> None:
    """`dataclass(kw_only=True)` 真把所有字段变成仅限关键字,位置传参被拒绝。"""

    @dataclass(kw_only=True)
    class _KwOnly:
        x: int
        y: int = 0

    assert [(f.name, f.kw_only) for f in fields(_KwOnly)] == [("x", True), ("y", True)]
    assert _KwOnly(x=1, y=2) == _KwOnly(x=1, y=2)
    with pytest.raises(TypeError, match="positional"):
        _KwOnly(1)


@pytest.mark.skipif(
    not _HAS_FIELD_KW_ONLY,
    reason="field(kw_only=...) 需要 Python 3.10+",
)
def test_field_kw_only_makes_single_field_keyword_only() -> None:
    """`field(kw_only=True)` 真只把该字段变成仅限关键字,其它字段仍可位置传参。"""

    @dataclass
    class _Mixed:
        x: int
        y: int = field(default=0, kw_only=True)

    assert [(f.name, f.kw_only) for f in fields(_Mixed)] == [("x", False), ("y", True)]
    assert _Mixed(1) == _Mixed(x=1, y=0)
    with pytest.raises(TypeError, match="positional"):
        _Mixed(1, 2)


def test_dataclass_params_expose_generated_configuration() -> None:
    """`__dataclass_params__` 真暴露 init/repr/eq/order/frozen 等生成配置。"""
    frozen_params = _Frozen.__dataclass_params__
    plain_params = _Profile.__dataclass_params__

    assert frozen_params.frozen is True
    assert frozen_params.eq is True
    assert frozen_params.order is False
    assert frozen_params.init is True
    assert frozen_params.repr is True
    assert plain_params.frozen is False
    assert plain_params.unsafe_hash is False


def test_order_true_enables_ordered_comparison() -> None:
    """`order=True` 真让数据类支持按字段顺序比较与排序。"""
    assert _Ordered(1, "a") < _Ordered(2, "a")
    assert _Ordered(1, "a") < _Ordered(1, "b")
    assert sorted([_Ordered(2, "b"), _Ordered(1, "a")]) == [_Ordered(1, "a"), _Ordered(2, "b")]
    assert (_Ordered(1, "a") > _Ordered(1, "a")) is False
    assert (_Ordered(1, "a") <= _Ordered(1, "a")) is True


def test_missing_sentinel_marks_field_without_default() -> None:
    """`dataclasses.MISSING` 真用来标记没有默认值的字段。"""
    profile_fields = fields(_Profile)

    assert profile_fields[0].default is dataclasses.MISSING
    assert profile_fields[2].default is dataclasses.MISSING
    assert profile_fields[1].default is not dataclasses.MISSING
    assert type(dataclasses.MISSING).__name__ == "_MISSING_TYPE"
