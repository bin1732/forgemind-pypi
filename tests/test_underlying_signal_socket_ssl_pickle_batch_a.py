# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""signal 与 socket 的底层真实行为测试(全 stdlib,零模拟,零 mock)。

覆盖模块:
  signal —— 信号编号常量、getsignal 查询结果、signal 在子进程里安装与恢复
             handler、raise_signal 真实触发 handler、默认 int handler 抛
             KeyboardInterrupt、alarm 的真实超时与取消、父进程用 os.kill
             向子进程投递信号、SIGTERM 真实终止子进程。
  socket —— socketpair 真实双向收发、AF_INET / SOCK_STREAM 等常量的取值、
             gethostname 的真实主机名、getaddrinfo 对本地回环地址的解析。

真实测试项(12 个 signal + 4 个 socket = 16):
  1.  test_signal_sigint_sigterm_use_standard_numbers
  2.  test_signal_signals_enum_lookup_by_number
  3.  test_signal_strsignal_returns_standard_descriptions
  4.  test_signal_getsignal_reports_default_handler
  5.  test_signal_getsignal_rejects_out_of_range_number
  6.  test_signal_valid_signals_contains_standard_handlers
  7.  test_signal_signal_installs_and_restores_handler_in_subprocess
  8.  test_signal_signal_rejects_unknown_signal_number_in_subprocess
  9.  test_signal_raises_signal_triggers_installed_handler_in_subprocess
  10. test_signal_raise_signal_with_default_handler_raises_keyboard_interrupt
  11. test_signal_alarm_handler_fires_after_one_second_in_subprocess
  12. test_signal_alarm_zero_cancels_pending_alarm_in_subprocess
  13. test_signal_sigusr1_kill_reaches_child_process_handler
  14. test_signal_sigterm_terminates_child_process_with_negative_returncode
  15. test_socketpair_transfers_bytes_in_both_directions
  16. test_socket_af_inet_and_sock_stream_constant_values
  17. test_socket_gethostname_returns_nonempty_local_hostname
  18. test_socket_getaddrinfo_resolves_loopback_ipv4_address

