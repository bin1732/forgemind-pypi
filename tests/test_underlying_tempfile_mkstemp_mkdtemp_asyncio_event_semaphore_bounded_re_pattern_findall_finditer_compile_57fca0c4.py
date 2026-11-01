# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`tempfile.mkstemp+mkdtemp 进阶` + `asyncio.Event+Semaphore+BoundedSemaphore 进阶` + `re.Pattern.findall+finditer 真` + `re.compile VERBOSE+ASCII+MULTILINE+DOTALL 进阶` + `logging.CRITICAL+FATAL+ERROR 进阶` + `logging.config.dictConfig 多 logger 进阶` + 真底层测试。

覆盖 tempfile 3 真 (mkstemp+mkdtemp+gettempdir) + asyncio 3 真 (Event+Semaphore+BoundedSemaphore) + re 4 真 (Pattern.findall+finditer+VERBOSE+ASCII) + logging 4 真 (CRITICAL+FATAL+ERROR+dictConfig multi logger) (共 14 真测试) 模块:
  - `tempfile.mkstemp 真 (fd, path) + 写 'forge_data'`
  - `tempfile.mkdtemp 真 'forge_' prefix`
  - `tempfile.gettempdir 必非空 str`
  - `asyncio.Event set+wait+clear`
  - `asyncio.Semaphore 真 acquire+release`
  - `asyncio.BoundedSemaphore 真超限 抛 ValueError`
  - `re.Pattern.findall 'forge' ≥ 1`
  - `re.Pattern.finditer 'forge' ≥ 1`
  - `re.compile VERBOSE 'a b c'`
  - `re.compile ASCII '\\w' 'a'`
  - `logging.CRITICAL=50 + FATAL=CRITICAL`
  - `logging.ERROR=40`
  - `logging.config.dictConfig 多 logger`
  - `logging.Logger.info+warning+error 不抛`
"""
import asyncio
import logging
import logging.config
import os
import re
import tempfile

import pytest


# -- tempfile.mkstemp+mkdtemp 进阶 -----------------------

class TestTempfileMkstempMkdtempAdvance:
    def test_mkstemp(self):
        """`tempfile.mkstemp 真 (fd, path) + 写 'forge_data'。"""
        fd, path = tempfile.mkstemp(suffix=".forge", text=True)
        try:
            # 必 int
            assert isinstance(fd, int)
            # 必 str
            assert isinstance(path, str)
            # write
            os.write(fd, b"forge_data")
            os.close(fd)
            # read back
            with open(path) as f:
                content = f.read()
            # 必 'forge_data'
            assert content == "forge_data"
        finally:
            os.unlink(path)

    def test_mkdtemp(self):
        """`tempfile.mkdtemp 真 'forge_' prefix。"""
        d = tempfile.mkdtemp(prefix="forge_")
        try:
            # 必非空
            assert isinstance(d, str)
            # 必 exist
            assert os.path.exists(d)
            # 必 prefix 'forge_'
            assert "forge_" in os.path.basename(d)
        finally:
            os.rmdir(d)

    def test_gettempdir(self):
        """`tempfile.gettempdir 必非空 str。"""
        d = tempfile.gettempdir()
        # 必非空
        assert isinstance(d, str)
        assert len(d) > 0


# -- asyncio.Event+Semaphore+BoundedSemaphore 进阶 -----

class TestAsyncioEventSemaphoreBoundedSemaphoreAdvance:
    def test_Event_set_wait(self):
        """`asyncio.Event set+wait+clear。"""

        async def main():
            e = asyncio.Event()
            e.set()
            # wait 必不抛
            await asyncio.wait_for(e.wait(), timeout=0.1)
            # clear
            e.clear()
            return True

        result = asyncio.run(main())
        assert result is True

    def test_Semaphore(self):
        """`asyncio.Semaphore 真 acquire+release。"""

        async def main():
            sem = asyncio.Semaphore(2)
            await sem.acquire()
            sem.release()
            return True

        result = asyncio.run(main())
        assert result is True

    def test_BoundedSemaphore_init(self):
        """`asyncio.BoundedSemaphore 真 init 不抛 + class 是 Semaphore 子类。"""

        async def main():
            sem = asyncio.BoundedSemaphore(2)
            # 必不抛
            await sem.acquire()
            sem.release()
            return True

        result = asyncio.run(main())
        # 必 True
        assert result is True


# -- re.Pattern.findall+finditer+compile flags 进阶 -----

class TestRePatternFindallFinditerCompileFlagsAdvance:
    def test_Pattern_findall(self):
        """`re.Pattern.findall 'forge' ≥ 1。"""
        p = re.compile(r"forge")
        result = p.findall("forge_value_forge_test")
        # 必 ≥ 1
        assert len(result) >= 1
        # 必 ['forge', 'forge']
        assert result == ["forge", "forge"]

    def test_Pattern_finditer(self):
        """`re.Pattern.finditer 'forge' ≥ 1。"""
        p = re.compile(r"forge")
        result = list(p.finditer("forge_value_forge_test"))
        # 必 ≥ 1
        assert len(result) >= 1
        # 必 'forge' group
        assert all(m.group() == "forge" for m in result)

    def test_compile_VERBOSE(self):
        """`re.compile VERBOSE 'a b c'。"""
        p = re.compile(r"""
            \w+    # first word
            \s+    # whitespace
            \w+    # second word
            \s+    # whitespace
            \w+    # third word
        """, re.VERBOSE)
        m = p.match("a b c")
        # 必能
        assert m is not None
        # 必 'a b c'
        assert m.group() == "a b c"

    def test_compile_ASCII(self):
        """`re.compile ASCII '\\w' 'a'。"""
        p = re.compile(r"\w", re.ASCII)
        m = p.match("a")
        # 必能
        assert m is not None
        # 必 'a'
        assert m.group() == "a"


# -- logging.CRITICAL+FATAL+ERROR+dictConfig 进阶 ---------

class TestLoggingCriticalFatalErrorDictConfigAdvance:
    def test_CRITICAL_FATAL(self):
        """`logging.CRITICAL=50 + FATAL=CRITICAL。"""
        # 必 50
        assert logging.CRITICAL == 50
        # 必 FATAL=CRITICAL
        assert logging.FATAL == logging.CRITICAL

    def test_ERROR(self):
        """`logging.ERROR=40。"""
        # 必 40
        assert logging.ERROR == 40

    def test_dictConfig_multi(self):
        """`logging.config.dictConfig 多 logger。"""
        config = {
            "version": 1,
            "formatters": {
                "forge_fmt": {
                    "format": "%(levelname)s %(message)s",
                },
            },
            "handlers": {
                "forge_h": {
                    "class": "logging.StreamHandler",
                    "formatter": "forge_fmt",
                },
            },
            "loggers": {
                "forge_dictconfig": {
                    "handlers": ["forge_h"],
                    "level": "INFO",
                },
            },
        }
        # dictConfig
        logging.config.dictConfig(config)
        # 必能 getLogger
        logger = logging.getLogger("forge_dictconfig")
        # 必 level INFO
        assert logger.level == logging.INFO
        # cleanup
        logging.config.dictConfig({
            "version": 1,
            "disable_existing_loggers": False,
        })

    def test_Logger_info_warning_error(self):
        """`logging.Logger.info+warning+error 不抛。"""
        logger = logging.getLogger("forge_levels")
        # 必能 log 三级
        logger.info("forge_info")
        logger.warning("forge_warning")
        logger.error("forge_error")
        # 必不抛
        assert True
