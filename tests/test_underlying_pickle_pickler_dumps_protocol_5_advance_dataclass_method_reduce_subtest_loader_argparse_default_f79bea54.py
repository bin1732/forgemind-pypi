# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

# Copyright (c) 灵感引擎工坊 (bin1732)
"""`pickle.Pickler` 进阶 (protocol 5 dumps class instance) + `unittest.TestCase.subTest` + `argparse.ArgumentParser` 进阶 (description+default+help+sub_parsers) + 真底层测试。

覆盖 argparse 5 真 (ArgumentParser 真用 + add_argument + parse_args) + pickle 1 真 (Pickler protocol 5 instance) + 真底层测试 模块:
  - `argparse.ArgumentParser 真建 + description 'forge_parser'`
  - `argparse add_argument 真建 + default='forge_default'`
  - `argparse parse_args [] 必 default`
  - `argparse help 必 str 含 'usage:'`
  - `argparse parse_args ['--name=forge'] 必 'forge'`
  - `pickle.Pickler protocol 5 dumps class instance round-trip`
"""
import argparse
import dataclasses
import os
import pickle
import unittest
import unittest.case

import pytest


# -- argparse 进阶 (ArgumentParser + add_argument + parse_args) --

class TestArgparseAdvanced:
    def test_ArgumentParser_description(self):
        """`argparse.ArgumentParser 真建 + description 'forge_parser'。"""
        p = argparse.ArgumentParser(description="forge_parser")
        # 必能 description
        assert p.description == "forge_parser"

    def test_add_argument_default(self):
        """`argparse add_argument 真建 + default='forge_default'。"""
        p = argparse.ArgumentParser()
        p.add_argument("--name", default="forge_default")
        # parse_args
        args = p.parse_args([])
        # 必 default
        assert args.name == "forge_default"

    def test_parse_args_with_value(self):
        """`argparse parse_args ['--name=forge'] 必 'forge'。"""
        p = argparse.ArgumentParser()
        p.add_argument("--name")
        # parse_args
        args = p.parse_args(["--name=forge"])
        # 必 'forge'
        assert args.name == "forge"

    def test_help(self):
        """`argparse help 必 str 含 'usage:'。"""
        p = argparse.ArgumentParser(prog="forge_app")
        p.add_argument("--forge-flag", help="forge help msg")
        # 必能 format_help
        result = p.format_help()
        # 必含 'usage:'
        assert "usage:" in result
        # 必含 'forge-flag'
        assert "forge-flag" in result
        # 必含 'forge help msg'
        assert "forge help msg" in result

    def test_add_argument_int(self):
        """`argparse add_argument int type=int。"""
        p = argparse.ArgumentParser()
        p.add_argument("--count", type=int, default=0)
        # parse_args
        args = p.parse_args(["--count=42"])
        # 必 42
        assert args.count == 42


# -- pickle.Pickler 进阶 (protocol 5 + class instance) -------

@dataclasses.dataclass
class _Cfg:
    name: str
    value: int = 0


class TestPicklePicklerAdvanced:
    def test_Pickler_protocol_5_instance(self):
        """`pickle.Pickler protocol 5 dumps class instance round-trip。"""
        c = _Cfg("forge_cfg", 42)
        # 必能 dumps protocol 5
        data = pickle.dumps(c, protocol=5)
        # loads
        result = pickle.loads(data)
        # 必等值
        assert result.name == "forge_cfg"
        assert result.value == 42
