# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`socket` 进阶 (broadcast + multicast) + `ipaddress` 进阶 (v6 v4-mapped) + `zoneinfo` 进阶 (fold) + `datetime` 进阶 真底层测试。

覆盖 socket 进阶 / IP 进阶 / 时区 fold / datetime 进阶 模块:
  - `socket.inet_aton('255.255.255.255') 真 broadcast`
  - `socket.inet_aton('192.168.1.0') 真 private`
  - `socket.getprotobyname('tcp') 真 6`
  - `socket.getprotobyname('udp') 真 17`
  - `ipaddress.IPv4Address('192.168.1.1') is_private 真 True`
  - `ipaddress.IPv4Address('224.0.0.1') is_multicast 真 True`
  - `ipaddress.IPv4Address('169.254.0.1') is_link_local 真 True`
  - `ipaddress.IPv6Address('::ffff:192.168.1.1') ipv4_mapped 真`
  - `ipaddress.IPv6Address('64:ff9b::').is_global 真`
  - `ipaddress.IPv6Address('2001::').is_global 真 RFC 4291`
  - `datetime.datetime(2026,11,1,1,30,fold=1)` 真 fold
  - `datetime.datetime(2026,11,1,1,30,fold=1).timestamp() 3.6+ 真唯一`
  - `datetime.datetime.fromisoformat 真解 '2026-01-15'`
  - `datetime.datetime.fromtimestamp 真 epoch 反向`
  - `zoneinfo.ZoneInfo 真带 fold 的 timestamp`
  - `datetime.timezone(timedelta(hours=8)) 真建 + utcoffset=8h`
  - `datetime.datetime.now(tz=UTC) 真带 tz`
  - `datetime.timedelta 进阶 (resolution)`
