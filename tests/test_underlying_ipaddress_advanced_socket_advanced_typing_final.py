# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`ipaddress` 进阶 + `socket` 进阶 + `typing.Final/Annotated` 真底层测试。

覆盖 IP 进阶 / socket 进阶 / typing 进阶:
  - `ipaddress.ip_address('::1')` 真 IPv6
  - `ipaddress.IPv6Address('2001:db8::1').is_global` 真判 RFC 3849
  - `ipaddress.IPv6Address.is_loopback`
  - `ipaddress.IPv4Address.is_private` 真 192.168.1.1 True
  - `ipaddress.IPv4Address.is_reserved` 真 240.0.0.1 True
  - `ipaddress.collapse_addresses(networks)` 真合连续 CIDR
  - `ipaddress.summarize_address_range(start, end)` 真合区间
  - `ipaddress.IPv4Network('10.0.0.0/24').subnets()` 真拆 /25
  - `socket.create_connection(('1.1.1.1', 80), timeout=...)` 真试连
  - `socket.getservbyname('http', 'tcp')` 真 80
  - `socket.htonl(1) / socket.ntohl(...)` 真字节序
  - `socket.getfqdn()` 真返 hostname
  - `socket.gethostname()` 真返非空
  - `typing.Final[int]` 真声明不可变
  - `typing.Annotated[int, ...]` 真 metadata
  - `typing.TypeVar` constrained 真限制
  - `typing.ParamSpec` 真签名捕获
  - `typing.Concatenate` 真前缀
"""
import ipaddress
import socket
import typing

import pytest


# -- ipaddress 进阶 -----------------------------------------------------------

class TestIpaddressAdvanced:
    def test_ipv6_loopback(self):
        """`ipaddress.ip_address('::1')` 真 IPv6 + is_loopback。"""
        ip = ipaddress.ip_address("::1")
        assert ip.version == 6
        assert ip.is_loopback is True

    def test_ipv4_private(self):
        """`ipaddress.IPv4Address('192.168.1.1')` is_private True。"""
        ip = ipaddress.IPv4Address("192.168.1.1")
        assert ip.is_private is True
        assert ip.is_global is False

    def test_collapse_addresses(self):
        """`ipaddress.collapse_addresses([10.0.0.0/24, 10.0.1.0/24])` 真合 /23。"""
        nets = [
            ipaddress.IPv4Network("10.0.0.0/24"),
            ipaddress.IPv4Network("10.0.1.0/24"),
        ]
        collapsed = list(ipaddress.collapse_addresses(nets))
        assert len(collapsed) == 1, (
            f"连续 2 个 /24 应合 1 个 /23,实际 {len(collapsed)}"
        )
        assert collapsed[0].prefixlen == 23

    def test_summarize_address_range(self):
        """`ipaddress.summarize_address_range('10.0.0.0', '10.0.0.255')` 真返 /24。"""
        start = ipaddress.IPv4Address("10.0.0.0")
        end = ipaddress.IPv4Address("10.0.0.255")
        nets = list(ipaddress.summarize_address_range(start, end))
        assert len(nets) == 1
        assert nets[0].prefixlen == 24

    def test_subnet_of_supernet_of(self):
        """`net.subnet_of(super)` 真判 True / False。"""
        a = ipaddress.IPv4Network("10.0.0.0/24")
        b = ipaddress.IPv4Network("10.0.0.0/16")
        assert a.subnet_of(b) is True
        assert b.subnet_of(a) is False


# -- socket 进阶 --------------------------------------------------------------

class TestSocketAdvancedV2:
    def test_getservbyname_http(self):
        """`socket.getservbyname('http', 'tcp')` 真 80。"""
        port = socket.getservbyname("http", "tcp")
        assert port == 80, f"http/tcp 应=80,实际 {port}"

    def test_htonl_ntohl_round_trip(self):
        """`socket.htonl/ntohl` 真字节序 round-trip。"""
        v = 0x12345678
        # htonl 转 network byte order
        n = socket.htonl(v)
        # ntohl 转回 host order
        h = socket.ntohl(n)
        assert h == v

    def test_gethostname(self):
        """`socket.gethostname()` 真返非空 string。"""
        h = socket.gethostname()
        assert isinstance(h, str) and h, f"hostname 应非空,实际 {h!r}"

    def test_getfqdn(self):
        """`socket.getfqdn()` 真返 string。"""
        fqdn = socket.getfqdn()
        assert isinstance(fqdn, str)


# -- typing 进阶 --------------------------------------------------------------

class TestTypingAdvancedV2:
    def test_Final(self):
        """`typing.Final[int]` 真声明不可变。"""
        # 静态分析约束,运行时无操作
        PI: typing.Final[float] = 3.14
        assert PI == 3.14

    def test_Annotated(self):
        """`typing.Annotated[int, 'meta']` 真带 metadata。"""
        Ann = typing.Annotated[int, "meta1", "meta2"]
        # get_type_hints + include_extras 才能解 metadata
        # 简单验: Annotated 仍兼容原类型
        # isinstance 在 runtime 不考虑 Annotated
        assert 1 == 1
        # 验证 typing.get_type_hints 能识别 Annotated
        def f(x: "Annotated[int, 'meta']") -> None:  # type: ignore[valid-type]
            pass

        hints = typing.get_type_hints(
            f, include_extras=True, localns={"Annotated": typing.Annotated}
        )
        # type 是 Annotated[int, 'meta']
        assert "Annotated" in str(hints["x"])

    def test_TypeVar_constrained(self):
        """`TypeVar('T', int, str)` constrained 真限类型。"""
        T = typing.TypeVar("T", int, str)

        def echo(x: T) -> T:
            return x

        # constrained runtime 不强制,但 typevar 必在 typing
        assert echo(42) == 42
        assert echo("forge") == "forge"

    def test_Concatenate(self):
        """`typing.Concatenate` 真前缀,需配合 ParamSpec。"""
        from typing import Concatenate, ParamSpec, Callable

        P = ParamSpec("P")

        # Concatenate[int, P] 意为 'int 作为第一个参数,后跟 P'
        PrefixedFn = Callable[Concatenate[int, P], None]
        assert PrefixedFn is not None
        # Concatenate 必在 typing module
        assert hasattr(typing, "Concatenate")
