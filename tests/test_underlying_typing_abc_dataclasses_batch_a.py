# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""typing 方向的底层真实行为测试:类型提示解析、泛型参数绑定与类型构造器约束。

覆盖模块:typing(标准库类型系统)。

真实测试项:
  - `get_type_hints` 真把字符串注解解析成真实类型对象
  - `get_type_hints(..., include_extras=True)` 真保留 Annotated 元数据
  - `get_type_hints` 传入 localns 时真用局部命名空间解析前向引用
  - `get_type_hints` 遇到无法解析的注解真抛 NameError
  - 泛型别名真把 TypeVar 绑定成类型参数,且同一参数复用同一别名对象
  - 泛型子类的 `__orig_bases__` 真保留参数化后的基类
  - TypeVar 的 `__bound__` 与 `__constraints__` 真分别记录上界与取值约束
  - `Literal` 的取值集合真由 `get_args` 完整给出
  - `Literal[True]` 与 `Literal[1]` 真是两个互不相同的类型
  - `Annotated` 真保留全部元数据并暴露底层类型
  - TypedDict 真用 `__required_keys__` / `__optional_keys__` 区分必填与可选
  - `get_origin` / `get_args` 真给出 list / dict / tuple 的参数化结果
  - `get_origin` / `get_args` 真给出 Callable 的参数列表与返回类型
  - `get_origin` / `get_args` 真给出 Union 与 Optional 的成员
  - `Required` / `NotRequired` 缺失时用 skipif 跳过
  - `TypeIs` 缺失时用 skipif 跳过
