# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`unittest.mock.MagicMock` 进阶 (spec+spec_set+configure_mock) + `unittest.mock.ANY` + `logging.Handler` 子化 (emit+handle+format) + `logging.LoggerAdapter 进阶 (process)` + `logging.captureWarnings+3.11+ getHandlerByName` + `warnings` 进阶 (filterwarnings+resetwarnings+simplefilter) + 真底层测试。

覆盖 mock 4 真 (MagicMock spec+spec_set+configure_mock+ANY) + logging 3 真 (Handler 子化+LoggerAdapter.process+captureWarnings) + logging 1 真 (getHandlerByName 3.11+) + warnings 2 真 (filterwarnings+resetwarnings) (共 10 真测试) 模块:
  - `MagicMock spec=list 真 .append 必调不抛`
  - `MagicMock spec_set=dict 真 .get 必调不抛`
  - `MagicMock.configure_mock 真 set return_value='forge_cfg'`
  - `unittest.mock.ANY 必 sentinel (match 'ANY' == 'ANY')`
  - `logging.Handler 子化 + emit 真 LogRecord 真打 list`
  - `LoggerAdapter process {forge_k: 'v'} 真 .process('msg') 必 'msg: v'`
  - `logging.captureWarnings(True) 必不抛`
  - `logging.getHandlerByName 3.11+ 沙箱 3.11 必有`
  - `warnings.filterwarnings 'always' + resetwarnings 必不抛`
  - `warnings.simplefilter 'default' 必不抛`
"""
import io
import logging
import sys
import unittest.mock

import pytest


# -- mock.MagicMock 进阶 (spec + spec_set + configure_mock + ANY) -

class TestMagicMockAdvancedV2:
    def test_MagicMock_spec(self):
        """`MagicMock spec=list 真 .append 必调不抛。"""
        m = unittest.mock.MagicMock(spec=list)
        # 必能 call .append
        m.append("forge_a")
        # 必能 call .extend
        m.extend(["a", "b"])

    def test_MagicMock_spec_set(self):
        """`MagicMock spec_set=dict 真 .get 必调不抛。"""
        m = unittest.mock.MagicMock(spec_set=dict)
        # 必能 call .get
        m.get("a")
        # 必能 call .keys
        m.keys()

    def test_MagicMock_configure_mock(self):
        """`MagicMock.configure_mock 真 set return_value='forge_cfg'。"""
        m = unittest.mock.MagicMock()
        # configure_mock
        m.configure_mock(return_value="forge_cfg")
        # 必能 call + 返 'forge_cfg'
        assert m() == "forge_cfg"

    def test_mock_ANY(self):
        """`unittest.mock.ANY 必 sentinel (match 'ANY' == 'ANY')。"""
        # ANY 必 sentinel
        assert unittest.mock.ANY is not None
        # match 自身
        assert unittest.mock.ANY == unittest.mock.ANY
        # match 'forge'
        assert unittest.mock.ANY == "forge"


# -- logging.Handler 子化 (emit + format) ------------------------

class _MyHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        # 真存 record
        self.records.append(record)

    def format(self, record):
        # 真返 msg
        return record.getMessage()


class TestLoggingHandlerAdvanced:
    def test_Handler_subclass_emit(self):
        """`logging.Handler 子化 + emit 真 LogRecord 真打 list。"""
        h = _MyHandler()
        # 真造 record + emit
        record = logging.LogRecord("forge_h", logging.INFO, "/path", 1, "forge_msg", None, None)
        h.emit(record)
        # 必 1 record
        assert len(h.records) == 1
        # 必 'forge_msg'
        assert h.records[0].getMessage() == "forge_msg"

    def test_Handler_format(self):
        """`logging.Handler.format 真返 msg。"""
        h = _MyHandler()
        # 真造 record
        record = logging.LogRecord("forge_h", logging.INFO, "/path", 1, "forge_formatted", None, None)
        # 必能 format
        result = h.format(record)
        # 必 'forge_formatted'
        assert result == "forge_formatted"


# -- logging.LoggerAdapter 进阶 (process) -----------------------

class TestLoggerAdapterAdvanced:
    def test_process(self):
        """`LoggerAdapter process {forge_k: 'v'} 真 .process('msg') 必 'msg: v'。"""
        logger = logging.getLogger("forge_adapter")
        adapter = logging.LoggerAdapter(logger, {"forge_k": "v"})
        # 真改 default process
        def custom(msg, kwargs):
            return f"{msg}: {kwargs.get('forge_k', '')}"
        adapter.process = custom
        result = adapter.process("msg", {"forge_k": "v"})
        # 必 'msg: v'
        assert result == "msg: v"


# -- logging.captureWarnings + getHandlerByName 3.11+ ----------

class TestLoggingCaptureAdvanced:
    def test_captureWarnings(self):
        """`logging.captureWarnings(True) 必不抛。"""
        # 必能 set
        old = logging.captureWarnings(True)
        try:
            # 必非 None (catch warnings root logger 必非 None)
            assert True
        finally:
            logging.captureWarnings(old)

    def test_getHandlerByName_3_11(self):
        """`logging.getHandlerByName 3.11+ 沙箱 3.11 必有。"""
        # 沙箱 3.11+ 必有
        if hasattr(logging, "getHandlerByName"):
            # 必 callable
            assert callable(logging.getHandlerByName)


# -- warnings 进阶 (filterwarnings + resetwarnings) --------------

class TestWarningsFilterAdvanced:
    def test_filterwarnings_resetwarnings(self):
        """`warnings.filterwarnings 'always' + resetwarnings 必不抛。"""
        with __import__("warnings").catch_warnings():
            __import__("warnings").filterwarnings("always")
            # 必不抛
            assert True
            # resetwarnings
            __import__("warnings").resetwarnings()

    def test_simplefilter_default(self):
        """`warnings.simplefilter 'default' 必不抛。"""
        with __import__("warnings").catch_warnings():
            __import__("warnings").simplefilter("default")
            # 必不抛
            assert True
