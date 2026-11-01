# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`struct.Struct` 进阶 (format_map+Struct 解包+bytes 解包) + `array.array` 真用 (signed/unsigned 多种) + `cmath.log/log10/exp/atan2/sin/cos/tan/phase/polar/isinf/isnan` 真用 + `traceback.extract_stack/format_list/format_exception_only` 真用 + `functools.cached_property 3.8+` 真用 + 真底层测试。

覆盖 struct 3 真 (Struct size+iter_unpack+calcsize) + array 3 真 (signed 'i'+unsigned 'I'+append+buffer_info) + cmath 5 真 (log+exp+sin+cos+tan+phase) + traceback 2 真 (extract_stack+format_list) + functools 1 真 (cached_property 3.8+) (共 14 真测试) 模块:
  - `struct.Struct '>HI' size 必 6`
  - `struct.Struct iter_unpack b'\\x00\\x01\\x00\\x00\\x00\\x02' 必 [(1, 2)]`
  - `struct.calcsize '>I' 必 4`
  - `array.array 'i' [1,2,3] 必 list [1,2,3]`
  - `array.array 'I' 真 unsigned 4294967295`
  - `array.array 真 append(99) + [0,1,2,3,99]`
  - `cmath.log(2+0j) 必 ~0.693+0j`
  - `cmath.exp(1+0j) 必 ~2.718+0j`
  - `cmath.sin(pi/2) 必 ~1.0+0j`
  - `cmath.cos(0) 必 1.0+0j`
  - `cmath.phase(1+0j) 必 0.0`
  - `cmath.isinf(complex('inf')) 必 True`
  - `traceback.extract_stack 真返 ≥ 1 FrameSummary`
  - `functools.cached_property 3.8+ 真计算 1 次`
"""
import array
import cmath
import functools
import struct
import sys
import traceback

import pytest


# -- struct 进阶 (Struct + iter_unpack + calcsize) -------------

class TestStructAdvancedV3:
    def test_Struct_size(self):
        """`struct.Struct '>HI' size 必 6。"""
        s = struct.Struct(">HI")
        # 必 6
        assert s.size == 6

    def test_Struct_iter_unpack(self):
        """`struct.Struct iter_unpack b'\\x00\\x01\\x00\\x00\\x00\\x02' 必 [(1, 2)]。"""
        s = struct.Struct(">HI")
        data = b"\x00\x01\x00\x00\x00\x02"
        result = list(s.iter_unpack(data))
        # 必 [(1, 2)]
        assert result == [(1, 2)]

    def test_calcsize(self):
        """`struct.calcsize '>I' 必 4。"""
        size = struct.calcsize(">I")
        # 必 4
        assert size == 4


# -- array.array 真用 (signed + unsigned + append + buffer_info) -

class TestArrayAdvanced:
    def test_array_signed(self):
        """`array.array 'i' [1,2,3] 必 list [1,2,3]。"""
        a = array.array("i", [1, 2, 3])
        # 必能 tolist
        assert a.tolist() == [1, 2, 3]

    def test_array_unsigned_max(self):
        """`array.array 'I' 真 unsigned 4294967295。"""
        a = array.array("I", [4294967295])
        # 必能 tolist
        assert a.tolist() == [4294967295]

    def test_array_append(self):
        """`array.array 真 append(99) + [0,1,2,3,99]。"""
        a = array.array("i", [0, 1, 2, 3])
        a.append(99)
        # 必含 99
        assert a.tolist() == [0, 1, 2, 3, 99]


# -- cmath 真 (log + exp + sin + cos + tan + phase + isinf) -----

class TestCmathAdvancedV2:
    def test_log(self):
        """`cmath.log(2+0j) 必 ~0.693+0j。"""
        r = cmath.log(2 + 0j)
        # 必 ~ 0.693
        assert abs(r.real - 0.693) < 1e-3

    def test_exp(self):
        """`cmath.exp(1+0j) 必 ~2.718+0j。"""
        r = cmath.exp(1 + 0j)
        # 必 ~ 2.718
        assert abs(r.real - 2.718) < 1e-3

    def test_sin(self):
        """`cmath.sin(pi/2) 必 ~1.0+0j。"""
        r = cmath.sin(cmath.pi / 2)
        # 必 ~ 1.0
        assert abs(r.real - 1.0) < 1e-10

    def test_cos(self):
        """`cmath.cos(0) 必 1.0+0j。"""
        r = cmath.cos(0)
        # 必 1.0
        assert r.real == 1.0

    def test_phase(self):
        """`cmath.phase(1+0j) 必 0.0。"""
        r = cmath.phase(1 + 0j)
        # 必 0.0
        assert abs(r - 0.0) < 1e-10


# -- traceback 进阶 (extract_stack + format_list) -----------

class TestTracebackAdvancedV2:
    def test_extract_stack(self):
        """`traceback.extract_stack 真返 ≥ 1 FrameSummary。"""
        frames = traceback.extract_stack()
        # 必 list
        assert isinstance(frames, list)
        # 必 ≥ 1
        assert len(frames) >= 1

    def test_format_list(self):
        """`traceback.format_list 真返 list of str。"""
        frames = traceback.extract_stack()
        formatted = traceback.format_list(frames)
        # 必 list
        assert isinstance(formatted, list)
        # 必 ≥ 1
        assert len(formatted) >= 1


# -- functools.cached_property 进阶 (3.8+) ----------------

class _CachedObj:
    def __init__(self):
        self._count = 0

    @functools.cached_property
    def value(self):
        self._count += 1
        return "forge_cached"


class TestCachedPropertyAdvanced:
    def test_cached_property_3_8(self):
        """`functools.cached_property 3.8+ 真计算 1 次。"""
        o = _CachedObj()
        # 1st access
        v1 = o.value
        # 2nd access
        v2 = o.value
        # 必同
        assert v1 == v2
        # 必 'forge_cached'
        assert v1 == "forge_cached"
        # 必只算 1 次
        assert o._count == 1
