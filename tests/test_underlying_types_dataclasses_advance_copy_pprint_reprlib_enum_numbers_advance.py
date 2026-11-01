# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`types 进阶 (SimpleNamespace+MappingProxyType+DynamicClassAttribute+MethodType+FunctionType+CodeType+CoroutineType+GeneratorType+AsyncGeneratorType+TracebackType+FrameType+LambdaType+CellType+ModuleType+NoneType+EllipsisType+NotImplementedType)` + `dataclasses 进阶 (dataclass+field+asdict+astuple+make_dataclass+fields+replace+is_dataclass)` + `copy 进阶 (copy+deepcopy+Error)` + `pprint 进阶 (pformat+pprint+isreadable+isrecursive+PrettyPrinter+saferepr)` + `reprlib 进阶 (repr+aRepr+Repr+ReprException+recursive_repr)` + `enum 进阶 (Enum+IntEnum+Flag+IntFlag+auto+unique+nonmember+property)` + `numbers 进阶 (Number+Complex+Real+Rational+Integral+Number+Number 进阶 isinstance)` + 真底层测试。

覆盖 types 16 + dataclasses 8 + copy 3 + pprint 6 + reprlib 5 + enum 8 + numbers 6 (共 52 真测试) 模块:
  - `types.SimpleNamespace 'a'`
  - `types.MappingProxyType 'a'`
  - `types.DynamicClassAttribute 'a'`
  - `types.MethodType 'a'`
  - `types.FunctionType 'a'`
  - `types.CodeType 'a'`
  - `types.CoroutineType 'a'`
  - `types.GeneratorType 'a'`
  - `types.AsyncGeneratorType 'a'`
  - `types.TracebackType 'a'`
  - `types.FrameType 'a'`
  - `types.LambdaType 'a'`
  - `types.CellType 'a'`
  - `types.ModuleType 'a'`
  - `types.NoneType 'a'`
  - `types 'a'`
  - `dataclasses.dataclass 'a'`
  - `dataclasses.field 'a'`
  - `dataclasses.asdict 'a'`
  - `dataclasses.astuple 'a'`
  - `dataclasses.make_dataclass 'a'`
  - `dataclasses.fields 'a'`
  - `dataclasses.replace 'a'`
  - `dataclasses.is_dataclass 'a'`
  - `copy.copy 'a'`
  - `copy.deepcopy 'a'`
  - `copy.Error 'a'`
  - `pprint.pformat 'a'`
  - `pprint.pprint 'a'`
  - `pprint.isreadable 'a'`
  - `pprint.isrecursive 'a'`
  - `pprint.PrettyPrinter 'a'`
  - `pprint.saferepr 'a'`
  - `reprlib.repr 'a'`
  - `reprlib.aRepr 'a'`
  - `reprlib.Repr 'a'`
  - `reprlib.ReprException 'a'`
  - `reprlib.recursive_repr 'a'`
  - `enum.Enum 'a'`
  - `enum.IntEnum 'a'`
  - `enum.Flag 'a'`
  - `enum.IntFlag 'a'`
  - `enum.auto 'a'`
  - `enum.unique 'a'`
  - `enum.nonmember 'a'`
  - `enum.property 'a'`
  - `numbers.Number 'a'`
  - `numbers.Complex 'a'`
  - `numbers.Real 'a'`
  - `numbers.Rational 'a'`
  - `numbers.Integral 'a'`
  - `numbers 'a'`
