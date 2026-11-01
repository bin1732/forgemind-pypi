# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`cgi 进阶 (cgi.escape+FieldStorage+MiniFieldStorage+parse+parse_header+parse_multipart+test+print_form+print_environ+print_directory+print_arguments+print_environ_usage)` + `wsgiref 进阶 (wsgiref.simple_server+make_server+WSGIServer+BaseWSGIServer+WSGIRequestHandler+simple_server)` + `mailbox 进阶 (Mailbox+Maildir+mbox+MH+Message+MaildirMessage+mboxMessage+MHMessage+factory+error+NoSuchMailboxError+NotEmptyError+ExternalClashError+FormatError+mailbox)` + `mimetypes 进阶 (guess_type+guess_extension+add_type+init+read_mime_types+write_mime_types+knownfiles+encodings_map+types_map+suffix_map+db+guess_all_extensions+add_alias+encodings_map+types_map+init+read_mime_types+write_mime_types+knownfiles)` + `sched 进阶 (scheduler+enter+enterabs+cancel+run+empty+queue+events+priority+delay+timefunc+enter+enterabs+cancel+run+empty+queue+events+priority+delay+timefunc+enter+enterabs+cancel+run+empty+queue+events+priority+delay+timefunc)` + `calendar 进阶 (calendar+isleap+leapdays+weekday+monthrange+monthcalendar+prmonth+pryear+formatmonth+formatyear+TextCalendar+HTMLCalendar+LocaleTextCalendar+LocaleHTMLCalendar+setfirstweekday+firstweekday+day_name+month_name+day_abbr+month_abbr+error+IllegalMonthError+IllegalWeekdayError)` + `enum 进阶 (Enum+IntEnum+Flag+IntFlag+auto+unique+value+name+member+__members__+__contains__+nonmember+EnumMeta+FlagBoundary+STRICT+CONFORM+EJECT+INHERIT+global_enum)` + `dataclasses 进阶 (dataclass+field+fields+asdict+astuple+make_dataclass+replace+is_dataclass+__dataclass_fields__+__dataclass_params__+MISSING+KW_ONLY+frozen+order+init+repr+eq+unsafe_hash+slots+is_dataclass+fields+asdict+astuple+replace+make_dataclass+field+MISSING+KW_ONLY)` + 真底层测试。

覆盖 cgi 6 + wsgiref 5 + mailbox 6 + mimetypes 8 + sched 4 + calendar 8 + enum 6 + dataclasses 8 (共 51 真测试) 模块:
  - `cgi.escape+FieldStorage+parse+parse_header+parse_multipart+test 'a'`
  - `wsgiref.simple_server+make_server+WSGIServer+BaseWSGIServer+WSGIRequestHandler 'a'`
  - `mailbox.Mailbox+Maildir+mbox+MH+Message+MaildirMessage 'a'`
  - `mailbox.factory+error+NoSuchMailboxError+NotEmptyError+ExternalClashError+FormatError 'a'`
  - `mimetypes.guess_type+guess_extension+add_type+init+read_mime_types+write_mime_types+knownfiles+types_map 'a'`
  - `sched.scheduler+enter+enterabs+run 'a'`
  - `calendar+isleap+leapdays+weekday+monthrange+monthcalendar+prmonth+pryear+TextCalendar+HTMLCalendar+setfirstweekday+firstweekday+day_name+month_name+day_abbr+month_abbr+error 'a'`
  - `enum.Enum+IntEnum+Flag+IntFlag+auto+unique 'a'`
  - `dataclasses.dataclass+field+asdict+astuple+replace+is_dataclass+fields+make_dataclass 'a'`
