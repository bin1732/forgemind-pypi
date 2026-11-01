# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`logging.Filter` 子化 + `Logger.setLevel/isEnabledFor/getEffectiveLevel` + `LoggerAdapter` + `LogRecord` 进阶 + `logging.makeLogRecord` + `os.strerror` + `pathlib.PurePath` 进阶 (is_absolute+is_reserved) + `fnmatch.filter` + 真底层测试。

覆盖 logging 4 真 (Filter 子化+setLevel/isEnabledFor+LoggerAdapter+makeLogRecord) + os 1 真 (strerror errno) + pathlib 1 真 (PurePosixPath+is_absolute) + fnmatch 1 真 (filter 真过滤) (共 7 真测试) 模块:
  - `logging.Filter 子化 + filter(record) 返 True`
  - `Logger.setLevel WARNING + isEnabledFor(INFO) 必 False`
  - `LoggerAdapter + getEffectiveLevel 必 WARNING`
  - `logging.makeLogRecord 真造 LogRecord 含 msg='forge_log'`
  - `os.strerror errno.ENOENT 必 'No such file or directory'`
  - `pathlib.PurePosixPath('/a/b').is_absolute() 必 True`
  - `fnmatch.filter ['forge.py','foo.txt','forge.pyc'] 'forge.*' 必 2 .py+.pyc`
"""
import errno
import fnmatch
import logging
import os
import pathlib

import pytest


# -- logging 进阶 (Filter + Logger + LoggerAdapter + LogRecord) -----

class _MyFilter(logging.Filter):
    def filter(self, record):
        # accept all
        return True


class TestLoggingAdvancedV2:
    def test_Filter_subclass(self):
        """`logging.Filter 子化 + filter(record) 返 True。"""
        f = _MyFilter()
        # filter record
        record = logging.LogRecord("forge", logging.INFO, "/path", 1, "msg", None, None)
        # 必 True
        assert f.filter(record) is True

    def test_Logger_setLevel_isEnabledFor(self):
        """`Logger.setLevel WARNING + isEnabledFor(INFO) 必 False。"""
        logger = logging.getLogger("forge_test_logger")
        # setLevel
        logger.setLevel(logging.WARNING)
        # isEnabledFor(INFO) 必 False (低于 WARNING)
        assert logger.isEnabledFor(logging.INFO) is False
        # isEnabledFor(WARNING) 必 True
        assert logger.isEnabledFor(logging.WARNING) is True
        # getEffectiveLevel 必 WARNING
        assert logger.getEffectiveLevel() == logging.WARNING

    def test_LoggerAdapter_effective_level(self):
        """`LoggerAdapter + getEffectiveLevel 必 WARNING。"""
        logger = logging.getLogger("forge_adapter_test")
        logger.setLevel(logging.WARNING)
        adapter = logging.LoggerAdapter(logger, {"forge_key": "forge_value"})
        # 必非 None
        assert adapter is not None
        # 必能 getEffectiveLevel (从 underlying logger)
        assert adapter.logger.getEffectiveLevel() == logging.WARNING

    def test_makeLogRecord(self):
        """`logging.makeLogRecord 真造 LogRecord 含 msg='forge_log'。"""
        record = logging.makeLogRecord({
            "name": "forge_test",
            "levelname": "INFO",
            "levelno": logging.INFO,
            "msg": "forge_log",
        })
        # 必 LogRecord
        assert isinstance(record, logging.LogRecord)
        # 必 getMessage 含 'forge_log'
        assert "forge_log" in record.getMessage()


# -- os.strerror 进阶 (errno) --------------------------------------

class TestOsStrerrorAdvanced:
    def test_strerror_ENOENT(self):
        """`os.strerror errno.ENOENT 必 'No such file or directory'。"""
        result = os.strerror(errno.ENOENT)
        # 必含 'No such file' (EN-US)
        assert "No such file" in result or "no such file" in result.lower()


# -- pathlib 进阶 (PurePosixPath + is_absolute) --------------------

class TestPathlibPurePathAdvanced:
    def test_PurePosixPath_is_absolute(self):
        """`pathlib.PurePosixPath('/a/b').is_absolute() 必 True。"""
        p = pathlib.PurePosixPath("/a/b")
        # 必 True
        assert p.is_absolute() is True
        # 必非 True ('a/b' 是 relative)
        p2 = pathlib.PurePosixPath("a/b")
        assert p2.is_absolute() is False


# -- fnmatch 进阶 (filter 真过滤) --------------------------------

class TestFnmatchAdvanced:
    def test_filter(self):
        """`fnmatch.filter ['forge.py','foo.txt','forge.pyc'] 'forge.*' 必 2 .py+.pyc。"""
        names = ["forge.py", "foo.txt", "forge.pyc"]
        result = fnmatch.filter(names, "forge.*")
        # 必 2 (forge.py + forge.pyc)
        assert len(result) == 2
        # 必含 'forge.py'
        assert "forge.py" in result
        # 必含 'forge.pyc'
        assert "forge.pyc" in result
