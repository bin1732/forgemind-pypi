# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 multiprocessing — Manager 跨进程真共享 list / dict;
atexit 真在子进程跑; os.fork 真派生; 父进程共享 fd 句柄。
"""
import multiprocessing
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


def test_manager_dict_shared_across_processes():
    """Manager dict 跨 2 进程真共享"""
    with multiprocessing.Manager() as manager:
        shared_dict = manager.dict()
        shared_dict["key"] = "initial"

        def worker(d):
            d["from_worker"] = "yes"
            d["counter"] = d.get("counter", 0) + 1

        p = multiprocessing.Process(target=worker, args=(shared_dict,))
        p.start()
        p.join(timeout=5)
        assert p.exitcode == 0, f"子进程退码 {p.exitcode}"

        # 父进程应看到子进程的写入
        assert shared_dict.get("from_worker") == "yes"
        assert shared_dict.get("counter") == 1


def test_manager_list_shared_with_append():
    """Manager list 跨进程 append, 父进程真能看到"""
    with multiprocessing.Manager() as manager:
        shared_list = manager.list()

        def worker(lst, n):
            for i in range(n):
                lst.append(f"item_{i}")

        p = multiprocessing.Process(target=worker, args=(shared_list, 100))
        p.start()
        p.join(timeout=5)

        assert len(shared_list) == 100, f"应 100 项, 实际 {len(shared_list)}"
        assert shared_list[0] == "item_0"
        assert shared_list[99] == "item_99"


def test_atexit_runs_in_child_not_parent():
    """子进程的 atexit 只在子进程跑, 不在父进程"""
    marker = "CHILD_ATEXIT_RAN"
    marker_file = "/tmp/test_atexit_child_marker.txt"

    # 清理
    if os.path.exists(marker_file):
        os.unlink(marker_file)

    script = f"""
import atexit, os
def cleanup():
    with open({marker_file!r}, 'w') as f:
        f.write({marker!r})
atexit.register(cleanup)
print('PID=' + str(os.getpid()), flush=True)
import time
time.sleep(0.5)  # 短睡, 完成后自然退, 走 atexit
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    # 等子进程起 + 写 PID
    line = proc.stdout.readline().decode("utf-8", errors="ignore")
    child_pid = int(line.split("PID=")[1].strip())
    # 等子进程自然退 (走 atexit)
    proc.wait(timeout=10)

    # marker 真写
    assert os.path.exists(marker_file), (
        f"atexit 应写 marker, 实际不存在 (子进程 PID={child_pid})"
    )
    with open(marker_file) as f:
        content = f.read()
    assert content == marker
    # 父进程不应写 (我们没写)
    assert os.getpid() != child_pid
    # 清理
    os.unlink(marker_file)


def test_os_fork_creates_real_child():
    """os.fork 真派生子进程, 子进程真收到 fork 返回值 0"""
    # 沙箱可能没 os.fork (Windows), 跳过
    if not hasattr(os, "fork"):
        pytest.skip("Windows 没 os.fork")

    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        # 子进程
        os.write(w, f"CHILD_PID={os.getpid()}\n".encode())
        os._exit(0)
    else:
        # 父进程
        os.close(w)
        # 读子进程消息
        data = b""
        while True:
            chunk = os.read(r, 1024)
            if not chunk:
                break
            data += chunk
        os.close(r)
        # 收子进程
        _, status = os.waitpid(pid, 0)
        assert os.WIFEXITED(status), "子进程应正常退"
        assert os.WEXITSTATUS(status) == 0
        # 验证消息
        assert b"CHILD_PID=" in data
        child_pid_from_msg = int(data.decode().strip().split("=")[1])
        # 子进程 PID 应 = fork 返回值
        assert child_pid_from_msg == pid, f"消息中 PID {child_pid_from_msg} != fork 返回 {pid}"


def test_subprocess_with_cwd_changes_dir():
    """subprocess cwd 真切到子进程 (子进程 pwd 应 = 新 cwd)"""
    new_dir = "/tmp"
    r = subprocess.run(
        [sys.executable, "-c", "import os; print(os.getcwd())"],
        cwd=new_dir, capture_output=True, text=True, timeout=5,
    )
    assert r.stdout.strip() == new_dir, f"cwd 应 {new_dir}, 实际: {r.stdout!r}"


def test_subprocess_env_inheritance():
    """子进程真继承父进程 env (但可被 env= 覆盖)"""
    # 父进程设
    os.environ["FORGEMIND_TEST_INHERITED"] = "parent_value"
    r = subprocess.run(
        [sys.executable, "-c",
         "import os; print(os.environ.get('FORGEMIND_TEST_INHERITED', 'MISSING'))"],
        capture_output=True, text=True, timeout=5,
    )
    assert r.stdout.strip() == "parent_value", f"子进程应继承 env, 实际: {r.stdout!r}"
    del os.environ["FORGEMIND_TEST_INHERITED"]

    # 父进程 env 不含, 子进程也不含 (除非显式给 env=)
    r = subprocess.run(
        [sys.executable, "-c",
         "import os; print(os.environ.get('FORGEMIND_TEST_INHERITED', 'MISSING'))"],
        capture_output=True, text=True, timeout=5,
    )
    assert r.stdout.strip() == "MISSING"


def test_subprocess_env_override_does_not_leak():
    """subprocess env={} 真能屏蔽父 env (不让敏感变量漏)"""
    os.environ["FORGEMIND_TEST_SECRET"] = "topsecret"
    r = subprocess.run(
        [sys.executable, "-c",
         "import os; print(os.environ.get('FORGEMIND_TEST_SECRET', 'CLEAN'))"],
        env={},  # 显式给空 env
        capture_output=True, text=True, timeout=5,
    )
    assert r.stdout.strip() == "CLEAN", (
        f"env={{}} 应清空 env, 不让 'topsecret' 漏到子进程, 实际: {r.stdout!r}"
    )
    del os.environ["FORGEMIND_TEST_SECRET"]


def test_subprocess_pipe_3mb_data_integrity(tmp_path):
    """subprocess 真走 pipe 传 3 MiB 数据, 父进程收 100% 一致"""
    payload = b"X" * (3 * 1024 * 1024)
    # 写 tmp 文件, 子进程读 + 写 stdout (避免 argv 长限制)
    payload_file = tmp_path / "payload.bin"
    payload_file.write_bytes(payload)
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; "
         f"sys.stdout.buffer.write(open({str(payload_file)!r}, 'rb').read())"],
        capture_output=True, timeout=15,
    )
    assert r.returncode == 0
    assert r.stdout == payload, f"3MB pipe 应原样, 实际 {len(r.stdout)}/{len(payload)}"
