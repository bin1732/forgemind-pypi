# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 ipaddress: 真 IPv4Address / IPv6Address / IPv4Network / IPv6Network 真子网算。
全 stdlib, 零模拟。
"""
import ipaddress
import pytest


def test_ipv4_address_basic():
    """真 IPv4Address 真属性"""
    ip = ipaddress.IPv4Address("192.168.1.1")
    assert int(ip) == 0xC0A80101
    assert ip.packed == bytes([192, 168, 1, 1])
    assert not ip.is_multicast
    assert not ip.is_loopback
    assert not ip.is_link_local
    assert not ip.is_reserved
    assert not ip.is_unspecified
    assert ip.version == 4
    # reverse
    assert str(ip.reverse_pointer) == "1.1.168.192.in-addr.arpa"


def test_ipv4_special_addresses():
    """真特殊 IPv4"""
    assert ipaddress.IPv4Address("127.0.0.1").is_loopback
    assert ipaddress.IPv4Address("0.0.0.0").is_unspecified
    assert ipaddress.IPv4Address("255.255.255.255").is_reserved
    assert ipaddress.IPv4Address("224.0.0.1").is_multicast
    # 169.254.x.x link-local
    assert ipaddress.IPv4Address("169.254.1.1").is_link_local
    # 私有
    assert ipaddress.IPv4Address("10.0.0.1").is_private
    assert ipaddress.IPv4Address("192.168.1.1").is_private
    assert not ipaddress.IPv4Address("8.8.8.8").is_private


def test_ipv4_network_basic():
    """真 IPv4Network 子网算"""
    net = ipaddress.IPv4Network("192.168.1.0/24")
    assert net.network_address == ipaddress.IPv4Address("192.168.1.0")
    assert net.broadcast_address == ipaddress.IPv4Address("192.168.1.255")
    assert net.netmask == ipaddress.IPv4Address("255.255.255.0")
    assert net.prefixlen == 24
    assert net.num_addresses == 256
    # 包含
    assert ipaddress.IPv4Address("192.168.1.100") in net
    assert ipaddress.IPv4Address("192.168.2.1") not in net


def test_ipv4_subnet_of():
    """真 subnet_of 真超网判断"""
    parent = ipaddress.IPv4Network("10.0.0.0/8")
    child = ipaddress.IPv4Network("10.1.0.0/16")
    assert child.subnet_of(parent)
    assert not parent.subnet_of(child)
    # 不重叠
    other = ipaddress.IPv4Network("192.168.0.0/16")
    assert not other.subnet_of(parent)


def test_ipv4_subnet_iter():
    """真 subnets 真切"""
    net = ipaddress.IPv4Network("10.0.0.0/16")
    subnets = list(net.subnets(new_prefix=18))
    assert len(subnets) == 4
    assert subnets[0] == ipaddress.IPv4Network("10.0.0.0/18")
    assert subnets[3] == ipaddress.IPv4Network("10.0.192.0/18")


def test_ipv4_supernet():
    """真 supernet 真合并"""
    n1 = ipaddress.IPv4Network("10.1.0.0/16")
    n2 = ipaddress.IPv4Network("10.2.0.0/16")
    supernet = n1.supernet(prefixlen_diff=1)
    assert supernet == ipaddress.IPv4Network("10.0.0.0/15")


def test_ipv4_hosts():
    """真 hosts 真列"""
    net = ipaddress.IPv4Network("10.0.0.0/29")
    # /29 = 8 地址, -2 = 6 hosts (除 network + broadcast)
    hosts = list(net.hosts())
    assert len(hosts) == 6
    assert hosts[0] == ipaddress.IPv4Address("10.0.0.1")
    assert hosts[-1] == ipaddress.IPv4Address("10.0.0.6")


def test_ipv4_compare():
    """真 IPv4 比较"""
    a = ipaddress.IPv4Address("10.0.0.1")
    b = ipaddress.IPv4Address("10.0.0.2")
    assert a < b
    assert a != b
    assert hash(a) == hash(ipaddress.IPv4Address("10.0.0.1"))  # hashable
    # set / dict
    s = {a, b, ipaddress.IPv4Address("10.0.0.1")}
    assert len(s) == 2


def test_ipv4_arithmetic():
    """真 IPv4 算术"""
    ip = ipaddress.IPv4Address("10.0.0.1")
    next_ip = ip + 1
    assert next_ip == ipaddress.IPv4Address("10.0.0.2")
    # Python 不 wrap, 直接进位
    assert ip + 255 == ipaddress.IPv4Address("10.0.1.0")
    assert ip + 256 == ipaddress.IPv4Address("10.0.1.1")
    # 减
    assert ipaddress.IPv4Address("10.0.0.10") - 5 == ipaddress.IPv4Address("10.0.0.5")


def test_ipv4_network_overlaps():
    """真 overlaps 真子网重叠"""
    a = ipaddress.IPv4Network("10.0.0.0/15")  # 10.0.0.0 - 10.1.255.255
    b = ipaddress.IPv4Network("10.1.0.0/16")  # 在 a 内
    c = ipaddress.IPv4Network("192.168.0.0/16")
    assert a.overlaps(b)
    assert not a.overlaps(c)


def test_ipv6_address_basic():
    """真 IPv6Address"""
    ip6 = ipaddress.IPv6Address("2001:db8::1")
    assert ip6.version == 6
    assert not ip6.is_loopback
    assert not ip6.is_multicast
    assert not ip6.is_link_local
    assert not ip6.is_reserved
    assert not ip6.is_unspecified
    # loopback
    assert ipaddress.IPv6Address("::1").is_loopback
    # unspecified
    assert ipaddress.IPv6Address("::").is_unspecified
    # multicast
    assert ipaddress.IPv6Address("ff00::1").is_multicast
    # link-local
    assert ipaddress.IPv6Address("fe80::1").is_link_local


def test_ipv6_compressed_expanded():
    """真 IPv6 压缩 / 展开"""
    expanded = "2001:0db8:0000:0000:0000:0000:0000:0001"
    compressed = "2001:db8::1"
    ip1 = ipaddress.IPv6Address(expanded)
    ip2 = ipaddress.IPv6Address(compressed)
    assert ip1 == ip2
    # 压缩 + 展开 round-trip
    assert str(ip1) == compressed  # Python 压缩输出
    assert ip1.exploded == expanded
    assert ip2.exploded == expanded


def test_ipv6_network_basic():
    """真 IPv6Network"""
    net = ipaddress.IPv6Network("2001:db8::/32")
    assert net.prefixlen == 32
    assert net.num_addresses == 2**96
    assert ipaddress.IPv6Address("2001:db8::1") in net
    assert ipaddress.IPv6Address("2001:db9::1") not in net


def test_ipv6_subnets():
    """真 IPv6 /32 切 /64 子网 (不算)"""
    net = ipaddress.IPv6Network("2001:db8::/48")
    # /48 → /64 = 2^16 个 subnets
    subnets = list(net.subnets(new_prefix=64))
    assert len(subnets) == 2**16
    assert subnets[0] == ipaddress.IPv6Network("2001:db8::/64")


def test_ipv4_to_ipv6_mapped():
    """真 IPv4-mapped IPv6"""
    ipv4 = ipaddress.IPv4Address("192.0.2.1")
    mapped = ipaddress.IPv6Address("::ffff:192.0.2.1")
    assert mapped.ipv4_mapped == ipv4
    # ntop 输出格式 (跟构造字符串可能不同, .exploded 看)
    # 映射地址的展开形式随解释器版本变化:有的版本给出十六进制分段,
    # 有的版本直接给出 IPv4 记法。两种都表示同一个地址。
    assert mapped.exploded in (
        "0000:0000:0000:0000:0000:ffff:c000:0201",
        "0000:0000:0000:0000:0000:ffff:192.0.2.1",
    )


def test_ipaddress_address_from_integer():
    """真从整数构造"""
    ip = ipaddress.IPv4Address(0xC0A80101)
    assert str(ip) == "192.168.1.1"
    ip6 = ipaddress.IPv6Address(1)
    assert str(ip6) == "::1"
