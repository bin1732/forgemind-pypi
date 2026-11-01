# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""time 模块真实行为测试:挂钟、单调时钟、时区换算与时间格式化。

覆盖模块:time(与 datetime / os 交叉校验)。
真实测试项(18 项,全部使用系统真实时钟与真实时区数据):

  1. time.time 返回的真实纪元秒与 datetime 给出的时间戳一致
  2. time.time 连续采样单调不减
  3. time.monotonic 连续采样严格递增
  4. time.perf_counter 连续采样严格递增且分辨率足够细
  5. time.get_clock_info 报告每个时钟的真实属性
  6. time.process_time 随真实计算量增长
  7. time.thread_time 不超过 time.process_time
  8. time.clock_gettime(CLOCK_REALTIME) 与 time.time 相符
  9. time.localtime 的每个字段与 datetime.fromtimestamp 相符
 10. time.gmtime(0) 给出 1970-01-01 00:00:00 星期四
 11. time.localtime 与 time.gmtime 的时差等于 tm_gmtoff
 12. time.strftime 与 time.strptime 往返后各字段一致
 13. time.strftime 的各个格式符给出真实取值
 14. time.strptime 对非法输入抛 ValueError
 15. time.mktime 与 time.localtime 往返后纪元秒完全相同
 16. time.mktime(time.gmtime(ts)) 与模块时区常量一致
 17. time.sleep 的真实耗时不小于请求的时长
 18. time.tzset 立即响应 TZ 环境变量的变化
