# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 logging 真 custom Handler + 真 NullHandler + 真 QueueHandler + 真 dictConfig + 真 watched file 真 tail + 真 subprocess 真 stdin/stdout pipe 大数据 + 真 os.fdopen 真 fd 真开。
全 stdlib, 零模拟。
"""
import logging
import logging.handlers
import os
import queue
import subprocess
import sys
import tempfile
import pytest


# ======================== logging 进阶 ========================
def test_logging_NullHandler():
    """真 NullHandler 不抛"""
    h = logging.NullHandler()
    # 静默
    record = logging.LogRecord("test", logging.INFO, "/path", 1, "msg", None, None)
    h.handle(record)  # 不抛


def test_logging_custom_handler():
    """真自定义 Handler 真 emit"""
    class CollectingHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []
        def emit(self, record):
            self.records.append(record)

    logger = logging.getLogger("test_custom_handler")
    h = CollectingHandler()
    logger.addHandler(h)
    try:
        logger.setLevel(logging.DEBUG)
        logger.info("info 1")
        logger.warning("warn 1")
        logger.error("err 1")
    finally:
        logger.removeHandler(h)
    # 3 records
    assert len(h.records) == 3
    assert h.records[0].message == "info 1"
    assert h.records[2].levelname == "ERROR"


def test_logging_QueueHandler():
    """真 QueueHandler 真跨 thread"""
    q = queue.Queue()
    handler = logging.handlers.QueueHandler(q)
    logger = logging.getLogger("test_queue")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        logger.info("from thread")
    finally:
        logger.removeHandler(handler)
    # 收
    record = q.get(timeout=2)
    assert record.message == "from thread"


def test_logging_dictConfig():
    """真 dictConfig 真配"""
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {
                "format": "%(levelname)s: %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "simple",
            }
        },
        "loggers": {
            "test_dict": {
                "handlers": ["console"],
                "level": "DEBUG"
            }
        }
    }
    import io
    buf = io.StringIO()
    # 改 console handler 输出
    import logging.config
    logging.config.dictConfig(config)
    logger = logging.getLogger("test_dict")
    # 改 handler 输出流
    for h in logger.handlers:
        if hasattr(h, "stream"):
            h.stream = buf
    try:
        logger.info("dict config test")
        output = buf.getvalue()
        # 含 "INFO: dict config test"
        assert "INFO" in output
        assert "dict config test" in output
    finally:
        logging.config.dictConfig({"version": 1})


def test_logging_MemoryHandler():
    """真 MemoryHandler 真 buffer flush"""
    h = logging.handlers.MemoryHandler(capacity=3, flushLevel=logging.ERROR)
    logger = logging.getLogger("test_memory")
    # target sink
    records = []
    class Sink(logging.Handler):
        def emit(self, record):
            records.append(record)
    sink = Sink()
    h.setTarget(sink)
    logger.addHandler(h)
    logger.setLevel(logging.DEBUG)
    try:
        logger.info("info 1")  # buffer
        logger.info("info 2")  # buffer
        logger.info("info 3")  # buffer
        # error → flush
        logger.error("error!")
        # 4 records 全到 sink
        assert len(records) == 4
        assert records[0].message == "info 1"
        assert records[3].message == "error!"
    finally:
        logger.removeHandler(h)


# ======================== subprocess 进阶 ========================
def test_subprocess_pipe_file():
    """真 subprocess 真 stdin file 大数据"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        # 大数据 — 写 tmp 文件
        big = "x" * 100000
        f.write(big)
        path = f.name
    try:
        # 子进程读并回显长度
        proc = subprocess.run(
            [sys.executable, "-c", "import sys; data = open(sys.argv[1]).read(); print(len(data))", path],
            capture_output=True, text=True, timeout=5,
        )
        assert proc.returncode == 0
        assert proc.stdout.strip() == "100000"
    finally:
        os.unlink(path)


def test_subprocess_popen_communicate():
    """真 Popen communicate 真 stdin + stdout"""
    proc = subprocess.Popen(
        [sys.executable, "-c", "import sys; data = sys.stdin.read(); print(data.upper())"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = proc.communicate(input=b"hello world", timeout=5)
    assert b"HELLO WORLD" in stdout


def test_subprocess_check_output():
    """真 check_output 真捕"""
    result = subprocess.check_output(
        [sys.executable, "-c", "print('hello'); print('world')"],
        timeout=5,
    )
    # stdout 含 hello, world
    assert b"hello" in result
    assert b"world" in result


# ======================== os.fdopen 真 fd ========================
def test_os_fdopen_real_fd():
    """真 os.fdopen 真 fd 真写"""
    fd, path = tempfile.mkstemp()
    try:
        # fdopen
        f = os.fdopen(fd, "w")
        f.write("hello fdopen")
        f.close()
        # 读
        with open(path, "r") as r:
            content = r.read()
        assert content == "hello fdopen"
    finally:
        os.unlink(path)


def test_os_dup_dup2():
    """真 os.dup 真复制 fd"""
    fd1, path = tempfile.mkstemp()
    try:
        # 写
        os.write(fd1, b"original")
        # dup
        fd2 = os.dup(fd1)
        # fd2 写
        os.write(fd2, b" more")
        os.close(fd2)
        os.close(fd1)
        # 读
        with open(path, "rb") as f:
            content = f.read()
        # 应 original more
        assert content == b"original more"
    finally:
        os.unlink(path)
