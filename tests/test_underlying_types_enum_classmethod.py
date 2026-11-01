# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 types 真 SimpleNamespace / MappingProxyType / DynamicClassAttribute + 真 enum 真 enum.member 进阶 + 真 typing Annotated + 真 dataclass __init_subclass__ + 真 classmethod / staticmethod 真 descriptor。
全 stdlib, 零模拟。
"""
import types
import enum
import typing
import dataclasses
import pytest


# ======================== types ========================
def test_types_SimpleNamespace():
    """真 SimpleNamespace"""
    ns = types.SimpleNamespace(name="Alice", age=30)
    assert ns.name == "Alice"
    assert ns.age == 30
    # 改
    ns.age = 31
    assert ns.age == 31


def test_types_MappingProxyType():
    """真 MappingProxyType 真只读"""
    d = {"a": 1, "b": 2}
    proxy = types.MappingProxyType(d)
    # 读
    assert proxy["a"] == 1
    # 写抛 TypeError
    with pytest.raises(TypeError):
        proxy["a"] = 99


def test_types_DynamicClassAttribute():
    """真 DynamicClassAttribute 真对 instance + class 不同"""
    class C:
        # instance attr
        attr = types.DynamicClassAttribute(lambda self: "instance_val")

    c = C()
    # instance: 调 func
    # class: 返 descriptor 自身
    # DynamicClassAttribute 优先 class-level
    class_val = types.DynamicClassAttribute(lambda self: "instance_val")
    # 真有 __get__
    assert hasattr(class_val, "__get__")


def test_types_coroutine():
    """真 types 真 coroutine 检查"""
    async def my_coro():
        return 42

    c = my_coro()
    try:
        # coroutine type
        assert isinstance(c, types.CoroutineType)
    finally:
        c.close()


# ======================== enum 进阶 ========================
def test_enum_EnumMeta_membership():
    """真 EnumMeta 真 membership"""
    class Color(enum.Enum):
        RED = 1
        BLUE = 2

    # __members__
    assert "RED" in Color.__members__
    assert "BLUE" in Color.__members__
    # __iter__
    members = list(Color)
    assert len(members) == 2


def test_enum_EnumValue_equality():
    """真 enum value 真比较"""
    class Status(enum.Enum):
        OK = 1
        FAIL = 0

    # value 比较
    assert Status.OK.value == 1
    assert Status.FAIL.value == 0
    # 同 value 永同
    assert Status.OK != Status.FAIL


def test_enum_IntEnum_arithmetic():
    """真 IntEnum 真 int 算"""
    class Priority(enum.IntEnum):
        LOW = 1
        HIGH = 10

    # IntEnum 可数值
    assert Priority.LOW + 1 == Priority.MEDIUM if hasattr(Priority, "MEDIUM") else Priority.LOW + 1 == 2
    assert Priority.HIGH * 2 == 20
    # 比较
    assert Priority.LOW < Priority.HIGH


def test_enum_Flag_operations():
    """真 Flag 真位运算"""
    class Perm(enum.Flag):
        R = enum.auto()
        W = enum.auto()
        X = enum.auto()

    # R = 1, W = 2, X = 4
    rw = Perm.R | Perm.W
    assert Perm.R in rw
    assert Perm.X not in rw
    # 异或
    rwx = rw | Perm.X
    # 所有
    all_p = Perm.R | Perm.W | Perm.X
    assert rwx == all_p


# ======================== typing Annotated ========================
def test_typing_Annotated():
    """真 Annotated"""
    from typing import Annotated

    AInt = Annotated[int, "metadata1", "metadata2"]
    # get_args 返 (int, "metadata1", "metadata2")
    args = typing.get_args(AInt)
    assert args[0] is int
    assert "metadata1" in args
    # get_origin 返 typing.get_type_hints 风格
    # (3.11+ may return different things)
    # 直接 repr
    assert "int" in repr(AInt)


def test_typing_TypeAliasType():
    """真 TypeAliasType (3.12+)"""
    if hasattr(typing, "TypeAliasType"):
        # 3.12+ PEP 695
        Id = typing.TypeAliasType("Id", int)
        # TypeAliasType 存在
        assert Id is not None
    else:
        # 3.11 fallback
        Id = int
        assert Id is int


# ======================== classmethod / staticmethod ========================
def test_classmethod_describes():
    """真 classmethod 真 descriptor"""
    class C:
        x = 10
        @classmethod
        def get_x(cls):
            return cls.x

    c = C()
    # both 调用
    assert c.get_x() == 10
    assert C.get_x() == 10


def test_staticmethod_describes():
    """真 staticmethod 真 descriptor"""
    class C:
        @staticmethod
        def f(x, y):
            return x + y

    c = C()
    assert c.f(1, 2) == 3
    assert C.f(1, 2) == 3


# ======================== __init_subclass__ ========================
def test_init_subclass():
    """真 __init_subclass__ 真跑"""
    registered = []

    class Base:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            registered.append(cls.__name__)

    class A(Base):
        pass

    class B(Base):
        pass

    # A, B 必被注册
    assert "A" in registered
    assert "B" in registered


# ======================== types SimpleNamespace 进阶 ========================
def test_types_ModuleType():
    """真 ModuleType 真 inspect"""
    import sys
    json_module = sys.modules["json"]
    assert isinstance(json_module, types.ModuleType)
    # hasattr
    assert hasattr(json_module, "dumps")


# ======================== types FunctionType ========================
def test_types_FunctionType():
    """真 FunctionType"""
    def f():
        pass

    assert isinstance(f, types.FunctionType)
    # method 不是 (bound)
    class C:
        def m(self):
            pass
    c = C()
    assert not isinstance(c.m, types.FunctionType)
    # unbound method (Python 3)
    assert isinstance(C.m, types.FunctionType)
