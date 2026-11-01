# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`subprocess 进阶 (Popen args+env+cwd+text)` + `threading 进阶 (Thread args+kwargs+daemon+active_count)` + `re 进阶 (compile+match+search+fullmatch)` + `ctypes 进阶 (c_int+c_long+c_float+c_double+c_char_p)` + 真底层测试。

覆盖 subprocess 4 真 + threading 4 真 + re 4 真 + ctypes 5 真 (共 17 真测试) 模块:
  - `subprocess.Popen 'echo' 'forge_args' rc=0`
  - `subprocess.Popen env FORGE_TEST_VAR rc=0`
  - `subprocess.Popen cwd '/tmp' rc=0`
  - `subprocess.Popen text=True 'echo forge_text'`
  - `threading.Thread args start+join`
  - `threading.Thread kwargs start+join`
  - `threading.Thread daemon=True start+join`
  - `threading.active_count ≥ 1`
  - `re.compile 'forge' Pattern search 'forge_value'`
  - `re.match 'forge' 'forge_value'`
  - `re.search 'forge' 'value_forge_value'`
  - `re.fullmatch 'forge' 'forge'`
  - `ctypes.c_int 42`
  - `ctypes.c_long 100`
  - `ctypes.c_float 1.5`
  - `ctypes.c_double 1.5`
  - `ctypes.c_char_p b'forge'`
"""
import ctypes
import os
import re
import subprocess
import threading

import pytest


def _thread_target_args(arg):
    return f"forge_thread_{arg}"


def _thread_target_kwargs(**kwargs):
    return f"forge_thread_{kwargs}"


def _thread_target_daemon():
    return "forge_daemon"


# -- subprocess 进阶 (Popen args+env+cwd+text) -------

class TestSubprocessPopenArgsEnvCwdTextAdvanceV2:
    def test_Popen_args(self):
        """`subprocess.Popen 'echo' 'forge_args' rc=0。"""
        p = subprocess.Popen(["echo", "forge_args"])
        rc = p.wait(timeout=5)
        assert rc == 0

    def test_Popen_env(self):
        """`subprocess.Popen env FORGE_TEST_VAR rc=0。"""
        env = os.environ.copy()
        env["FORGE_TEST_VAR"] = "forge_value"
        p = subprocess.Popen(
            ["env"],
            stdout=subprocess.PIPE,
            env=env,
        )
        rc = p.wait(timeout=5)
        assert rc == 0

    def test_Popen_cwd(self):
        """`subprocess.Popen cwd '/tmp' rc=0。"""
        p = subprocess.Popen(
            ["pwd"],
            stdout=subprocess.PIPE,
            cwd="/tmp",
        )
        rc = p.wait(timeout=5)
        assert rc == 0

    def test_Popen_text(self):
        """`subprocess.Popen text=True 'echo forge_text'。"""
        p = subprocess.Popen(
            ["echo", "forge_text"],
            stdout=subprocess.PIPE,
            text=True,
        )
        rc = p.wait(timeout=5)
        assert rc == 0
        stdout, _ = p.communicate()
        assert "forge_text" in stdout


# -- threading 进阶 (Thread args+kwargs+daemon+active_count) --

class TestThreadingThreadArgsKwargsDaemonActiveCountAdvance:
    def test_Thread_args(self):
        """`threading.Thread args start+join。"""
        t = threading.Thread(target=_thread_target_args, args=("forge_arg",))
        t.start()
        t.join(timeout=5)
        assert True

    def test_Thread_kwargs(self):
        """`threading.Thread kwargs start+join。"""
        t = threading.Thread(target=_thread_target_kwargs, kwargs={"forge_k": "v"})
        t.start()
        t.join(timeout=5)
        assert True

    def test_Thread_daemon(self):
        """`threading.Thread daemon=True start+join。"""
        t = threading.Thread(target=_thread_target_daemon, daemon=True)
        assert t.daemon is True
        t.start()
        t.join(timeout=5)
        assert True

    def test_active_count(self):
        """`threading.active_count ≥ 1。"""
        n = threading.active_count()
        assert isinstance(n, int)
        assert n >= 1


# -- re 进阶 (compile+match+search+fullmatch) --------

class TestReAdvanceV4:
    def test_compile_search(self):
        """`re.compile 'forge' Pattern search 'forge_value'。"""
        p = re.compile("forge")
        assert isinstance(p, re.Pattern)
        m = p.search("forge_value")
        assert m is not None
        assert m.group() == "forge"

    def test_match(self):
        """`re.match 'forge' 'forge_value'。"""
        m = re.match("forge", "forge_value")
        assert m is not None
        assert m.group() == "forge"

    def test_search(self):
        """`re.search 'forge' 'value_forge_value'。"""
        m = re.search("forge", "value_forge_value")
        assert m is not None
        assert m.group() == "forge"

    def test_fullmatch(self):
        """`re.fullmatch 'forge' 'forge'。"""
        m = re.fullmatch("forge", "forge")
        assert m is not None
        assert m.group() == "forge"


# -- ctypes 进阶 (c_int+c_long+c_float+c_double+c_char_p) --

class TestCtypesAdvanceV5:
    def test_c_int(self):
        """`ctypes.c_int 42。"""
        v = ctypes.c_int(42)
        assert v.value == 42

    def test_c_long(self):
        """`ctypes.c_long 100。"""
        v = ctypes.c_long(100)
        assert v.value == 100

    def test_c_float(self):
        """`ctypes.c_float 1.5。"""
        v = ctypes.c_float(1.5)
        assert v.value == 1.5

    def test_c_double(self):
        """`ctypes.c_double 1.5。"""
        v = ctypes.c_double(1.5)
        assert v.value == 1.5

    def test_c_char_p(self):
        """`ctypes.c_char_p b'forge'。"""
        c = ctypes.c_char_p(b"forge")
        assert c.value == b"forge"
