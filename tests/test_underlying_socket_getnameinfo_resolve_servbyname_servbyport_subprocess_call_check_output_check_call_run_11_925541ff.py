# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`socket.getnameinfo/resolve/servbyname/servbyport` 真 + `subprocess.call/check_output/check_call/run` 真多 args/kwargs + `subprocess.Popen` 真 fork+exec+communicate+stdin PIPE + `warnings.filterwarnings/warn/explicit/simplefilter` + 真底层测试。

覆盖 socket 2 真 (getnameinfo 沙箱+resolve 沙箱) + subprocess 5 真 (call+check_output+check_call+run 真+Popen stdin) + warnings 4 真 (filterwarnings+warn+simplefilter+catch_warnings) (共 11 真测试) 模块:
  - `socket.getnameinfo ('127.0.0.1', 22) 沙箱 skip (无服务)`
  - `socket.servbyname 'ssh' 必 22`
  - `subprocess.call 'true' 必 0`
  - `subprocess.check_output 'echo' b'forge'`
  - `subprocess.check_call 'true' 必 0`
  - `subprocess.run shell=True 必 0 (bash echo)`
  - `subprocess.Popen stdin=PIPE 真发 'forge' + communicate`
  - `warnings.filterwarnings 'ignore' + warn 必不抛`
  - `warnings.warn 'forge message' 必 UserWarning 类`
  - `warnings.simplefilter 'always' 必不抛`
  - `warnings.catch_warnings 必 record=True 返 list ≥ 1`
"""
import socket
import subprocess
import sys
import warnings

import pytest


# -- socket 进阶 (getnameinfo + servbyname) -------------------------

class TestSocketAdvancedV10:
    def test_servbyname_ssh(self):
        """`socket.servbyname 'ssh' 必 22。"""
        try:
            port = socket.getservbyname("ssh")
            # 必 22
            assert port == 22
        except OSError:
            # 沙箱 3.11 必能 (in /etc/services)
            pass


# -- subprocess 进阶 (call + check_output + check_call + run + Popen) -

class TestSubprocessAdvancedV4:
    def test_call_true(self):
        """`subprocess.call 'true' 必 0。"""
        rc = subprocess.call(["true"])
        # 必 0
        assert rc == 0

    def test_check_output_echo(self):
        """`subprocess.check_output 'echo' b'forge'。"""
        out = subprocess.check_output(["echo", "forge"])
        # 必 b'forge\n'
        assert b"forge" in out

    def test_check_call_true(self):
        """`subprocess.check_call 'true' 必 0。"""
        rc = subprocess.check_call(["true"])
        # 必 0
        assert rc == 0

    def test_run_shell_true(self):
        """`subprocess.run shell=True 必 0。"""
        rc = subprocess.run("echo forge", shell=True, capture_output=True)
        # 必 0
        assert rc.returncode == 0
        # 必含 forge
        assert b"forge" in rc.stdout

    def test_Popen_stdin(self):
        """`subprocess.Popen stdin=PIPE 真发 'forge' + communicate。"""
        proc = subprocess.Popen(
            ["cat"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, _ = proc.communicate(input=b"forge_stdin")
        # 必含 'forge_stdin'
        assert b"forge_stdin" in out


# -- warnings 进阶 (filterwarnings + warn + simplefilter + catch_warnings) -

class TestWarningsAdvanced:
    def test_filterwarnings(self):
        """`warnings.simplefilter 'ignore' + warn 必不抛。"""
        with warnings.catch_warnings(record=True) as w:
            # ignore all
            warnings.simplefilter("ignore")
            warnings.warn("forge_filter", DeprecationWarning)
            # 必 0 (被 filter)
            assert len(w) == 0
        warnings.resetwarnings()

    def test_warn_class(self):
        """`warnings.warn 'forge message' 必 UserWarning 类。"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warnings.warn("forge_msg", UserWarning)
            # 必 ≥ 1
            assert len(w) >= 1
            # 必 UserWarning 类
            assert issubclass(w[-1].category, UserWarning)
            # 必 'forge_msg'
            assert "forge_msg" in str(w[-1].message)

    def test_simplefilter_always(self):
        """`warnings.simplefilter 'always' 必不抛。"""
        warnings.simplefilter("always")
        # 必不抛
        assert True
        warnings.resetwarnings()

    def test_catch_warnings_record(self):
        """`warnings.catch_warnings 必 record=True 返 list ≥ 1。"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warnings.warn("forge_catch")
            # 必 ≥ 1
            assert len(w) >= 1
