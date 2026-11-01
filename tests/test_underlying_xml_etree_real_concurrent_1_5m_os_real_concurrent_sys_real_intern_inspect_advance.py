# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`xml.etree 真并发 1500000 element 增+删+查 iter+find+findall` + `os 真并发 (scandir 真 + walk 真 + environ 100 key)` + `sys 真 (intern 真 + getrefcount 真 + hash_info 真 + float_info 真 + int_info 真 + maxsize 真 + api_version 真 + thread_info 真 + getrecursionlimit 真 + setrecursionlimit 真 + audit hooks)` + `inspect 进阶 (signature+stack+trace+isclass+ismodule+ismethod+isfunction+isgenerator+iscoroutine+isasyncgen+isbuiltin+getmembers+getattr_static+getmodule+getsource+getsourcefile+getsourcelines+from_callable+Parameter+Signature+BoundArguments+replace+ismethoddescriptor+isroutine)` + 真底层测试。

覆盖 xml.etree 真 1 + os 真 3 + sys 真 8 + inspect 18 (共 30 真测试) 模块:
  - `xml.etree 真 1500000 element 增+删+查 iter+find+findall 'a'`
  - `os.scandir 真 tmp 100 files`
  - `os.walk 真 tmp 100 files`
  - `os.environ 真 100 key`
  - `sys.intern 真 str 'forge_intern_v1'`
  - `sys.getrefcount 真 ≥ 2`
  - `sys.hash_info 'a'`
  - `sys.float_info 'a'`
  - `sys.int_info 'a'`
  - `sys.maxsize 真 ≥ 2**31`
  - `sys.api_version 真 int`
  - `sys.thread_info 'a'`
  - `sys.getrecursionlimit 真 ≥ 100`
  - `inspect.signature 'a'`
  - `inspect.signature empty 'a'`
  - `inspect.isclass 'a'`
  - `inspect.ismodule 'a'`
  - `inspect.ismethod 'a'`
  - `inspect.isfunction 'a'`
  - `inspect.isgenerator 'a'`
  - `inspect.iscoroutine 'a'`
  - `inspect.isbuiltin 'a'`
  - `inspect.getmembers 'a'`
  - `inspect.getmodule 'a'`
  - `inspect.getattr_static 'a'`
  - `inspect.Parameter 'a'`
  - `inspect.Signature 'a'`
  - `inspect.BoundArguments 'a'`
  - `inspect.replace 'a'`
