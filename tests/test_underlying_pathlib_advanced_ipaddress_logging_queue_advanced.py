# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`pathlib` 进阶 + `ipaddress` 进阶 (network addresses) + `logging` 进阶 (QueueHandler) + `queue` 真底层测试。

覆盖 pathlib 进阶 / IP 进阶 / 队列 handler / 队列 进阶:
  - `pathlib.PurePosixPath + WindowsPath 真跨平台 部件`
  - `pathlib.PurePath.match 真 glob 匹配`
  - `pathlib.PurePath.parts 真 list`
  - `pathlib.PurePath.drive + root 真 drive/root`
  - `pathlib.PurePath.as_posix 真 unix path string`
  - `pathlib.PurePath.is_absolute 真判`
  - `ipaddress.IPv4Network('10.0.0.0/24').hosts() 真 iter hosts`
  - `ipaddress.IPv4Network.num_addresses 真=256`
  - `ipaddress.IPv4Network.hostmask 真='0.0.0.255'`
  - `ipaddress.IPv4Network.netmask 真='255.255.255.0'`
  - `ipaddress.IPv4Network.broadcast_address 真 .255`
  - `logging.handlers.QueueHandler 真 send log 到 queue`
  - `logging.handlers.QueueListener 真 receive log`
  - `queue.Queue 真 put_many + 收多`
  - `queue.deque 真双端 (collections.deque)`
