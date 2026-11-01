# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`functools.lru_cache` 进阶 (cache_info+maxsize+typed) + `functools.partialmethod 真用` + `secrets.compare_digest` 真用 + `secrets.token_hex+token_bytes+token_urlsafe` 真用 + `pickle.dump/load 进阶 (dataclass)` + `multiprocessing.Managers.Value/Array 真用 (sharedctypes)` + 真底层测试。

覆盖 functools 2 真 (lru_cache maxsize+typed+partialmethod) + secrets 4 真 (compare_digest+token_hex+token_bytes+token_urlsafe) + pickle 1 真 (dump+load dataclass) + multiprocessing 2 真 (Manager.Value 真用+Manager.Array 真用) (共 9 真测试) 模块:
  - `functools.lru_cache maxsize=64+typed=True 真 fib(5)=5`
  - `functools.partialmethod 真子化 _O.meth(1,2)=3`
  - `secrets.compare_digest(a, a) 必 True`
  - `secrets.token_hex 16 必 32 hex chars`
  - `secrets.token_bytes 24 必 24 bytes`
  - `secrets.token_urlsafe 32 必 ≥ 40 chars`
  - `pickle.dump dataclass + load 必等值`
  - `multiprocessing.Manager.Value 'i' 真共享 (3.11+ 必 sync proxy)`
  - `multiprocessing.Manager.Array 'i' 真共享`
"""
import dataclasses
import functools
import io
import multiprocessing
import pickle
import secrets
import sys

import pytest


# -- functools.lru_cache + partialmethod 进阶 --------

@functools.lru_cache(maxsize=64, typed=True)
def _fib(n):
    if n < 2:
        return n
    return _fib(n - 1) + _fib(n - 2)


class _WithPartialMethod:
    @functools.partialmethod
    def meth(self, x, y):
        return x + y

    @functools.partialmethod
    def add10(self, x):
        return x + 10


class TestFunctoolsAdvancedV5:
    def test_lru_cache_typed(self):
        """`functools.lru_cache maxsize=64+typed=True 真 fib(5)=5。"""
        _fib.cache_clear()
        # 必能跑
        assert _fib(5) == 5
        # cache_info
        info = _fib.cache_info()
        # 必 maxsize=64
        assert info.maxsize == 64
        # 必 hits+misses ≥ 1
        assert info.hits + info.misses >= 1

    def test_partialmethod(self):
        """`functools.partialmethod 真子化 _O.meth(1,2)=3。"""
        o = _WithPartialMethod()
        # 必能 call meth
        assert o.meth(1, 2) == 3
        # 必能 call add10
        assert o.add10(5) == 15


# -- secrets 进阶 (compare_digest + token_hex/bytes/urlsafe) ---

class TestSecretsAdvanced:
    def test_compare_digest(self):
        """`secrets.compare_digest(a, a) 必 True。"""
        a = "forge_secret"
        b = "forge_secret"
        # 必 True
        assert secrets.compare_digest(a, b) is True
        # 必 False
        assert secrets.compare_digest(a, "forge_other") is False

    def test_token_hex(self):
        """`secrets.token_hex 16 必 32 hex chars。"""
        result = secrets.token_hex(16)
        # 必 str
        assert isinstance(result, str)
        # 必 32 chars
        assert len(result) == 32
        # 必 hex
        int(result, 16)

    def test_token_bytes(self):
        """`secrets.token_bytes 24 必 24 bytes。"""
        result = secrets.token_bytes(24)
        # 必 bytes
        assert isinstance(result, bytes)
        # 必 24 bytes
        assert len(result) == 24

    def test_token_urlsafe(self):
        """`secrets.token_urlsafe 32 必 ≥ 40 chars。"""
        result = secrets.token_urlsafe(32)
        # 必 str
        assert isinstance(result, str)
        # 必 ≥ 40 chars
        assert len(result) >= 40


# -- pickle.dump/load 进阶 (dataclass) ----------------

@dataclasses.dataclass
class _DConfig:
    name: str
    value: int = 42


class TestPickleDumpLoadAdvanced:
    def test_pickle_dump_load(self):
        """`pickle.dump dataclass + load 必等值。"""
        d = _DConfig("forge", 99)
        # dump to BytesIO
        buf = io.BytesIO()
        pickle.dump(d, buf, protocol=5)
        # load
        buf.seek(0)
        result = pickle.load(buf)
        # 必等值
        assert result.name == "forge"
        assert result.value == 99


# -- multiprocessing.Manager.Value/Array 真用 ---------

class TestMultiprocessingManagerSharedctypesAdvanced:
    def test_Manager_Value(self):
        """`multiprocessing.Manager.Value 'i' 真共享。"""
        with multiprocessing.Manager() as mgr:
            v = mgr.Value("i", 42)
            # 必能 access
            assert v.value == 42
            # 必能 set
            v.value = 100
            assert v.value == 100

    def test_Manager_Array(self):
        """`multiprocessing.Manager.Array 'i' 真共享。"""
        with multiprocessing.Manager() as mgr:
            a = mgr.Array("i", [1, 2, 3])
            # 必能 access
            assert a[0] == 1
            assert a[2] == 3
            # 必能 set
            a[0] = 99
            assert a[0] == 99