"""

import collections.abc
import typing
from typing import (
    Annotated,
    Generic,
    Literal,
    TypedDict,
    TypeVar,
    get_args,
    get_origin,
    get_type_hints,
)

import pytest

T = TypeVar("T")
NumT = TypeVar("NumT", bound=int)
StrT = TypeVar("StrT", str, bytes)

_HAS_REQUIRED = hasattr(typing, "Required") and hasattr(typing, "NotRequired")
_HAS_TYPEIS = hasattr(typing, "TypeIs")

# `typing.Union` 与 PEP 604 的 `int | str` 是两种不同的类型对象:
# 前者的 get_origin 返回 typing.Union,后者返回 types.UnionType。
# 本组用例要验证的正是 typing.Union 的解析结果,因此保留 typing 写法。
_UNION_ALIAS = typing.Union[int, str]  # noqa: UP007
_OPTIONAL_ALIAS = typing.Optional[int]  # noqa: UP045


# 泛型基类刻意用 TypeVar + Generic[T] 的传统写法:本组用例验证的正是
# 这套写法下 `__parameters__` / `__orig_bases__` 的绑定语义。
class Box(Generic[T]):  # noqa: UP046
    """泛型容器:把类型参数 T 绑定到实例上。"""

    def __init__(self, value: T) -> None:
        self.value = value


class IntBox(Box[int]):
    """把基类参数化为 int 的具体子类。"""


class _Tagged:
    """带 Annotated 注解的类。"""

    plain: int
    tagged: Annotated[int, "meta", 42]


class _MovieBase(TypedDict):
    """必填键的 TypedDict。"""

    name: str


class _MovieExtended(_MovieBase, total=False):
    """在必填键基础上追加可选键的 TypedDict。"""

    year: int


def test_get_type_hints_resolves_annotations_to_real_type_objects() -> None:
    """`get_type_hints` 真把 "str" / "list[int]" / "int | None" 解析成真实类型对象。"""

    class Sample:
        a: int
        b: "str"
        c: "list[int]"
        d: "int | None"

    hints = get_type_hints(Sample)

    assert hints == {"a": int, "b": str, "c": list[int], "d": int | None}
    assert hints["b"] is str
    assert hints["c"] == list[int]
    assert hints["d"] == int | None


def test_get_type_hints_include_extras_preserves_annotated_metadata() -> None:
    """默认解析剥掉 Annotated,`include_extras=True` 时元数据原样保留。"""
    stripped = get_type_hints(_Tagged)
    kept = get_type_hints(_Tagged, include_extras=True)

    assert stripped["tagged"] is int
    assert stripped["plain"] is int
    assert kept["tagged"] == Annotated[int, "meta", 42]
    assert kept["tagged"].__metadata__ == ("meta", 42)
    assert kept["tagged"].__origin__ is int


def test_get_type_hints_uses_localns_to_resolve_forward_reference() -> None:
    """`localns` 提供的名字真被用于解析函数返回注解里的前向引用。"""

    class LocalOnly:
        pass

    def handler() -> "LocalOnly":
        raise NotImplementedError

    hints = get_type_hints(handler, localns={"LocalOnly": LocalOnly})

    assert hints == {"return": LocalOnly}
    assert hints["return"] is LocalOnly


def test_get_type_hints_raises_name_error_on_unresolvable_annotation() -> None:
    """注解里的名字不存在时,`get_type_hints` 真抛 NameError 并点名该名字。"""

    def broken() -> "NeverDefinedName":  # noqa: F821
        raise NotImplementedError

    with pytest.raises(NameError, match="NeverDefinedName"):
        get_type_hints(broken)


def test_generic_alias_binds_typevar_to_type_parameter() -> None:
    """`Box[int]` 真把 TypeVar 绑定成类型参数,并复用同一个别名对象。"""
    alias = Box[int]

    assert alias.__origin__ is Box
    assert alias.__args__ == (int,)
    assert Box.__parameters__ == (T,)
    assert alias is Box[int]


def test_generic_subclass_keeps_parameterized_base_in_orig_bases() -> None:
    """泛型子类的 `__orig_bases__` 真保留参数化后的基类 `Box[int]`。"""
    assert IntBox.__orig_bases__ == (Box[int],)
    assert Box.__orig_bases__ == (Generic[T],)
    assert IntBox.__mro__[:3] == (IntBox, Box, Generic)


def test_typevar_bound_is_recorded_and_constraints_stay_empty() -> None:
    """带 bound 的 TypeVar 真把上界记进 `__bound__`,且 `__constraints__` 为空。"""
    assert NumT.__bound__ is int
    assert NumT.__constraints__ == ()
    assert NumT.__name__ == "NumT"
    assert NumT.__covariant__ is False
    assert NumT.__contravariant__ is False


def test_typevar_constraints_are_recorded_as_tuple() -> None:
    """带取值约束的 TypeVar 真把约束记成 `__constraints__` 元组,且没有上界。"""
    assert StrT.__constraints__ == (str, bytes)
    assert StrT.__bound__ is None
    assert StrT.__name__ == "StrT"


def test_literal_get_args_exposes_allowed_values() -> None:
    """`Literal` 的取值集合真由 `get_args` 原样给出,`get_origin` 指向 Literal。"""
    assert get_origin(Literal["a", "b"]) is Literal
    assert get_args(Literal["a", "b"]) == ("a", "b")
    assert get_origin(Literal[1, 2]) is Literal
    assert get_args(Literal[1, 2]) == (1, 2)


def test_literal_bool_and_int_literals_are_distinct_types() -> None:
    """`Literal[True]` 与 `Literal[1]` 真是两个不同的类型,取值仍是原值。"""
    assert Literal[True] == Literal[True]
    assert Literal[True] != Literal[1]
    assert get_args(Literal[True]) == (True,)
    assert get_args(Literal[1]) == (1,)


def test_annotated_exposes_metadata_tuple_and_origin() -> None:
    """`Annotated` 真保留全部元数据,`__origin__` 指向底层类型。"""
    tagged = Annotated[int, "meta", 42]

    assert tagged.__metadata__ == ("meta", 42)
    assert tagged.__origin__ is int
    assert get_origin(tagged) is typing.Annotated
    assert get_args(tagged) == (int, "meta", 42)


def test_typeddict_splits_required_and_optional_keys() -> None:
    """TypedDict 真把必填键放进 `__required_keys__`,把可选键放进 `__optional_keys__`。"""
    assert _MovieBase.__required_keys__ == frozenset({"name"})
    assert _MovieBase.__optional_keys__ == frozenset()
    assert _MovieExtended.__required_keys__ == frozenset({"name"})
    assert _MovieExtended.__optional_keys__ == frozenset({"year"})


def test_typeddict_get_type_hints_returns_declared_types() -> None:
    """TypedDict 的 `get_type_hints` 真返回声明的类型,`__total__` 反映必填策略。"""
    assert get_type_hints(_MovieBase) == {"name": str}
    assert get_type_hints(_MovieExtended) == {"name": str, "year": int}
    assert _MovieBase.__annotations__ == {"name": str}
    assert _MovieBase.__total__ is True
    assert _MovieExtended.__total__ is False


def test_get_origin_and_args_for_list_and_dict_aliases() -> None:
    """`get_origin` / `get_args` 真给出 list / dict / tuple 的参数化结果。"""
    assert get_origin(list[int]) is list
    assert get_args(list[int]) == (int,)
    assert get_origin(dict[str, int]) is dict
    assert get_args(dict[str, int]) == (str, int)
    assert get_origin(tuple[int, ...]) is tuple
    assert get_args(tuple[int, ...]) == (int, Ellipsis)


def test_get_origin_and_args_for_callable_alias() -> None:
    """`Callable[[int, str], bool]` 真解出参数列表与返回类型。"""
    alias = collections.abc.Callable[[int, str], bool]

    assert get_origin(alias) is collections.abc.Callable
    assert get_args(alias) == ([int, str], bool)
    assert get_origin(typing.Callable[[int, str], bool]) is collections.abc.Callable
    assert get_args(typing.Callable[[int, str], bool]) == ([int, str], bool)


def test_get_origin_and_args_for_union_and_optional() -> None:
    """Union 与 Optional 真解出成员类型,Optional 的成员含 NoneType。"""
    assert get_origin(_UNION_ALIAS) is typing.Union
    assert get_args(_UNION_ALIAS) == (int, str)
    assert get_origin(_OPTIONAL_ALIAS) is typing.Union
    assert get_args(_OPTIONAL_ALIAS) == (int, type(None))
    assert get_origin(int | str) is not typing.Union
    assert get_origin(int | None) is not typing.Union


@pytest.mark.skipif(not _HAS_REQUIRED, reason="Required/NotRequired 需要 Python 3.11+")
def test_typeddict_required_notrequired_markers_split_keys() -> None:
    """`Required` / `NotRequired` 真把带标记的键分别算进必填与可选集合。"""

    class Movie(TypedDict):
        name: str
        year: typing.Required[int]
        rating: typing.NotRequired[float]

    assert Movie.__required_keys__ == frozenset({"name", "year"})
    assert Movie.__optional_keys__ == frozenset({"rating"})
    assert get_type_hints(Movie) == {"name": str, "year": int, "rating": float}


@pytest.mark.skipif(not _HAS_TYPEIS, reason="TypeIs 需要 Python 3.13+")
def test_typeis_marks_narrowing_annotation() -> None:
    """`TypeIs[int]` 真构造出类型收窄注解,repr 里带 TypeIs 与目标类型。"""
    alias = typing.TypeIs[int]

    assert alias.__class__.__name__ == "TypeIsType"
    assert "TypeIs" in repr(alias)
    assert "int" in repr(alias)
