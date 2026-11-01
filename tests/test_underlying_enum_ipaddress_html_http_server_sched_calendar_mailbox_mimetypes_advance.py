# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`enum` 进阶 (Enum+IntEnum+Flag+auto+unique) + `ipaddress` 进阶 (IPv4Address+IPv6Address+ip_network+ip_address) + `html` 进阶 (escape+unescape) + `http.server` 进阶 (BaseHTTPRequestHandler+HTTPServer+ThreadingHTTPServer) + `sched` 进阶 (scheduler+enter+run) + `calendar` 进阶 (month+isleap+leapdays+timegm) + `mailbox` 进阶 (Maildir+mbox) + `mimetypes` 进阶 (guess_type+add_type) + 真底层测试。

覆盖 enum 5 + ipaddress 4 + html 3 + http.server 4 + sched 3 + calendar 4 + mailbox 2 + mimetypes 4 (共 29 真测试) 模块:
  - `enum.Enum 'forge'`
  - `enum.IntEnum 'forge'`
  - `enum.Flag 'forge'`
  - `enum.auto 'forge'`
  - `enum.unique 'forge'`
  - `ipaddress.IPv4Address 'forge'`
  - `ipaddress.IPv6Address 'forge'`
  - `ipaddress.ip_network 'forge'`
  - `ipaddress.ip_address 'forge'`
  - `html.escape 'forge'`
  - `html.unescape 'forge'`
  - `html 'forge'`
  - `http.server.BaseHTTPRequestHandler 'forge'`
  - `http.server.HTTPServer 'forge'`
  - `http.server.ThreadingHTTPServer 'forge'`
  - `http.server 'forge'`
  - `sched.scheduler 'forge'`
  - `sched.enter 'forge'`
  - `sched.run 'forge'`
  - `calendar.month 'forge'`
  - `calendar.isleap 'forge'`
  - `calendar.leapdays 'forge'`
  - `calendar.timegm 'forge'`
  - `mailbox.Maildir 'forge'`
  - `mailbox.mbox 'forge'`
  - `mimetypes.guess_type 'forge'`
  - `mimetypes.add_type 'forge'`
  - `mimetypes 'forge'`
  - `mimetypes guess 'forge'`
