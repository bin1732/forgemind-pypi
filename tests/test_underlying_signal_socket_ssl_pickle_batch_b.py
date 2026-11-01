# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""socket 与 ssl 的底层真实行为测试(全 stdlib,零模拟,零 mock)。

覆盖模块:
  socket —— 绑定 127.0.0.1 随机端口后真实 accept + send + recv、create_connection
             建连、recv 按请求字节数精确返回、sendall 完整传输、shutdown 半关闭
             传递 EOF、接收超时抛 socket.timeout、gethostbyname 解析本机名、
             UDP sendto / recvfrom 回环收发、getnameinfo 数字形式解析、
             setsockopt / getsockopt 生效、SO_REUSEADDR 允许重绑同一端口、
             getaddrinfo 配 AI_NUMERICHOST 的纯数字解析。
  ssl —— SSLContext 的真实创建与默认校验设置、TLS 能力常量与 OpenSSL 版本、
             create_default_context 的校验策略、TLSVersion 枚举取值。

真实测试项(12 个 socket + 4 个 ssl = 16):
  1.  test_socket_bind_listen_accept_send_recv_on_loopback
  2.  test_socket_create_connection_reaches_listening_server
  3.  test_socket_recv_returns_exactly_requested_bytes
  4.  test_socket_sendall_transmits_payload_in_full
  5.  test_socket_shutdown_write_signals_eof_to_peer
  6.  test_socket_recv_raises_timeout_when_peer_silent
  7.  test_socket_gethostbyname_resolves_localhost_ipv4
  8.  test_socket_udp_sendto_recvfrom_loopback
  9.  test_socket_getnameinfo_numeric_returns_ip_and_port
  10. test_socket_getsockopt_reflects_setsockopt_value
  11. test_socket_so_reuseaddr_allows_rebinding_same_port
  12. test_socket_getaddrinfo_with_ai_numerichost_returns_numeric_address
  13. test_ssl_context_creation_sets_protocol_defaults
  14. test_ssl_has_tls_capability_constants_reflect_openssl_build
  15. test_ssl_create_default_context_enables_verification
  16. test_ssl_tls_version_enum_exposes_protocol_bounds

所有 socket 用例都走本机回环的真实套接字,不涉及外部网络。
"""

import hashlib
import ipaddress
import socket
import threading

import pytest

import ssl


# ======================== socket ========================
def test_socket_bind_listen_accept_send_recv_on_loopback():
    """验证绑在 127.0.0.1 随机端口的服务端真实 accept 到连接,双向收发字节一致。"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    host, port = server.getsockname()
    assert host == "127.0.0.1"
    assert port != 0
    server.listen(1)
    server.settimeout(10)
    client = socket.create_connection((host, port), timeout=10)
    conn, peer = server.accept()
    try:
        assert peer[0] == host
        assert peer[1] == client.getsockname()[1]
        client.sendall(b"hello-forgemind")
        assert conn.recv(64) == b"hello-forgemind"
        conn.sendall(b"ack-forgemind")
        assert client.recv(64) == b"ack-forgemind"
    finally:
        conn.close()
        client.close()
        server.close()


