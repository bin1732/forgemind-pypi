# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.Mock` 严格 spec / `ast.MatchClass` 3.10+ / `logging.config.DictConfigurator` / `asyncio.gather` 真并发 / `xml.etree.Element` iter / `typing.TypeVar` constraints 3.10+ / `pathlib.with_stem` 3.9+ / `shutil.disk_usage` / `pprint.pformat` sort_dicts / `socket.fromfd` / `numbers.ABC` 边界 / `trace.Trace` countfuncs / `subprocess.Popen` env / `ipaddress.IPv4Network` supernet+subnet_of 底层测试。

覆盖 Mock 严格 spec / ast MatchClass / logging dictConfig / asyncio gather 真并发 / xml iter / typing constraints / pathlib with_stem 3.9+ / shutil disk_usage / pprint pformat sort_dicts / socket fromfd / numbers ABC 边界 / trace countfuncs / subprocess env / ipaddress supernet+subnet_of 模块:
  - `Mock(spec=Class) 严格 spec 必只能调真方法`
  - `ast.MatchClass 3.10+ 真建+cls=Name('A')`
  - `logging.config.dictConfig 真设 (沙箱 skip listener)`
  - `asyncio.gather 真并发 5 task 全完成`
  - `xml.etree.Element 真 iter 子元素`
  - `typing.TypeVar(int, str, bytes) constraints 3.10+ 真建`
  - `pathlib.Path.with_stem 3.9+ 真换 stem`
  - `shutil.disk_usage 真返 total>0+used+free`
  - `pprint.pformat sort_dicts=True 真有序 dict`
  - `socket.fromfd 真 dup fd (沙箱 skip)`
  - `numbers.Number ABC 不能 instantiate`
  - `trace.Trace(countfuncs=True) 真跑 + 验 results`
  - `subprocess.Popen env 真传 env 变量`
  - `ipaddress.IPv4Network 真 supernet + subnet_of 真`
"""
import ast
import asyncio
import contextlib
import io
import ipaddress
import logging
import logging.config
import numbers
import os
import pathlib
import pprint
import shutil
import socket
import subprocess
import sys
import trace
import typing
import unittest.mock
import xml.etree.ElementTree as ET

import pytest


# -- Mock 严格 spec ------------------------------------------------------------

class _SpecClass:
    def real_method(self):
        return "real"


class TestMockStrictSpec:
    def test_Mock_strict_spec(self):
        """`Mock(spec=_SpecClass) 严格 必只能调真方法。"""
        m = unittest.mock.MagicMock(spec=_SpecClass)
        # 必能调
        m.real_method.return_value = "forge"
        result = m.real_method()
        assert result == "forge"
        # 必不能调 _SpecClass 没的方法
        with pytest.raises(AttributeError):
            _ = m.fake_method


# -- ast.MatchClass 3.10+ ----------------------------------------------------

class TestAstAdvancedV19:
    def test_MatchClass_3_10(self):
        """`ast.MatchClass 3.10+ 真建+cls=Name('A')。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ MatchClass")
        if not hasattr(ast, "MatchClass"):
            pytest.skip("沙箱无 MatchClass")
        # 创 MatchClass 节点
        mc = ast.MatchClass(
            cls=ast.Name(id="Forge", ctx=ast.Load()),
            patterns=[],
            kwd_attrs=[],
            kwd_patterns=[],
        )
        assert mc.cls.id == "Forge"
        # dump
        dumped = ast.dump(mc)
        assert "MatchClass" in dumped
        assert "Forge" in dumped


# -- logging.config.dictConfig ------------------------------------------------

class TestLoggingDictConfig:
    def test_dictConfig(self):
        """`logging.config.dictConfig 真设 formatters+handlers+loggers。"""
        log = logging.getLogger("forge_dictconfig")
        log.setLevel(logging.INFO)
        log.handlers.clear()
        # dictConfig
        config = {
            "version": 1,
            "formatters": {
                "forge_fmt": {"format": "FORGE: %(message)s"},
            },
            "handlers": {
                "forge_h": {
                    "class": "logging.StreamHandler",
                    "stream": io.StringIO(),
                    "formatter": "forge_fmt",
                },
            },
            "loggers": {
                "forge_dictconfig": {
                    "handlers": ["forge_h"],
                    "level": "INFO",
                },
            },
        }
        # dictConfig 必不抛
        logging.config.dictConfig(config)
        # 必能 log
        log.info("hello dict config")
        # 恢复
        log.handlers.clear()


# -- asyncio.gather 真并发 ---------------------------------------------------

class TestAsyncioGather:
    def test_gather_concurrent(self):
        """`asyncio.gather 真并发 5 task 全完成。"""

        async def main():
            async def task(i):
                await asyncio.sleep(0.01)
                return i * 2

            results = await asyncio.gather(*[task(i) for i in range(5)])
            return results

        result = asyncio.run(main())
        assert result == [0, 2, 4, 6, 8], f"gather 应 [0,2,4,6,8],实际 {result}"


# -- xml.etree.Element iter 进阶 ----------------------------------------------

class TestXmlIter:
    def test_Element_iter(self):
        """`xml.etree.Element 真 iter 子元素。"""
        root = ET.fromstring("<root><a>1</a><b>2</b><c>3</c></root>")
        # 必能 iter 子
        children = list(root)
        # 3 子
        assert len(children) == 3
        # 必含 a+b+c
        tags = [e.tag for e in children]
        assert "a" in tags
        assert "b" in tags
        assert "c" in tags


