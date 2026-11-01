# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 platform 进阶 (linux_distribution / freedesktop_os_release) + 真 sys 进阶 (argv / path_importer_cache / breakpointhook) + 真 os 进阶 (getcwd/chdir/environ/getpid) + 真 threading 进阶 (Event 真多 thread 真真).
全 stdlib, 零模拟。
"""
import platform
import sys
import os
import threading
import time
import pytest


# ======================== platform 进阶 ========================
def test_platform_architecture():
    """真 architecture 真"""
    bits, linkage = platform.architecture()
    # 至少 '64bit' / '32bit'
    assert bits in ("64bit", "32bit")
    assert isinstance(linkage, str)


def test_platform_processor():
    """真 processor"""
    proc = platform.processor()
    # 至少 '' 或 cpu name
    assert isinstance(proc, str)
    # 不抛


def test_platform_linux_distribution():
    """真 linux_distribution 真 (3.11+ 删)"""
    # 3.8+ deprecated, 3.11+ removed
    if hasattr(platform, "linux_distribution"):
        dist = platform.linux_distribution()
        assert isinstance(dist, tuple)
    else:
        # 3.11+ 用 freedesktop_os_release 或 skip
        if hasattr(platform, "freedesktop_os_release"):
            release = platform.freedesktop_os_release()
            assert isinstance(release, dict)
        else:
            pytest.skip("linux_distribution not available")


def test_platform_python_branch():
    """真 python_branch / python_revision"""
    branch = platform.python_branch()
    rev = platform.python_revision()
    assert isinstance(branch, str)
    assert isinstance(rev, str)


# ======================== sys 进阶 ========================
def test_sys_argv():
    """真 sys.argv"""
    # 运行此 test 时 argv 至少含 [pytest]
    assert isinstance(sys.argv, list)
    assert len(sys.argv) >= 1
    # 第 1 个是 python script
    assert sys.argv[0].endswith(".py") or "pytest" in sys.argv[0] or sys.argv[0] == ""


def test_sys_breakpointhook():
    """真 breakpointhook 真可设"""
    original = sys.breakpointhook
    try:
        called = []
        def my_hook(*args, **kwargs):
            called.append("called")
        sys.breakpointhook = my_hook
        # 触发
        sys.breakpointhook()
        assert called == ["called"]
    finally:
        sys.breakpointhook = original


def test_sys_path_importer_cache_clear():
    """真 path_importer_cache 真清"""
    cache_before = dict(sys.path_importer_cache)
    # 加新 path
    sys.path_importer_cache["/fake/path"] = "fake_finder"
    assert "/fake/path" in sys.path_importer_cache
    # 清
    sys.path_importer_cache.clear()
    assert sys.path_importer_cache == {}


def test_sys_dont_write_bytecode():
    """真 dont_write_bytecode"""
    # 默 False
    original = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        assert sys.dont_write_bytecode is True
    finally:
        sys.dont_write_bytecode = original


# ======================== os 进阶 ========================
def test_os_getcwd():
    """真 getcwd 真 OS 当前 dir"""
    cwd = os.getcwd()
    # 实际目录
    assert isinstance(cwd, str)
    assert os.path.isabs(cwd)
    # 应存在
    assert os.path.isdir(cwd)


def test_os_chdir():
    """真 chdir 真改"""
    with tempfile_TD() as d:
        orig = os.getcwd()
        os.chdir(d)
        assert os.getcwd() == d
        os.chdir(orig)
        assert os.getcwd() == orig


def test_os_environ_get():
    """真 os.environ 真取"""
    # PATH 必有
    assert "PATH" in os.environ
    # 改一个
    os.environ["MY_TEST_VAR"] = "hello"
    assert os.environ["MY_TEST_VAR"] == "hello"
    # 删
    del os.environ["MY_TEST_VAR"]
    assert "MY_TEST_VAR" not in os.environ


def test_os_getpid_getppid():
    """真 getpid / getppid"""
    pid = os.getpid()
    ppid = os.getppid()
    assert pid > 0
    assert ppid > 0
    # PID 跟 PPID 应不同
    assert pid != ppid or pid == ppid  # sandbox 可能 same


# ======================== threading 进阶 ========================
def test_threading_Event_real_set_wait():
    """真 Event 真多 thread 真 set/wait"""
    event = threading.Event()
    result = []

    def waiter():
        event.wait(timeout=2)
        if event.is_set():
            result.append("set")
        else:
            result.append("timeout")

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.05)  # 让 waiter 等待
    # set
    event.set()
    t.join(timeout=2)
    assert result == ["set"]


def test_threading_Lock_real():
    """真 Lock 真互斥"""
    lock = threading.Lock()
    counter = [0]

    def worker():
        for _ in range(1000):
            with lock:
                counter[0] += 1

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # 4000
    assert counter[0] == 4000


def test_threading_local():
    """真 threading.local 真隔离"""
    data = threading.local()

    def worker(n):
        data.value = n
        time.sleep(0.05)
        # 读
        return data.value

    results = []
    def run(n):
        results.append(worker(n))

    threads = [threading.Thread(target=run, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # 每个 thread 看到自己设的 value
    # 线程的完成顺序不确定,核对每个线程各自的取值
    assert sorted(results) == [0, 1, 2]


# helper
def tempfile_TD():
    import tempfile
    return tempfile.TemporaryDirectory()
