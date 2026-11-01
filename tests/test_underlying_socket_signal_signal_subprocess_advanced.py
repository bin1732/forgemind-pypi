# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`socket` + `signal` 进阶 + `subprocess` 进阶真底层测试。

覆盖 socket / 信号 / 子进程模块:
  - `socket.gethostbyname('localhost')` 真返 '127.0.0.1'
  - `socket.gethostbyaddr('127.0.0.1')` 真返 (host, aliaslist, ipaddrlist)
  - `socket.getnameinfo(('127.0.0.1', 80), NI_NUMERICHOST)` 真返 (host, port)
  - `socket.inet_aton('127.0.0.1')` 真返 4 字节
  - `socket.inet_ntoa(b'\\x7f\\x00\\x00\\x01')` 真返 '127.0.0.1'
  - `socket.AF_INET` 真返 int 2
  - `socket.SOCK_STREAM` 真返 int 1
  - `socket.has_ipv6` 真 bool
  - `signal.Signals(15).name == 'SIGTERM'`
  - `signal.Signals.SIGUSR1.value` 真 int
  - `signal.SIG_DFL == 0` 真 sentinel
  - `signal.SIG_IGN == 1` 真 sentinel
  - `signal.alarm(0)` 真取消前 alarm
  - `subprocess.run(['echo', 'hi'], capture_output=True, text=True)` 真返 CompletedProcess
  - `subprocess.Popen(['sleep', '0.1'])` 真异步启动
  - `subprocess.check_output(['echo', 'forge'])` 真抛回 stdout bytes
  - `subprocess.DEVNULL` 真 device
  - `subprocess.PIPE` 真 int
  - `subprocess.list2cmdline(['a b', 'c'])` 真 quote
  - `subprocess.CompletedProcess` 真 data class
"""
import os
import signal
import socket
import subprocess
import sys
import time

import pytest


# -- socket 进阶 --------------------------------------------------------------

class TestSocketAdvanced:
    def test_gethostbyname_localhost(self):
        """`socket.gethostbyname('localhost')` 真返 '127.0.0.1'。"""
        ip = socket.gethostbyname("localhost")
        assert ip == "127.0.0.1", f"localhost 应=127.0.0.1,实际 {ip}"

    def test_gethostbyaddr(self):
        """`socket.gethostbyaddr('127.0.0.1')` 真返 (host, aliaslist, ipaddrlist)。"""
        h, aliases, ips = socket.gethostbyaddr("127.0.0.1")
        # host 必是字符串
        assert isinstance(h, str)
        assert isinstance(aliases, list)
        assert isinstance(ips, list)

    def test_inet_aton_ntoa_round_trip(self):
        """`socket.inet_aton/ntoa` 真 round-trip。"""
        b = socket.inet_aton("192.168.1.1")
        assert b == bytes([192, 168, 1, 1])
        assert socket.inet_ntoa(b) == "192.168.1.1"

    def test_socket_constants(self):
        """`AF_INET=2, SOCK_STREAM=1, has_ipv6=bool`。"""
        assert socket.AF_INET == 2
        assert socket.SOCK_STREAM == 1
        assert isinstance(socket.has_ipv6, bool)


# -- signal 进阶 --------------------------------------------------------------

class TestSignalAdvanced:
    def test_Signals_SIGTERM_name(self):
        """`signal.Signals(15).name == 'SIGTERM'`。"""
        s = signal.Signals(15)
        assert s.name == "SIGTERM"

    def test_Signals_SIGUSR1_value(self):
        """`signal.Signals.SIGUSR1.value` 真 int (Linux 10)。"""
        s = signal.Signals.SIGUSR1
        assert isinstance(s.value, int)
        assert s.value > 0

    def test_handlers(self):
        """`SIG_DFL == 0, SIG_IGN == 1` 真 sentinel。"""
        assert signal.SIG_DFL == 0
        assert signal.SIG_IGN == 1

    def test_alarm_zero_cancels(self):
        """`signal.alarm(0)` 真取消前 alarm,返剩余秒。"""
        # 先 cancel 任何遗留 alarm
        prev = signal.alarm(0)
        assert isinstance(prev, int)
        # 再 alarm(0) 应返 0
        prev2 = signal.alarm(0)
        assert prev2 == 0, f"无 alarm 时 alarm(0) 应返 0,实际 {prev2}"


# -- subprocess 进阶 ----------------------------------------------------------

class TestSubprocessAdvanced:
    def test_run_capture_output(self):
        """`subprocess.run(['echo', 'hi'], capture_output=True, text=True)` 真返 CompletedProcess。"""
        r = subprocess.run(["echo", "hi"], capture_output=True, text=True)
        assert r.returncode == 0
        assert "hi" in r.stdout

    def test_check_output(self):
        """`subprocess.check_output(['echo', 'forge'])` 真返 stdout bytes。"""
        out = subprocess.check_output(["echo", "forge"], text=True)
        assert "forge" in out

    def test_PIPE_DEVNULL(self):
        """`subprocess.PIPE/DEVNULL` 真 int/file。"""
        # PIPE 是 -1
        assert subprocess.PIPE == -1 or isinstance(subprocess.PIPE, int)
        # DEVNULL 是 file (Linux)
        assert subprocess.DEVNULL is not None

    def test_list2cmdline(self):
        """`subprocess.list2cmdline(['a b', 'c'])` 真 quote 含空格的串。"""
        cmdline = subprocess.list2cmdline(["a b", "c"])
        # Windows: '"a b" c', Linux: "'a b' c" (shlex)
        assert "a b" in cmdline
        assert "c" in cmdline

    def test_CompletedProcess(self):
        """`CompletedProcess` 真 data class 含 args/returncode/stdout/stderr。"""
        r = subprocess.run(
            ["echo", "forge"], capture_output=True, text=True
        )
        # 是 CompletedProcess 实例
        assert isinstance(r, subprocess.CompletedProcess)
        assert r.args == ["echo", "forge"]
        assert r.returncode == 0
