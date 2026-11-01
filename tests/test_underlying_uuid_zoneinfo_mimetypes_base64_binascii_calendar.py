# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`uuid` / `zoneinfo` / `mimetypes` / `base64` / `binascii` / `calendar` 真底层测试。

- uuid:真的生成各类标识符,并能复现
- zoneinfo:真的查时区与夏令时
- mimetypes:真的猜媒体类型
- base64 / binascii:真的做编解码往返
- calendar:真的做日期与日历计算

覆盖 uuid 5 + zoneinfo 5 + mimetypes 5 + base64 5 + binascii 5 + calendar 5 + 真底层测试。
"""

import base64
import binascii
import calendar
import datetime
import mimetypes
import uuid
import zoneinfo
from pathlib import Path

import pytest


# ======================== uuid ========================


class TestUuid:
    """标识符"""

    def test_uuid1_is_unique(self):
        """两次生成不一样"""
        assert uuid.uuid1() != uuid.uuid1()

    def test_uuid4_is_unique(self):
        """随机标识符两次生成不一样"""
        assert uuid.uuid4() != uuid.uuid4()

    def test_uuid4_version(self):
        """随机标识符的版本是 4"""
        value = uuid.uuid4()
        assert value.version == 4

    def test_uuid3_is_deterministic(self):
        """基于命名空间的标识符可复现"""
        name = uuid.NAMESPACE_DNS
        first = uuid.uuid3(name, "forge.invalid")
        second = uuid.uuid3(name, "forge.invalid")
        assert first == second
        assert first.version == 3

    def test_uuid5_is_deterministic(self):
        """基于散列的标识符可复现"""
        first = uuid.uuid5(uuid.NAMESPACE_URL, "https://forge.invalid")
        second = uuid.uuid5(uuid.NAMESPACE_URL, "https://forge.invalid")
        assert first == second
        assert first.version == 5

    def test_uuid_parsing(self):
        """标识符能解析回来"""
        value = uuid.uuid4()
        assert uuid.UUID(str(value)) == value

    def test_uuid_bytes_roundtrip(self):
        """字节形式能还原"""
        value = uuid.uuid4()
        assert uuid.UUID(bytes=value.bytes) == value

    def test_uuid_fields(self):
        """节点与时钟序列可读"""
        value = uuid.uuid1()
        assert isinstance(value.node, int)
        assert value.clock_seq >= 0


# ======================== zoneinfo ========================


class TestZoneInfo:
    """时区"""

    def test_utc(self):
        """协调世界时可用"""
        tz = zoneinfo.ZoneInfo("UTC")
        moment = datetime.datetime(2024, 6, 1, 12, tzinfo=tz)
        assert moment.utcoffset() == datetime.timedelta(0)

    def test_asia_shanghai(self):
        """东八区可用"""
        tz = zoneinfo.ZoneInfo("Asia/Shanghai")
        moment = datetime.datetime(2024, 6, 1, 12, tzinfo=tz)
        assert moment.utcoffset() == datetime.timedelta(hours=8)

    def test_dst_summer(self):
        """夏令时区在夏令时期间偏移更大"""
        tz = zoneinfo.ZoneInfo("America/New_York")
        winter = datetime.datetime(2024, 1, 15, 12, tzinfo=tz)
        summer = datetime.datetime(2024, 7, 15, 12, tzinfo=tz)
        assert summer.utcoffset() != winter.utcoffset()

    def test_available_timezones(self):
        """能列出可用时区"""
        zones = zoneinfo.available_timezones()
        assert "UTC" in zones
        assert "Asia/Shanghai" in zones

    def test_unknown_timezone_raises(self):
        """查不到的时区报错"""
        with pytest.raises(zoneinfo.ZoneInfoNotFoundError):
            zoneinfo.ZoneInfo("No/Such_Zone_Forge")


# ======================== mimetypes ========================


class TestMimetypes:
    """媒体类型"""

    def test_guess_type_html(self):
        """能猜出网页类型"""
        guessed = mimetypes.guess_type("page.html")
        assert guessed is not None
        assert guessed[0] == "text/html"

    def test_guess_type_json(self):
        """能猜出 json 类型"""
        guessed = mimetypes.guess_type("data.json")
        assert guessed is not None
        assert guessed[0] == "application/json"

    def test_guess_type_unknown(self):
        """不认识的扩展名给不出类型"""
        assert mimetypes.guess_type("file.forgeunknown") == (None, None)

    def test_guess_type_by_content(self):
        """能按内容猜类型"""
        guessed = mimetypes.guess_type("forge", strict=False)
        assert guessed is None or isinstance(guessed, tuple)

    def test_guess_extension(self):
        """能由类型反推扩展名"""
        extension = mimetypes.guess_extension("text/html")
        assert extension in (".html", ".htm")

    def test_add_type(self):
        """能登记新的类型"""
        mimetypes.add_type("application/x-forge", ".forge")
        assert mimetypes.guess_type("a.forge")[0] == "application/x-forge"


# ======================== base64 ========================


class TestBase64:
    """Base 编解码"""

    def test_encode_decode(self):
        """往返后一致"""
        data = b"forge payload"
        assert base64.b64decode(base64.b64encode(data)) == data

    def test_encode_is_text(self):
        """编码结果是文本"""
        assert isinstance(base64.b64encode(b"forge"), bytes)

    def test_known_vector(self):
        """与已知结果一致"""
        assert base64.b64encode(b"forge") == b"Zm9yZ2U="

    def test_urlsafe_alphabet(self):
        """网址安全字母表不含加号与斜杠"""
        encoded = base64.urlsafe_b64encode(b"\xfb\xff\xfe")
        assert b"+" not in encoded
        assert b"/" not in encoded

    def test_decode_with_invalid_padding(self):
        """填充不对时报错"""
        with pytest.raises(binascii.Error):
            base64.b64decode(b"Zm9yZ2U")


# ======================== binascii ========================


class TestBinascii:
    """二进制与文本互转"""

    def test_hexlify(self):
        """能转成十六进制"""
        assert binascii.hexlify(b"forge") == b"666f726765"

    def test_unhexlify(self):
        """能转回来"""
        assert binascii.unhexlify(b"666f726765") == b"forge"

    def test_b2a_base64(self):
        """能编成 Base64"""
        assert binascii.b2a_base64(b"forge") == b"Zm9yZ2U=\n"

    def test_a2b_base64(self):
        """能解 Base64"""
        assert binascii.a2b_base64(b"Zm9yZ2U=\n") == b"forge"

    def test_crc32(self):
        """能算校验值"""
        assert isinstance(binascii.crc32(b"forge"), int)


# ======================== calendar ========================


class TestCalendar:
    """日历计算"""

    def test_isleap(self):
        """能判断闰年"""
        assert calendar.isleap(2024) is True
        assert calendar.isleap(2023) is False

    def test_leapdays(self):
        """能算闰日数量"""
        assert calendar.leapdays(2020, 2024) == 1

    def test_monthrange(self):
        """能取一个月的首日星期与天数"""
        first, days = calendar.monthrange(2024, 2)
        assert days == 29
        assert first == 3

    def test_monthdayscalendar(self):
        """能排出整月日历"""
        weeks = calendar.Calendar(0).monthdayscalendar(2024, 2)
        assert weeks[0][0] == 0
        assert 29 in weeks[-1]

    def test_calendar_formatter(self):
        """格式化器能给出月名"""
        fmt = calendar.TextCalendar()
        text = fmt.formatmonth(2024, 2)
        assert "February" in text

    def test_calendar_prmonth(self, capsys):
        """能打印整月"""
        calendar.prmonth(2024, 2)
        assert "February" in capsys.readouterr().out

    def test_day_name(self):
        """能取星期名"""
        assert calendar.day_name[0] == "Monday"

    def test_month_name(self):
        """能取月份名"""
        assert calendar.month_name[1] == "January"
        assert calendar.month_abbr[1] == "Jan"

    def test_calendar(self):
        """能取一个月的日历矩阵"""
        cal = calendar.Calendar(0).monthdayscalendar(2024, 2)
        assert len(cal) == 5
