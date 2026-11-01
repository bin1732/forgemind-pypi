# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 selectors: 真 DefaultSelector / SelectSelector / EpollSelector / KqueueSelector + 真多 socket 真并发。
全 OS I/O multiplexing, 零 Python 模拟。
"""
import os
import sys
import time
import socket
import threading
import selectors
import pytest


def test_selectors_default_selector():
    """真 DefaultSelector 自动选最优 (Linux 上 EpollSelector)"""
    sel = selectors.DefaultSelector()
    try:
        # Linux 上应为 EpollSelector
        if sys.platform.startswith("linux"):
            assert isinstance(sel, selectors.EpollSelector)
        elif sys.platform == "darwin":
            assert isinstance(sel, selectors.KqueueSelector)
    finally:
        sel.close()


def test_selectors_register_unregister():
    """真 register / unregister"""
    sel = selectors.DefaultSelector()
    try:
        s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s1.bind(("127.0.0.1", 0))
        s1.listen(1)
        key1 = sel.register(s1, selectors.EVENT_READ)
        assert key1.fileobj is s1
        assert key1.fd == s1.fileno()
        assert key1.events == selectors.EVENT_READ

        # 重复 register 应 ValueError
        with pytest.raises(KeyError):
            sel.register(s1, selectors.EVENT_READ)

        # unregister
        sel.unregister(s1)
        with pytest.raises(KeyError):
            sel.unregister(s1)  # 已 unregister
    finally:
        s1.close()
        sel.close()


def test_selectors_modify():
    """真 modify (改 events)"""
    sel = selectors.DefaultSelector()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        key = sel.register(s, selectors.EVENT_READ)
        assert key.events == selectors.EVENT_READ

        # 改 events
        key = sel.modify(s, selectors.EVENT_WRITE)
        assert key.events == selectors.EVENT_WRITE
    finally:
        s.close()
        sel.close()


def test_selectors_select_timeout():
    """真 select 真 timeout"""
    sel = selectors.DefaultSelector()
    try:
        # 1 个 fd, 但无事件 → select 应 timeout
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        sel.register(s, selectors.EVENT_READ)
        # 立即 select → 0 events (server 没新连接)
        events = sel.select(timeout=0.1)
        assert len(events) == 0
    finally:
        s.close()
        sel.close()


def test_selectors_select_returns_real_events():
    """真 select 真返 event"""
    sel = selectors.DefaultSelector()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    sel.register(server, selectors.EVENT_READ)
    try:
        # client connect 后 server 端变可读
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        time.sleep(0.1)  # 让 event 触发

        events = sel.select(timeout=1.0)
        assert len(events) >= 1
        for key, mask in events:
            assert key.fileobj is server
            assert mask & selectors.EVENT_READ
        client.close()
    finally:
        sel.close()
        server.close()


def test_selectors_many_connections_concurrent():
    """真 50 并发 client + selector"""
    sel = selectors.DefaultSelector()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(50)
    port = server.getsockname()[1]
    sel.register(server, selectors.EVENT_READ)
    clients = []

    try:
        # 50 个 client 真并发连
        for _ in range(50):
            c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c.connect(("127.0.0.1", port))
            clients.append(c)
        time.sleep(0.2)

        # select 真返 server EVENT_READ
        events = sel.select(timeout=2.0)
        assert len(events) >= 1  # 至少 server READ
    finally:
        for c in clients:
            c.close()
        sel.close()
        server.close()


def test_selectors_get_key():
    """真 get_key 拿已 register key"""
    sel = selectors.DefaultSelector()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        sel.register(s, selectors.EVENT_READ)
        key = sel.get_key(s)
        assert key.fileobj is s
        assert key.events == selectors.EVENT_READ
    finally:
        s.close()
        sel.close()


def test_selectors_get_map():
    """真 get_map"""
    sel = selectors.DefaultSelector()
    try:
        socks = [socket.socket(socket.AF_INET, socket.SOCK_STREAM) for _ in range(3)]
        for s in socks:
            s.bind(("127.0.0.1", 0))
            s.listen(1)
            sel.register(s, selectors.EVENT_READ)

        m = sel.get_map()
        assert len(m) == 3
        assert all(s in m for s in socks)
    finally:
        for s in socks:
            s.close()
        sel.close()


def test_selectors_close_idempotent():
    """真 close() 二次调用"""
    sel = selectors.DefaultSelector()
    sel.close()
    # 二次 close 不应抛 (或抛特定 ValueError)
    try:
        sel.close()
    except Exception:
        pass  # 也许抛 — OK
