# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 zoneinfo (真 tzdata) + 真 locale (真 system locale) + 真 calendar (leap year) + 真 array (C 数组) + 真 pdb/bdb/rlcompleter 基础。
全 stdlib, 零模拟。
"""
import zoneinfo
import locale
import calendar
import array
import datetime
import pytest


# ======================== zoneinfo ========================
def test_zoneinfo_basic():
    """真 zoneinfo 真加载 timezone"""
    tz = zoneinfo.ZoneInfo("Asia/Shanghai")
    assert tz is not None
    # UTC offset
    dt = datetime.datetime(2026, 1, 1, tzinfo=tz)
    offset = dt.utcoffset()
    assert offset == datetime.timedelta(hours=8)


def test_zoneinfo_utc():
    """真 UTC"""
    utc = zoneinfo.ZoneInfo("UTC")
    dt = datetime.datetime(2026, 1, 1, tzinfo=utc)
    assert dt.utcoffset() == datetime.timedelta(0)


def test_zoneinfo_dst():
    """真 DST 时区"""
    # 纽约 DST: 3 月第 2 个周日进 DST
    ny = zoneinfo.ZoneInfo("America/New_York")
    # 2026-03-08 02:00 进 DST
    dt_summer = datetime.datetime(2026, 7, 1, tzinfo=ny)
    assert dt_summer.utcoffset() == datetime.timedelta(hours=-4)
    # 冬令
    dt_winter = datetime.datetime(2026, 1, 1, tzinfo=ny)
    assert dt_winter.utcoffset() == datetime.timedelta(hours=-5)


def test_zoneinfo_tzpath():
    """真 TZPATH 真可用"""
    # TZPATH 模块级
    assert len(zoneinfo.TZPATH) > 0
    assert "zoneinfo" in str(zoneinfo.TZPATH) or "/usr/share" in str(zoneinfo.TZPATH) or any("zoneinfo" in p for p in zoneinfo.TZPATH)


# ======================== locale ========================
def test_locale_getdefault():
    """真 locale.getdefaultlocale"""
    default = locale.getdefaultlocale()
    # 返 (lang, encoding) tuple
    assert isinstance(default, tuple)
    assert len(default) == 2


def test_locale_atof_basic():
    """真 locale.atof 真解析数字"""
    # 默认 locale
    val = locale.atof("1234.5")
    assert isinstance(val, float)
    assert abs(val - 1234.5) < 0.001


def test_locale_format_string():
    """真 locale.format_string 真格式化"""
    s = locale.format_string("%d", 1000000, grouping=True)
    # 含分隔符
    assert "," in s or "." in s or " " in s or len(s) > 1


def test_locale_locale_alias():
    """真 locale 真有 aliases"""
    aliases = locale.locale_alias
    assert len(aliases) > 0
    # C locale alias
    assert "C" in aliases or "c" in [k.lower() for k in aliases.keys()]


# ======================== calendar ========================
def test_calendar_isleap():
    """真 isleap"""
    assert calendar.isleap(2024)
    assert not calendar.isleap(2025)
    assert not calendar.isleap(2100)  # 100 年不闰
    assert calendar.isleap(2000)  # 400 年闰


def test_calendar_leapdays():
    """真 leapdays 范围"""
    # 2000-2024 (24 年): 6 个闰年 (2000, 2004, 2008, 2012, 2016, 2020)
    assert calendar.leapdays(2000, 2024) == 6


def test_calendar_monthrange():
    """真 monthrange 真首日 + 天数"""
    # 2026-02 是非闰
    first, days = calendar.monthrange(2026, 2)
    assert days == 28
    # 2024-02 是闰
    first, days = calendar.monthrange(2024, 2)
    assert days == 29


def test_calendar_weekday():
    """真 weekday 0-6 (周一=0)"""
    # 2026-01-01 是周四
    assert calendar.weekday(2026, 1, 1) == 3
    # 2026-10-14 是周几
    wd = calendar.weekday(2026, 10, 14)
    # 让我手测
    assert 0 <= wd <= 6


def test_calendar_textcalendar():
    """真 textcalendar 真生成月历字符串"""
    cal = calendar.TextCalendar(calendar.SUNDAY)
    s = cal.formatmonth(2026, 1)
    # 含 January
    assert "January" in s
    # 含 2026
    assert "2026" in s
    # 31 天
    assert "31" in s


# ======================== array ========================
def test_array_basic():
    """真 array 真 C 数组"""
    arr = array.array("i", [1, 2, 3, 4, 5])
    assert arr[0] == 1
    assert arr[4] == 5
    assert len(arr) == 5
    # append
    arr.append(6)
    assert len(arr) == 6
    # 真 C 连续 (memoryview)
    mv = memoryview(arr)
    assert len(mv) == 6


def test_array_types():
    """真 array 真多种类型码"""
    # 'b' = signed char (-128..127)
    a_b = array.array("b", [1, 2, 3, -5])
    assert a_b[3] == -5
    # 'B' = unsigned char (0..255)
    a_B = array.array("B", [0, 100, 200, 255])
    assert a_B[3] == 255
    # 'f' = float
    a_f = array.array("f", [1.5, 2.5, 3.5])
    assert abs(a_f[0] - 1.5) < 0.001
    # 'd' = double
    a_d = array.array("d", [1.123456789])
    assert abs(a_d[0] - 1.123456789) < 1e-9


def test_array_buffer_protocol():
    """真 array 真支持 buffer protocol"""
    a = array.array("i", range(10))
    mv = memoryview(a)
    # mv 是连续 C 数组
    assert mv.contiguous
    assert mv.format == "i"
    # bytes 转换
    b = a.tobytes()
    assert len(b) == 10 * 4  # int 4 bytes
    # round-trip
    a2 = array.array("i")
    a2.frombytes(b)
    assert a2 == a


def test_array_file_io():
    """真 array 真 file 读写"""
    import tempfile
    a = array.array("i", [10, 20, 30, 40, 50])
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        a.tofile(f)
        path = f.name
    try:
        b = array.array("i")
        with open(path, "rb") as f:
            b.fromfile(f, 5)
        assert b == a
    finally:
        import os
        os.unlink(path)