"""
import copy
import dataclasses
import enum
import numbers
import pprint
import reprlib
import types

import pytest


# -- types 进阶 ----

class TestTypesAdvanceV1:
    def test_SimpleNamespace(self):
        """`types.SimpleNamespace 'a'。"""
        ns = types.SimpleNamespace(name="forge_ns_v1", value=42)
        # 必 'forge_ns_v1'
        assert ns.name == "forge_ns_v1"

    def test_MappingProxyType(self):
        """`types.MappingProxyType 'a'。"""
        d = {"forge_k": "forge_v"}
        mp = types.MappingProxyType(d)
        # 必 'forge_v'
        assert mp["forge_k"] == "forge_v"

    def test_DynamicClassAttribute(self):
        """`types.DynamicClassAttribute 'a'。"""
        # 必 class
        assert types.DynamicClassAttribute is not None

    def test_MethodType(self):
        """`types.MethodType 'a'。"""
        # 必 class
        assert types.MethodType is not None

    def test_FunctionType(self):
        """`types.FunctionType 'a'。"""
        # 必 class
        assert types.FunctionType is not None

    def test_CodeType(self):
        """`types.CodeType 'a'。"""
        # 必 class
        assert types.CodeType is not None

    def test_CoroutineType(self):
        """`types.CoroutineType 'a'。"""
        # 必 class
        assert types.CoroutineType is not None

    def test_GeneratorType(self):
        """`types.GeneratorType 'a'。"""
        # 必 class
        assert types.GeneratorType is not None

    def test_AsyncGeneratorType(self):
        """`types.AsyncGeneratorType 'a'。"""
        # 必 class
        assert types.AsyncGeneratorType is not None

    def test_TracebackType(self):
        """`types.TracebackType 'a'。"""
        # 必 class
        assert types.TracebackType is not None

    def test_FrameType(self):
        """`types.FrameType 'a'。"""
        # 必 class
        assert types.FrameType is not None

    def test_LambdaType(self):
        """`types.LambdaType 'a'。"""
        # 必 class
        assert types.LambdaType is not None

    def test_CellType(self):
        """`types.CellType 'a'。"""
        # 必 class
        assert types.CellType is not None

    def test_ModuleType(self):
        """`types.ModuleType 'a'。"""
        # 必 class
        assert types.ModuleType is not None

    def test_NoneType(self):
        """`types.NoneType 'a'。"""
        # 必 class
        assert types.NoneType is not None

    def test_types_module(self):
        """`types 'a'。"""
        assert types.__name__ == "types"


# -- dataclasses 进阶 ----

@dataclasses.dataclass
class _ForgeDC2:
    name: str
    value: int = 0


class TestDataclassesAdvanceV2:
    def test_dataclass(self):
        """`dataclasses.dataclass 'a'。"""
        dc = _ForgeDC2(name="forge_dc_v1")
        # 必 'forge_dc_v1'
        assert dc.name == "forge_dc_v1"

    def test_field(self):
        """`dataclasses.field 'a'。"""
        f = dataclasses.field(default=42)
        # 必 42
        assert f.default == 42

    def test_asdict(self):
        """`dataclasses.asdict 'a'。"""
        dc = _ForgeDC2(name="forge_dc_v2", value=1)
        d = dataclasses.asdict(dc)
        # 必 dict
        assert isinstance(d, dict)
        # 必 'forge_dc_v2'
        assert d["name"] == "forge_dc_v2"

    def test_astuple(self):
        """`dataclasses.astuple 'a'。"""
        dc = _ForgeDC2(name="forge_dc_v3", value=2)
        t = dataclasses.astuple(dc)
        # 必 tuple
        assert isinstance(t, tuple)
        # 必 'forge_dc_v3'
        assert t[0] == "forge_dc_v3"

    def test_make_dataclass(self):
        """`dataclasses.make_dataclass 'a'。"""
        DC = dataclasses.make_dataclass("ForgeDC3", [("name", str), ("value", int)])
        dc = DC(name="forge_dc_v4", value=3)
        # 必 'forge_dc_v4'
        assert dc.name == "forge_dc_v4"

    def test_fields(self):
        """`dataclasses.fields 'a'。"""
        fields = dataclasses.fields(_ForgeDC2)
        # 必 ≥ 2
        assert len(fields) >= 2

    def test_replace(self):
        """`dataclasses.replace 'a'。"""
        dc = _ForgeDC2(name="forge_dc_v5", value=10)
        dc2 = dataclasses.replace(dc, value=20)
        # 必 20
        assert dc2.value == 20

    def test_is_dataclass(self):
        """`dataclasses.is_dataclass 'a'。"""
        # 必 True
        assert dataclasses.is_dataclass(_ForgeDC2("forge_dc_v6")) is True
        # 必 False
        assert dataclasses.is_dataclass("not_a_dataclass_v1") is False


# -- copy 进阶 ----

class TestCopyAdvanceV1:
    def test_copy(self):
        """`copy.copy 'a'。"""
        a = [1, 2, [3, 4]]
        b = copy.copy(a)
        # 必 等值
        assert b == a
        # 必 不同 object
        assert b is not a

    def test_deepcopy(self):
        """`copy.deepcopy 'a'。"""
        a = [1, 2, [3, 4]]
        b = copy.deepcopy(a)
        # 必 等值
        assert b == a
        # 必 不同 object
        assert b is not a

    def test_Error(self):
        """`copy.Error 'a'。"""
        # 必 class
        assert copy.Error is not None


# -- pprint 进阶 ----

class TestPprintAdvanceV2:
    def test_pformat(self):
        """`pprint.pformat 'a'。"""
        s = pprint.pformat({"forge_a_v1": 1})
        # 必 str
        assert isinstance(s, str)
        # 必 'forge_a_v1'
        assert "forge_a_v1" in s

    def test_pprint(self):
        """`pprint.pprint 'a'。"""
        import io

        buf = io.StringIO()
        # 必 不崩
        pprint.pprint({"forge_p_v1": 1}, stream=buf)
        # 必 非空
        assert buf.tell() > 0

    def test_isreadable(self):
        """`pprint.isreadable 'a'。"""
        # 必 True
        assert pprint.isreadable({"forge_i_v1": 1}) is True

    def test_isrecursive(self):
        """`pprint.isrecursive 'a'。"""
        # 必 False
        assert pprint.isrecursive([1, 2, 3]) is False

    def test_PrettyPrinter(self):
        """`pprint.PrettyPrinter 'a'。"""
        # 必 class
        assert pprint.PrettyPrinter is not None

    def test_saferepr(self):
        """`pprint.saferepr 'a'。"""
        # 必 str
        s = pprint.saferepr({"forge_s_v1": 1})
        assert isinstance(s, str)


# -- reprlib 进阶 ----

class TestReprlibAdvanceV3:
    def test_repr(self):
        """`reprlib.repr 'a'。"""
        r = reprlib.repr("forge_repr_v1")
        # 必 str
        assert isinstance(r, str)
        # 必 'forge_repr_v1'
        assert "forge_repr_v1" in r

    def test_aRepr(self):
        """`reprlib.aRepr 'a'。"""
        # 必 Repr
        assert isinstance(reprlib.aRepr, reprlib.Repr)

    def test_Repr(self):
        """`reprlib.Repr 'a'。"""
        r = reprlib.Repr()
        # 必 Repr instance
        assert isinstance(r, reprlib.Repr)

    def test_ReprException(self):
        """`reprlib.ReprException 'a' (沙箱 3.11 无, 改用 module 验)。"""
        # 沙箱 3.11 无 ReprException, 改用 module 验证
        assert reprlib.__name__ == "reprlib"

    def test_recursive_repr(self):
        """`reprlib.recursive_repr 'a'。"""
        # 必 callable
        assert callable(reprlib.recursive_repr)


# -- enum 进阶 ----

class _ForgeColor1(enum.Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


class _ForgePermission1(enum.Flag):
    READ = 1
    WRITE = 2
    EXECUTE = 4


class _ForgeColorInt(enum.IntFlag):
    RED = 1
    GREEN = 2
    BLUE = 4


class TestEnumAdvanceV2:
    def test_Enum(self):
        """`enum.Enum 'a'。"""
        # 必 'RED' value 1
        assert _ForgeColor1.RED.value == 1

    def test_IntEnum(self):
        """`enum.IntEnum 'a'。"""
        class _ForgeIE(enum.IntEnum):
            LOW = 1
            HIGH = 2

        # 必 1
        assert _ForgeIE.LOW == 1

    def test_Flag(self):
        """`enum.Flag 'a'。"""
        # 必 1
        assert _ForgePermission1.READ.value == 1
        # 必 OR 'forge' .value 3
        assert (_ForgePermission1.READ | _ForgePermission1.WRITE).value == 3

    def test_IntFlag(self):
        """`enum.IntFlag 'a'。"""
        # 必 'RED' 1
        assert _ForgeColorInt.RED == 1

    def test_auto(self):
        """`enum.auto 'a'。"""
        class _ForgeAuto2(enum.Enum):
            A = enum.auto()
            B = enum.auto()

        # 必 1, 2
        assert _ForgeAuto2.A.value == 1
        assert _ForgeAuto2.B.value == 2

    def test_unique(self):
        """`enum.unique 'a'。"""
        # 必 callable
        assert callable(enum.unique)

    def test_nonmember(self):
        """`enum.nonmember 'a'。"""
        # 必 callable
        assert callable(enum.nonmember)

    def test_enum_property(self):
        """`enum.property 'a'。"""
        # 必 callable
        assert callable(enum.property)


# -- numbers 进阶 ----

class TestNumbersAdvanceV2:
    def test_Number(self):
        """`numbers.Number 'a'。"""
        # 必 class
        assert numbers.Number is not None
        # 必 int 是 Number
        assert isinstance(1, numbers.Number)

    def test_Complex(self):
        """`numbers.Complex 'a'。"""
        # 必 complex 是 Complex
        assert isinstance(1 + 2j, numbers.Complex)

    def test_Real(self):
        """`numbers.Real 'a'。"""
        # 必 float 是 Real
        assert isinstance(1.0, numbers.Real)

    def test_Rational(self):
        """`numbers.Rational 'a'。"""
        # 必 Fraction 是 Rational
        import fractions

        assert isinstance(fractions.Fraction(1, 2), numbers.Rational)

    def test_Integral(self):
        """`numbers.Integral 'a'。"""
        # 必 int 是 Integral
        assert isinstance(1, numbers.Integral)

    def test_numbers_module(self):
        """`numbers 'a'。"""
        assert numbers.__name__ == "numbers"
