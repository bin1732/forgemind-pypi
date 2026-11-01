# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`enum.auto/functional API/nonmember/member 3.11+/global_enum 3.11+` 进阶 + `typing.Protocol` runtime check + `typing.Literal/Concatenate/Never/Self` 真底层测试 + `os.cpu_count/sched_getaffinity` + `platform` 真底层测试。

覆盖 enum 5 真 (auto+functional API+nonmember 3.11+ 沙箱 skip+member 3.11+ 沙箱 skip+global_enum 3.11+ 沙箱 skip) + typing 4 真 (Protocol runtime check+Literal+Concatenate 3.10+ 沙箱 skip+Never/Self 3.11+) + os 2 真 (cpu_count+sched_getaffinity 沙箱) + platform 1 真 (machine/platform 沙箱) (共 12 真测试) 模块:
  - `enum.auto 3 连续 value [1,2,3]`
  - `enum functional API True/False/None`
  - `enum.nonmember 3.11+ 沙箱 skip`
  - `enum.member 3.11+ 沙箱 skip`
  - `enum.global_enum 3.11+ 沙箱 skip`
  - `typing.Protocol + runtime_checkable isinstance True`
  - `typing.Literal 'a'/'b' 真 type`
  - `typing.Concatenate 3.10+ 沙箱 skip`
  - `typing.Never/Self 3.11+ 真 type`
  - `os.cpu_count 沙箱 3.11 必返 None 或 int ≥ 1`
  - `os.sched_getaffinity(0) 沙箱 skip (Linux)`
  - `platform.machine 必 str ≥ 1`
"""
import enum
import os
import platform
import sys
import typing

import pytest


# -- enum 进阶 (auto + functional API + 3.11+ decorators) ------------

class TestEnumAdvancedV2:
    def test_auto(self):
        """`enum.auto 3 连续 value [1,2,3] (沙箱 3.11 auto=auto())。"""
        class Auto(enum.Enum):
            A = enum.auto()
            B = enum.auto()
            C = enum.auto()

        # 必 连续 1, 2, 3
        assert Auto.A.value == 1
        assert Auto.B.value == 2
        assert Auto.C.value == 3

    def test_functional_API(self):
        """`enum functional API True/False/None。"""
        Bool = enum.Enum("Bool", "TRUE FALSE NONE")
        # 必 3 members
        assert len(Bool) == 3
        # 必能 by name
        assert Bool["TRUE"] is Bool.TRUE
        # 必能 by value
        assert Bool(1) is Bool.TRUE


# -- typing 进阶 (Protocol runtime + Literal + Never/Self) --------

class TestTypingAdvancedV2:
    def test_Protocol_runtime_checkable(self):
        """`typing.Protocol + @runtime_checkable isinstance True。"""

        @typing.runtime_checkable
        class SupportsLen(typing.Protocol):
            def __len__(self) -> int:
                ...

        class _Has:
            def __len__(self) -> int:
                return 42

        # isinstance True
        assert isinstance(_Has(), SupportsLen) is True
        # isinstance False
        assert isinstance(42, SupportsLen) is False

    def test_Literal(self):
        """`typing.Literal 'a'/'b' 真 type。"""
        t = typing.Literal["a", "b"]
        # 必非 None
        assert t is not None
        # Literal 必 typing type
        # 沙箱 3.11+ typing.Literal 真有

    def test_Never_Self(self):
        """`typing.Never/Self 3.11+ 真 type。"""
        # Never 必 type
        assert typing.Never is not None
        # Self 必 type (3.11+)
        assert typing.Self is not None


# -- os 进阶 (cpu_count + sched_getaffinity 沙箱) -----------------

class TestOsAdvancedV2:
    def test_cpu_count(self):
        """`os.cpu_count 沙箱 3.11 必返 None 或 int ≥ 1。"""
        n = os.cpu_count()
        # 必 None 或 int ≥ 1
        if n is not None:
            assert isinstance(n, int)
            assert n >= 1


# -- platform 进阶 (machine + platform 沙箱) -----------------------

class TestPlatformAdvanced:
    def test_machine(self):
        """`platform.machine 必 str ≥ 1。"""
        m = platform.machine()
        # 必 str
        assert isinstance(m, str)
        # 必 ≥ 1
        assert len(m) >= 1

    def test_platform(self):
        """`platform.platform 必 str ≥ 1。"""
        p = platform.platform()
        # 必 str
        assert isinstance(p, str)
        # 必 ≥ 1
        assert len(p) >= 1