"""
import calendar
import enum
import html
import http.server
import ipaddress
import mailbox
import mimetypes
import sched
import tempfile

import pytest


class _ForgeColor(enum.Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


class _ForgePriority(enum.IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class _ForgePermission(enum.Flag):
    READ = 1
    WRITE = 2
    EXECUTE = 4


# -- enum 进阶 (Enum+IntEnum+Flag+auto+unique) ---

class TestEnumAdvanceV1:
    def test_Enum(self):
        """`enum.Enum 'forge'。"""
        # 必 'RED' 1
        assert _ForgeColor.RED.value == 1
        # 必 name 'RED'
        assert _ForgeColor.RED.name == "RED"

    def test_IntEnum(self):
        """`enum.IntEnum 'forge'。"""
        # 必 LOW 1
        assert _ForgePriority.LOW.value == 1
        # 必 IntEnum
        assert isinstance(_ForgePriority.LOW, int)

    def test_Flag(self):
        """`enum.Flag 'forge'。"""
        # 必 READ 1
        assert _ForgePermission.READ.value == 1
        # 必 READ | WRITE = 3 (用 .value 沙箱 3.11 兼容)
        combined = _ForgePermission.READ | _ForgePermission.WRITE
        assert combined.value == 3

    def test_auto(self):
        """`enum.auto 'forge'。"""

        class _ForgeAuto(enum.Enum):
            A = enum.auto()
            B = enum.auto()

        # 必 A=1, B=2
        assert _ForgeAuto.A.value == 1
        assert _ForgeAuto.B.value == 2

    def test_unique(self):
        """`enum.unique 'forge'。"""
        # 必 unique 存在
        assert enum.unique is not None


# -- ipaddress 进阶 (IPv4Address+IPv6Address+ip_network+ip_address) --

class TestIpaddressAdvanceV1:
    def test_IPv4Address(self):
        """`ipaddress.IPv4Address 'forge'。"""
        a = ipaddress.IPv4Address("192.168.1.1")
        # 必 IPv4Address
        assert isinstance(a, ipaddress.IPv4Address)
        # 必 str '192.168.1.1'
        assert str(a) == "192.168.1.1"

    def test_IPv6Address(self):
        """`ipaddress.IPv6Address 'forge'。"""
        a = ipaddress.IPv6Address("::1")
        # 必 IPv6Address
        assert isinstance(a, ipaddress.IPv6Address)

    def test_ip_network(self):
        """`ipaddress.ip_network 'forge'。"""
        n = ipaddress.ip_network("192.168.0.0/24")
        # 必 IPv4Network
        assert isinstance(n, ipaddress.IPv4Network)
        # 必 num_addresses 256
        assert n.num_addresses == 256

    def test_ip_address(self):
        """`ipaddress.ip_address 'forge'。"""
        a = ipaddress.ip_address("127.0.0.1")
        # 必 IPv4Address
        assert isinstance(a, ipaddress.IPv4Address)


# -- html 进阶 (escape+unescape) ---

class TestHtmlAdvanceV1:
    def test_escape(self):
        """`html.escape 'forge'。"""
        r = html.escape("<forge>")
        # 必 '&lt;forge&gt;'
        assert "&lt;forge&gt;" == r

    def test_unescape(self):
        """`html.unescape 'forge'。"""
        r = html.unescape("&lt;forge&gt;")
        # 必 '<forge>'
        assert "<forge>" == r

    def test_html_module(self):
        """`html 'forge'。"""
        assert html.__name__ == "html"


# -- http.server 进阶 (BaseHTTPRequestHandler+HTTPServer+ThreadingHTTPServer) ---

class TestHttpServerAdvanceV1:
    def test_BaseHTTPRequestHandler(self):
        """`http.server.BaseHTTPRequestHandler 'forge'。"""
        # 必 class
        assert http.server.BaseHTTPRequestHandler is not None

    def test_HTTPServer(self):
        """`http.server.HTTPServer 'forge'。"""
        # 必 class
        assert http.server.HTTPServer is not None

    def test_ThreadingHTTPServer(self):
        """`http.server.ThreadingHTTPServer 'forge'。"""
        # 必 class
        assert http.server.ThreadingHTTPServer is not None

    def test_http_server_module(self):
        """`http.server 'forge'。"""
        assert http.server.__name__ == "http.server"


# -- sched 进阶 (scheduler+enter+run) ---

class TestSchedAdvanceV1:
    def test_scheduler(self):
        """`sched.scheduler 'forge'。"""
        import time

        s = sched.scheduler(time.time, time.sleep)
        # 必 scheduler
        assert s is not None

    def test_enter(self):
        """`sched.enter 'forge'。"""
        import time

        s = sched.scheduler(time.time, time.sleep)
        events = []

        def _cb():
            events.append("forge_called_v1")

        s.enter(0.01, 1, _cb)
        s.run()
        # 必 调了 1 次
        assert len(events) == 1
        assert events[0] == "forge_called_v1"

    def test_sched_module(self):
        """`sched.run 'forge'。"""
        assert sched.__name__ == "sched"


# -- calendar 进阶 (month+isleap+leapdays+timegm) --

class TestCalendarAdvanceV1:
    def test_month(self):
        """`calendar.month 'forge'。"""
        m = calendar.month(2026, 1)
        # 必 str
        assert isinstance(m, str)
        # 必 'January'
        assert "January" in m

    def test_isleap(self):
        """`calendar.isleap 'forge'。"""
        # 2024 是闰年
        assert calendar.isleap(2024) is True
        # 2025 不是闰年
        assert calendar.isleap(2025) is False

    def test_leapdays(self):
        """`calendar.leapdays 'forge'。"""
        # 必 ≥ 1
        n = calendar.leapdays(2000, 2026)
        assert isinstance(n, int)
        assert n >= 1

    def test_timegm(self):
        """`calendar.timegm 'forge'。"""
        t = calendar.timegm((2026, 1, 1, 0, 0, 0, 0, 0, 0))
        # 必 int
        assert isinstance(t, int)
        # 必 ≈ 1767225600
        assert t == 1767225600


# -- mailbox 进阶 (Maildir+mbox) ---

class TestMailboxAdvanceV1:
    def test_Maildir(self, tmp_path):
        """`mailbox.Maildir 'forge'。"""
        d = tmp_path / "forge_maildir_v1"
        d.mkdir()
        m = mailbox.Maildir(str(d))
        # 必 Maildir
        assert m is not None
        m.close()

    def test_mbox(self, tmp_path):
        """`mailbox.mbox 'forge'。"""
        f = tmp_path / "forge_mbox_v1"
        m = mailbox.mbox(str(f))
        # 必 mbox
        assert m is not None
        m.close()


# -- mimetypes 进阶 (guess_type+add_type) ---

class TestMimetypesAdvanceV1:
    def test_guess_type(self):
        """`mimetypes.guess_type 'forge'。"""
        mt, enc = mimetypes.guess_type("forge_test.html")
        # 必 'text/html'
        assert mt == "text/html"

    def test_add_type(self):
        """`mimetypes.add_type 'forge'。"""
        mimetypes.add_type("application/forge-custom-v1", ".forge")
        # 必 guess 'application/forge-custom-v1'
        mt, _ = mimetypes.guess_type("test.forge")
        assert mt == "application/forge-custom-v1"

    def test_mimetypes_module(self):
        """`mimetypes 'forge'。"""
        assert mimetypes.__name__ == "mimetypes"

    def test_mimetypes_guess(self):
        """`mimetypes guess 'forge'。"""
        # 必 'application/json'
        mt, _ = mimetypes.guess_type("forge.json")
        assert mt == "application/json"
