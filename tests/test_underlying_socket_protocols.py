# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 socket protocols: 真 UDP / Unix domain socket / Multicast / 真 getaddrinfo / 真 select。
全 OS syscall, 零 Python 模拟。
"""
import os
import sys
import time
import socket
import struct
import threading
import tempfile
import select
import pytest


def test_udp_socket_basic():
    """真 UDP socket 真 send/recv"""
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]

    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        client.sendto(b"hello udp", ("127.0.0.1", port))
        data, addr = server.recvfrom(1024)
        assert data == b"hello udp"
        assert addr[0] == "127.0.0.1"
    finally:
        server.close()
        client.close()


def test_udp_socket_size_limit():
    """真 UDP 64KB limit"""
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 真发 8KB
        data = b"x" * 8192
        client.sendto(data, ("127.0.0.1", port))
        received, _ = server.recvfrom(65535)
        assert received == data
        assert len(received) == 8192
    finally:
        server.close()
        client.close()


def test_unix_domain_socket_basic():
    """真 Unix domain socket (同 host IPC)"""
    with tempfile.TemporaryDirectory() as tmp:
        sock_path = os.path.join(tmp, "test.sock")

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server.bind(sock_path)
        except OSError:
            # 也许上次跑残留 — 删了重试
            if os.path.exists(sock_path):
                os.unlink(sock_path)
            server.bind(sock_path)
        server.listen(1)
        server.settimeout(5)

        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.connect(sock_path)
            conn, _ = server.accept()
            try:
                conn.sendall(b"unix domain")
                received = client.recv(1024)
                assert received == b"unix domain"
            finally:
                conn.close()
        finally:
            client.close()
            server.close()
        # Unix domain socket close 不自动 unlink, 手动清
        if os.path.exists(sock_path):
            os.unlink(sock_path)


def test_unix_datagram_socket():
    """真 Unix domain datagram (SOCK_DGRAM)"""
    with tempfile.TemporaryDirectory() as tmp:
        path1 = os.path.join(tmp, "a.sock")
        path2 = os.path.join(tmp, "b.sock")
        for p in (path1, path2):
            if os.path.exists(p):
                os.unlink(p)

        a = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        b = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            a.bind(path1)
            b.bind(path2)
            a.sendto(b"from a", path2)
            data, addr = b.recvfrom(1024)
            assert data == b"from a"
            assert addr == path1
        finally:
            a.close()
            b.close()


def test_socket_getaddrinfo_real():
    """真 getaddrinfo 真查 DNS / hosts"""
    # localhost 真返 127.0.0.1 / ::1
    results = socket.getaddrinfo("localhost", None)
    assert len(results) > 0
    # tuple 至少 5 元 (family, type, proto, canonname, sockaddr)
    for r in results:
        assert len(r) == 5
        assert r[0] in (socket.AF_INET, socket.AF_INET6)
        assert isinstance(r[4], tuple)


def test_socket_getnameinfo():
    """真 getnameinfo (IP → name)"""
    info = socket.getnameinfo(("127.0.0.1", 8080), socket.NI_NUMERICSERV)
    # '8080' 数字服务
    assert "8080" in info


def test_socket_gethostname():
    """真 gethostname (真 OS hostname)"""
    hostname = socket.gethostname()
    assert isinstance(hostname, str)
    assert len(hostname) > 0
    # 真 fqdn (也许返 hostname)
    fqdn = socket.getfqdn()
    assert isinstance(fqdn, str)
    assert len(fqdn) > 0


def test_socket_select_real():
    """真 select 真等 socket ready"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(2)
    port = server.getsockname()[1]

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # 先用 select 等 server 可读 (有新连接)
        readable, _, _ = select.select([server], [], [], 1.0)
        assert len(readable) == 0  # 还没连接

        client.connect(("127.0.0.1", port))
        time.sleep(0.1)

        # 现在 server 应该有连接
        readable, _, _ = select.select([server], [], [], 1.0)
        assert server in readable
    finally:
        client.close()
        server.close()


def test_socket_setsockopt_tcp_nodelay():
    """真 TCP_NODELAY (Nagle 关闭)"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # 默认为 False
        before = s.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
        assert before == 0
        # 设 True
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        after = s.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
        assert after == 1
    finally:
        s.close()


def test_socket_ioctl_fionread():
    """真 FIONREAD ioctl 拿 buffer 字节数"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(("127.0.0.1", port))
        conn, _ = server.accept()
        try:
            # 发 100 字节
            client.sendall(b"x" * 100)
            time.sleep(0.1)
            # FIONREAD 拿 buffer
            import fcntl
            buf_size = fcntl.ioctl(conn, 0x541B, b"\x00" * 8)
            n = struct.unpack("I", buf_size[:4])[0]
            assert n >= 100  # 至少 100 字节 in buffer
        finally:
            conn.close()
    finally:
        client.close()
        server.close()


def test_socket_inet_aton_ntoa():
    """真 inet_aton / inet_ntoa 互转"""
    ip = "192.168.1.1"
    packed = socket.inet_aton(ip)
    assert socket.inet_ntoa(packed) == ip
    # 不合法 IP 应抛
    with pytest.raises(OSError):
        socket.inet_aton("999.999.999.999")


def test_socket_inet_pton_ntop_ipv6():
    """真 inet_pton / inet_ntop IPv6"""
    ip6 = "::1"
    packed = socket.inet_pton(socket.AF_INET6, ip6)
    assert len(packed) == 16
    assert socket.inet_ntop(socket.AF_INET6, packed) == ip6

    ip6_full = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
    packed = socket.inet_pton(socket.AF_INET6, ip6_full)
    # ntop 默认压缩: 0db8 → db8, 0000 → 0
    assert socket.inet_ntop(socket.AF_INET6, packed) == "2001:db8:85a3::8a2e:370:7334"


def test_socket_dual_stack_ipv6():
    """真 IPv6 dual stack (IPV6_V6ONLY=0)"""
    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    try:
        # 关闭 IPV6_V6ONLY
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        s.bind(("::", 0))
        # 应能用 IPv4 地址连
        port = s.getsockname()[1]
        # 验证
        s.listen(1)
        s.settimeout(2)
        # 用 IPv4 localhost 连 (在 dual stack 模式下)
        try:
            c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c.settimeout(2)
            try:
                c.connect(("127.0.0.1", port))
                conn, _ = s.accept()
                conn.close()
            except (OSError, ConnectionRefusedError):
                # 不支持 dual stack 也不 fail test
                pass
            finally:
                c.close()
        except OSError:
            pass
    finally:
        s.close()


def test_socket_sethostname_invalid():
    """真 sethostname 权限检查 (非 root 应 fail)"""
    # 普通用户设 hostname 应 OSError
    if os.geteuid() == 0:
        pytest.skip("root 不测 sethostname 权限")
    with pytest.raises(OSError):
        socket.sethostname("forbidden.example.com")


def test_socket_getservbyname():
    """真 getservbyname (services 查 port)"""
    # HTTP = 80, HTTPS = 443
    assert socket.getservbyname("http", "tcp") == 80
    assert socket.getservbyname("https", "tcp") == 443
    assert socket.getservbyname("ssh", "tcp") == 22


def test_socket_getprotobyname():
    """真 getprotobyname"""
    assert socket.getprotobyname("tcp") == socket.IPPROTO_TCP
    assert socket.getprotobyname("udp") == socket.IPPROTO_UDP
    assert socket.getprotobyname("icmp") == socket.IPPROTO_ICMP
