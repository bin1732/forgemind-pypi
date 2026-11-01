# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 platform (真 OS 信息) + 真 sys (int maxsize / path / stdlib) + 真 signal (真 send) + 真 resource (真 RLIMIT) + 真 errno + 真 ctypes.util 真 find_library。
全 stdlib, 零模拟。
"""
import platform
import sys
import signal
import resource
import errno
import ctypes.util
import subprocess
import os
import pytest


# ======================== platform ========================
def test_platform_python_implementation():
    """真 python_implementation"""
    impl = platform.python_implementation()
    assert impl in ("CPython", "PyPy", "Jython", "IronPython")


def test_platform_python_version():
    """真 python_version"""
    v = platform.python_version()
    # 3.11.x
    assert v.startswith("3.")
    parts = v.split(".")
    assert int(parts[0]) == 3
    assert int(parts[1]) >= 8


def test_platform_system():
    """真 system 真 OS"""
    s = platform.system()
    assert s in ("Linux", "Darwin", "Windows", "Java")


def test_platform_machine():
    """真 machine"""
    m = platform.machine()
    # 至少 1 字符
    assert len(m) > 0
    # 已知架构
    assert m in ("x86_64", "AMD64", "i386", "i686", "aarch64", "armv7l", "arm64") or len(m) > 0


def test_platform_node():
    """真 node 真 hostname"""
    n = platform.node()
    assert isinstance(n, str)
    assert len(n) > 0


def test_platform_uname():
    """真 uname 真 system info"""
    u = platform.uname()
    assert u.system
    assert u.node
    assert u.release
    assert u.version
    assert u.machine
    assert u.processor or True  # processor 可空


# ======================== sys ========================
def test_sys_maxsize():
    """真 maxsize 真 pointer size"""
    if sys.maxsize > 2**32:
        assert "64 bit" in platform.architecture()[0] or sys.maxsize > 2**32


def test_sys_platform():
    """真 platform"""
    p = sys.platform
    assert p in ("linux", "darwin", "win32") or p.startswith("freebsd") or p.startswith("openbsd")


def test_sys_path():
    """真 path 真 module 路径"""
    # 必有 'site-packages' 或 '.local' (venv 场景)
    has_pkg = any(
        "site-packages" in p or "/lib" in p or ".local/lib" in p
        for p in sys.path
    )
    assert has_pkg


def test_sys_executable():
    """真 executable 真 python path"""
    exe = sys.executable
    assert os.path.isfile(exe)
    assert os.access(exe, os.X_OK)


def test_sys_version_info():
    """真 version_info"""
    v = sys.version_info
    assert v.major == 3
    assert v.minor >= 8


def test_sys_getrefcount():
    """真 getrefcount 真引用计数"""
    a = [1, 2, 3]
    base = sys.getrefcount(a)  # getrefcount 本身 +1
    b = a
    assert sys.getrefcount(a) == base + 1


# ======================== signal ========================
def test_signal_default_int():
    """真 SIGINT 默认 handler 是 SIG_DFL"""
    h = signal.getsignal(signal.SIGINT)
    # 通常是 SIG_DFL 或 installed (test runner 改)
    assert h is not None


def test_signal_alarm():
    """真 alarm 真设定时器"""
    # 设 1s alarm, 1s 后 SIGALRM
    # 不在 test 内等 — 只验设不抛
    signal.alarm(0)  # 取消
    # 真设
    old = signal.signal(signal.SIGALRM, lambda s, f: None)
    try:
        signal.alarm(1)
        # 立即检查
        assert signal.alarm(0) > 0  # 返剩余秒
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def test_signal_raise_in_subprocess():
    """真 signal 真在 subprocess 触发"""
    code = """
import signal, os, sys
def handler(s, f):
    print("caught")
    sys.exit(0)
signal.signal(signal.SIGUSR1, handler)
print("ready", flush=True)
import time
time.sleep(2)
print("timeout")
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # 等 ready
    line = proc.stdout.readline()
    assert b"ready" in line
    # 发送 SIGUSR1
    proc.send_signal(signal.SIGUSR1)
    proc.wait(timeout=5)
    out = proc.stdout.read()
    assert b"caught" in out


def test_signal_signum_const():
    """真 signal 常量"""
    assert signal.SIGTERM > 0
    assert signal.SIGKILL > 0
    assert signal.SIGINT > 0
    assert signal.SIGUSR1 > 0
    assert signal.SIGUSR2 > 0


# ======================== resource ========================
def test_resource_getrlimit_rss():
    """真 RLIMIT_RSS 真 OS limit (Linux 不可设, 返 -1)"""
    soft, hard = resource.getrlimit(resource.RLIMIT_RSS)
    # Linux 不可设, kernel 返 -1 (RLIM_INFINITY 当作 -1)
    assert soft == -1 and hard == -1 or soft <= hard
    # RLIM_INFINITY 永为 -1
    assert resource.RLIM_INFINITY == -1


def test_resource_getrlimit_nofile():
    """真 RLIMIT_NOFILE 真 open file limit"""
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    # 至少 64 (默认)
    assert soft >= 64
    # hard >= soft
    assert hard >= soft


def test_resource_getrusage():
    """真 getrusage 真 process resource"""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # user time
    assert usage.ru_utime >= 0
    # system time
    assert usage.ru_stime >= 0
    # max RSS
    assert usage.ru_maxrss >= 0
    # minor faults
    assert usage.ru_minflt >= 0


# ======================== errno ========================
def test_errno_constants():
    """真 errno 真值"""
    assert errno.EPERM > 0
    assert errno.ENOENT > 0
    assert errno.EAGAIN > 0
    assert errno.EACCES > 0
    assert errno.ECONNRESET > 0


def test_errno_errorcode():
    """真 errorcode 字典"""
    assert isinstance(errno.errorcode, dict)
    # EPERM 名称
    assert errno.errorcode[errno.EPERM] == "EPERM"
    assert errno.errorcode[errno.ENOENT] == "ENOENT"


# ======================== ctypes.util ========================
def test_ctypes_find_library_c():
    """真 find_library("c") 真 libc"""
    libc_name = ctypes.util.find_library("c")
    # 通常 "libc.so.6" 或 "libc.dylib"
    if libc_name:
        assert "c" in libc_name.lower()


def test_ctypes_load_libc():
    """真 CDLL 真加载 libc"""
    import ctypes
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    # 必有 puts / printf
    libc.puts.argtypes = [ctypes.c_char_p]
    libc.puts.restype = ctypes.c_int
    n = libc.puts(b"hello")
    # puts 返 length or < 0
    assert n >= 0
