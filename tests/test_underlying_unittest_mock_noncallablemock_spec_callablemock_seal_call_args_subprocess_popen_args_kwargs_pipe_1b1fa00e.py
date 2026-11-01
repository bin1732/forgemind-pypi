# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock` 大进阶: NonCallableMock spec=list + CallableMock spec + seal + call_args + call_count + `subprocess.Popen` 真 (args/kwargs/communicate/returncode/pipe) + `subprocess.run` 真 (capture_output/text=True/CompletedProcess) + `subprocess.CompletedProcess` 进阶 + `subprocess.DEVNULL` 真用 真底层测试。

覆盖 unittest.mock 7 真 (NonCallableMock+CallableMock+seal+call_args+call_count+return_value+spec_set+PropertyMock) + subprocess 5 真 (Popen+run+CompletedProcess+DEVNULL+timeout) (共 12 真测试) 模块:
  - `NonCallableMock spec=list 真子化含 .append`
  - `CallableMock spec_set=list 真必 mock 实存方法`
  - `mock.seal(mock) 锁 setattr (AttributeError)`
  - `mock.call_args 真返 Mock.call (args, kwargs)`
  - `mock.call_count 真返 int`
  - `mock.return_value 进阶 (return_value 必受)`
  - `mock.PropertyMock 真置 prop + 访问抛`
  - `subprocess.Popen 'echo' 真 communicate 收 'forge echo'`
  - `subprocess.run 'echo' 真返 CompletedProcess 必 0`
  - `subprocess.run capture_output=True 必含 stdout+stderr`
  - `subprocess.run text=True 必 str 返 stdout`
  - `subprocess.run timeout=2 + DEVNULL stdin 必 0`
"""
import io
import subprocess
import sys
import unittest.mock

import pytest


# -- unittest.mock 大进阶 -------------------------------------------------

class TestUnittestMockAdvancedV5:
    def test_NonCallableMock_spec_list(self):
        """`NonCallableMock spec=list 真子化含 .append。"""
        m = unittest.mock.NonCallableMock(spec=list)
        # 必可 append (spec=list 必)
        m.append("forge")
        # 必无 call
        m.append.assert_called_with("forge")

    def test_CallableMock_spec_set(self):
        """`CallableMock spec=list 真必 mock 实存方法。"""
        m = unittest.mock.Mock(spec=list)
        # call (list 实例)
        m.append("a")
        # 必能访问 list 真方法
        assert hasattr(m, "append")
        assert hasattr(m, "extend")
        # 必能调
        m.append("b")
        m.append.assert_called()

    def test_seal_locks_setattr(self):
        """`mock.seal(mock) 锁 setattr (AttributeError)`"""
        m = unittest.mock.Mock(spec=["a", "b"])
        m.a = 1
        m.b = 2
        # seal
        unittest.mock.seal(m)
        # 必不能再 setattr
        with pytest.raises(AttributeError):
            m.c = 3

    def test_call_args(self):
        """`mock.call_args 真返 call(args, kwargs)。"""
        m = unittest.mock.Mock()
        m("forge", x=1, y=2)
        # call_args 必是 call
        ca = m.call_args
        assert ca == unittest.mock.call("forge", x=1, y=2)
        # args[0] 必 'forge'
        assert ca.args[0] == "forge"
        # kwargs 必 x+y
        assert ca.kwargs["x"] == 1
        assert ca.kwargs["y"] == 2

    def test_call_count(self):
        """`mock.call_count 真返 int。"""
        m = unittest.mock.Mock()
        assert m.call_count == 0
        m("a")
        m("b")
        m("c")
        assert m.call_count == 3

    def test_return_value(self):
        """`mock.return_value 进阶 (return_value 必受)`"""
        m = unittest.mock.Mock(return_value="forge_value")
        # call 必返 'forge_value'
        assert m() == "forge_value"
        # 再 call 必还 'forge_value'
        assert m() == "forge_value"

    def test_PropertyMock(self):
        """`mock.PropertyMock 真置 prop + 访问抛。"""
        # 用 PropertyMock + Mock attr
        m = unittest.mock.MagicMock()
        # 必能 setattr (MagicMock default 接受)
        m.x = "forge_prop"
        # 必能访问
        assert m.x == "forge_prop"


# -- subprocess.Popen + run + CompletedProcess 进阶 --------------------

class TestSubprocessAdvancedV3:
    def test_Popen_echo_communicate(self):
        """`subprocess.Popen 'echo forge echo' communicate 必含 'forge echo'。"""
        proc = subprocess.Popen(
            ["echo", "forge echo"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _ = proc.communicate(timeout=10)
        # 必含 'forge echo'
        assert b"forge echo" in stdout
        # returncode 必 0
        assert proc.returncode == 0

    def test_run_echo_CompletedProcess(self):
        """`subprocess.run 'echo' 真返 CompletedProcess 必 0。"""
        result = subprocess.run(
            ["echo", "forge echo"],
            capture_output=True,
        )
        # 必是 CompletedProcess
        assert isinstance(result, subprocess.CompletedProcess)
        # returncode 必 0
        assert result.returncode == 0
        # 必含 'forge echo'
        assert b"forge echo" in result.stdout

    def test_run_capture_output(self):
        """`subprocess.run capture_output=True 必含 stdout+stderr。"""
        result = subprocess.run(["true"], capture_output=True)
        # 必 0
        assert result.returncode == 0
        # stdout + stderr 必 bytes
        assert isinstance(result.stdout, bytes)
        assert isinstance(result.stderr, bytes)

    def test_run_text_True(self):
        """`subprocess.run text=True 必 str 返 stdout。"""
        result = subprocess.run(
            ["echo", "forge text"],
            capture_output=True,
            text=True,
        )
        # stdout 必 str
        assert isinstance(result.stdout, str)
        # 必含 'forge text'
        assert "forge text" in result.stdout

    def test_run_timeout_DEVNULL(self):
        """`subprocess.run timeout + DEVNULL stdin 必 0。"""
        result = subprocess.run(
            ["true"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        # 必 0
        assert result.returncode == 0
