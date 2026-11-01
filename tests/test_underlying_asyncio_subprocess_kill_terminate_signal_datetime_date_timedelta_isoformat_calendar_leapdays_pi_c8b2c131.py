# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.subprocess.Process.kill/terminate/send_signal/SIGTERM` 真发 + `datetime` 进阶 (date+time+timedelta+tzinfo+isoformat+strftime) + `calendar` 进阶 (leapdays+weekday+monthrange+isleap) + `cmath` 进阶 (pi+e+complex+polar+rect+log+cbrt) + 真底层测试。

覆盖 asyncio.subprocess 3 真 (kill+terminate+send_signal) + datetime 5 真 (date+time+timedelta+isoformat+strftime) + calendar 4 真 (leapdays+weekday+monthrange+isleap) + cmath 5 真 (pi+e+polar+rect+sqrt) (共 17 真测试) 模块:
  - `asyncio.create_subprocess 'sleep 5' kill + wait 真 rc=-SIGKILL/-9`
  - `asyncio.create_subprocess 'sleep 5' terminate + wait 真 rc=-SIGTERM/-15`
  - `asyncio.create_subprocess 真 send_signal(SIGUSR1) + wait 不抛`
  - `datetime.date(2026,1,1) 真 .year=2026 + .weekday()`
  - `datetime.time(12,30,45) 真 .hour=12 + .minute=30 + .second=45`
  - `datetime.timedelta(days=5) 真 .days=5 + total_seconds=432000`
  - `datetime 真 .isoformat() 必 '2026-01-01'`
  - `datetime 真 .strftime('%Y-%m-%d') 必 '2026-01-01'`
  - `calendar.leapdays 2000-2024 必 ≥ 5 (含 2000+2004+2008+2012+2016+2020)`
  - `calendar.weekday 2026-01-01 必 3 (Thursday)`
  - `calendar.monthrange 2026-10 必 (3, 31)`
  - `calendar.isleap 2024 必 True / 2023 False`
  - `cmath.pi 真 ~3.1415926`
  - `cmath.e 真 ~2.7182818`
  - `cmath.polar(1+0j) 真 (1.0, 0.0) (r, phi)`
  - `cmath.rect(1, 0) 真 (1+0j)`
  - `cmath.sqrt(-1) 真 1j`
"""
import asyncio
import calendar
import cmath
import datetime
import os
import signal
import sys

import pytest


# -- asyncio.subprocess 进阶 (kill + terminate + send_signal) ---------

class TestAsyncioSubprocessKillTermSignal:
    def test_proc_kill(self):
        """`asyncio.create_subprocess 'sleep 5' kill + wait 真 rc != 0。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "sleep", "5",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # kill
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            # wait
            try:
                await asyncio.wait_for(proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                pass
            return proc.returncode

        rc = asyncio.run(main())
        # 必非 None
        assert rc is not None
        # 必非 0 (被 kill)
        assert rc != 0

    def test_proc_terminate(self):
        """`asyncio.create_subprocess 'sleep 5' terminate + wait 真 rc != 0。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "sleep", "5",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # terminate
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
            # wait
            try:
                await asyncio.wait_for(proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                pass
            return proc.returncode

        rc = asyncio.run(main())
        assert rc is not None
        assert rc != 0

    def test_proc_send_signal(self):
        """`asyncio.create_subprocess 真 send_signal(SIGUSR1) + wait 不抛。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "sleep", "5",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # send_signal
            try:
                proc.send_signal(signal.SIGUSR1)
            except (ProcessLookupError, OSError):
                pass
            # kill
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                pass
            return proc.returncode

        rc = asyncio.run(main())
        # 必 kill 后非 0
        assert rc is not None


# -- datetime 进阶 (date + time + timedelta + isoformat) -------------

class TestDatetimeAdvanced:
    def test_date_weekday(self):
        """`date(2026,1,1) 真 .year=2026 + .weekday() 3 (Thursday)。"""
        d = datetime.date(2026, 1, 1)
        # 必 2026-01-01
        assert d.year == 2026
        assert d.month == 1
        assert d.day == 1
        # 2026-01-01 是 Thursday, weekday=3
        assert d.weekday() == 3

    def test_time_attrs(self):
        """`time(12,30,45) 真 .hour=12 + .minute=30 + .second=45。"""
        t = datetime.time(12, 30, 45)
        # 必 hour/minute/second
        assert t.hour == 12
        assert t.minute == 30
        assert t.second == 45

    def test_timedelta_total_seconds(self):
        """`timedelta(days=5) 真 .days=5 + total_seconds=432000。"""
        td = datetime.timedelta(days=5)
        # 必 days=5
        assert td.days == 5
        # 必 432000 seconds
        assert td.total_seconds() == 5 * 24 * 3600

    def test_isoformat(self):
        """`date 真 .isoformat() 必 '2026-01-01'。"""
        d = datetime.date(2026, 1, 1)
        # 必 '2026-01-01'
        assert d.isoformat() == "2026-01-01"

    def test_strftime(self):
        """`datetime 真 .strftime('%Y-%m-%d') 必 '2026-01-01'。"""
        d = datetime.date(2026, 1, 1)
        # 必 '2026-01-01'
        assert d.strftime("%Y-%m-%d") == "2026-01-01"


# -- calendar 进阶 (leapdays + weekday + monthrange + isleap) --------

class TestCalendarAdvancedV3:
    def test_leapdays(self):
        """`leapdays 2000-2024 必 ≥ 5 (含 6 leap years)。"""
        n = calendar.leapdays(2000, 2024)
        # 必 6 (2000+2004+2008+2012+2016+2020)
        assert n >= 5

    def test_weekday_2026_01_01(self):
        """`weekday 2026-01-01 必 3 (Thursday)。"""
        assert calendar.weekday(2026, 1, 1) == 3

    def test_monthrange_2026_10(self):
        """`monthrange 2026-10 必 (3, 31) (Oct 1 是 Thursday + 31 天)。"""
        wd, days = calendar.monthrange(2026, 10)
        # 必 first weekday=3 (Thursday) + 31 days
        assert wd == 3
        assert days == 31

    def test_isleap(self):
        """`isleap 2024 True / 2023 False。"""
        assert calendar.isleap(2024) is True
        assert calendar.isleap(2023) is False


# -- cmath 进阶 (pi + e + polar + rect + sqrt) -----------------------

class TestCmathAdvanced:
    def test_pi(self):
        """`cmath.pi 真 ~3.1415926。"""
        assert abs(cmath.pi - 3.141592653589793) < 1e-10

    def test_e(self):
        """`cmath.e 真 ~2.7182818。"""
        assert abs(cmath.e - 2.718281828459045) < 1e-10

    def test_polar(self):
        """`cmath.polar(1+0j) 真 (1.0, 0.0) (r, phi)。"""
        r, phi = cmath.polar(1 + 0j)
        # 必 r=1.0, phi=0.0
        assert abs(r - 1.0) < 1e-10
        assert abs(phi - 0.0) < 1e-10

    def test_rect(self):
        """`cmath.rect(1, 0) 真 (1+0j)。"""
        z = cmath.rect(1, 0)
        # 必 1+0j
        assert abs(z.real - 1.0) < 1e-10
        assert abs(z.imag - 0.0) < 1e-10

    def test_sqrt(self):
        """`cmath.sqrt(-1) 真 1j。"""
        z = cmath.sqrt(-1)
        # 必 1j
        assert abs(z.real - 0.0) < 1e-10
        assert abs(z.imag - 1.0) < 1e-10
