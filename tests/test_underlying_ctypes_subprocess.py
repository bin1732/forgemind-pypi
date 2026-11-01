# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 ctypes 调 libc + 真 subprocess stdin/stdout 通信。
不走 mock, 真 C 库, 真进程间 pipe。
"""
import ctypes
import ctypes.util
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


def test_ctypes_getpid_matches_os_getpid():
    """ctypes 真调 libc.getpid() 应 = os.getpid()"""
    libc_path = ctypes.util.find_library("c")
    assert libc_path, "Linux 应能找到 libc"
    libc = ctypes.CDLL(libc_path)
    libc.getpid.restype = ctypes.c_int
    pid_c = libc.getpid()
    pid_py = os.getpid()
    assert pid_c == pid_py, f"C getpid {pid_c} != Python getpid {pid_py}"


def test_ctypes_sleep_actually_sleeps():
    """ctypes 真调 libc.usleep() 真睡"""
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    libc.usleep.argtypes = [ctypes.c_uint]
    libc.usleep.restype = None
    t0 = time.monotonic()
    libc.usleep(50_000)  # 50ms
    elapsed = time.monotonic() - t0
    assert 0.045 <= elapsed <= 0.5, f"usleep(50ms) 应 ~50ms, 实际 {elapsed*1000:.0f}ms"


def test_ctypes_strlen_actually_counts():
    """ctypes 真调 libc.strlen() 算字符串长度"""
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    libc.strlen.argtypes = [ctypes.c_char_p]
    libc.strlen.restype = ctypes.c_size_t
    n = libc.strlen(b"hello world")
    assert n == 11, f"strlen 应 11, 实际 {n}"
    assert libc.strlen(b"") == 0
    assert libc.strlen(b"a") == 1


def test_ctypes_getenv_returns_real_env():
    """ctypes 真调 libc.getenv() 读环境变量"""
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    libc.getenv.argtypes = [ctypes.c_char_p]
    libc.getenv.restype = ctypes.c_char_p

    os.environ["FORGEMIND_TEST_LIBC"] = "real-c-value"
    val = libc.getenv(b"FORGEMIND_TEST_LIBC")
    assert val is not None
    assert val.decode("utf-8") == "real-c-value"
    # 不存在的 env
    val_none = libc.getenv(b"FORGEMIND_DEFINITELY_NOT_SET_12345")
    assert val_none is None


def test_ctypes_malloc_free_actually_works():
    """ctypes 真调 libc.malloc / free 真分配真释放"""
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    libc.malloc.argtypes = [ctypes.c_size_t]
    libc.malloc.restype = ctypes.c_void_p
    libc.free.argtypes = [ctypes.c_void_p]
    libc.free.restype = None

    # 100 字节
    ptr = libc.malloc(100)
    assert ptr is not None and ptr != 0, f"malloc 应返非空, 实际 {ptr}"
    # 写
    ctypes.memset(ptr, 0x41, 100)  # 100 个 'A'
    # 读
    buf = (ctypes.c_char * 100).from_address(ptr)
    assert bytes(buf) == b"A" * 100, "memset 后真应是 100 个 A"
    # 释放
    libc.free(ptr)


def test_ctypes_memcpy_actually_copies():
    """ctypes.memcpy 真拷字节"""
    src = b"X" * 1024
    dst = (ctypes.c_char * 1024)()
    ctypes.memmove(dst, src, 1024)
    assert bytes(dst) == src, f"memcpy 后 dst 应 = src, 实际 {bytes(dst)[:10]!r}..." if bytes(dst) != src else True


def test_subprocess_stdin_pipe_real_communication():
    """真 subprocess 通过 stdin/stdout 通信, 不是 args"""
    # 子进程读 stdin, 大写, 写 stdout
    script = """
import sys
for line in sys.stdin:
    sys.stdout.write(line.upper())
    sys.stdout.flush()
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate(input="hello\nworld\nforge\n", timeout=10)
    assert err == ""
    assert out == "HELLO\nWORLD\nFORGE\n", f"stdin 大写应 HELLO\\nWORLD\\nFORGE\\n, 实际: {out!r}"


def test_subprocess_stdin_pipe_real_sum():
    """真 subprocess 一次发 stdin, 收 stdout"""
    script = (
        "import sys\n"
        "for line in sys.stdin:\n"
        "    line = line.strip()\n"
        "    if not line or line == 'quit':\n"
        "        continue\n"
        "    nums = [int(x) for x in line.split(',')]\n"
        "    sys.stdout.write('sum=' + str(sum(nums)) + '\\n')\n"
        "    sys.stdout.flush()\n"
        "sys.stdout.write('done\\n')\n"
        "sys.stdout.flush()\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", script],
        input="1,2,3\n10,20\n100,200,300\nquit\n",
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0, f"子进程失败: {r.stderr}"
    out = r.stdout
    assert "sum=6" in out, f"应 sum=6, 实际: {out!r}"
    assert "sum=30" in out, f"应 sum=30, 实际: {out!r}"
    assert "sum=600" in out, f"应 sum=600, 实际: {out!r}"
    assert out.strip().endswith("done")


def test_subprocess_returncode_after_exception():
    """子进程抛异常, 父进程真能拿非零 returncode"""
    r = subprocess.run(
        [sys.executable, "-c", "raise ValueError('test error')"],
        capture_output=True, text=True, timeout=5,
    )
    assert r.returncode != 0
    assert "ValueError" in r.stderr
    assert "test error" in r.stderr


def test_subprocess_no_window_terminal_windows_compat():
    """真 subprocess 在 Linux 也走, 不依赖 Windows 特性"""
    # 这条测的是跨平台行为: 不传 creationflags / CREATE_NEW_CONSOLE
    # 在 Linux 上等价于普通 Popen
    r = subprocess.run([sys.executable, "-c", "print('ok')"],
                       capture_output=True, text=True, timeout=5)
    assert r.stdout.strip() == "ok"
    assert r.returncode == 0