"""

import datetime
import os
import time

import pytest

HAS_TZSET = hasattr(time, "tzset")
HAS_THREAD_TIME = hasattr(time, "thread_time")

# 固定时刻:1609502400 = 2021-01-01 12:00:00 UTC。取 UTC 正午,本地时间
# 落在各时区夏令时切换点(当地凌晨)之外,mktime 与 localtime 的往返
# 因此在每个时区都精确成立。
FIXED_TS = 1609502400.0
HAS_CLOCK_GETTIME = hasattr(time, "clock_gettime") and hasattr(time, "CLOCK_REALTIME")


# ======================== 挂钟与单调时钟 ========================
def test_time_time_matches_wall_clock_epoch():
    """time.time() 返回真实的纪元秒,与 datetime 给出的时间戳相符。

    取值落在 2020-09-13 之后,与 datetime.now(UTC) 的时间戳相差
    不超过 1 秒。
    """
    now = time.time()
    assert isinstance(now, float)
    assert now > 1_600_000_000.0
    utc_timestamp = datetime.datetime.now(datetime.timezone.utc).timestamp()  # noqa: UP017
    assert abs(now - utc_timestamp) < 1.0
    assert abs(now - datetime.datetime.now().timestamp()) < 1.0


def test_time_time_is_non_decreasing():
    """time.time 连续采样单调不减,整体跨度为正。

    连续 500 次采样中后一个值不小于前一个值,首尾差值大于 0。
    """
    samples = [time.time() for _ in range(500)]
    assert all(later >= earlier for earlier, later in zip(samples, samples[1:]))
    assert samples[-1] > samples[0]
    assert samples[-1] - samples[0] >= 0.0


def test_time_monotonic_is_strictly_increasing():
    """time.monotonic 连续采样严格递增,且不受系统时间调整影响。

    连续 500 次采样中后一个值严格大于前一个值,整体数值大于 0。
    """
    samples = [time.monotonic() for _ in range(500)]
    assert all(later > earlier for earlier, later in zip(samples, samples[1:]))
    assert samples[-1] > samples[0]
    assert samples[-1] > 0.0


def test_time_perf_counter_is_strictly_increasing():
    """time.perf_counter 连续采样严格递增,分辨率达到纳秒量级。

    高精度计数器的分辨率不超过 1e-6 秒,连续采样的间隔严格为正。
    """
    clock_info = time.get_clock_info("perf_counter")
    assert clock_info.resolution <= 1e-6
    assert clock_info.monotonic is True

    samples = [time.perf_counter() for _ in range(500)]
    assert all(later > earlier for earlier, later in zip(samples, samples[1:]))
    assert samples[-1] > samples[0]


def test_time_clock_info_describes_each_clock():
    """time.get_clock_info 报告每个时钟的真实属性。

    wall clock 的 monotonic 为 False,monotonic、perf_counter、
    process_time、thread_time 的 monotonic 均为 True,
    各自的 resolution 都不超过 1e-6 秒。
    """
    assert time.get_clock_info("time").monotonic is False
    names = ["monotonic", "perf_counter", "process_time"]
    if HAS_THREAD_TIME:
        names.append("thread_time")
    for name in names:
        info = time.get_clock_info(name)
        assert info.monotonic is True
        assert info.resolution <= 1e-6
        assert isinstance(info.implementation, str)
        assert info.implementation != ""


def test_time_process_time_tracks_cpu_work():
    """time.process_time 随真实计算量增长,且不超过真实流逝时间。

    一段纯计算循环之后进程 CPU 时间明显增加,进程 CPU 时间不大于
    墙钟流逝时间(单线程下 CPU 时间被墙钟时间包含)。
    """
    cpu_before = time.process_time()
    wall_before = time.perf_counter()
    total = 0
    for index in range(300_000):
        total += index * index
    cpu_delta = time.process_time() - cpu_before
    wall_delta = time.perf_counter() - wall_before

    assert total == sum(index * index for index in range(300_000))
    assert cpu_delta > 0.0
    assert wall_delta > 0.0
    assert cpu_delta <= wall_delta + 0.5


@pytest.mark.skipif(
    not HAS_THREAD_TIME,
    reason="该平台没有 time.thread_time 时钟",
)
def test_time_thread_time_within_process_time():
    """time.thread_time 不超过 time.process_time,且在计算后同样增长。

    线程 CPU 时间在计算之后为正,并且始终不大于进程 CPU 时间。
    """
    thread_before = time.thread_time()
    process_before = time.process_time()
    total = 0
    for index in range(200_000):
        total += index
    thread_delta = time.thread_time() - thread_before

    assert total == sum(range(200_000))
    assert thread_delta > 0.0
    assert time.thread_time() > 0.0
    assert time.thread_time() <= time.process_time() + 1e-6
    assert time.process_time() >= process_before


@pytest.mark.skipif(
    not HAS_CLOCK_GETTIME,
    reason="需要 clock_gettime 与 CLOCK_REALTIME 常量",
)
def test_time_clock_gettime_realtime_matches_time():
    """time.clock_gettime(CLOCK_REALTIME) 与 time.time 给出同一挂钟读数。

    两次调用的差值小于 0.01 秒,说明它们读的是同一个系统时钟。
    """
    realtime = time.clock_gettime(time.CLOCK_REALTIME)
    wall = time.time()
    assert isinstance(realtime, float)
    assert abs(realtime - wall) < 0.01
    assert abs(time.clock_gettime(time.CLOCK_REALTIME) - time.time()) < 0.01


# ======================== 时区与结构体 ========================
def test_time_localtime_fields_match_datetime():
    """time.localtime 的每个字段与 datetime.fromtimestamp 的结果相符。

    年月日时分秒、星期序号与年内第几天全部一致,夏令时标志取值为
    -1、0、1 之一。
    """
    timestamp = FIXED_TS
    local = time.localtime(timestamp)
    reference = datetime.datetime.fromtimestamp(timestamp)

    assert local.tm_year == reference.year
    assert local.tm_mon == reference.month
    assert local.tm_mday == reference.day
    assert local.tm_hour == reference.hour
    assert local.tm_min == reference.minute
    assert local.tm_sec == reference.second
    assert local.tm_wday == reference.weekday()
    assert local.tm_yday == reference.timetuple().tm_yday
    assert local.tm_isdst in (-1, 0, 1)


def test_time_gmtime_epoch_fields():
    """time.gmtime(0) 给出 1970-01-01 00:00:00 且为星期四。

    年月日时分秒、年内第 1 天、星期序号 3 全部确定,
    gmtime(1609502400) 的小时数等于纪元秒整除 3600 后对 24 取模,
    年份为 2021。
    """
    epoch = time.gmtime(0)
    assert epoch.tm_year == 1970
    assert epoch.tm_mon == 1
    assert epoch.tm_mday == 1
    assert epoch.tm_hour == 0
    assert epoch.tm_min == 0
    assert epoch.tm_sec == 0
    assert epoch.tm_yday == 1
    assert epoch.tm_wday == 3
    assert epoch.tm_isdst == 0

    later = time.gmtime(FIXED_TS)
    assert later.tm_hour == int(FIXED_TS // 3600 % 24)
    assert later.tm_hour == 12
    assert later.tm_year == 2021


def test_time_localtime_offset_matches_tm_gmtoff():
    """time.localtime 与 time.gmtime 的时差等于结构体里的 tm_gmtoff。

    本地时间比 UTC 快多少秒,本地小时数与 UTC 小时数的差(对 24 取模)
    必须等于 tm_gmtoff 换算成的小时数。
    """
    timestamp = FIXED_TS
    local = time.localtime(timestamp)
    utc = time.gmtime(timestamp)
    if not hasattr(local, "tm_gmtoff"):
        pytest.skip("该平台的 struct_time 不带 tm_gmtoff 字段")

    offset = local.tm_gmtoff
    assert offset == -time.timezone or offset == -time.altzone
    hour_gap = (local.tm_hour - utc.tm_hour) % 24
    assert hour_gap == (offset // 3600) % 24
    assert time.mktime(local) - time.mktime(utc) == offset
    assert time.mktime(local) == timestamp


# ======================== 格式化与解析 ========================
def test_time_strftime_strptime_roundtrip():
    """time.strftime 与 time.strptime 往返后各字段完全一致。

    格式化出的文本用同一格式解析回来,年月日时分秒与纪元秒都与原始
    本地时间相同。
    """
    timestamp = FIXED_TS
    local = time.localtime(timestamp)
    text = time.strftime("%Y-%m-%d %H:%M:%S", local)
    parsed = time.strptime(text, "%Y-%m-%d %H:%M:%S")

    assert text == time.strftime("%Y-%m-%d %H:%M:%S", local)
    assert parsed.tm_year == local.tm_year
    assert parsed.tm_mon == local.tm_mon
    assert parsed.tm_mday == local.tm_mday
    assert parsed.tm_hour == local.tm_hour
    assert parsed.tm_min == local.tm_min
    assert parsed.tm_sec == local.tm_sec
    assert time.mktime(parsed) == time.mktime(local)


def test_time_strftime_directive_values():
    """time.strftime 的各个格式符给出确定的取值。

    对结构体 2021-03-04 05:06:07(星期四、年内第 63 天),
    %Y-%m-%d 为 2021-03-04、%H:%M:%S 为 05:06:07、%j 为 063、
    %y 为 21、%I 为 05、%m 为 03;
    %p 给出的上下午标记能区分 05:06 与 17:06,按同一标记回解时
    小时数分别还原为 5 与 17。
    """
    moment = time.struct_time((2021, 3, 4, 5, 6, 7, 3, 63, 0))
    evening = time.struct_time((2021, 3, 4, 17, 6, 7, 3, 63, 0))
    assert time.strftime("%Y-%m-%d", moment) == "2021-03-04"
    assert time.strftime("%H:%M:%S", moment) == "05:06:07"
    assert time.strftime("%j", moment) == "063"
    assert time.strftime("%y", moment) == "21"
    assert time.strftime("%I", moment) == "05"
    assert time.strftime("%m", moment) == "03"

    morning_marker = time.strftime("%p", moment)
    evening_marker = time.strftime("%p", evening)
    assert morning_marker != ""
    assert evening_marker != ""
    assert morning_marker != evening_marker
    assert time.strptime(f"05:06 {morning_marker}", "%I:%M %p").tm_hour == 5
    assert time.strptime(f"05:06 {evening_marker}", "%I:%M %p").tm_hour == 17

    weekday_text = time.strftime("%A", moment)
    assert time.strptime(weekday_text, "%A").tm_wday == 3


def test_time_strptime_rejects_invalid_input():
    """time.strptime 对非法输入抛 ValueError。

    月份 13、日 45 无法构成合法日期,非日期文本同样被拒绝。
    """
    with pytest.raises(ValueError, match="does not match format"):
        time.strptime("2021-13-45", "%Y-%m-%d")
    with pytest.raises(ValueError, match="does not match format"):
        time.strptime("not a date", "%Y-%m-%d")
    with pytest.raises(ValueError, match="out of range for month"):
        time.strptime("2021-02-30", "%Y-%m-%d")


def test_time_mktime_localtime_roundtrip():
    """time.mktime 与 time.localtime 往返后纪元秒完全相同。

    三个取整秒的时间戳往返后逐个相等,说明本地时区换算是自洽的。
    """
    for timestamp in (1_609_502_400.0, 1_655_294_400.0, 1_694_779_200.0):
        assert time.mktime(time.localtime(timestamp)) == timestamp

    local = time.localtime(FIXED_TS)
    assert time.mktime(local) == FIXED_TS
    assert time.mktime(time.localtime(FIXED_TS)) == int(FIXED_TS)


def test_time_mktime_gmtime_offset_matches_timezone_constants():
    """time.mktime(time.gmtime(ts)) 的结果与模块时区常量一致。

    用 GMT 结构体构造出的本地纪元秒,等于纪元秒减去本地相对 UTC 的
    偏移;该偏移必须与 time.timezone / time.altzone 之一吻合,
    且 time.tzname 始终给出两个非空名称。
    """
    timestamp = FIXED_TS
    local = time.localtime(timestamp)
    if not hasattr(local, "tm_gmtoff"):
        pytest.skip("该平台的 struct_time 不带 tm_gmtoff 字段")

    offset = local.tm_gmtoff
    rebuilt = time.mktime(time.gmtime(timestamp))
    assert rebuilt == pytest.approx(timestamp - offset, abs=1.0)
    assert offset in (-time.timezone, -time.altzone)
    assert time.daylight in (0, 1)
    assert len(time.tzname) == 2
    assert all(isinstance(name, str) and name != "" for name in time.tzname)


# ======================== 等待与时区刷新 ========================
def test_time_sleep_waits_at_least_requested():
    """time.sleep 的真实耗时不小于请求的时长。

    请求 0.05 秒的等待,实测耗时不少于 0.05 秒且远小于 5 秒;
    time.sleep(0) 立即返回,耗时不足 0.5 秒。
    """
    start = time.perf_counter()
    time.sleep(0.05)
    elapsed = time.perf_counter() - start
    assert elapsed >= 0.05
    assert elapsed < 5.0

    start = time.perf_counter()
    time.sleep(0)
    immediate = time.perf_counter() - start
    assert immediate >= 0.0
    assert immediate < 0.5


@pytest.mark.skipif(not HAS_TZSET, reason="需要 POSIX 的 time.tzset")
def test_time_tzset_honours_tz_environment():
    """time.tzset 立即响应 TZ 环境变量的变化。

    TZ 设为 UTC 时,纪元时刻的本地小时数为 0、时区偏移为 0;
    TZ 设为 Asia/Shanghai 时,本地小时数为 8;
    还原 TZ 后本地小时数回到原值。
    """
    original_tz = os.environ.get("TZ")
    original_hour = time.localtime(0).tm_hour
    try:
        os.environ["TZ"] = "UTC"
        time.tzset()
        assert time.localtime(0).tm_hour == 0
        assert time.timezone == 0
        assert time.altzone == 0
        assert time.tzname[0] == "UTC"

        if os.path.exists("/usr/share/zoneinfo/Asia/Shanghai"):
            os.environ["TZ"] = "Asia/Shanghai"
            time.tzset()
            assert time.localtime(0).tm_hour == 8
            assert time.localtime(0).tm_yday == 1
            assert time.timezone == -8 * 3600
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        time.tzset()

    assert time.localtime(0).tm_hour == original_hour