涉及 handler 安装的用例全部在独立子进程里执行,pytest 主进程的信号状态
不受影响。
"""

import os
import signal
import socket
import subprocess
import sys
import time

import pytest


def _run_python(code: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """在独立子进程里执行一段 Python 代码,返回其完成结果(不抛异常)。"""
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


# ======================== signal ========================
def test_signal_sigint_sigterm_use_standard_numbers():
    """验证 SIGINT=2、SIGTERM=15、SIGKILL=9、SIGALRM=14、SIGUSR1=10 的标准编号。"""
    assert signal.SIGINT == 2
    assert signal.SIGTERM == 15
    assert signal.SIGKILL == 9
    assert signal.SIGALRM == 14
    assert signal.SIGUSR1 == 10


def test_signal_signals_enum_lookup_by_number():
    """验证 signal.Signals 枚举可按编号反查,成员名与编号一一对应。"""
    assert signal.Signals(2) is signal.SIGINT
    assert signal.Signals(15) is signal.SIGTERM
    assert int(signal.SIGTERM) == 15
    assert signal.SIGINT.name == "SIGINT"
    assert signal.SIGTERM.name == "SIGTERM"
    assert signal.Signals.SIGALRM.value == 14


def test_signal_strsignal_returns_standard_descriptions():
    """验证 strsignal 对 SIGTERM/SIGINT/SIGKILL 返回标准英文描述文本。"""
    assert signal.strsignal(signal.SIGTERM) == "Terminated"
    assert signal.strsignal(signal.SIGINT) == "Interrupt"
    assert signal.strsignal(signal.SIGKILL) == "Killed"


def test_signal_getsignal_reports_default_handler():
    """验证显式设为 SIG_DFL 后,getsignal 返回 SIG_DFL 哨兵对象。"""
    code = (
        "import signal\n"
        "for name in ('SIGINT', 'SIGTERM', 'SIGALRM'):\n"
        "    signal.signal(getattr(signal, name), signal.SIG_DFL)\n"
        "print('sigint', signal.getsignal(signal.SIGINT) == signal.SIG_DFL)\n"
        "print('sigterm', signal.getsignal(signal.SIGTERM) == signal.SIG_DFL)\n"
        "print('sigalm', signal.getsignal(signal.SIGALRM) == signal.SIG_DFL)\n"
    )
    result = _run_python(code)
    assert result.returncode == 0, result.stderr
    assert "sigint True" in result.stdout
    assert "sigterm True" in result.stdout
    assert "sigalm True" in result.stdout


def test_signal_getsignal_rejects_out_of_range_number():
    """验证 getsignal 对越界编号抛 ValueError、对字符串编号抛 TypeError。"""
    with pytest.raises(ValueError):
        signal.getsignal(9999)
    with pytest.raises(TypeError):
        signal.getsignal("SIGINT")


def test_signal_valid_signals_contains_standard_handlers():
    """验证 valid_signals() 覆盖全部 Signals 枚举成员,并含标准信号编号。"""
    valid = signal.valid_signals()
    assert isinstance(valid, set)
    assert {signal.SIGINT, signal.SIGTERM, signal.SIGKILL, signal.SIGALRM} <= valid
    assert {int(member) for member in signal.Signals} <= valid


def test_signal_signal_installs_and_restores_handler_in_subprocess():
    """验证 signal 返回被替换的旧 handler,安装后 getsignal 命中该函数,恢复后回到 SIG_DFL。"""
    code = (
        "import signal\n"
        "def handler(signum, frame):\n"
        "    pass\n"
        "signal.signal(signal.SIGUSR1, signal.SIG_DFL)\n"
        "original = signal.getsignal(signal.SIGUSR1)\n"
        "previous = signal.signal(signal.SIGUSR1, handler)\n"
        "installed = signal.getsignal(signal.SIGUSR1)\n"
        "signal.signal(signal.SIGUSR1, original)\n"
        "print('original_is_dfl', original == signal.SIG_DFL)\n"
        "print('previous_is_dfl', previous == signal.SIG_DFL)\n"
        "print('installed_is_handler', installed is handler)\n"
        "print('after_restore_is_dfl', signal.getsignal(signal.SIGUSR1) == signal.SIG_DFL)\n"
    )
    result = _run_python(code)
    assert result.returncode == 0, result.stderr
    assert "original_is_dfl True" in result.stdout
    assert "previous_is_dfl True" in result.stdout
    assert "installed_is_handler True" in result.stdout
    assert "after_restore_is_dfl True" in result.stdout


def test_signal_signal_rejects_unknown_signal_number_in_subprocess():
    """验证子进程里 signal 传入越界编号抛 ValueError,且不会安装任何 handler。"""
    code = (
        "import signal, sys\n"
        "def handler(signum, frame):\n"
        "    pass\n"
        "try:\n"
        "    signal.signal(9999, handler)\n"
        "except ValueError as exc:\n"
        "    print('ValueError', exc)\n"
        "    sys.exit(0)\n"
        "print('NO_ERROR')\n"
        "sys.exit(1)\n"
    )
    result = _run_python(code)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ValueError signal number out of range" in result.stdout
    assert "NO_ERROR" not in result.stdout


def test_signal_raises_signal_triggers_installed_handler_in_subprocess():
    """验证 raise_signal 真实触发已安装的 handler,且 handler 收到正确的信号编号。"""
    code = (
        "import signal\n"
        "received = []\n"
        "def handler(signum, frame):\n"
        "    received.append(signum)\n"
        "signal.signal(signal.SIGUSR1, handler)\n"
        "signal.raise_signal(signal.SIGUSR1)\n"
        "print('received', received)\n"
        "print('count', len(received))\n"
    )
    result = _run_python(code)
    assert result.returncode == 0, result.stderr
    assert "received [10]" in result.stdout
    assert "count 1" in result.stdout


def test_signal_raise_signal_with_default_handler_raises_keyboard_interrupt():
    """验证默认 int handler 下 raise_signal(SIGINT) 抛出 KeyboardInterrupt。"""
    code = (
        "import signal, sys\n"
        "signal.signal(signal.SIGINT, signal.default_int_handler)\n"
        "try:\n"
        "    signal.raise_signal(signal.SIGINT)\n"
        "except KeyboardInterrupt:\n"
        "    print('KeyboardInterrupt caught')\n"
        "    sys.exit(0)\n"
        "print('NOT_RAISED')\n"
        "sys.exit(1)\n"
    )
    result = _run_python(code)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "KeyboardInterrupt caught" in result.stdout
    assert "NOT_RAISED" not in result.stdout


def test_signal_alarm_handler_fires_after_one_second_in_subprocess():
    """验证 alarm(1) 的 handler 在 1 秒后真实触发,触发间隔落在 [1.0, 2.5) 秒。"""
    code = (
        "import signal, time\n"
        "fired = []\n"
        "start = time.monotonic()\n"
        "def handler(signum, frame):\n"
        "    fired.append(time.monotonic() - start)\n"
        "signal.signal(signal.SIGALRM, handler)\n"
        "signal.alarm(1)\n"
        "time.sleep(2.5)\n"
        "print('fired_count', len(fired))\n"
        "print('elapsed', fired[0] if fired else -1)\n"
    )
    result = _run_python(code)
    assert result.returncode == 0, result.stderr
    assert "fired_count 1" in result.stdout
    elapsed = float(result.stdout.split("elapsed ")[1].split()[0])
    assert 1.0 <= elapsed < 2.5


def test_signal_alarm_zero_cancels_pending_alarm_in_subprocess():
    """验证 alarm(0) 取消挂起的 alarm,挂起 5 秒的定时器不会再触发 handler。"""
    code = (
        "import signal, time\n"
        "fired = []\n"
        "def handler(signum, frame):\n"
        "    fired.append(signum)\n"
        "signal.signal(signal.SIGALRM, handler)\n"
        "signal.alarm(5)\n"
        "signal.alarm(0)\n"
        "time.sleep(1.2)\n"
        "print('fired_count', len(fired))\n"
    )
    result = _run_python(code)
    assert result.returncode == 0, result.stderr
    assert "fired_count 0" in result.stdout


def test_signal_sigusr1_kill_reaches_child_process_handler(tmp_path):
    """验证父进程 os.kill(SIGUSR1) 投递的信号被子进程 handler 真实接收并执行。"""
    marker = tmp_path / "sigusr1_marker.txt"
    child_code = (
        "import signal, sys, time\n"
        "path = sys.argv[1]\n"
        "def handler(signum, frame):\n"
        "    with open(path, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('GOT:%d\\n' % signum)\n"
        "    raise SystemExit(0)\n"
        "signal.signal(signal.SIGUSR1, handler)\n"
        "with open(path, 'w', encoding='utf-8') as fh:\n"
        "    fh.write('READY\\n')\n"
        "time.sleep(15)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", child_code, str(marker)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if marker.exists() and "READY" in marker.read_text(encoding="utf-8"):
                break
            time.sleep(0.05)
        else:
            pytest.fail("子进程未在 10 秒内完成 SIGUSR1 handler 安装")
        os.kill(proc.pid, signal.SIGUSR1)
        proc.communicate(timeout=15)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    assert proc.returncode == 0
    content = marker.read_text(encoding="utf-8")
    assert "READY" in content
    assert "GOT:10" in content


def test_signal_sigterm_terminates_child_process_with_negative_returncode():
    """验证 SIGTERM 真实终止子进程,父进程看到的返回码为 -15。"""
    child_code = "import signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_DFL)\ntime.sleep(30)\n"
    proc = subprocess.Popen(
        [sys.executable, "-c", child_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(0.5)
        assert proc.poll() is None
        os.kill(proc.pid, signal.SIGTERM)
        proc.communicate(timeout=15)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    assert proc.returncode == -signal.SIGTERM
    assert proc.returncode == -15


# ======================== socket ========================
def test_socketpair_transfers_bytes_in_both_directions():
    """验证 socketpair 建立的两个套接字能真实互发数据,两个方向字节完全一致。"""
    left, right = socket.socketpair()
    left.settimeout(10)
    right.settimeout(10)
    try:
        left.sendall(b"ping-from-left")
        assert right.recv(64) == b"ping-from-left"
        right.sendall(b"pong-from-right")
        assert left.recv(64) == b"pong-from-right"
        assert left.family == socket.AF_UNIX
        assert left.fileno() != right.fileno()
        assert left.getsockname() == ""
        assert right.getsockname() == ""
    finally:
        left.close()
        right.close()


def test_socket_af_inet_and_sock_stream_constant_values():
    """验证 AF_INET=2、SOCK_STREAM=1、SOCK_DGRAM=2 等常量的真实取值。"""
    assert socket.AF_INET == 2
    assert socket.SOCK_STREAM == 1
    assert socket.SOCK_DGRAM == 2
    assert socket.AF_UNIX == 1
    assert socket.AF_INET6 != socket.AF_INET
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        assert sock.family == socket.AF_INET
        assert sock.type == socket.SOCK_STREAM


def test_socket_gethostname_returns_nonempty_local_hostname():
    """验证 gethostname 返回非空且不含空白字符的主机名字符串。"""
    hostname = socket.gethostname()
    assert isinstance(hostname, str)
    assert hostname != ""
    assert len(hostname) <= 255
    assert all(not char.isspace() for char in hostname)
    assert all(char.isalnum() or char in "._-" for char in hostname)


def test_socket_getaddrinfo_resolves_loopback_ipv4_address():
    """验证 getaddrinfo 对 127.0.0.1 解析出 AF_INET 结果,地址与端口原样返回。"""
    results = socket.getaddrinfo("127.0.0.1", 0, family=socket.AF_INET)
    assert len(results) >= 1
    for family, socktype, _proto, _canon, sockaddr in results:
        assert family == socket.AF_INET
        assert sockaddr[0] == "127.0.0.1"
        assert sockaddr[1] == 0
    assert any(entry[1] == socket.SOCK_STREAM for entry in results)
