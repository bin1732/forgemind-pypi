# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`calendar` + `html.parser` + `pwd` + `getpass` + `hmac` 真底层测试。

覆盖日历 / HTML 解析 / 用户查 / 密码回退 / HMAC 模块:
  - `calendar.isleap(2024)` 真判闰年,`is_leap(2024) == True`
  - `calendar.weekday(2024, 1, 1)` 真返 0 (Mon)
  - `calendar.monthrange(2024, 2)` 真返 (3, 29) — Feb 2024 29 天,start weekday=3
  - `calendar.TextCalendar().formatmonth(2026, 10)` 真含 'October 2026' + 'Mo Tu We'
  - `html.parser.HTMLParser` 子类化真解析 `<a href="...">`,handler 收到 attrs
  - `pwd.getpwnam('root')` 真拿 root passwd entry,`pw_uid=0`
  - `pwd.getpwuid(0)` 真返 root entry
  - `getpass.getpass` 沙箱无 tty 时抛 `GetPassWarning` 或 `OSError`
  - `hmac.new(key, msg, hashlib.sha256).hexdigest()` 真算 HMAC
  - `hmac.compare_digest(a, a) == True` 真防时序攻击
"""
import calendar
import getpass
import hashlib
import hmac
import html.parser
import os
import pwd
import pytest


# -- calendar -----------------------------------------------------------------

class TestCalendar:
    def test_isleap_true(self):
        """`calendar.isleap(2024)` 真判闰年=True。"""
        assert calendar.isleap(2024) is True

    def test_isleap_false(self):
        """`calendar.isleap(2025)` 真判非闰年=False。"""
        assert calendar.isleap(2025) is False

    def test_weekday_2024_new_year(self):
        """`calendar.weekday(2024, 1, 1)` 真返 0 (Mon)。"""
        assert calendar.weekday(2024, 1, 1) == 0, (
            f"2024-01-01 应=0 (Mon),实际 {calendar.weekday(2024, 1, 1)}"
        )

    def test_monthrange_feb_2024(self):
        """`calendar.monthrange(2024, 2)` 真返 (3, 29) — Feb 2024 29 天,start weekday=3。"""
        first_weekday, days = calendar.monthrange(2024, 2)
        assert days == 29, f"Feb 2024 应=29 天,实际 {days}"
        assert first_weekday == 3, f"Feb 2024 1st weekday 应=3 (Thu),实际 {first_weekday}"

    def test_TextCalendar_formatmonth(self):
        """`TextCalendar().formatmonth(2026, 10)` 真含 'October 2026' + 'Mo Tu We'。"""
        out = calendar.TextCalendar().formatmonth(2026, 10)
        assert "October 2026" in out, f"formatmonth 应含 'October 2026',实际 {out!r}"
        assert "Mo Tu We" in out, f"formatmonth 应含 'Mo Tu We',实际 {out!r}"


# -- html.parser --------------------------------------------------------------

class _Recorder(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.events = []

    def handle_starttag(self, tag, attrs):
        self.events.append(("start", tag, dict(attrs)))

    def handle_endtag(self, tag):
        self.events.append(("end", tag))


class TestHtmlParser:
    def test_parser_extracts_anchor_with_attrs(self):
        """`html.parser.HTMLParser` 子类化真解析 `<a href="x">link</a>`,handler 收到 attrs。"""
        p = _Recorder()
        p.feed('<a href="https://example.com" target="_blank">link</a>')
        starts = [e for e in p.events if e[0] == "start"]
        assert len(starts) == 1
        tag, attrs = starts[0][1], starts[0][2]
        assert tag == "a"
        assert attrs.get("href") == "https://example.com"
        assert attrs.get("target") == "_blank"

    def test_parser_extracts_nested_structure(self):
        """`HTMLParser` 真解析嵌套结构,`div` + 子 `span`。"""
        p = _Recorder()
        p.feed("<div><span>hi</span></div>")
        starts = [e for e in p.events if e[0] == "start"]
        ends = [e for e in p.events if e[0] == "end"]
        assert [s[1] for s in starts] == ["div", "span"]
        assert [e[1] for e in ends] == ["span", "div"]

    def test_parser_extracts_data(self):
        """`HTMLParser` 真解析 text node 走 `handle_data`。"""
        captured = []

        class P(html.parser.HTMLParser):
            def handle_data(self, data):
                captured.append(data)

        p = P()
        p.feed("Hello <b>forge</b> world")
        joined = "".join(captured)
        assert "Hello" in joined
        assert "forge" in joined
        assert "world" in joined


# -- pwd ----------------------------------------------------------------------

class TestPwd:
    def test_getpwnam_root(self):
        """`pwd.getpwnam('root')` 真拿 root passwd entry,`pw_uid=0`。"""
        try:
            entry = pwd.getpwnam("root")
        except KeyError:
            pytest.skip("系统无 root 用户")
        assert entry.pw_uid == 0, f"root 应 pw_uid=0,实际 {entry.pw_uid}"
        assert entry.pw_name == "root"

    def test_getpwuid_zero(self):
        """`pwd.getpwuid(0)` 真返 root entry。"""
        try:
            entry = pwd.getpwuid(0)
        except KeyError:
            pytest.skip("系统无 UID 0")
        assert entry.pw_name == "root", f"UID 0 应=root,实际 {entry.pw_name}"


# -- getpass ------------------------------------------------------------------

class TestGetpass:
    def test_getpass_no_tty_raises(self):
        """`getpass.getpass` 沙箱无 tty 时抛 `GetPassWarning` 或 `OSError`。"""
        # 沙箱 stdin 非 tty,getpass 必抛异常
        with pytest.raises((getpass.GetPassWarning, OSError, ValueError, EOFError)):
            getpass.getpass("prompt: ")


# -- hmac ---------------------------------------------------------------------

class TestHmacAdvanced:
    def test_hmac_new_hexdigest(self):
        """`hmac.new(key, msg, hashlib.sha256).hexdigest()` 真算 HMAC-SHA256。"""
        key = b"secret"
        msg = b"hello"
        h = hmac.new(key, msg, hashlib.sha256).hexdigest()
        assert isinstance(h, str) and len(h) == 64, (
            f"HMAC-SHA256 hex 应=64 字符,实际 {len(h)}: {h!r}"
        )
        # 用 hmac 同样 input 真算验算
        assert hmac.new(b"secret", b"hello", hashlib.sha256).hexdigest() == h

    def test_hmac_compare_digest_equal(self):
        """`hmac.compare_digest(a, a) == True` 真防时序攻击。"""
        a = b"identical bytes"
        b = b"identical bytes"
        assert hmac.compare_digest(a, b) is True

    def test_hmac_compare_digest_different(self):
        """`hmac.compare_digest(a, c) == False` 真区分不同 bytes。"""
        a = b"identical bytes"
        c = b"different bytes"
        assert hmac.compare_digest(a, c) is False

    def test_hmac_digest_size_matches_hashlib(self):
        """`HMAC.digest_size == hashlib.sha256().digest_size` 真匹配。"""
        h = hmac.new(b"k", b"m", hashlib.sha256)
        assert h.digest_size == hashlib.sha256().digest_size == 32
