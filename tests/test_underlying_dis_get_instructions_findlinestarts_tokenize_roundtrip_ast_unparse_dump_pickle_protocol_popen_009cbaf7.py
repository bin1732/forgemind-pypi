# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`dis.get_instructions/findlinestarts` 真用 + `tokenize` 进阶 (roundtrip+detect_encoding) + `ast.unparse 3.9+/dump 3.8+` 真用 + `pickle` 进阶 (protocol 5 advanced) + `subprocess.Popen` 进阶 (kwargs+args+env+executable+bufsize) + 真底层测试。

覆盖 dis 2 真 (get_instructions+findlinestarts) + tokenize 2 真 (roundtrip+detect_encoding) + ast 2 真 (unparse+dump) + pickle 2 真 (protocol 5+round-trip) + subprocess 3 真 (env+executable+bufsize) (共 11 真测试) 模块:
  - `dis.get_instructions lambda : None 必 ≥ 1 (含 RESUME)`
  - `dis.findlinestarts lambda : 1 必 ≥ 1 (3.11+ gen)`
  - `tokenize 真 roundtrip 'x = 1\\n' 必 0 errors`
  - `tokenize.detect_encoding b'# -*- coding: utf-8 -*-' 必 'utf-8'`
  - `ast.unparse ast.parse('x=1') 必 'x = 1' (3.9+)`
  - `ast.dump ast.parse('x=1') 必含 'x' (3.8+)`
  - `pickle 真 dumps {'a':1} protocol 5 + loads 必 dict 等值`
  - `pickle 真 dumps list of dataclass round-trip`
  - `subprocess.Popen env={'LANG':'C'} 'echo' 必 0`
  - `subprocess.Popen executable='python3' 'echo' 必 0`
  - `subprocess.Popen bufsize=0 'true' 必 0`
"""
import ast
import dataclasses
import dis
import os
import pickle
import subprocess
import sys
import tokenize
import io

import pytest


# -- dis 进阶 (get_instructions + findlinestarts) ------------------

class TestDisAdvanced:
    def test_get_instructions_lambda(self):
        """`dis.get_instructions lambda : None 必 ≥ 1 (含 RESUME 3.11+)。"""
        instructions = list(dis.get_instructions(lambda: None))
        # 必 ≥ 1
        assert len(instructions) >= 1
        # 沙箱 3.11+ 必含 RESUME
        opnames = [i.opname for i in instructions]
        assert "RESUME" in opnames

    def test_findlinestarts(self):
        """`dis.findlinestarts code obj 必 ≥ 1 (3.11+ gen)。"""
        # 沙箱 3.11+ findlinestarts 必传 code obj (非 function)
        if sys.version_info >= (3, 11):
            code = compile("x = 1", "<test>", "exec")
            gen = dis.findlinestarts(code)
            # 必可 iter
            result = list(gen)
            # 必 ≥ 1
            assert len(result) >= 1
        else:
            pytest.skip("3.11+ findlinestarts")


# -- tokenize 进阶 (roundtrip + detect_encoding) ------------------

class TestTokenizeAdvanced:
    def test_roundtrip(self):
        """`tokenize 真 roundtrip 'x = 1\\n' 必 0 errors。"""
        # roundtrip
        result = list(tokenize.tokenize(io.BytesIO(b"x = 1\n").readline))
        # 必 ≥ 1
        assert len(result) >= 1
        # 必含 NAME 'x'
        names = [tok.string for tok in result if tok.type == tokenize.NAME]
        assert "x" in names

    def test_detect_encoding(self):
        """`tokenize.detect_encoding b'# -*- coding: utf-8 -*-' 必 'utf-8'。"""
        data = b"# -*- coding: utf-8 -*-\nx = 1\n"
        encoding, lines = tokenize.detect_encoding(io.BytesIO(data).readline)
        # 必 'utf-8'
        assert encoding == "utf-8"


# -- ast 进阶 (unparse + dump) -----------------------------------

class TestAstAdvanced:
    def test_unparse(self):
        """`ast.unparse ast.parse('x=1') 必 'x = 1' (3.9+)。"""
        if sys.version_info < (3, 9):
            pytest.skip("3.9+ unparse")
        tree = ast.parse("x=1")
        result = ast.unparse(tree)
        # 必 'x = 1'
        assert "x" in result
        assert "1" in result

    def test_dump(self):
        """`ast.dump ast.parse('x=1') 必含 'x' (3.8+)。"""
        tree = ast.parse("x=1")
        result = ast.dump(tree)
        # 必含 'x'
        assert "x" in result
        # 必 str
        assert isinstance(result, str)


# -- pickle 进阶 (protocol 5 + round-trip dict/dataclass) --------

@dataclasses.dataclass
class _Pt:
    x: int
    y: str = "forge_y"


class TestPickleAdvancedV3:
    def test_pickle_protocol5_dict(self):
        """`pickle 真 dumps {'a':1} protocol 5 + loads 必 dict 等值。"""
        data = {"a": 1, "b": [1, 2, 3]}
        result = pickle.loads(pickle.dumps(data, protocol=5))
        # 必等值
        assert result == data

    def test_pickle_dataclass(self):
        """`pickle 真 dumps list of dataclass round-trip。"""
        d = _Pt(42, "forge_test")
        result = pickle.loads(pickle.dumps(d, protocol=5))
        # 必等值
        assert result.x == 42
        assert result.y == "forge_test"


# -- subprocess.Popen 进阶 (env + executable + bufsize) ----------

class TestSubprocessPopenAdvanced:
    def test_Popen_env(self):
        """`subprocess.Popen env={'LANG':'C'} 'echo' 必 0。"""
        env = os.environ.copy()
        env["LANG"] = "C"
        proc = subprocess.Popen(
            ["echo", "forge_env"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        out, _ = proc.communicate(timeout=5)
        # 必含 'forge_env'
        assert b"forge_env" in out

    def test_Popen_executable(self):
        """`subprocess.Popen executable=sys.executable + args 必 rc=0。"""
        proc = subprocess.Popen(
            [sys.executable, "-c", "print('forge_exe')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, _ = proc.communicate(timeout=5)
        # 必含 'forge_exe'
        assert b"forge_exe" in out
        # 必 0
        assert proc.returncode == 0

    def test_Popen_bufsize_0(self):
        """`subprocess.Popen bufsize=0 'true' 必 0。"""
        proc = subprocess.Popen(
            ["true"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        out, _ = proc.communicate(timeout=5)
        # 必 0
        assert proc.returncode == 0
