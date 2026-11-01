# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 stdlib typing — dataclass + frozen + field + Enum/IntEnum/Flag + Protocol。
"""
import enum
import sys
from dataclasses import dataclass, field, fields, asdict, astuple, FrozenInstanceError, replace
from enum import Enum, IntEnum, Flag, auto
from typing import Protocol, runtime_checkable

import pytest


def test_dataclass_real_field_init():
    """dataclass 真 __init__ 接受 fields"""
    @dataclass
    class Point:
        x: float
        y: float
        z: float = 0.0

    p = Point(1.0, 2.0)
    assert p.x == 1.0
    assert p.y == 2.0
    assert p.z == 0.0
    p2 = Point(1.0, 2.0, 3.0)
    assert p2.z == 3.0


def test_dataclass_frozen_real_immutable():
    """dataclass(frozen=True) 真不可变 — 改属性抛 FrozenInstanceError"""
    @dataclass(frozen=True)
    class Const:
        x: int
        y: int

    c = Const(1, 2)
    with pytest.raises(FrozenInstanceError):
        c.x = 99


def test_dataclass_field_factory_real():
    """dataclass field(default_factory=list) 真每次新建 list"""
    @dataclass
    class Bag:
        items: list = field(default_factory=list)

    b1 = Bag()
    b2 = Bag()
    b1.items.append(1)
    # b2.items 应仍空 (不共享)
    assert b2.items == [], f"b2.items 应空, 实际 {b2.items}"


def test_dataclass_asdict_astuple_real():
    """dataclass asdict/astuple 真转 dict/tuple"""
    @dataclass
    class User:
        name: str
        age: int

    u = User("Alice", 30)
    assert asdict(u) == {"name": "Alice", "age": 30}
    assert astuple(u) == ("Alice", 30)


def test_dataclass_fields_real_introspection():
    """dataclass fields 真返 Field 列表"""
    @dataclass
    class Config:
        host: str
        port: int
        debug: bool = False

    f = fields(Config)
    assert len(f) == 3
    names = [fi.name for fi in f]
    assert names == ["host", "port", "debug"]
    types = {fi.name: fi.type for fi in f}
    assert types["port"] is int


def test_dataclass_replace_real():
    """dataclass replace 真创建新 instance (不改原)"""
    @dataclass
    class V:
        x: int
        y: int

    v1 = V(1, 2)
    v2 = replace(v1, x=99)
    assert v1.x == 1, f"原 v1.x 应 1, 实际 {v1.x}"
    assert v2.x == 99
    assert v2.y == 2  # 其他字段保留


def test_enum_real_value_uniqueness():
    """Enum 真按 value 找 member"""
    class Color(Enum):
        RED = 1
        GREEN = 2
        BLUE = 3
    assert Color(1) is Color.RED
    assert Color["RED"] is Color.RED
    assert Color.RED.value == 1


def test_intenum_real_int_compat():
    """IntEnum 真兼容 int (可参与 int 算)"""
    class Priority(IntEnum):
        LOW = 1
        MED = 5
        HIGH = 10

    assert Priority.LOW < Priority.HIGH
    assert Priority.HIGH + 1 == 11
    assert int(Priority.MED) == 5


def test_flag_real_bitwise_or():
    """Flag 真支持位或"""
    class Perm(Flag):
        READ = auto()
        WRITE = auto()
        EXEC = auto()

    rw = Perm.READ | Perm.WRITE
    assert Perm.READ in rw
    assert Perm.WRITE in rw
    assert Perm.EXEC not in rw
    # rw.value = 1 | 2 = 3
    assert rw.value == 3


def test_protocol_runtime_checkable_real():
    """@runtime_checkable Protocol 真能 isinstance"""
    @runtime_checkable
    class Drawable(Protocol):
        def draw(self) -> None: ...

    class Circle:
        def draw(self) -> None:
            pass

    class Square:
        def draw(self) -> None:
            pass

    class NotDrawable:
        pass

    assert isinstance(Circle(), Drawable)
    assert isinstance(Square(), Drawable)
    assert not isinstance(NotDrawable(), Drawable)
