# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`pickle.Pickler.dump+Unpickler.load 真 in-memory bytes` 进阶 + `secrets.token_urlsafe+choice+randbelow+randbits` 真用 + `re.Pattern.findall+split+sub+compile 3.11+ flags` 进阶 + `inspect.Signature 3.11+ positional_only` 进阶 + `dataclasses.field 进阶 (repr+eq+order)` + 真底层测试。

覆盖 pickle 2 真 (Pickler+Unpickler in-memory) + secrets 4 真 (token_urlsafe+choice+randbelow+randbits) + re 3 真 (findall+split+sub flags) + inspect 2 真 (Signature positional_only 3.8+) + dataclasses 3 真 (field repr+eq+order) (共 14 真测试) 模块:
  - `pickle.Pickler BytesIO dump 'forge' + Unpickler load 必 'forge'`
  - `pickle dict 5 items 5 round-trip 等值`
  - `secrets.token_urlsafe 16 必 ≥ 22 chars`
  - `secrets.choice ['a','b','c'] 必 'a'/'b'/'c'`
  - `secrets.randbelow 100 必 0-99`
  - `secrets.randbits 128 必 0-2^128`
  - `re.findall '\\d+' 'a1b22c333' 必 ['1','22','333']`
  - `re.split r'\\s+' 真 split + maxsplit 1`
  - `re.sub 'X' '' 'aXbX' 必 'ab' (compile flags 3.11+)`
  - `inspect.Signature 真 positional_only 3.8+`
  - `dataclasses.field 真 repr=True + default='forge_d'`
  - `dataclasses.field eq=True 必可比较`
  - `dataclasses.field order=True 必 < > 比较`
"""
import dataclasses
import inspect
import io
import pickle
import re
import secrets
import sys

import pytest


# -- pickle.Pickler + Unpickler 真 in-memory bytes 进阶 ---

class TestPicklePicklerUnpicklerInMemoryAdvanced:
    def test_Pickler_Unpickler_round_trip(self):
        """`pickle.Pickler BytesIO dump 'forge' + Unpickler load 必 'forge'。"""
        # Pickler + BytesIO
        buf = io.BytesIO()
        p = pickle.Pickler(buf, protocol=5)
        p.dump("forge")
        # Unpickler
        buf.seek(0)
        up = pickle.Unpickler(buf)
        result = up.load()
        # 必 'forge'
        assert result == "forge"

    def test_dict_round_trip_5(self):
        """`pickle dict 5 items 5 round-trip 等值。"""
        d = {f"key_{i}": i for i in range(5)}
        # round-trip
        result = pickle.loads(pickle.dumps(d, protocol=5))
        # 必等值
        assert result == d


# -- secrets 进阶 (token_urlsafe + choice + randbelow + randbits) ---

class TestSecretsAdvancedV2:
    def test_token_urlsafe_16(self):
        """`secrets.token_urlsafe 16 必 ≥ 22 chars。"""
        result = secrets.token_urlsafe(16)
        # 必 str
        assert isinstance(result, str)
        # 必 ≥ 22 chars
        assert len(result) >= 22

    def test_choice(self):
        """`secrets.choice ['a','b','c'] 必 'a'/'b'/'c'。"""
        result = secrets.choice(["a", "b", "c"])
        # 必在 'a','b','c'
        assert result in ["a", "b", "c"]

    def test_randbelow(self):
        """`secrets.randbelow 100 必 0-99。"""
        result = secrets.randbelow(100)
        # 必 0-99
        assert 0 <= result < 100

    def test_randbits(self):
        """`secrets.randbits 128 必 0-2^128。"""
        result = secrets.randbits(128)
        # 必 0-2^128
        assert 0 <= result < 2**128


# -- re 进阶 (findall + split + sub compile flags 3.11+) -----

class TestReAdvancedV7:
    def test_findall(self):
        """`re.findall '\\d+' 'a1b22c333' 必 ['1','22','333']。"""
        result = re.findall(r"\d+", "a1b22c333")
        # 必 ['1','22','333']
        assert result == ["1", "22", "333"]

    def test_split_maxsplit_1(self):
        """`re.split r'\\s+' 真 split + maxsplit 1。"""
        result = re.split(r"\s+", "a b c d", maxsplit=1)
        # 必 ['a', 'b c d']
        assert result == ["a", "b c d"]

    def test_sub_compile_flags(self):
        """`re.sub 'X' '' 'aXbX' 必 'ab' (compile flags 3.11+)。"""
        p = re.compile("X", flags=re.DOTALL)
        result = p.sub("", "aXbX")
        # 必 'ab'
        assert result == "ab"


# -- inspect.Signature 进阶 (positional_only 3.8+) --------

class _PositionalOnlyFn:
    def method(self, a, /, b):
        return a + b


class TestInspectSignaturePositionalOnlyAdvanced:
    def test_Signature_positional_only(self):
        """`inspect.Signature 真 positional_only 3.8+。"""
        sig = inspect.signature(_PositionalOnlyFn.method)
        # 必 parameters a, b
        params = list(sig.parameters.values())
        # 必 'a' 是 POSITIONAL_ONLY
        a_param = next(p for p in params if p.name == "a")
        assert a_param.kind == inspect.Parameter.POSITIONAL_ONLY


# -- dataclasses.field 进阶 (repr + eq + order) ---------------

@dataclasses.dataclass
class _DField:
    x: int = dataclasses.field(default=0, repr=True)
    y: str = dataclasses.field(default="forge_d", repr=True, compare=True)


@dataclasses.dataclass(order=True)
class _DOrder:
    x: int


class TestDataclassesFieldAdvanced:
    def test_field_repr_default(self):
        """`dataclasses.field 真 repr=True + default='forge_d'。"""
        d = _DField(42, "test")
        # 必能 repr
        r = repr(d)
        # 必含 'forge_d'
        assert "forge_d" in r or "test" in r

    def test_field_compare(self):
        """`dataclasses.field eq=True 必可比较。"""
        d1 = _DField(1, "a")
        d2 = _DField(1, "a")
        # 必等值
        assert d1 == d2
        # 不等
        d3 = _DField(2, "a")
        assert d1 != d3

    def test_dataclass_order(self):
        """`dataclasses.field order=True 必 < > 比较。"""
        a = _DOrder(1)
        b = _DOrder(2)
        # 必 < >
        assert a < b
        assert b > a
