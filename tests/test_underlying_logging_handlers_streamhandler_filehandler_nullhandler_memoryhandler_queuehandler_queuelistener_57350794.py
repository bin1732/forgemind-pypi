# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`logging.handlers` 大进阶: StreamHandler/FileHandler/NullHandler/MemoryHandler/QueueHandler/QueueListener/SMTPHandler/SocketHandler/DatagramHandler/WatchedFileHandler 真底层测试。

覆盖 logging.StreamHandler 真写流 / FileHandler 真写文件 / NullHandler 不抛 / MemoryHandler buffer+flush / QueueHandler emit 不抛 / QueueListener 真收 / SMTPHandler 真 class / SocketHandler 真 class / DatagramHandler 真 class / WatchedFileHandler 真写 模块:
  - `StreamHandler 真 StringIO 写 'forge stream'`
  - `StreamHandler 真 setLevel + createLock`
  - `StreamHandler 真 setFormatter + 真格式`
  - `FileHandler 真写 file 'hello forge file handler'`
  - `NullHandler 真 emit 不抛`
  - `NullHandler 必继承 Handler`
  - `MemoryHandler 真 emit+flush 真到 target`
  - `MemoryHandler capacity=10 flush 真写`
  - `QueueHandler emit 真入 queue`
  - `QueueListener start+stop 真 drain`
  - `SMTPHandler 真 class 存在`
  - `SocketHandler 真 class 存在`
  - `DatagramHandler 真 class 存在`
  - `WatchedFileHandler 真写 'forge watched'`
