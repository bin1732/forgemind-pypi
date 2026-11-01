# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 os 真 read / write 真 + 真 fcntl 真 flock 真 + 真 mmap 真跨进程 mmap + 真 tempfile 进阶 (mkdtemp 0o700 + NamedTemporaryFile 真 reopen) + 真 os.scandir 真列 + 真 os.walk 真遍历。
全 stdlib, 零模拟。
"""
import os
import fcntl
import mmap
import tempfile
import pathlib
import stat as stat_mod
import pytest


# ======================== os 真 read/write ========================
def test_os_read_write_real():
    """真 os.read / os.write 真 fd"""
    fd, path = tempfile.mkstemp()
    try:
        # write
        n = os.write(fd, b"hello world")
        assert n == 11
        # seek + read
        os.lseek(fd, 0, os.SEEK_SET)
        data = os.read(fd, 100)
        assert data == b"hello world"
        os.close(fd)
        # 真文件内容
        with open(path, "rb") as f:
            assert f.read() == b"hello world"
    finally:
        os.unlink(path)


def test_os_lseek_whence():
    """真 lseek + whence 真"""
    fd, path = tempfile.mkstemp()
    try:
        os.write(fd, b"0123456789")
        # SEEK_SET: 0
        os.lseek(fd, 0, os.SEEK_SET)
        assert os.read(fd, 1) == b"0"
        # SEEK_CUR: 5 → 5
        os.lseek(fd, 4, os.SEEK_CUR)
        assert os.read(fd, 1) == b"5"
        # SEEK_END: -1
        os.lseek(fd, -1, os.SEEK_END)
        assert os.read(fd, 1) == b"9"
        os.close(fd)
    finally:
        os.unlink(path)


def test_os_pread_pwrite():
    """真 pread / pwrite 真"""
    fd, path = tempfile.mkstemp()
    try:
        os.pwrite(fd, b"hello", 0)
        os.pwrite(fd, b"world", 5)
        # pread 不动 offset
        data = os.pread(fd, 5, 0)
        assert data == b"hello"
        data2 = os.pread(fd, 5, 5)
        assert data2 == b"world"
        os.close(fd)
        with open(path, "rb") as f:
            assert f.read() == b"helloworld"
    finally:
        os.unlink(path)


def test_os_ftruncate():
    """真 ftruncate 真截"""
    fd, path = tempfile.mkstemp()
    try:
        os.write(fd, b"X" * 100)
        os.ftruncate(fd, 10)
        os.close(fd)
        with open(path, "rb") as f:
            assert f.read() == b"X" * 10
    finally:
        os.unlink(path)


def test_os_fstat():
    """真 fstat 真文件状态"""
    fd, path = tempfile.mkstemp()
    try:
        os.write(fd, b"abc")
        s = os.fstat(fd)
        assert s.st_size == 3
        # 真 regular
        assert stat_mod.S_ISREG(s.st_mode)
        os.close(fd)
    finally:
        os.unlink(path)


# ======================== fcntl flock ========================
def test_fcntl_flock_shared():
    """真 flock 真共享锁"""
    fd, path = tempfile.mkstemp()
    try:
        # LOCK_SH
        fcntl.flock(fd, fcntl.LOCK_SH)
        # 锁住后还能 LOCK_SH
        fd2 = os.open(path, os.O_RDONLY)
        try:
            fcntl.flock(fd2, fcntl.LOCK_SH | fcntl.LOCK_NB)
            # 成功 (共享 + 共享)
            fcntl.flock(fd2, fcntl.LOCK_UN)
        finally:
            os.close(fd2)
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    finally:
        os.unlink(path)


def test_fcntl_flock_exclusive_block():
    """真 flock 真排他锁真阻塞"""
    fd, path = tempfile.mkstemp()
    try:
        # 真排他
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # 另个 fd 试 LOCK_EX LOCK_NB → BlockingIOError
        fd2 = os.open(path, os.O_RDWR)
        try:
            with pytest.raises((BlockingIOError, OSError)):
                fcntl.flock(fd2, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd2)
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    finally:
        os.unlink(path)


# ======================== mmap 跨进程 ========================
def _mmap_child(path):
    """subprocess worker"""
    with open(path, "r+b") as f:
        with mmap.mmap(f.fileno(), 100) as m:
            if m[0:4] == b"MAIN":
                m[0:4] = b"CHLD"
            return "ok"


def test_mmap_shared_across_forks():
    """真 mmap 真 fork 共享"""
    import multiprocessing
    # 创文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(b"\x00" * 100)
        path = f.name
    try:
        # 主进程设标志
        with open(path, "r+b") as f:
            with mmap.mmap(f.fileno(), 100) as m:
                m[0:4] = b"MAIN"
        # 跑子进程 (ProcessPool 沙箱 trigger assert_spawning)
        p = multiprocessing.Process(target=_mmap_child, args=(path,))
        p.start()
        p.join(timeout=10)
        # 验
        with open(path, "rb") as f:
            content = f.read()
        assert content[:4] == b"CHLD"
    finally:
        os.unlink(path)


# ======================== os.scandir ========================
def test_os_scandir():
    """真 scandir 真列 dir"""
    with tempfile.TemporaryDirectory() as d:
        # 创文件
        for i in range(3):
            pathlib.Path(d, f"f{i}.txt").write_text("x")
        pathlib.Path(d, "sub").mkdir()
        # scandir
        entries = list(os.scandir(d))
        names = [e.name for e in entries]
        assert "f0.txt" in names
        assert "f1.txt" in names
        assert "f2.txt" in names
        assert "sub" in names
        # 3 file + 1 dir = 4
        assert len(entries) == 4


def test_os_scandir_with_file_type():
    """真 scandir 真 file_type"""
    with tempfile.TemporaryDirectory() as d:
        pathlib.Path(d, "a.txt").write_text("x")
        pathlib.Path(d, "b").mkdir()
        for entry in os.scandir(d):
            if entry.name == "a.txt":
                # True for regular file
                assert entry.is_file()
            elif entry.name == "b":
                assert entry.is_dir()


# ======================== os.walk ========================
def test_os_walk_recursive():
    """真 walk 真递归"""
    with tempfile.TemporaryDirectory() as d:
        # 结构
        pathlib.Path(d, "a.txt").write_text("x")
        pathlib.Path(d, "sub1").mkdir()
        pathlib.Path(d, "sub1", "b.txt").write_text("y")
        pathlib.Path(d, "sub1", "sub2").mkdir()
        pathlib.Path(d, "sub1", "sub2", "c.txt").write_text("z")
        # walk
        all_files = []
        for root, dirs, files in os.walk(d):
            for f in files:
                all_files.append(os.path.join(root, f))
        # 3 file
        assert len(all_files) == 3
        # 包含
        names = [os.path.basename(p) for p in all_files]
        assert "a.txt" in names
        assert "b.txt" in names
        assert "c.txt" in names


# ======================== tempfile 进阶 ========================
def test_tempfile_mkdtemp_permissions():
    """真 mkdtemp 真 0o700 默认"""
    d = tempfile.mkdtemp()
    try:
        mode = os.stat(d).st_mode & 0o777
        # 默认 0o700
        assert mode == 0o700
    finally:
        os.rmdir(d)


def test_NamedTemporaryFile_reopen():
    """真 NamedTemporaryFile 真 reopen"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("initial")
        path = f.name
    try:
        # 关后 reopen 读
        with open(path, "r") as r:
            assert r.read() == "initial"
        # 追加
        with open(path, "a") as a:
            a.write(" more")
        # 重读
        with open(path, "r") as r:
            assert r.read() == "initial more"
    finally:
        os.unlink(path)