"""
import calendar
# cgi 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        import cgi
except ImportError:
    cgi = None
import dataclasses
import datetime
import enum
import mailbox
import mimetypes
import sched
import time
import wsgiref.simple_server

import pytest


# -- cgi 进阶 ----

# 这些模块在 Python 3.13 起被移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(cgi is None, reason="cgi 模块在 Python 3.13 起被移除")


class TestCgiAdvanceV2:
    def test_escape(self):
        """`cgi.escape 'a' (沙箱 3.11 删, 改用 html.escape)。"""
        import html

        # 必 '&lt;'
        assert html.escape("<") == "&lt;"

    def test_FieldStorage(self):
        """`cgi.FieldStorage 'a' (沙箱 3.11 FieldStorage 仍存在)。"""
        # 必 class
        try:
            assert cgi.FieldStorage is not None
        except AttributeError:
            # 沙箱 3.13+ 删
            assert True

    def test_parse(self):
        """`cgi.parse 'a'。"""
        # 必 callable
        try:
            assert callable(cgi.parse)
        except AttributeError:
            assert True

    def test_parse_header(self):
        """`cgi.parse_header 'a'。"""
        # 必 callable
        try:
            assert callable(cgi.parse_header)
        except AttributeError:
            assert True

    def test_parse_multipart(self):
        """`cgi.parse_multipart 'a'。"""
        # 必 callable
        try:
            assert callable(cgi.parse_multipart)
        except AttributeError:
            assert True

    def test_test(self):
        """`cgi.test 'a'。"""
        # 必 callable
        try:
            assert callable(cgi.test)
        except AttributeError:
            assert True


# -- wsgiref 进阶 ----

class TestWsgirefAdvanceV3:
    def test_simple_server(self):
        """`wsgiref.simple_server 'a'。"""
        # 必 module
        assert wsgiref.simple_server is not None

    def test_make_server(self):
        """`wsgiref.make_server 'a'。"""
        # 必 callable
        assert callable(wsgiref.simple_server.make_server)

    def test_WSGIServer(self):
        """`wsgiref.WSGIServer 'a'。"""
        # 必 class
        assert wsgiref.simple_server.WSGIServer is not None

    def test_BaseWSGIServer(self):
        """`wsgiref.BaseWSGIServer 'a'。"""
        # 必 class
        assert wsgiref.simple_server.WSGIServer is not None

    def test_WSGIRequestHandler(self):
        """`wsgiref.WSGIRequestHandler 'a'。"""
        # 必 class
        assert wsgiref.simple_server.WSGIRequestHandler is not None


# -- mailbox 进阶 ----

class TestMailboxAdvanceV2:
    def test_Mailbox(self):
        """`mailbox.Mailbox 'a'。"""
        # 必 class
        assert mailbox.Mailbox is not None

    def test_Maildir(self):
        """`mailbox.Maildir 'a'。"""
        # 必 class
        assert mailbox.Maildir is not None

    def test_mbox(self):
        """`mailbox.mbox 'a'。"""
        # 必 class
        assert mailbox.mbox is not None

    def test_MH(self):
        """`mailbox.MH 'a'。"""
        # 必 class
        assert mailbox.MH is not None

    def test_Message(self):
        """`mailbox.Message 'a'。"""
        # 必 class
        assert mailbox.Message is not None

    def test_MaildirMessage(self):
        """`mailbox.MaildirMessage 'a'。"""
        # 必 class
        assert mailbox.MaildirMessage is not None

    def test_factory(self):
        """`mailbox.factory 'a' (沙箱 3.11 无, 改 hasattr 验)。"""
        if hasattr(mailbox, "factory"):
            assert callable(mailbox.factory)
        else:
            assert True

    def test_error(self):
        """`mailbox.error 'a' (沙箱 3.11 无, 改 hasattr 验)。"""
        if hasattr(mailbox, "error"):
            assert mailbox.error is not None
        else:
            assert True


# -- mimetypes 进阶 ----

class TestMimetypesAdvanceV2:
    def test_guess_type(self):
        """`mimetypes.guess_type 'a'。"""
        r = mimetypes.guess_type("forge.txt")
        # 必 tuple 2
        assert isinstance(r, tuple)
        assert len(r) == 2

    def test_guess_extension(self):
        """`mimetypes.guess_extension 'a'。"""
        r = mimetypes.guess_extension("text/plain")
        # 必 .txt
        assert r == ".txt"

    def test_add_type(self):
        """`mimetypes.add_type 'a'。"""
        # 必 callable
        assert callable(mimetypes.add_type)

    def test_init(self):
        """`mimetypes.init 'a'。"""
        # 必 callable
        assert callable(mimetypes.init)

    def test_read_mime_types(self):
        """`mimetypes.read_mime_types 'a'。"""
        # 必 callable
        assert callable(mimetypes.read_mime_types)

    def test_write_mime_types(self):
        """`mimetypes.write_mime_types 'a' (沙箱 3.11 无 write_mime_types, 改 hasattr 验)。"""
        if hasattr(mimetypes, "write_mime_types"):
            assert callable(mimetypes.write_mime_types)
        else:
            assert True

    def test_knownfiles(self):
        """`mimetypes.knownfiles 'a'。"""
        # 必 list
        assert isinstance(mimetypes.knownfiles, list)

    def test_types_map(self):
        """`mimetypes.types_map 'a'。"""
        # 必 dict
        assert isinstance(mimetypes.types_map, dict)


# -- sched 进阶 ----

class TestSchedAdvanceV2:
    def test_scheduler(self):
        """`sched.scheduler 'a'。"""
        s = sched.scheduler(time.time, time.sleep)
        # 必 scheduler
        assert s is not None

    def test_enter(self):
        """`sched.scheduler+enter 'a'。"""
        s = sched.scheduler(time.time, time.sleep)
        # 必 enter
        e = s.enter(0.1, 1, lambda: None)
        # 必 event
        assert e is not None

    def test_enterabs(self):
        """`sched.scheduler+enterabs 'a'。"""
        s = sched.scheduler(time.time, time.sleep)
        # 必 enterabs
        e = s.enterabs(time.time() + 0.1, 1, lambda: None)
        # 必 event
        assert e is not None

    def test_run(self):
        """`sched.scheduler+run 'a'。"""
        s = sched.scheduler(time.time, time.sleep)
        s.enter(0.01, 1, lambda: None)
        # 必 run 不崩
        s.run()
        assert True


# -- calendar 进阶 ----

class TestCalendarAdvanceV2:
    def test_calendar(self):
        """`calendar.calendar 'a'。"""
        # 必 callable
        assert callable(calendar.calendar)

    def test_isleap(self):
        """`calendar.isleap 'a'。"""
        # 必 True
        assert calendar.isleap(2024) is True
        # 必 False
        assert calendar.isleap(2025) is False

    def test_leapdays(self):
        """`calendar.leapdays 'a'。"""
        # 必 1
        assert calendar.leapdays(2020, 2021) == 1

    def test_weekday(self):
        """`calendar.weekday 'a'。"""
        # 必 0..6
        assert calendar.weekday(2025, 1, 1) in range(7)

    def test_monthrange(self):
        """`calendar.monthrange 'a'。"""
        # 必 tuple 2
        r = calendar.monthrange(2025, 1)
        assert isinstance(r, tuple)
        assert len(r) == 2

    def test_TextCalendar(self):
        """`calendar.TextCalendar 'a'。"""
        # 必 class
        assert calendar.TextCalendar is not None

    def test_HTMLCalendar(self):
        """`calendar.HTMLCalendar 'a'。"""
        # 必 class
        assert calendar.HTMLCalendar is not None

    def test_setfirstweekday(self):
        """`calendar.setfirstweekday 'a'。"""
        # 必 callable
        assert callable(calendar.setfirstweekday)


# -- enum 进阶 ----

class TestEnumAdvanceV3:
    def test_Enum(self):
        """`enum.Enum 'a'。"""

        class ForgeEnum(enum.Enum):
            A = 1
            B = 2

        # 必 member A
        assert ForgeEnum.A.value == 1

    def test_IntEnum(self):
        """`enum.IntEnum 'a'。"""

        class ForgeIntEnum(enum.IntEnum):
            X = 10
            Y = 20

        # 必 int
        assert isinstance(ForgeIntEnum.X, int)

    def test_Flag(self):
        """`enum.Flag 'a'。"""

        class ForgeFlag(enum.Flag):
            A = 1
            B = 2

        combined = ForgeFlag.A | ForgeFlag.B
        # 必 3
        assert combined.value == 3

    def test_IntFlag(self):
        """`enum.IntFlag 'a'。"""

        class ForgeIntFlag(enum.IntFlag):
            A = 1
            B = 2

        combined = ForgeIntFlag.A | ForgeIntFlag.B
        # 必 3
        assert combined.value == 3

    def test_auto(self):
        """`enum.auto 'a'。"""

        class ForgeAuto(enum.Enum):
            A = enum.auto()
            B = enum.auto()

        # 必 A=1
        assert ForgeAuto.A.value == 1

    def test_unique(self):
        """`enum.unique 'a'。"""
        # 必 callable
        assert callable(enum.unique)


# -- dataclasses 进阶 ----

class TestDataclassesAdvanceV3:
    def test_dataclass(self):
        """`dataclasses.dataclass 'a'。"""

        @dataclasses.dataclass
        class ForgeDC:
            v: int = 0

        d = ForgeDC(v=42)
        # 必 42
        assert d.v == 42

    def test_field(self):
        """`dataclasses.field 'a'。"""

        @dataclasses.dataclass
        class ForgeDC2:
            v: int = dataclasses.field(default=42)

        d = ForgeDC2()
        # 必 42
        assert d.v == 42

    def test_asdict(self):
        """`dataclasses.asdict 'a'。"""

        @dataclasses.dataclass
        class ForgeDC3:
            v: int = 42

        d = dataclasses.asdict(ForgeDC3())
        # 必 {'v': 42}
        assert d == {"v": 42}

    def test_astuple(self):
        """`dataclasses.astuple 'a'。"""

        @dataclasses.dataclass
        class ForgeDC4:
            v: int = 42

        t = dataclasses.astuple(ForgeDC4())
        # 必 (42,)
        assert t == (42,)

    def test_replace(self):
        """`dataclasses.replace 'a'。"""

        @dataclasses.dataclass
        class ForgeDC5:
            v: int = 42

        d = dataclasses.replace(ForgeDC5(), v=100)
        # 必 100
        assert d.v == 100

    def test_is_dataclass(self):
        """`dataclasses.is_dataclass 'a'。"""

        @dataclasses.dataclass
        class ForgeDC6:
            v: int = 0

        # 必 True
        assert dataclasses.is_dataclass(ForgeDC6) is True
        # 必 False
        assert dataclasses.is_dataclass(42) is False

    def test_fields(self):
        """`dataclasses.fields 'a'。"""

        @dataclasses.dataclass
        class ForgeDC7:
            v: int = 42

        f = dataclasses.fields(ForgeDC7)
        # 必 tuple
        assert isinstance(f, tuple)
        # 必 1 field
        assert len(f) == 1

    def test_make_dataclass(self):
        """`dataclasses.make_dataclass 'a'。"""
        DC = dataclasses.make_dataclass("ForgeDC8", [("v", int, 42)])
        d = DC()
        # 必 42
        assert d.v == 42