"""
import io
import logging
import logging.handlers
import os
import queue
import socket
import sys
import tempfile

import pytest


# -- StreamHandler 真用 -----------------------------------------------------

class TestStreamHandlerAdvanced:
    def test_StreamHandler_emit(self):
        """`StreamHandler 真 StringIO 写 'forge stream'。"""
        log = logging.getLogger("forge_stream_emit")
        log.setLevel(logging.INFO)
        log.handlers.clear()
        buf = io.StringIO()
        h = logging.StreamHandler(buf)
        log.addHandler(h)
        try:
            log.info("forge stream emit")
            assert "forge stream emit" in buf.getvalue()
        finally:
            log.removeHandler(h)

    def test_StreamHandler_setFormatter(self):
        """`StreamHandler 真 setFormatter 含 level+message。"""
        log = logging.getLogger("forge_stream_fmt")
        log.setLevel(logging.INFO)
        log.handlers.clear()
        buf = io.StringIO()
        h = logging.StreamHandler(buf)
        # 设 formatter
        h.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        log.addHandler(h)
        try:
            log.warning("forge format test")
            assert "WARNING: forge format test" in buf.getvalue()
        finally:
            log.removeHandler(h)


# -- FileHandler 真用 -------------------------------------------------------

class TestFileHandlerAdvanced:
    def test_FileHandler_write(self):
        """`FileHandler 真写 file。"""
        with tempfile.NamedTemporaryFile(
            mode="w+", delete=False, suffix=".log"
        ) as f:
            path = f.name
        try:
            log = logging.getLogger("forge_file_adv")
            log.setLevel(logging.INFO)
            log.handlers.clear()
            h = logging.FileHandler(path)
            log.addHandler(h)
            try:
                log.info("hello forge file handler")
            finally:
                log.removeHandler(h)
                h.close()
            with open(path) as f:
                content = f.read()
            assert "hello forge file handler" in content
        finally:
            os.unlink(path)


# -- NullHandler 真用 -------------------------------------------------------

class TestNullHandlerAdvanced:
    def test_NullHandler_emit_silent(self):
        """`NullHandler 真 emit 不抛。"""
        nh = logging.NullHandler()
        # 必是 Handler 子
        assert isinstance(nh, logging.Handler)
        # 必 emit 不抛
        nh.emit(logging.LogRecord(
            "forge_null_adv", logging.INFO, "/x", 1, "msg", (), None
        ))


# -- MemoryHandler 真用 -----------------------------------------------------

class TestMemoryHandlerAdvanced:
    def test_MemoryHandler_flush(self):
        """`MemoryHandler 真 buffer+flush 真到 target。"""
        log = logging.getLogger("forge_mem_adv")
        log.setLevel(logging.INFO)
        log.handlers.clear()
        target_buf = io.StringIO()
        target_h = logging.StreamHandler(target_buf)
        # MemoryHandler
        mh = logging.handlers.MemoryHandler(capacity=10, target=target_h)
        log.addHandler(mh)
        try:
            log.info("forge memory 1")
            log.info("forge memory 2")
            # 必 not flushed
            assert "forge memory 1" not in target_buf.getvalue()
            # flush 必写
            mh.flush()
            assert "forge memory 1" in target_buf.getvalue()
            assert "forge memory 2" in target_buf.getvalue()
        finally:
            log.removeHandler(mh)


# -- QueueHandler + QueueListener 真用 --------------------------------------

class TestQueueHandlerAdvanced:
    def test_QueueHandler_emit(self):
        """`QueueHandler emit 真入 queue。"""
        log_queue = queue.Queue()
        log = logging.getLogger("forge_qh_adv")
        log.setLevel(logging.INFO)
        log.handlers.clear()
        qh = logging.handlers.QueueHandler(log_queue)
        log.addHandler(qh)
        try:
            log.info("forge queue handler 1")
            # 必 ≥ 1 record
            assert log_queue.qsize() >= 1
            record = log_queue.get_nowait()
            assert record.getMessage() == "forge queue handler 1"
        finally:
            log.removeHandler(qh)


class TestQueueListenerAdvanced:
    def test_QueueListener_start_stop(self):
        """`QueueListener start+stop 真 drain queue。"""
        log_queue = queue.Queue()
        log = logging.getLogger("forge_ql_adv")
        log.setLevel(logging.INFO)
        log.handlers.clear()
        # Target
        target_buf = io.StringIO()
        qh = logging.StreamHandler(target_buf)
        # Listener
        ql = logging.handlers.QueueListener(log_queue, qh)
        ql.start()
        try:
            # 走 QueueHandler
            qh2 = logging.handlers.QueueHandler(log_queue)
            log.addHandler(qh2)
            log.info("forge listener msg")
            # listener 异步, 给点时间
            import time
            time.sleep(0.1)
            # 必含
            assert "forge listener msg" in target_buf.getvalue()
            log.removeHandler(qh2)
        finally:
            ql.stop()


# -- SMTPHandler / SocketHandler / DatagramHandler 真 class 存在 ----------

class TestLoggingHandlersClasses:
    def test_SMTPHandler_class(self):
        """`SMTPHandler 真 class 存在。"""
        assert logging.handlers.SMTPHandler is not None
        assert callable(logging.handlers.SMTPHandler)

    def test_SocketHandler_class(self):
        """`SocketHandler 真 class 存在。"""
        assert logging.handlers.SocketHandler is not None

    def test_DatagramHandler_class(self):
        """`DatagramHandler 真 class 存在。"""
        assert logging.handlers.DatagramHandler is not None

    def test_WatchedFileHandler_write(self):
        """`WatchedFileHandler 真写 'forge watched'. """
        with tempfile.NamedTemporaryFile(
            mode="w+", delete=False, suffix=".log"
        ) as f:
            path = f.name
        try:
            log = logging.getLogger("forge_watched_adv")
            log.setLevel(logging.INFO)
            log.handlers.clear()
            h = logging.handlers.WatchedFileHandler(path)
            log.addHandler(h)
            try:
                log.info("forge watched msg")
            finally:
                log.removeHandler(h)
                h.close()
            with open(path) as f:
                content = f.read()
            assert "forge watched msg" in content
        finally:
            os.unlink(path)


# -- logging.Formatter 进阶 -------------------------------------------------

class TestLoggingFormatter:
    def test_Formatter_format(self):
        """`Formatter 真 format 含 levelname+name+message。"""
        fmt = logging.Formatter("%(levelname)s - %(name)s - %(message)s")
        record = logging.LogRecord(
            "forge_fmt_adv", logging.WARNING, "/x", 1, "msg", (), None
        )
        result = fmt.format(record)
        assert "WARNING" in result
        assert "forge_fmt_adv" in result
        assert "msg" in result


# -- logging.Logger 真用 ----------------------------------------------------

class TestLoggerAdvanced:
    def test_Logger_handlers_iter(self):
        """`Logger.handlers 真 list 可迭代。"""
        log = logging.getLogger("forge_logger_adv")
        log.handlers.clear()
        h = logging.NullHandler()
        log.addHandler(h)
        # 必 ≥ 1 handler
        assert len(log.handlers) >= 1
        # 必能 iter
        handlers = list(log.handlers)
        assert h in handlers
        log.removeHandler(h)
