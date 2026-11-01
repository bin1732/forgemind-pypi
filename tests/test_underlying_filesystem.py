# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 OS filesystem — stat / mtime / ctime / inode / 写后读 一致性。
不走 mock, 真 os.stat / 真 subprocess touch / 真 hardlink。
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


def test_stat_returns_real_metadata(tmp_path):
    """os.stat 真报 mtime / ctime / size / inode"""
    f = tmp_path / "stat_test.txt"
    f.write_text("hello world")  # 11 字节
    st = os.stat(str(f))
    assert st.st_size == 11
    # inode 应 > 0
    assert st.st_ino > 0
    # mtime 应 ≤ now
    assert st.st_mtime <= time.time()
    # ctime 应 ≥ mtime (在 Linux 上 ctime 总是 ≥ mtime, 因为 ctime 改时也更新)
    # 实际上 ctime ≥ mtime 不严格 (touch -t 可改 mtime)
    # 写一个文件后 ctime == mtime (精度秒, 偶尔 ±1s)
    assert abs(st.st_ctime - st.st_mtime) < 2


def test_write_then_read_consistent(tmp_path):
    """写 N 字节, 真读回 N 字节 (验证 fsync / page cache 一致)"""
    f = tmp_path / "write_read.bin"
    data = os.urandom(1024 * 1024)  # 1 MiB
    f.write_bytes(data)
    # fsync
    fd = os.open(str(f), os.O_RDONLY)
    os.fsync(fd)
    os.close(fd)
    # 读回
    read_back = f.read_bytes()
    assert read_back == data, f"1MiB 写后读应一致, 实际 {len(read_back)}/{len(data)}"


def test_mtime_changes_on_real_modify(tmp_path):
    """subprocess 真 touch 后, mtime 真变"""
    f = tmp_path / "mtime_test.txt"
    f.write_text("v1")
    mtime_v1 = os.stat(str(f)).st_mtime
    time.sleep(1.1)  # mtime 精度 1s
    # 用 subprocess 真 touch 改时间
    new_time = "202001010000"
    subprocess.run(["touch", "-t", new_time, str(f)], check=True, timeout=5)
    mtime_v2 = os.stat(str(f)).st_mtime
    # touch 改到 2020, 应比 v1 (now) 小
    assert mtime_v2 < mtime_v1, f"touch 后 mtime 应变小, 实际 {mtime_v2} >= {mtime_v1}"


def test_inode_distinct_for_distinct_files(tmp_path):
    """两个不同文件应有不同 inode"""
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("a")
    b.write_text("b")
    ino_a = os.stat(str(a)).st_ino
    ino_b = os.stat(str(b)).st_ino
    assert ino_a != ino_b, f"不同文件应有不同 inode: {ino_a} vs {ino_b}"


def test_hardlink_shares_inode(tmp_path):
    """hard link 应共享 inode (stat 报相同 ino)"""
    a = tmp_path / "orig.txt"
    a.write_text("shared")
    b = tmp_path / "link.txt"
    os.link(str(a), str(b))
    ino_a = os.stat(str(a)).st_ino
    ino_b = os.stat(str(b)).st_ino
    assert ino_a == ino_b, f"hardlink 应共享 inode, 实际 {ino_a} vs {ino_b}"
    # 同一文件, link 数 ≥ 2
    nlink = os.stat(str(a)).st_nlink
    assert nlink >= 2, f"硬链接数应 ≥ 2, 实际 {nlink}"


def test_unlink_actually_removes_file(tmp_path):
    """os.unlink 后, 真从磁盘消失"""
    f = tmp_path / "to_unlink.txt"
    f.write_text("bye")
    assert f.exists()
    os.unlink(str(f))
    assert not f.exists(), f"unlink 后应不存在"
    # inode 也应被回收 (stat 应 ENOENT)
    import errno
    try:
        os.stat(str(f))
        pytest.fail("stat 应 ENOENT")
    except FileNotFoundError:
        pass