"""
import collections
import ipaddress
import logging
import logging.handlers
import pathlib
import queue
import threading
import time

import pytest


# -- pathlib 进阶 ------------------------------------------------------------

class TestPathlibAdvancedV2:
    def test_PurePath_parts(self):
        """`PurePath.parts 真 list of path components。"""
        p = pathlib.PurePosixPath("/a/b/c")
        assert p.parts == ("/", "a", "b", "c"), (
            f"parts 应=('/', 'a', 'b', 'c'),实际 {p.parts!r}"
        )

    def test_PurePath_match(self):
        """`PurePath.match 真 glob 匹配。"""
        p = pathlib.PurePosixPath("/forge/test.py")
        assert p.match("test.py") is True
        assert p.match("*.py") is True
        assert p.match("*.txt") is False

    def test_PurePath_drive_root(self):
        """`PureWindowsPath.drive + root 真分别返 'C:' + '\\\\'。"""
        p = pathlib.PureWindowsPath("C:/Users/forge")
        assert p.drive == "C:"
        assert p.root == "\\"
        # PurePosixPath drive 必是 ''
        p2 = pathlib.PurePosixPath("/home/forge")
        assert p2.drive == ""

    def test_PurePath_as_posix(self):
        """`PureWindowsPath.as_posix 真返 unix 形式 'C:/Users/forge'。"""
        p = pathlib.PureWindowsPath("C:\\Users\\forge")
        posix = p.as_posix()
        # 必用 /
        assert "/" in posix

    def test_PurePath_is_absolute(self):
        """`PurePath.is_absolute 真判绝对路径。"""
        assert pathlib.PurePosixPath("/a/b").is_absolute() is True
        assert pathlib.PurePosixPath("a/b").is_absolute() is False


# -- ipaddress 进阶 (network addresses) ---------------------------------------

class TestIpaddressNetwork:
    def test_IPv4Network_num_addresses(self):
        """`IPv4Network('10.0.0.0/24').num_addresses 真=256 (2**8)`。"""
        n = ipaddress.IPv4Network("10.0.0.0/24")
        assert n.num_addresses == 256, f"/24 应=256,实际 {n.num_addresses}"

    def test_IPv4Network_hostmask(self):
        """`IPv4Network.hostmask 真='0.0.0.255'`。"""
        n = ipaddress.IPv4Network("10.0.0.0/24")
        assert n.hostmask == ipaddress.IPv4Address("0.0.0.255"), (
            f"hostmask 应=0.0.0.255,实际 {n.hostmask}"
        )

    def test_IPv4Network_netmask(self):
        """`IPv4Network.netmask 真='255.255.255.0'`。"""
        n = ipaddress.IPv4Network("10.0.0.0/24")
        assert n.netmask == ipaddress.IPv4Address("255.255.255.0"), (
            f"netmask 应=255.255.255.0,实际 {n.netmask}"
        )

    def test_IPv4Network_broadcast_address(self):
        """`IPv4Network.broadcast_address 真='10.0.0.255'。"""
        n = ipaddress.IPv4Network("10.0.0.0/24")
        assert n.broadcast_address == ipaddress.IPv4Address("10.0.0.255"), (
            f"broadcast_address 应=10.0.0.255,实际 {n.broadcast_address}"
        )

    def test_IPv4Network_hosts(self):
        """`IPv4Network.hosts() 真返 hosts iterator (不含 net+bc)`。"""
        n = ipaddress.IPv4Network("10.0.0.0/30")
        hosts = list(n.hosts())
        # /30 有 4 地址, 减去 net+bc = 2
        assert len(hosts) == 2, f"/30 应有 2 hosts,实际 {len(hosts)}"
        # 必含 .1 + .2
        assert ipaddress.IPv4Address("10.0.0.1") in hosts
        assert ipaddress.IPv4Address("10.0.0.2") in hosts


# -- logging QueueHandler 进阶 ------------------------------------------------

class TestLoggingQueueHandler:
    def test_QueueHandler_puts_logrecord(self):
        """`QueueHandler 真发 log record 到 queue。"""
        q = queue.Queue()
        handler = logging.handlers.QueueHandler(q)
        record = logging.LogRecord(
            "forge", logging.INFO, "/x", 1, "queue test", (), None
        )
        handler.emit(record)
        # 队列里必有一条 (LogRecord 或 dict 取决于 python 版本)
        data = q.get(timeout=1)
        # 3.11+ default 是 LogRecord
        # 我们只验 msg 字段
        if isinstance(data, dict):
            assert data["msg"] == "queue test"
            assert data["levelname"] == "INFO"
        else:
            # LogRecord
            assert data.getMessage() == "queue test"
            assert data.levelname == "INFO"

    def test_QueueListener_drains(self):
        """`QueueListener 真从 queue 拿 log + 转给 target logger。"""
        q = queue.Queue()
        # 创 target logger
        target = logging.getLogger("forge_queue_target")
        target.setLevel(logging.INFO)
        captured = []
        # 临时 handler 收集
        class _Capture(logging.Handler):
            def emit(self, record):
                captured.append(record.getMessage())

        target.addHandler(_Capture())
        # Listener
        listener = logging.handlers.QueueListener(q, _Capture())
        # 启动
        listener.start()
        try:
            # 手动 enqueue 一条 record
            record = logging.LogRecord(
                "forge", logging.INFO, "/x", 1, "queue listener test", (), None
            )
            q.put(record)
            time.sleep(0.1)
            # 必收到
            assert "queue listener test" in captured
        finally:
            listener.stop()


# -- queue 进阶 --------------------------------------------------------------

class TestQueueAdvancedV3:
    def test_Queue_put_many(self):
        """`Queue.put_many 真发多 + qsize 跟踪。"""
        q = queue.Queue()
        # put 100 个
        for i in range(100):
            q.put(i)
        assert q.qsize() == 100
        # 收 100 个
        received = [q.get() for _ in range(100)]
        assert received == list(range(100))

    def test_deque_double_ended(self):
        """`collections.deque 真双端操作。"""
        d = collections.deque()
        d.append(1)
        d.append(2)
        d.appendleft(0)
        # 左 0
        assert d[0] == 0
        # 右 2
        assert d[-1] == 2
        # pop right
        assert d.pop() == 2
        # popleft
        assert d.popleft() == 0
        assert list(d) == [1]

    def test_deque_rotate(self):
        """`collections.deque.rotate 真旋转。"""
        d = collections.deque([1, 2, 3, 4, 5])
        d.rotate(2)
        # rotate(2) → [4, 5, 1, 2, 3]
        assert list(d) == [4, 5, 1, 2, 3]
        d.rotate(-3)
        # rotate(-3) → [2, 3, 4, 5, 1]
        assert list(d) == [2, 3, 4, 5, 1]
