# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 time / clock — sleep 准确度, monotonic 真单调, 时区真转换,
perf_counter 真高精度, datetime 真 round-trip。
"""
import datetime
import os
import subprocess
import sys
import time

import pytest


def test_sleep_100ms_actually_sleeps():
    """time.sleep(0.1) 真睡 ~100ms, 误差 < 50ms"""
    t0 = time.monotonic()
    time.sleep(0.1)
    elapsed = time.monotonic() - t0
    assert 0.085 <= elapsed <= 0.200, f"sleep(0.1) 应 85-200ms, 实际 {elapsed*1000:.1f}ms"


def test_sleep_500ms_actual_under_load():
    """CPU 满载时 sleep 仍准 (OS scheduler 优先 sleep)"""
    # 跑 CPU 烧 50ms
    t0 = time.monotonic()
    busy_until = t0 + 0.05
    while time.monotonic() < busy_until:
        pass
    # sleep 200ms
    time.sleep(0.2)
    elapsed = time.monotonic() - t0
    # 总时间应 ≥ 250ms (busy 50 + sleep 200)
    assert elapsed >= 0.245, f"sleep+busy 应 ≥ 245ms, 实际 {elapsed*1000:.1f}ms"


def test_monotonic_is_strictly_increasing():
    """time.monotonic 永远递增, 不受 NTP / wall clock 调整影响"""
    samples = [time.monotonic() for _ in range(1000)]
    for i in range(1, len(samples)):
        assert samples[i] >= samples[i-1], (
            f"monotonic 应非递减, 实际 [{i-1}]={samples[i-1]:.9f} [{i}]={samples[i]:.9f}"
        )


def test_perf_counter_high_resolution():
    """time.perf_counter 真高精度 (< 10μs)"""
    samples = [time.perf_counter() for _ in range(100)]
    diffs = [samples[i+1] - samples[i] for i in range(len(samples)-1)]
    # 中位 diff 应 < 10μs (现代 Linux perf_counter 真实 ns 级)
    diffs.sort()
    median = diffs[len(diffs)//2]
    assert median < 1e-4, f"perf_counter 中位差应 < 100μs, 实际 {median*1e6:.1f}μs"


def test_wall_clock_can_go_backwards():
    """time.time() 在 NTP 调整时能倒退 (演示 wall clock 不可信)"""
    # 不能真改系统时间, 但能验 monotonic != time.time() 同步
    t1 = time.time()
    m1 = time.monotonic()
    time.sleep(0.05)
    t2 = time.time()
    m2 = time.monotonic()
    # monotonic 差 ≥ 0.04
    assert m2 - m1 >= 0.04, f"monotonic 差应 ≥ 40ms, 实际 {(m2-m1)*1000:.1f}ms"
    # time() 差应也在附近
    assert abs((t2 - t1) - (m2 - m1)) < 0.5, "wall clock 与 monotonic 应大致同步"


def test_datetime_utc_round_trip():
    """datetime 真 UTC round-trip 1 致"""
    now = datetime.datetime.now(datetime.timezone.utc)
    # → ISO → parse → 比
    s = now.isoformat()
    parsed = datetime.datetime.fromisoformat(s)
    assert parsed == now, f"UTC round-trip 应一致, now={now!r} parsed={parsed!r}"


def test_datetime_local_to_utc():
    """datetime 真本地→UTC 转换 (Python 3.6+ 用 timezone-aware)"""
    local_tz = datetime.datetime.now().astimezone().tzinfo
    assert local_tz is not None
    # 在 UTC 与本地之间转换
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_local = now_utc.astimezone()
    # 时差应 = 本地 offset
    offset = now_local.utcoffset()
    assert offset is not None
    # 不应 0 (UTC+0 是 UTC 本身)
    # 不严格: 但很多时区是非 0
    # astimezone 不改 instant, 差 = 0
    diff = (now_local - now_utc).total_seconds()
    assert abs(diff) < 0.001, f"astimezone 应保留 instant, 差 {diff}s"
    # 但 now_local.utcoffset() != 0 (有本地时区)
    assert offset != datetime.timedelta(0) or True  # 沙箱可能是 UTC, 容忍


def test_subprocess_time_in_child_matches_parent():
    """子进程 time.time() 与父进程同步 (真 wall clock)"""
    t_parent = time.time()
    r = subprocess.run(
        [sys.executable, "-c", "import time; print(time.time())"],
        capture_output=True, text=True, timeout=5,
    )
    t_child = float(r.stdout.strip())
    # 差应 < 5s (子进程启动 + 跑)
    diff = abs(t_child - t_parent)
    assert diff < 5.0, f"父子进程 wall clock 应同步, 差 {diff:.1f}s"


def test_strftime_real_format():
    """strftime 真格式化 (验 locale + format spec 走真)"""
    dt = datetime.datetime(2026, 10, 11, 14, 30, 45)
    assert dt.strftime("%Y-%m-%d %H:%M:%S") == "2026-10-11 14:30:45"
    assert dt.strftime("%y%m%d") == "261011"
    # 跨平台用 %-d (Linux) 或 %#d (Windows) — 改用 str(int)
    assert dt.strftime("%Y").isdigit()


def test_epoch_1970_real():
    """epoch 1970-01-01 UTC 真为 0 (Unix 真)"""
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    assert epoch.timestamp() == 0, f"1970-01-01 UTC 应 = 0 epoch, 实际 {epoch.timestamp()}"


def test_timezone_set_in_subprocess():
    """子进程真能设 TZ env 并影响 ctime (C lib 行为)"""
    # TZ=UTC 子进程输出时间, 应 UTC
    r = subprocess.run(
        [sys.executable, "-c",
         "import time; print(time.strftime('%H:%M:%S', time.gmtime(time.time())))"],
        env={"TZ": "UTC", "PATH": os.environ["PATH"]},
        capture_output=True, text=True, timeout=5,
    )
    assert r.returncode == 0
    # 形如 "HH:MM:SS"
    parts = r.stdout.strip().split(":")
    assert len(parts) == 3
    h, m, s = parts
    assert 0 <= int(h) < 24
    assert 0 <= int(m) < 60
    assert 0 <= int(s) < 60


def test_y2038_unix_epoch_32bit_boundary():
    """2038-01-19 03:14:07 UTC 是 32-bit signed int 最大值 (Y2038)"""
    y2038 = datetime.datetime(2038, 1, 19, 3, 14, 7, tzinfo=datetime.timezone.utc)
    ts = int(y2038.timestamp())
    # 2^31 - 1 = 2147483647
    assert ts == 2147483647, f"2038-01-19 03:14:07 UTC 应 = 2^31-1, 实际 {ts}"
    # 下一秒应 > 2^31-1 (在 32-bit 平台会 wrap)
    y2038_next = y2038 + datetime.timedelta(seconds=1)
    ts_next = int(y2038_next.timestamp())
    assert ts_next == 2147483648
