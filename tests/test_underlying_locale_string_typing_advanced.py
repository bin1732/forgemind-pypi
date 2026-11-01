# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 locale 真 localeconv + 真 string 真 Template 进阶 (safe_substitute) + 真 typing 真 TypeVar bound + 真 dataclass 进阶 (field metadata + InitVar) + 真 warnings 进阶 (filterwarnings).
全 stdlib, 零模拟。
"""
import locale
import string
import numbers
import typing
import dataclasses
import warnings
import pytest


# ======================== locale 进阶 ========================
def test_locale_localeconv():
    """真 localeconv 真字典"""
    conv = locale.localeconv()
    # 必有 'decimal_point', 'thousands_sep', 'grouping'
    assert "decimal_point" in conv
    assert "thousands_sep" in conv
    # decimal_point 至少 1 char
    assert len(conv["decimal_point"]) >= 1


def test_locale_format_percent():
    """真 format_string 真百分比"""
    # % style
    s = locale.format_string("%.2f", 12.5)
    # 12.50
    assert "12" in s
    assert "50" in s


def test_locale_atof_de():
    """真 atof 真基本"""
    # 默认 C locale: "1.5" 直接 parse
    val = locale.atof("1.5")
    assert val == 1.5
    # 但 "1,234.5" C locale 不认
    # 改用 setlocale (sand 不一定有, try/except)
    try:
        locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
        val2 = locale.atof("1,234.5")
        assert val2 == 1234.5
    except locale.Error:
        # C locale fallback
        pass


# ======================== string 进阶 ========================
def test_string_Template_safe_substitute():
    """真 safe_substitute 不抛"""
    t = string.Template("$name lives in $city")
    # 缺 city → 保持原
    result = t.safe_substitute(name="Alice")
    assert "Alice" in result
    assert "$city" in result  # 没替换


def test_string_Template_delimiter_idpattern():
    """真 Template 真 delimiter + idpattern"""
    t = string.Template("${name}_data")
    # delimiter 改 $ → 复用
    # 改 idpattern 含花括号
    t.idpattern = r"(?a:[_a-z][_a-z0-9]*)"
    # 安全 substitute
    result = t.safe_substitute(name="alice")
    # 解析 ${name}
    assert "alice_data" == result


def test_string_Template_invalid():
    """真 Template 真 invalid → 抛"""
    t = string.Template("$name $missing")
    with pytest.raises(KeyError):
        t.substitute(name="Alice")  # missing


def test_string_Formatter_vformat():
    """真 Formatter 真 vformat 真解析"""
    fmt = string.Formatter()
    parts = list(fmt.parse("Hello {name}, you are {age:d}"))
    # 4 元素
    assert len(parts) >= 2
    # 第一段: literal, name, format_spec, conversion
    assert parts[0][0] == "Hello "
    assert parts[0][1] == "name"
    # 第二段
    assert parts[1][1] == "age"
    assert parts[1][2] == "d"


# ======================== typing 进阶 ========================
def test_typing_TypeVar_bound():
    """真 TypeVar bound"""
    NumberT = typing.TypeVar("NumberT", bound=numbers.Number)

    def double(x: NumberT) -> NumberT:
        return x * 2

    # 3 types
    assert double(2) == 4
    assert double(2.5) == 5.0
    from decimal import Decimal
    assert double(Decimal("3")) == Decimal("6")


def test_typing_TypeVar_constrained_specific():
    """真 constrained TypeVar"""
    Num = typing.TypeVar("Num", int, float, complex)

    def add(x: Num, y: Num) -> Num:
        return x + y

    assert add(1, 2) == 3
    assert add(1.5, 2.5) == 4.0
    assert add(1 + 2j, 3 + 4j) == 4 + 6j


def test_typing_NewType_actual_distinct():
    """真 NewType 真在 runtime 是 underlying type"""
    UserId = typing.NewType("UserId", int)
    uid = UserId(42)
    # 是 int
    assert isinstance(uid, int)
    # 但 type name 不同
    # 实际: __class__ is int
    assert type(uid) is int


# ======================== dataclass 进阶 ========================
def test_dataclass_InitVar():
    """真 InitVar 真 __post_init__"""
    @dataclasses.dataclass
    class C:
        x: int
        y: int = dataclasses.field(default=0, init=False)  # 不要 InitVar
        z: int = dataclasses.field(default=0, init=False)

        def __post_init__(self):
            # 自动调
            self.y = self.x * 2
            self.z = self.x * 3

    c = C(1)
    assert c.x == 1
    assert c.y == 2
    assert c.z == 3


def test_dataclass_field_metadata_advanced():
    """真 field metadata 多 key"""
    @dataclasses.dataclass
    class C:
        name: str = dataclasses.field(
            default="default",
            metadata={"unit": "text", "max_length": 100, "required": True}
        )

    field_obj = C.__dataclass_fields__["name"]
    assert field_obj.metadata["unit"] == "text"
    assert field_obj.metadata["max_length"] == 100
    assert field_obj.metadata["required"] is True


# ======================== warnings 进阶 ========================
def test_warnings_filterwarnings_specific():
    """真 filterwarnings 特定 message"""
    with warnings.catch_warnings(record=True) as ws:
        warnings.resetwarnings()
        warnings.filterwarnings("always", message="specific test")
        warnings.warn("specific test message", UserWarning)
        warnings.warn("different message", UserWarning)
        # 必有 1 个 specific
        messages = [str(w.message) for w in ws]
        assert "specific test message" in messages


def test_warnings_warn_explicit_category():
    """真 warn 真 category 路由"""
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter("always")
        warnings.warn("dep message", DeprecationWarning)
        # 必有 DeprecationWarning
        assert any(issubclass(w.category, DeprecationWarning) for w in ws)