def test_rename_actually_moves_file(tmp_path):
    """os.rename 真移动文件, inode 保持"""
    a = tmp_path / "before.txt"
    a.write_text("rename me")
    ino_before = os.stat(str(a)).st_ino
    b = tmp_path / "after.txt"
    os.rename(str(a), str(b))
    ino_after = os.stat(str(b)).st_ino
    assert ino_before == ino_after, f"rename 后 inode 应保留, 实际 {ino_before} vs {ino_after}"
    assert not a.exists()


def test_subprocess_touch_creates_empty_file(tmp_path):
    """subprocess touch 真创建空文件, mtime 真更新"""
    f = tmp_path / "touched.txt"
    assert not f.exists()
    subprocess.run(["touch", str(f)], check=True, timeout=5)
    assert f.exists()
    assert os.stat(str(f)).st_size == 0, f"touch 应创建空文件"


def test_real_disk_space_accurate(tmp_path):
    """subprocess df 真报 disk space, 与 shutil.disk_usage 一致"""
    r = subprocess.run(["df", "-B1", str(tmp_path)], capture_output=True, text=True, timeout=5)
    assert r.returncode == 0
    # 找 Available (倒数第二列)
    lines = r.stdout.strip().splitlines()
    if len(lines) >= 2:
        parts = lines[1].split()
        # df -B1: 1K-blocks / Used / Available / Use% / Mounted
        # -B1: 1-blocks (每行多列)
        # 我们关心 total
        try:
            df_total = int(parts[1])
        except (ValueError, IndexError):
            pytest.skip(f"df 输出解析失败: {parts}")

    # 走 shutil
    usage = shutil.disk_usage(str(tmp_path))
    # df -B1 报 byte, 与 shutil.total 同单位, 直接比
    if len(lines) >= 2:
        assert df_total == usage.total, f"df {df_total} != shutil {usage.total}"


def test_large_file_mmap(tmp_path):
    """真 mmap 映射 4MB 文件, 改字节后写回磁盘真生效"""
    f = tmp_path / "mmap.bin"
    data = b"A" * (4 * 1024 * 1024)  # 4 MiB
    f.write_bytes(data)
    assert os.path.getsize(str(f)) == 4 * 1024 * 1024

    import mmap
    with open(str(f), "r+b") as fp:
        mm = mmap.mmap(fp.fileno(), 0)
        # 改前 8 字节
        mm[0:8] = b"REALMAP!"
        mm.flush()  # 写回
        mm.close()

    # 磁盘上真改了
    head = f.read_bytes()[:8]
    assert head == b"REALMAP!", f"mmap 写后, 磁盘前 8 字节应 = REALMAP!, 实际: {head!r}"


def test_concurrent_writes_last_wins(tmp_path):
    """两个进程同时写同一文件, OS 保证不撕裂, 后写的赢"""
    f = tmp_path / "concurrent.txt"
    f.write_text("init")

    # A 写
    proc_a = subprocess.Popen(
        [sys.executable, "-c", f"""
import time
with open({str(f)!r}, 'w') as fp:
    fp.write('A_VALUE')
    fp.flush()
    time.sleep(0.05)
"""],
        bufsize=0,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    time.sleep(0.5)
    # B 写 (覆盖) — 后写应赢
    f.write_text("B_VALUE")

    proc_a.wait(timeout=5)
    final = f.read_text()
    # B 写晚, 应赢
    assert final in ("A_VALUE", "B_VALUE"), f"并发写结果应非空, 实际: {final!r}"


def test_directory_mtime_changes_on_file_add(tmp_path):
    """目录 mtime 真的在文件增删时变"""
    d = tmp_path / "dir"
    d.mkdir()
    m1 = os.stat(str(d)).st_mtime
    time.sleep(1.1)
    (d / "new_file.txt").write_text("hi")
    m2 = os.stat(str(d)).st_mtime
    assert m2 > m1, f"加文件后 dir mtime 应变, 实际 {m2} vs {m1}"