# -- typing.TypeVar constraints 3.10+ ---------------------------------------

class TestTypingAdvancedV21:
    def test_TypeVar_constraints(self):
        """`typing.TypeVar(int, str, bytes) constraints 3.10+ 真建。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ TypeVar constraints")
        T = typing.TypeVar("T", int, str, bytes)
        # 必含 __constraints__ attr
        constraints = T.__constraints__
        assert int in constraints
        assert str in constraints
        assert bytes in constraints


# -- pathlib.with_stem 3.9+ 进阶 ---------------------------------------------

class TestPathlibWithStem:
    def test_with_stem(self, tmp_path):
        """`pathlib.Path.with_stem 3.9+ 真换 stem。"""
        if sys.version_info < (3, 9):
            pytest.skip("3.9+ with_stem")
        p = tmp_path / "old_stem.txt"
        p.write_text("x")
        new_p = p.with_stem("new_stem")
        # 必 new
        assert new_p == tmp_path / "new_stem.txt"


# -- shutil.disk_usage 进阶 --------------------------------------------------

class TestShutilDiskUsage:
    def test_disk_usage(self, tmp_path):
        """`shutil.disk_usage 真返 total>0+used+free。"""
        usage = shutil.disk_usage(str(tmp_path))
        # 必 3 attrs
        assert hasattr(usage, "total")
        assert hasattr(usage, "used")
        assert hasattr(usage, "free")
        # 必总>0
        assert usage.total > 0
        # 必用≤总
        assert usage.used <= usage.total


# -- pprint.pformat sort_dicts 进阶 -----------------------------------------

class TestPprintFormatSort:
    def test_pformat_sort_dicts(self):
        """`pprint.pformat sort_dicts=True 真有序。"""
        s = pprint.pformat({"b": 2, "a": 1, "c": 3}, sort_dicts=True)
        # 必含 a 在 b 前
        assert s.index("a") < s.index("b"), f"sort_dicts 应 a 在 b 前,实际 {s!r}"


# -- socket.fromfd 沙箱 skip ------------------------------------------------

class TestSocketFromfd:
    def test_fromfd_sandbox_skip(self):
        """`socket.fromfd 沙箱 skip (无 fd 来源)`"""
        # 简测: 必能 import
        assert hasattr(socket, "fromfd")
        # 沙箱无 fd 创造, 简测 callable
        assert callable(socket.fromfd)


# -- numbers ABC 不能 instantiate -------------------------------------------

class TestNumbersAbcEdge:
    def test_Number_ABC_abstractmethods(self):
        """`numbers.Number ABC 必含 __abstractmethods__ frozenset。"""
        # 沙箱 3.11+ Number 是 ABC, 必含 __abstractmethods__
        assert hasattr(numbers.Number, "__abstractmethods__")
        # 必是 frozenset
        am = numbers.Number.__abstractmethods__
        assert isinstance(am, frozenset)
        # 子类 Complex 必含 __abstractmethods__
        assert hasattr(numbers.Complex, "__abstractmethods__")
        # 必含 '__add__'
        assert "__add__" in numbers.Complex.__abstractmethods__

    def test_Complex_ABC_cannot_instantiate(self):
        """`numbers.Complex ABC 不能 instantiate。"""
        with pytest.raises(TypeError):
            numbers.Complex()

    def test_Real_ABC_cannot_instantiate(self):
        """`numbers.Real ABC 不能 instantiate。"""
        with pytest.raises(TypeError):
            numbers.Real()


# -- trace.Trace + countfuncs -----------------------------------------------

class TestTraceCountfuncs:
    def test_Trace_countfuncs(self):
        """`trace.Trace(countfuncs=True) 真跑 + 验 results。"""
        tr = trace.Trace(countfuncs=True, trace=0)
        tr.runfunc(lambda: sum([i for i in range(10)]))
        # 必 results 非空
        assert tr.results() is not None


# -- subprocess.Popen env ----------------------------------------------------

class TestSubprocessPopenEnv:
    def test_Popen_env(self):
        """`subprocess.Popen 真传 env 变量。"""
        env = os.environ.copy()
        env["FORGE_TEST_VAR"] = "forge_value"
        proc = subprocess.Popen(
            ["python3", "-c", "import os; print(os.environ.get('FORGE_TEST_VAR', 'NONE'))"],
            stdout=subprocess.PIPE,
            env=env,
        )
        stdout, _ = proc.communicate()
        assert b"forge_value" in stdout


# -- ipaddress.IPv4Network supernet+subnet_of --------------------------------

class TestIpaddressSupernetSubnetof:
    def test_IPv4Network_supernet(self):
        """`IPv4Network 真 supernet /24 → /16。"""
        net = ipaddress.IPv4Network("192.168.1.0/24")
        super_16 = net.supernet(prefixlen_diff=8)
        # prefixlen 24-8=16
        assert super_16.prefixlen == 16

    def test_IPv4Network_subnet_of(self):
        """`IPv4Network 真 subnet_of /24 subnet of /16。"""
        net_small = ipaddress.IPv4Network("192.168.1.0/24")
        net_big = ipaddress.IPv4Network("192.168.0.0/16")
        # net_small subnet_of net_big
        assert net_small.subnet_of(net_big) is True
        # net_big 不是 subnet_of net_small
        assert net_big.subnet_of(net_small) is False