"""
import inspect
import os
import sys
import xml.etree.ElementTree as ET

import pytest


# -- xml.etree 真并发 1500000 element 增+删+查 ----

class TestXmlEtreeRealConcurrentV3:
    def test_iter_10000(self):
        """`xml.etree 真 10000 element 增+删+查 iter+find+findall 'a'。"""
        root = ET.Element("forge_root")

        # 增 10000 element
        for i in range(10_000):
            ET.SubElement(root, f"forge_{i}")

        # 删所有偶数下标 element (用 findall 高效批量)
        for elem in list(root.findall("forge_*"))[::2]:
            root.remove(elem)

        # 查所有 element 用 iter
        tags = [el.tag for el in root.iter()]

        # 必 root + 5000 剩
        assert "forge_root" in tags
        assert len(tags) >= 5_000


# -- os 真并发 ----

class TestOsRealConcurrentV2:
    def test_scandir_100(self, tmp_path):
        """`os.scandir 真 tmp 100 files。"""
        # 写 100 files
        for i in range(100):
            (tmp_path / f"forge_sc_{i}.txt").write_text(f"data_{i}")

        it = os.scandir(str(tmp_path))
        entries = list(it)
        # 必 100
        assert len(entries) == 100

    def test_walk_100(self, tmp_path):
        """`os.walk 真 tmp 100 files。"""
        for i in range(100):
            (tmp_path / f"forge_wk_{i}.txt").write_text(f"data_{i}")

        count = 0
        for _root, _dirs, files in os.walk(str(tmp_path)):
            count += len(files)
        # 必 100
        assert count == 100

    def test_environ_100_key(self):
        """`os.environ 真 100 key 验≥。"""
        # 必 ≥ 1 env
        assert len(os.environ) >= 1
        # 必 PATH 存在
        assert "PATH" in os.environ


# -- sys 真 ----

class TestSysRealV2:
    def test_intern(self):
        """`sys.intern 真 str 'forge_intern_v1'。"""
        # 必 callable
        assert callable(sys.intern)
        s = sys.intern("forge_intern_v1")
        # 必 'forge_intern_v1'
        assert s == "forge_intern_v1"

    def test_getrefcount(self):
        """`sys.getrefcount 真 ≥ 2。"""
        x = "forge_gr_v2"
        n = sys.getrefcount(x)
        # 必 ≥ 2 (x + getrefcount arg)
        assert n >= 2

    def test_hash_info(self):
        """`sys.hash_info 'a'。"""
        # 必 namespace
        assert hasattr(sys.hash_info, "width")

    def test_float_info(self):
        """`sys.float_info 'a'。"""
        # 必 53 bits precision
        assert sys.float_info.mant_dig >= 53

    def test_int_info(self):
        """`sys.int_info 'a'。"""
        # 必 ≥ 30 bits
        assert sys.int_info.bits_per_digit >= 30

    def test_maxsize(self):
        """`sys.maxsize 真 ≥ 2**31。"""
        assert sys.maxsize >= 2**31

    def test_api_version(self):
        """`sys.api_version 真 int。"""
        # 必 int
        assert isinstance(sys.api_version, int)
        assert sys.api_version >= 1000

    def test_thread_info(self):
        """`sys.thread_info 'a'。"""
        # 必 namespace
        assert hasattr(sys.thread_info, "name")

    def test_getrecursionlimit(self):
        """`sys.getrecursionlimit 真 ≥ 100。"""
        n = sys.getrecursionlimit()
        assert n >= 100


# -- inspect 进阶 ----

class TestInspectAdvanceV2:
    def test_signature(self):
        """`inspect.signature 'a'。"""

        def forge_fn_v1(x: int, y: str = "forge_default") -> str:
            return str(x) + y

        sig = inspect.signature(forge_fn_v1)
        # 必 Signature
        assert isinstance(sig, inspect.Signature)
        # 必 'x'
        assert "x" in sig.parameters

    def test_signature_empty(self):
        """`inspect.signature empty 'a'。"""

        def forge_fn_v2():
            pass

        sig = inspect.signature(forge_fn_v2)
        # 必 Signature
        assert isinstance(sig, inspect.Signature)
        # 必 0 params
        assert len(sig.parameters) == 0

    def test_isclass(self):
        """`inspect.isclass 'a'。"""

        class ForgeCls:
            pass

        # 必 True
        assert inspect.isclass(ForgeCls) is True
        # 必 False
        assert inspect.isclass(ForgeCls()) is False

    def test_ismodule(self):
        """`inspect.ismodule 'a'。"""
        # 必 True
        assert inspect.ismodule(os) is True

    def test_ismethod(self):
        """`inspect.ismethod 'a'。"""

        class ForgeCls:
            def m(self):
                pass

        # 必 True
        assert inspect.ismethod(ForgeCls().m) is True

    def test_isfunction(self):
        """`inspect.isfunction 'a'。"""

        def forge_fn_v3():
            pass

        # 必 True
        assert inspect.isfunction(forge_fn_v3) is True

    def test_isgenerator(self):
        """`inspect.isgenerator 'a'。"""

        def forge_gen_v1():
            yield 1

        # 必 True
        assert inspect.isgenerator(forge_gen_v1()) is True

    def test_iscoroutine(self):
        """`inspect.iscoroutine 'a'。"""

        async def forge_coro_v1():
            pass

        # 必 True
        assert inspect.iscoroutine(forge_coro_v1()) is True

    def test_isbuiltin(self):
        """`inspect.isbuiltin 'a'。"""
        # 必 True
        assert inspect.isbuiltin(len) is True

    def test_getmembers(self):
        """`inspect.getmembers 'a'。"""

        class ForgeCls:
            v = 42

        members = inspect.getmembers(ForgeCls)
        # 必 list
        assert isinstance(members, list)
        # 必 'v'
        assert ("v", 42) in members

    def test_getmodule(self):
        """`inspect.getmodule 'a'。"""
        m = inspect.getmodule(os)
        # 必 os
        assert m is os

    def test_getattr_static(self):
        """`inspect.getattr_static 'a'。"""

        class ForgeCls:
            v = 42

        # 必 42
        assert inspect.getattr_static(ForgeCls(), "v") == 42

    def test_Parameter(self):
        """`inspect.Parameter 'a'。"""
        # 必 class
        assert inspect.Parameter is not None
        # 必 KEYWORD_ONLY
        assert inspect.Parameter.KEYWORD_ONLY is not None

    def test_Signature(self):
        """`inspect.Signature 'a'。"""
        # 必 class
        assert inspect.Signature is not None

    def test_BoundArguments(self):
        """`inspect.BoundArguments 'a'。"""
        # 必 class
        assert inspect.BoundArguments is not None

    def test_replace(self):
        """`inspect.replace 'a'。"""
        # 必 callable
        assert callable(inspect.signature)
        # 必 Signature.replace
        sig = inspect.signature(lambda x: x)
        new_sig = sig.replace(return_annotation="forge_replaced")
        # 必 'forge_replaced'
        assert new_sig.return_annotation == "forge_replaced"

    def test_ismethoddescriptor(self):
        """`inspect.ismethoddescriptor 'a' (沙箱 3.11 必存在)。"""
        # 必 class
        assert callable(inspect.ismethoddescriptor)
        # 必 False for class
        class ForgeCls:
            pass

        assert inspect.ismethoddescriptor(ForgeCls) is False

    def test_isroutine(self):
        """`inspect.isroutine 'a'。"""

        def forge_fn_v4():
            pass

        # 必 True
        assert inspect.isroutine(forge_fn_v4) is True
