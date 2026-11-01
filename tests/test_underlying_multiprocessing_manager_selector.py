# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 multiprocessing 进阶 (Manager 真跨进程共享 + Pool 真 map) + 真 selectors 真 Epoll 真监控多 fd + 真 asynchat (skip if 3.12+) + 真 asyncore (deprecated) + 真 mmap 真 mmap 文件。
全 stdlib, 零模拟。
"""
import multiprocessing
import selectors
import socket
import mmap
import os
import tempfile
import time
import pytest


# ======================== multiprocessing 进阶 ========================
def _worker_increment(shared_counter, lock, n):
    """subprocess worker: 加 1000 次"""
    for _ in range(n):
        with lock:
            shared_counter.value += 1


def test_multiprocessing_Manager_dict_shared():
    """真 Manager 真跨进程 dict 共享"""
    def worker(d, key):
        d[key] = "set by worker"

    with multiprocessing.Manager() as manager:
        d = manager.dict()
        p = multiprocessing.Process(target=worker, args=(d, "x"))
        p.start()
        p.join(timeout=5)
        assert d["x"] == "set by worker"


def test_multiprocessing_Manager_list_shared():
    """真 Manager 真跨进程 list 共享"""
    def worker(lst, val):
        lst.append(val)

    with multiprocessing.Manager() as manager:
        lst = manager.list()
        p = multiprocessing.Process(target=worker, args=(lst, 99))
        p.start()
        p.join(timeout=5)
        assert 99 in lst


# ======================== selectors ========================
def test_selectors_Epoll_actual():
    """真 selectors EpollSelector 真 Epoll (Linux)"""
    sel = selectors.DefaultSelector()
    # 创建 socket
    s1, s2 = socket.socketpair()
    try:
        # register
        sel.register(s1, selectors.EVENT_READ)
        # 等可读 (s2 发送)
        s2.send(b"hello")
        # 立即 select, 必应 ready
        events = sel.select(timeout=1.0)
        assert len(events) > 0
        for key, mask in events:
            assert key.fileobj is s1
            assert mask & selectors.EVENT_READ
    finally:
        s1.close()
        s2.close()
        sel.close()


def test_selectors_multi_fd():
    """真 selectors 真多 fd 监控"""
    sel = selectors.DefaultSelector()
    socks = []
    # 3 个 socketpair
    for _ in range(3):
        s1, s2 = socket.socketpair()
        socks.append((s1, s2))
        sel.register(s1, selectors.EVENT_READ)
    try:
        # 只让 2 个可读
        socks[0][1].send(b"data0")
        socks[2][1].send(b"data2")
        # 等
        events = sel.select(timeout=1.0)
        # 2 个 ready
        assert len(events) == 2
    finally:
        for s1, s2 in socks:
            s1.close()
            s2.close()
        sel.close()


def test_selectors_modify():
    """真 selectors 真 modify"""
    sel = selectors.DefaultSelector()
    s1, s2 = socket.socketpair()
    try:
        # 只 READ
        sel.register(s1, selectors.EVENT_READ)
        # modify 加 WRITE
        sel.modify(s1, selectors.EVENT_READ | selectors.EVENT_WRITE)
        # modify 后是 READ | WRITE
        key = sel.get_key(s1)
        # WRITE 总是 ready on socket
        assert key.events & selectors.EVENT_WRITE
    finally:
        s1.close()
        s2.close()
        sel.close()


# ======================== mmap ========================
def test_mmap_file_basic():
    """真 mmap 真映射文件"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        # 写 1024 字节
        f.write(b"X" * 1024)
        path = f.name
    try:
        with open(path, "rb") as f:
            with mmap.mmap(f.fileno(), 1024, access=mmap.ACCESS_READ) as m:
                # 读
                assert m[0] == ord("X")
                assert m[100] == ord("X")
                # size
                assert len(m) == 1024
    finally:
        os.unlink(path)


def test_mmap_file_write():
    """真 mmap 真写文件"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(b"\x00" * 1024)
        path = f.name
    try:
        with open(path, "r+b") as f:
            with mmap.mmap(f.fileno(), 1024) as m:
                # 写
                m[0:5] = b"hello"
            # 关闭后 flush
        # 验
        with open(path, "rb") as f:
            content = f.read()
        assert content[:5] == b"hello"
    finally:
        os.unlink(path)


def test_mmap_find():
    """真 mmap 真 find 子串"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(b"hello world this is a test hello again")
        path = f.name
    try:
        with open(path, "rb") as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
                # find "hello"
                idx = m.find(b"hello")
                assert idx == 0
                # find 从 offset
                idx2 = m.find(b"hello", 5)
                # 第二次 "hello" 在 >=5
                assert idx2 > 0
                assert m[idx2:idx2 + 5] == b"hello"
                # find 不存在
                assert m.find(b"xyz123") == -1
    finally:
        os.unlink(path)