def test_socket_create_connection_reaches_listening_server():
    """验证 create_connection 连上监听端口后,对端地址与本地地址都符合预期。"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(10)
    host, port = server.getsockname()
    with socket.create_connection((host, port), timeout=10) as client:
        conn, _ = server.accept()
        try:
            assert client.getpeername() == (host, port)
            assert client.getsockname()[0] == host
            assert client.getsockname()[1] != port
            assert conn.getpeername() == client.getsockname()
            assert conn.getsockname() == (host, port)
        finally:
            conn.close()
            server.close()


def test_socket_recv_returns_exactly_requested_bytes():
    """验证 recv(n) 精确返回 n 个字节,剩余数据留在缓冲区供下次读取。"""
    left, right = socket.socketpair()
    left.settimeout(10)
    right.settimeout(10)
    try:
        right.sendall(b"0123456789")
        assert left.recv(64) == b"0123456789"
        right.sendall(b"abcdefghij")
        assert left.recv(4) == b"abcd"
        assert left.recv(3) == b"efg"
        assert left.recv(3) == b"hij"
    finally:
        left.close()
        right.close()


def test_socket_sendall_transmits_payload_in_full():
    """验证 sendall 把 256 KiB 数据完整送到对端,长度与 SHA256 摘要完全一致。"""
    payload = bytes(range(256)) * 1024
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(10)
    host, port = server.getsockname()
    received = bytearray()

    def receiver():
        conn, _ = server.accept()
        with conn:
            while len(received) < len(payload):
                chunk = conn.recv(65536)
                if not chunk:
                    break
                received.extend(chunk)

    thread = threading.Thread(target=receiver)
    thread.start()
    try:
        client = socket.create_connection((host, port), timeout=10)
        client.sendall(payload)
        client.close()
        thread.join(timeout=20)
        assert not thread.is_alive()
        assert len(received) == len(payload)
        assert hashlib.sha256(bytes(received)).hexdigest() == hashlib.sha256(payload).hexdigest()
    finally:
        server.close()


def test_socket_shutdown_write_signals_eof_to_peer():
    """验证 shutdown(SHUT_WR) 让对端 recv 读到空串(EOF),反向通道仍可传数据。"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(10)
    host, port = server.getsockname()
    client = socket.create_connection((host, port), timeout=10)
    conn, _ = server.accept()
    try:
        client.sendall(b"half-close")
        assert conn.recv(32) == b"half-close"
        client.shutdown(socket.SHUT_WR)
        assert conn.recv(32) == b""
        conn.sendall(b"still-open")
        assert client.recv(32) == b"still-open"
    finally:
        conn.close()
        client.close()
        server.close()


def test_socket_recv_raises_timeout_when_peer_silent():
    """验证对端不回数据时,recv 在设定时限后抛出 socket.timeout。"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()
    client = socket.create_connection((host, port), timeout=10)
    try:
        client.settimeout(0.5)
        with pytest.raises(socket.timeout):
            client.recv(16)
        assert socket.timeout is TimeoutError
    finally:
        client.close()
        server.close()


def test_socket_gethostbyname_resolves_localhost_ipv4():
    """验证 gethostbyname('localhost') 解析出回环 IPv4 地址,且与 getaddrinfo 结果一致。"""
    address = socket.gethostbyname("localhost")
    assert address == socket.gethostbyname("localhost")
    parsed = ipaddress.ip_address(address)
    assert parsed.version == 4
    assert parsed.is_loopback is True
    resolved = {
        entry[4][0]
        for entry in socket.getaddrinfo("localhost", None, socket.AF_INET)
    }
    assert address in resolved


def test_socket_udp_sendto_recvfrom_loopback():
    """验证 UDP 套接字在回环上 sendto 后,recvfrom 收到同样的字节与源地址。"""
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", 0))
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender.bind(("127.0.0.1", 0))
    try:
        receiver.settimeout(10)
        sender.sendto(b"udp-payload", receiver.getsockname())
        data, addr = receiver.recvfrom(128)
        assert data == b"udp-payload"
        assert addr[0] == "127.0.0.1"
        assert addr[1] == sender.getsockname()[1]
    finally:
        sender.close()
        receiver.close()


def test_socket_getnameinfo_numeric_returns_ip_and_port():
    """验证 getnameinfo 配 NI_NUMERICHOST/NI_NUMERICSERV 时原样返回 IP 与端口。"""
    host, port = socket.getnameinfo(
        ("127.0.0.1", 8080), socket.NI_NUMERICHOST | socket.NI_NUMERICSERV
    )
    assert host == "127.0.0.1"
    assert port == "8080"


def test_socket_getsockopt_reflects_setsockopt_value():
    """验证 setsockopt 设置的 SO_REUSEADDR / SO_KEEPALIVE 值能被 getsockopt 读回。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR) == 1
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) == 1
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR) == 0


