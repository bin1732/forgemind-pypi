# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.subprocess.exec 真` + `asyncio.subprocess 进阶 (PIPE+STDOUT+DEVNULL+stderr=PIPE)` + `unittest.mock.AsyncMock 真用 (await_count+side_effect+return_value+AsyncMock)` + `datetime 进阶 (tzinfo.utcoffset+timedelta+datetime.now+replace+strptime+microsecond)` + 真底层测试。

覆盖 asyncio.subprocess 3 真 (PIPE+DEVNULL+stderr) + unittest.mock.AsyncMock 3 真 (await_count+side_effect+return_value) + datetime 4 真 (tzinfo.utcoffset+timedelta+now+strptime+microsecond) (共 10 真测试) 模块:
  - `asyncio.subprocess 'echo' stdout=PIPE 必 echo back`
  - `asyncio.subprocess 'true' stdin=DEVNULL 必 0`
  - `asyncio.subprocess 'false' stderr=PIPE 必 rc=1`
  - `AsyncMock 真 await_count=3 后 必 3`
  - `AsyncMock side_effect=[1,2,3] 真 await 返 next`
  - `AsyncMock return_value='forge' 真 await 返 'forge'`
  - `datetime tzinfo 真子化 + utcoffset 必 0 (UTC)`
  - `timedelta(1,1) 真 total_seconds=86401`
  - `datetime.now() 必 datetime instance`
  - `datetime strptime '2026-01-01' 真 dt.microsecond=0`
"""
import asyncio
import datetime
import unittest.mock

import pytest


# -- asyncio.subprocess 进阶 (PIPE + DEVNULL + stderr) ---------

class TestAsyncioSubprocessPipesAdvanced:
    def test_subprocess_stdout_pipe(self):
        """`asyncio.subprocess 'echo' stdout=PIPE 必 echo back。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "echo", "forge_echo",
                stdout=asyncio.subprocess.PIPE,
            )
            out, _ = await proc.communicate()
            return out

        out = asyncio.run(main())
        # 必含 'forge_echo'
        assert b"forge_echo" in out

    def test_subprocess_devnull(self):
        """`asyncio.subprocess 'true' stdin=DEVNULL 必 0。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "true",
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()
            return proc.returncode

        rc = asyncio.run(main())
        # 必 0
        assert rc == 0

    def test_subprocess_stderr_pipe(self):
        """`asyncio.subprocess 'false' stderr=PIPE 必 rc=1。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "false",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode

        rc = asyncio.run(main())
        # 必 1
        assert rc == 1


# -- unittest.mock.AsyncMock 真用 (await_count + side_effect + return_value) ----

class TestAsyncMockAdvanced:
    def test_AsyncMock_await_count(self):
        """`AsyncMock 真 await_count=3 后 必 3。"""

        async def main():
            m = unittest.mock.AsyncMock()
            # await 3 次
            for _ in range(3):
                await m()
            return m.await_count

        count = asyncio.run(main())
        # 必 3
        assert count == 3

    def test_AsyncMock_side_effect(self):
        """`AsyncMock side_effect=[1,2,3] 真 await 返 next。"""

        async def main():
            m = unittest.mock.AsyncMock(side_effect=[1, 2, 3])
            # await 3 次
            results = []
            for _ in range(3):
                results.append(await m())
            return results

        results = asyncio.run(main())
        # 必 [1, 2, 3]
        assert results == [1, 2, 3]

    def test_AsyncMock_return_value(self):
        """`AsyncMock return_value='forge' 真 await 返 'forge'。"""

        async def main():
            m = unittest.mock.AsyncMock(return_value="forge")
            # await
            result = await m()
            return result

        result = asyncio.run(main())
        # 必 'forge'
        assert result == "forge"


# -- datetime 进阶 (tzinfo + timedelta + now + strptime) ------

class _UtcTz(datetime.tzinfo):
    def utcoffset(self, dt):
        return datetime.timedelta(0)

    def dst(self, dt):
        return datetime.timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def fromutc(self, dt):
        return dt.replace(tzinfo=self)


class TestDatetimeTzinfoTimedeltaAdvanced:
    def test_tzinfo_utcoffset(self):
        """`datetime tzinfo 真子化 + utcoffset 必 0 (UTC)。"""
        tz = _UtcTz()
        # utcoffset(None) 必 0
        offset = tz.utcoffset(None)
        # 必 timedelta(0)
        assert offset == datetime.timedelta(0)

    def test_timedelta_1day_1sec(self):
        """`timedelta(1,1) 真 total_seconds=86401。"""
        td = datetime.timedelta(days=1, seconds=1)
        # 必 86401
        assert td.total_seconds() == 86401

    def test_datetime_now(self):
        """`datetime.now() 必 datetime instance。"""
        dt = datetime.datetime.now()
        # 必 datetime
        assert isinstance(dt, datetime.datetime)
        # 必 year ≥ 2026
        assert dt.year >= 2026

    def test_datetime_strptime_microsecond(self):
        """`datetime strptime '2026-01-01' 真 dt.microsecond=0。"""
        dt = datetime.datetime.strptime("2026-01-01", "%Y-%m-%d")
        # 必 2026-01-01
        assert dt.year == 2026
        # 必 microsecond=0
        assert dt.microsecond == 0
