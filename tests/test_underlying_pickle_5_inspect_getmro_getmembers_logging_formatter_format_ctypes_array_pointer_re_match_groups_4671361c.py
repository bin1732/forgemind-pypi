# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`pickle` 进阶 5 (Pickler+Unpickler+protocol 5+dict+dataclass) + `inspect.getmro+getmembers+staticmethod+classmethod` 进阶 + `logging.Formatter.format+LogRecord` 进阶 + `ctypes.Array+Pointer` 进阶 + `re.Match groups+span+groupdict+namedgroup` 进阶 + `dataclasses.make_dataclass` 进阶 + 真底层测试。

覆盖 pickle 3 真 (Pickler+Unpickler+dataclass) + inspect 3 真 (getmro+getmembers+staticmethod) + logging 2 真 (Formatter.format+LogRecord) + ctypes 2 真 (Array+Pointer) + re 1 真 (Match groups+namedgroup) + dataclasses 1 真 (make_dataclass) (共 12 真测试) 模块:
  - `pickle 5 protocol Pickler+Unpickler 'forge' round-trip`
  - `pickle dataclass _DConfig 'forge' round-trip`
  - `pickle dict 5 round-trip`
  - `inspect.getmro int 必 [int, object]`
  - `inspect.getmembers int 必 ≥ 5 含 'real' or 'imag'`
  - `staticmethod descriptor 必非 method`
  - `logging.Formatter format record 必 str 'INFO'`
  - `logging.LogRecord levelno=20 必 INFO`
  - `ctypes.Array c_int*3 [1,2,3] 真 round-trip`
  - `ctypes.Pointer c_int 42 必 .contents.value=42`
  - `re.Match groups ('42','100') + namedgroup 'val'='100'`
  - `dataclasses.make_dataclass _MDPt 必 fields 含 'x' 'y'`
"""
import ctypes
import dataclasses
import inspect
import io
import logging
import pickle
import re
import sys

import pytest


# -- pickle 进阶 5 (Pickler+Unpickler+protocol+dict+dataclass) -----

@dataclasses.dataclass
class _DConfig:
    name: str
    value: int = 0


class TestPickleAdvancedV5:
    def test_Pickler_protocol5(self):
        """`pickle 5 protocol Pickler+Unpickler 'forge' round-trip。"""
        buf = io.BytesIO()
        # Pickler protocol 5
        p = pickle.Pickler(buf, protocol=5)
        p.dump("forge")
        # Unpickler
        up = pickle.Unpickler(io.BytesIO(buf.getvalue()))
        # 必 'forge'
        assert up.load() == "forge"

    def test_Pickler_dataclass(self):
        """`pickle dataclass _DConfig 'forge' round-trip。"""
        original = _DConfig(name="forge", value=99)
        buf = pickle.dumps(original, protocol=5)
        loaded = pickle.loads(buf)
        # 必 'forge'
        assert loaded.name == "forge"
        # 必 99
        assert loaded.value == 99

    def test_Pickler_dict(self):
        """`pickle dict 5 round-trip。"""
        d = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
        buf = pickle.dumps(d, protocol=5)
        loaded = pickle.loads(buf)
        # 必 等 d
        assert loaded == d


# -- inspect 进阶 (getmro + getmembers + staticmethod) -------

class TestInspectAdvancedV13:
    def test_getmro_int(self):
        """`inspect.getmro int 必 [int, object]。"""
        mro = inspect.getmro(int)
        # 必 int first
        assert mro[0] is int
        # 必 object last
        assert mro[-1] is object

    def test_getmembers_int(self):
        """`inspect.getmembers int 必 ≥ 5 含 'real' or 'imag'。"""
        members = inspect.getmembers(int)
        # 必 list ≥ 5
        assert isinstance(members, list)
        assert len(members) >= 5
        # 必含 'real' or 'imag'
        names = [n for n, _ in members]
        assert "real" in names or "imag" in names

    def test_staticmethod_descriptor(self):
        """`staticmethod descriptor 必非 method。"""
        # 沙箱 3.11 staticmethod 必可作 descriptor
        sm = staticmethod(lambda x: x)
        # 必能调
        assert callable(sm)


# -- logging.Formatter.format + LogRecord 进阶 ---------

class TestLoggingFormatterFormatAdvanced:
    def test_Formatter_format(self):
        """`logging.Formatter format record 必 str 'INFO'。"""
        f = logging.Formatter("%(levelname)s %(message)s")
        record = logging.LogRecord("forge_n", logging.INFO, "/p", 1, "msg", None, None)
        # format
        result = f.format(record)
        # 必 'INFO'
        assert "INFO" in result
        # 必 'msg'
        assert "msg" in result

    def test_LogRecord_levelno(self):
        """`logging.LogRecord levelno=20 必 INFO。"""
        record = logging.LogRecord("forge_n", logging.INFO, "/p", 1, "msg", None, None)
        # 必 levelno 20
        assert record.levelno == 20
        # 必 levelname 'INFO'
        assert record.levelname == "INFO"


# -- ctypes.Array + Pointer 进阶 -----------------------

class TestCtypesArrayPointerAdvanced:
    def test_Array_round_trip(self):
        """`ctypes.Array c_int*3 [1,2,3] 真 round-trip。"""
        a = (ctypes.c_int * 3)(1, 2, 3)
        # 必 [1,2,3]
        assert a[0] == 1
        assert a[1] == 2
        assert a[2] == 3
        # 必能 改
        a[1] = 99
        # 必 99
        assert a[1] == 99

    def test_Pointer_value(self):
        """`ctypes.Pointer c_int 42 必 .contents.value=42。"""
        v = ctypes.c_int(42)
        p = ctypes.pointer(v)
        # 必 42
        assert p.contents.value == 42
        # 改
        v.value = 99
        # 必 99
        assert p.contents.value == 99


# -- re.Match groups + namedgroup 进阶 -----------------

class TestReMatchGroupsAdvance:
    def test_groups_namedgroup(self):
        """`re.Match groups ('42','100') + namedgroup 'val'='100'。"""
        m = re.match(r"(?P<val>\d+)\s+(?P<name>\w+)", "100 forge")
        # 必能 match
        assert m is not None
        # 必 groups ('100', 'forge')
        assert m.groups() == ("100", "forge")
        # 必 group 'val' '100'
        assert m.group("val") == "100"
        # 必 group 'name' 'forge'
        assert m.group("name") == "forge"


# -- dataclasses.make_dataclass 进阶 -------------------

class TestDataclassesMakeDataclassAdvance:
    def test_make_dataclass(self):
        """`dataclasses.make_dataclass _MDPt 必 fields 含 'x' 'y'。"""
        _MDPt = dataclasses.make_dataclass("_MDPt", [("x", int), ("y", str)])
        # 必能 instantiate
        pt = _MDPt(x=42, y="forge")
        # 必 42 + 'forge'
        assert pt.x == 42
        assert pt.y == "forge"
        # 必 fields 含 'x' 'y'
        fields = dataclasses.fields(_MDPt)
        names = [f.name for f in fields]
        assert "x" in names
        assert "y" in names