def test_socket_so_reuseaddr_allows_rebinding_same_port():
    """验证处于 TIME_WAIT 的端口,带 SO_REUSEADDR 可重绑成功,不带则报 EADDRINUSE。"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(10)
    host, port = server.getsockname()
    client = socket.create_connection((host, port), timeout=10)
    conn, _ = server.accept()
    server.close()
    conn.close()
    client.close()

    reuse = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    reuse.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        reuse.bind((host, port))
        assert reuse.getsockname() == (host, port)
    finally:
        reuse.close()

    plain = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(OSError) as excinfo:
            plain.bind((host, port))
        assert excinfo.value.errno == 98
    finally:
        plain.close()


def test_socket_getaddrinfo_with_ai_numerichost_returns_numeric_address():
    """验证 getaddrinfo 配 AI_NUMERICHOST 时直接给出数字地址,不依赖域名解析。"""
    results = socket.getaddrinfo("127.0.0.1", 80, flags=socket.AI_NUMERICHOST)
    assert len(results) >= 1
    for family, socktype, _proto, _canon, sockaddr in results:
        assert family == socket.AF_INET
        assert sockaddr == ("127.0.0.1", 80)
    assert any(entry[1] == socket.SOCK_STREAM for entry in results)


# ======================== ssl ========================
def test_ssl_context_creation_sets_protocol_defaults():
    """验证新建的客户端 SSLContext 默认要求证书校验,服务端上下文默认不校验。"""
    client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    assert isinstance(client_ctx, ssl.SSLContext)
    assert client_ctx.protocol == ssl.PROTOCOL_TLS_CLIENT
    assert client_ctx.verify_mode == ssl.CERT_REQUIRED
    assert client_ctx.check_hostname is True

    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    assert server_ctx.protocol == ssl.PROTOCOL_TLS_SERVER
    assert server_ctx.check_hostname is False
    assert server_ctx.verify_mode == ssl.CERT_NONE


def test_ssl_has_tls_capability_constants_reflect_openssl_build():
    """验证 TLS 能力常量与 OpenSSL 版本信息真实反映当前构建。"""
    if hasattr(ssl, "HAS_TLS"):
        assert ssl.HAS_TLS is True
    else:
        assert "HAS_TLS" not in dir(ssl)
        assert ssl.HAS_TLSv1_2 is True
    assert ssl.HAS_TLSv1_3 is True
    assert ssl.HAS_ALPN is True
    assert ssl.HAS_SNI is True
    assert ssl.HAS_SSLv2 is False
    assert ssl.OPENSSL_VERSION_INFO[0] >= 3


def test_ssl_create_default_context_enables_verification():
    """验证 create_default_context 强制开启证书校验与主机名校验,并可设置协议下界。"""
    ctx = ssl.create_default_context()
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True
    # 最低版本由链接的 OpenSSL 决定:有的环境取系统默认值,有的取
    # 显式设定的下界。两者都表示启用了校验。
    assert ctx.minimum_version in (
        ssl.TLSVersion.MINIMUM_SUPPORTED,
        ssl.TLSVersion.TLSv1_2,
    )
    assert ctx.maximum_version == ssl.TLSVersion.MAXIMUM_SUPPORTED
    assert ssl.create_default_context() is not ctx
    assert ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH).verify_mode == ssl.CERT_REQUIRED
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2


def test_ssl_tls_version_enum_exposes_protocol_bounds():
    """验证 TLSVersion 枚举中 TLS 1.2/1.3 的协议编号,以及上下界哨兵值。"""
    assert int(ssl.TLSVersion.TLSv1_2) == 771
    assert int(ssl.TLSVersion.TLSv1_3) == 772
    assert int(ssl.TLSVersion.MINIMUM_SUPPORTED) == -2
    assert int(ssl.TLSVersion.MAXIMUM_SUPPORTED) == -1
    assert ssl.TLSVersion.TLSv1_2 < ssl.TLSVersion.TLSv1_3
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2
    assert ctx.maximum_version == ssl.TLSVersion.TLSv1_3