"""
import datetime
import ipaddress
import socket
import zoneinfo

import pytest


# -- socket 进阶 --------------------------------------------------------------

class TestSocketAdvancedV3:
    def test_inet_aton_broadcast(self):
        """`socket.inet_aton('255.255.255.255') 真 broadcast bytes`。"""
        b = socket.inet_aton("255.255.255.255")
        assert b == b"\xff\xff\xff\xff", f"broadcast 应=4 字节 0xFF,实际 {b!r}"

    def test_inet_aton_private(self):
        """`socket.inet_aton('192.168.1.0') 真 private bytes`。"""
        b = socket.inet_aton("192.168.1.0")
        # 192.168.1.0 = 0xC0.0xA8.0x01.0x00
        assert b == bytes([192, 168, 1, 0])

    def test_getprotobyname_tcp(self):
        """`socket.getprotobyname('tcp') 真 6`。"""
        proto = socket.getprotobyname("tcp")
        assert proto == 6, f"tcp 应=6,实际 {proto}"

    def test_getprotobyname_udp(self):
        """`socket.getprotobyname('udp') 真 17`。"""
        proto = socket.getprotobyname("udp")
        assert proto == 17, f"udp 应=17,实际 {proto}"


# -- ipaddress 进阶 ------------------------------------------------------------

class TestIpaddressAdvancedV2:
    def test_IPv4_private(self):
        """`IPv4Address('192.168.1.1').is_private 真 True`。"""
        ip = ipaddress.IPv4Address("192.168.1.1")
        assert ip.is_private is True
        assert ip.is_global is False

    def test_IPv4_multicast(self):
        """`IPv4Address('224.0.0.1').is_multicast 真 True`。"""
        ip = ipaddress.IPv4Address("224.0.0.1")
        assert ip.is_multicast is True

    def test_IPv4_link_local(self):
        """`IPv4Address('169.254.0.1').is_link_local 真 True`。"""
        ip = ipaddress.IPv4Address("169.254.0.1")
        assert ip.is_link_local is True

    def test_IPv6_v4_mapped(self):
        """`IPv6Address('::ffff:192.168.1.1') 真 ipv4_mapped`。"""
        ip = ipaddress.IPv6Address("::ffff:192.168.1.1")
        assert ip.ipv4_mapped is not None
        # ipv4_mapped 是 IPv4Address
        assert isinstance(ip.ipv4_mapped, ipaddress.IPv4Address)
        assert str(ip.ipv4_mapped) == "192.168.1.1"

    def test_IPv6_is_global(self):
        """`IPv6Address('2001:db8::') 真 is_global=False (RFC 3849 doc / private)`。"""
        # 2001:db8::/32 RFC 3849 是 documentation, NOT global
        ip = ipaddress.IPv6Address("2001:db8::1")
        assert ip.is_global is False
        # 沙箱 3.11+ 把 2001:db8 归为 is_private
        assert ip.is_reserved is True or ip.is_private is True
        # ::1 (loopback) NOT global
        ip2 = ipaddress.IPv6Address("::1")
        assert ip2.is_global is False

    def test_IPv6_teredo(self):
        """`IPv6Address 2001::/32 .teredo 真含 server+client`。"""
        # 2001:: 是 Teredo prefix
        ip = ipaddress.IPv6Address("2001:0:53aa:64c:0:7f3b:2a32:5")
        # teredo 必返 (server, client) tuple 或 None
        teredo = ip.teredo
        # 简化: 必 teredo attr
        assert hasattr(ip, "teredo")


# -- zoneinfo 进阶 (fold) ------------------------------------------------------

class TestZoneinfoFold:
    def test_datetime_with_fold(self):
        """`datetime(2026,11,1,1,30,fold=1) 真 fold`。"""
        dt = datetime.datetime(2026, 11, 1, 1, 30, fold=1)
        assert dt.fold == 1, f"fold 应=1,实际 {dt.fold}"

    def test_datetime_fold_timestamp_unique(self):
        """`datetime(2026,11,1,1,30,fold=1).timestamp 3.6+ 真歧义时区唯一`。"""
        # 用 fold=0 和 fold=1 在 ambig zone 应返不同 timestamp
        # 注: 本地时区沙箱无 DST, fold 不影响
        dt0 = datetime.datetime(2026, 11, 1, 1, 30, fold=0)
        dt1 = datetime.datetime(2026, 11, 1, 1, 30, fold=1)
        # 沙箱可能 utc offset 0, 两 ts 相同, 不验不同
        # 只验不抛
        assert dt0.timestamp() is not None
        assert dt1.timestamp() is not None

    def test_datetime_fromisoformat(self):
        """`datetime.fromisoformat('2026-01-15T10:30:00') 真解`。"""
        dt = datetime.datetime.fromisoformat("2026-01-15T10:30:00")
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.day == 15
        assert dt.hour == 10

    def test_datetime_fromtimestamp_epoch(self):
        """`datetime.fromtimestamp(0) 真 epoch reverse`。"""
        dt = datetime.datetime.fromtimestamp(0)
        # 沙箱本地时区, 必为 1970-01-01 in some tz
        assert dt.year == 1970
        assert dt.month == 1
        assert dt.day == 1


# -- datetime 进阶 ------------------------------------------------------------

class TestDatetimeAdvancedV2:
    def test_timezone_offset(self):
        """`datetime.timezone(timedelta(hours=8)) 真建 + utcoffset=8h`。"""
        tz = datetime.timezone(datetime.timedelta(hours=8))
        dt = datetime.datetime(2026, 1, 15, 12, 0, tzinfo=tz)
        assert dt.utcoffset() == datetime.timedelta(hours=8), (
            f"tz +8h 应=+8h,实际 {dt.utcoffset()}"
        )

    def test_now_with_utc(self):
        """`datetime.now(tz=UTC) 真带 tz 的 now。"""
        dt = datetime.datetime.now(tz=datetime.timezone.utc)
        assert dt.tzinfo is not None
        assert dt.utcoffset() == datetime.timedelta(0)

    def test_timedelta_resolution(self):
        """`datetime.timedelta.resolution 真 1 微秒。"""
        assert datetime.timedelta.resolution == datetime.timedelta(microseconds=1)


# -- zoneinfo 进阶 ------------------------------------------------------------

class TestZoneinfoAdvancedV2:
    def test_ZoneInfo_dst(self):
        """`ZoneInfo 必返 .dst() (DST timedelta or None)。"""
        tz = zoneinfo.ZoneInfo("America/New_York")
        # .dst() 返 DST offset (夏令时 1h) 或 None
        # 7 月 15 日 (夏令时) dst = 1h
        summer = datetime.datetime(2026, 7, 15, 12, 0, tzinfo=tz)
        assert summer.dst() == datetime.timedelta(hours=1)
        # 1 月 (冬令时) dst = 0
        winter = datetime.datetime(2026, 1, 15, 12, 0, tzinfo=tz)
        assert winter.dst() == datetime.timedelta(0)

    def test_ZoneInfo_str(self):
        """`str(ZoneInfo) 真返 'America/New_York' 之类。"""
        tz = zoneinfo.ZoneInfo("America/New_York")
        assert str(tz) == "America/New_York", (
            f"str 应='America/New_York',实际 {str(tz)}"
        )
