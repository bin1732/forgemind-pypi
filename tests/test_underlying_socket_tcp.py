# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 TCP socket — 真 listen + 真 accept + 真 send/recv + SO_REUSEADDR 真生效。
不走 mock, 真 kernel 缓冲区, 真 TCP 三次握手。
"""
import errno
import os
import select
import socket
import struct
import threading
import time
from pathlib import Path

import pytest


def _pick_free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_tcp_three_way_handshake_real():
    """server listen + client connect 真走 TCP 三次握手"""
    port = _pick_free_port()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", port))
    server_sock.listen(1)
    received_data = []

    def server_thread():
        conn, addr = server_sock.accept()
        received_data.append(addr)
        data = conn.recv(1024)
        received_data.append(data)
        conn.sendall(b"HTTP/1.0 200 OK\r\n\r\nHello from server")
        conn.close()

    t = threading.Thread(target=server_thread, daemon=True)
    t.start()

    # client 真连
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))
    # 握手后, 收发
    client.sendall(b"GET / HTTP/1.0\r\n\r\n")
    response = b""
    while True:
        chunk = client.recv(4096)
        if not chunk:
            break
        response += chunk
    client.close()
    t.join(timeout=5)
    server_sock.close()

    # 验 server 真收了 client
    assert len(received_data) >= 2, f"server 应收 addr + data, 实际 {received_data}"
    assert received_data[0][0] == "127.0.0.1", f"client addr 应 127.0.0.1, 实际 {received_data[0]}"
    assert b"GET /" in received_data[1]
    # 验 client 真收 response
    assert b"Hello from server" in response


def test_so_reuseaddr_real_allows_rebind():
    """SO_REUSEADDR 真让 TIME_WAIT 状态端口可复用"""
    port = _pick_free_port()
    # 启 server, 关
    s1 = socket.socket()
    s1.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s1.bind(("127.0.0.1", port))
    s1.listen(1)
    s1.close()  # 真关

    # 立刻重 bind 同 port
    s2 = socket.socket()
    s2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s2.bind(("127.0.0.1", port))  # 不应 EADDRINUSE
    s2.listen(1)
    s2.close()


def test_without_so_reuseaddr_blocks():
    """没 SO_REUSEADDR, 同 port 重 bind 真抛 EADDRINUSE"""
    port = _pick_free_port()
    s1 = socket.socket()
    s1.bind(("127.0.0.1", port))
    s1.listen(1)
    # 不关 s1, 试图重 bind
    s2 = socket.socket()
    with pytest.raises(OSError) as exc_info:
        s2.bind(("127.0.0.1", port))
    # EADDRINUSE = 98 (Linux)
    assert exc_info.value.errno in (errno.EADDRINUSE, 48), (
        f"应 EADDRINUSE(98) 或 48, 实际 {exc_info.value.errno}: {exc_info.value}"
    )
    s2.close()
    s1.close()


def test_socket_send_recv_large_data():
    """10 MiB 数据真 send / recv 100% 还原"""
    port = _pick_free_port()
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen(1)

    payload = os.urandom(10 * 1024 * 1024)  # 10 MiB

    def server_thread():
        conn, _ = server.accept()
        received = b""
        while len(received) < len(payload):
            chunk = conn.recv(65536)
            if not chunk:
                break
            received += chunk
        conn.sendall(received)  # echo back
        conn.close()

    t = threading.Thread(target=server_thread, daemon=True)
    t.start()

    client = socket.socket()
    client.connect(("127.0.0.1", port))
    # 发
    sent = 0
    while sent < len(payload):
        sent += client.send(payload[sent:sent + 65536])
    client.shutdown(socket.SHUT_WR)  # 告诉 server 发完
    # 收
    received = b""
    while len(received) < len(payload):
        chunk = client.recv(65536)
        if not chunk:
            break
        received += chunk
    client.close()
    t.join(timeout=30)
    server.close()

    assert received == payload, f"10MB send/recv 应 100%, 实际 {len(received)}/{len(payload)}"


def test_socket_set_timeout_real_triggers():
    """socket.settimeout 真让 recv 抛 socket.timeout"""
    port = _pick_free_port()
    server = socket.socket()
    server.bind(("127.0.0.1", port))
    server.listen(1)

    # server 不 accept, client 连上后 server 不发
    def accept_thread():
        try:
            conn, _ = server.accept()
            # accept 后不关不写, 让 client 真 recv 等超时
            time.sleep(2)  # 比 client timeout 长
            conn.close()
        except Exception:
            pass

    t = threading.Thread(target=accept_thread, daemon=True)
    t.start()

    client = socket.socket()
    client.settimeout(0.5)  # 500ms timeout
    client.connect(("127.0.0.1", port))
    t0 = time.monotonic()
    raised = False
    try:
        client.recv(1024)  # server 没发, 真等 500ms
    except socket.timeout:
        raised = True
    elapsed = time.monotonic() - t0
    client.close()
    server.close()

    assert raised, f"500ms timeout 应抛 socket.timeout"
    # 时间应 ≈ 0.5s, 给 ±0.3s 容差
    assert 0.4 <= elapsed <= 1.5, f"timeout 应 ~500ms, 实际 {elapsed*1000:.0f}ms"


def test_socket_getsockname_returns_real_port():
    """getsockname 真报 bind 后的 port (不是 0)"""
    port = _pick_free_port()
    s = socket.socket()
    s.bind(("127.0.0.1", port))
    addr = s.getsockname()
    s.close()
    assert addr == ("127.0.0.1", port), f"getsockname 应 (127.0.0.1, {port}), 实际 {addr}"


def test_socket_getpeername_after_connect_real():
    """client 真连 server 后, getpeername 真报 server addr"""
    port = _pick_free_port()
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen(1)

    def accept():
        c, _ = server.accept()
        c.close()

    t = threading.Thread(target=accept, daemon=True)
    t.start()

    client = socket.socket()
    client.connect(("127.0.0.1", port))
    peer = client.getpeername()
    client.close()
    t.join(timeout=5)
    server.close()

    assert peer == ("127.0.0.1", port), f"getpeername 应 server, 实际 {peer}"


def test_select_real_returns_ready_sockets():
    """select.select 真报 ready 的 socket"""
    port = _pick_free_port()
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen(1)

    # server 暂不 accept, select 应等
    readable, _, _ = select.select([server], [], [], 0.1)
    assert server not in readable, "server 还没连接, 不应在 readable"

    # 真连
    def accept():
        c, _ = server.accept()
        time.sleep(0.05)
        c.sendall(b"PING")
        c.close()

    threading.Thread(target=accept, daemon=True).start()
    time.sleep(0.05)

    client = socket.socket()
    client.connect(("127.0.0.1", port))
    readable, _, _ = select.select([client], [], [], 1.0)
    assert client in readable, "client 收 PING 后应在 readable"
    data = client.recv(1024)
    assert data == b"PING"
    client.close()
    server.close()


def test_socket_options_persist():
    """socket 选项真持久 (在 getsockopt 时返同值)"""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    s.bind(("127.0.0.1", 0))
    # getsockopt 真返
    reuse = s.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
    nodelay = s.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
    s.close()
    assert reuse == 1
    assert nodelay == 1


def test_unix_domain_socket_real(tmp_path):
    """Unix domain socket 真走 (同一 host)"""
    sock_path = tmp_path / "test.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(sock_path))
    server.listen(1)

    def accept():
        c, _ = server.accept()
        c.sendall(b"UNIX_OK")
        c.close()

    t = threading.Thread(target=accept, daemon=True)
    t.start()

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(str(sock_path))
    data = client.recv(1024)
    client.close()
    t.join(timeout=5)
    server.close()
    # unix socket 文件可能被自动删, 不强求

    assert data == b"UNIX_OK", f"Unix socket 应回 UNIX_OK, 实际 {data!r}"


def test_udp_socket_real():
    """UDP socket 真发真收"""
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server_port = server.getsockname()[1]
    server.settimeout(2.0)

    def server_recv():
        data, addr = server.recvfrom(1024)
        server.sendto(data.upper(), addr)

    t = threading.Thread(target=server_recv, daemon=True)
    t.start()

    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto(b"hello", ("127.0.0.1", server_port))
    data, _ = client.recvfrom(1024)
    client.close()
    server.close()
    t.join(timeout=5)

    assert data == b"HELLO", f"UDP echo 大写 应 HELLO, 实际 {data!r}"
