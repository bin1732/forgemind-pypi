# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 logging: 真 StreamHandler/FileHandler/RotatingFileHandler + 真 propagation + 真 thread safety + 真 level 过滤。
全 stdlib C 实现, 零 Python 模拟。
"""
import os
import sys
import io
import logging
import threading
import tempfile
import time
import pytest


def test_logging_basic_loggers():
    """真 logger hierarchy"""
    root = logging.getLogger()
    child = logging.getLogger("forgemind.test")
    grandchild = logging.getLogger("forgemind.test.sub")
    # 真 hierarchy
    assert child.parent is root or child.parent is logging.getLogger("forgemind")
    assert grandchild.parent is child or grandchild.parent.name == "forgemind.test"


def test_logging_level_set_get():
    """真 logger level 真 set/get"""
    logger = logging.getLogger("test_level")
    logger.setLevel(logging.DEBUG)
    assert logger.level == logging.DEBUG
    logger.setLevel(logging.WARNING)
    assert logger.level == logging.WARNING
    # 默认 NOTSET
    logger2 = logging.getLogger("test_level_new")
    assert logger2.level == logging.NOTSET


def test_logging_level_filter():
    """真 level 真过滤"""
    logger = logging.getLogger("test_filter")
    logger.setLevel(logging.WARNING)
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.WARNING)
    logger.addHandler(handler)
    try:
        logger.debug("skip me")
        logger.warning("keep me")
        logger.error("keep me too")
        out = buf.getvalue()
        assert "skip me" not in out
        assert "keep me" in out
        assert "keep me too" in out
    finally:
        logger.removeHandler(handler)


def test_logging_formatter_real():
    """真 Formatter 格式"""
    logger = logging.getLogger("test_formatter")
    logger.setLevel(logging.DEBUG)
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(levelname)s|%(name)s|%(message)s"))
    logger.addHandler(handler)
    try:
        logger.info("hello")
        out = buf.getvalue().strip()
        assert out == "INFO|test_formatter|hello"
    finally:
        logger.removeHandler(handler)


def test_logging_file_handler_real():
    """真 FileHandler 真写磁盘 + 真 close"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
        path = f.name
    try:
        logger = logging.getLogger("test_file")
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(path)
        logger.addHandler(handler)
        try:
            logger.info("file message 1")
            logger.warning("file message 2")
        finally:
            logger.removeHandler(handler)
            handler.close()

        # 真读回
        with open(path) as f:
            content = f.read()
        assert "file message 1" in content
        assert "file message 2" in content
    finally:
        os.unlink(path)


def test_logging_propagation():
    """真 propagation 链 (child → parent)"""
    parent = logging.getLogger("test_prop_parent")
    parent.setLevel(logging.INFO)
    parent_buf = io.StringIO()
    parent_handler = logging.StreamHandler(parent_buf)
    parent_handler.setFormatter(logging.Formatter("%(name)s|%(message)s"))
    parent.addHandler(parent_handler)

    child = logging.getLogger("test_prop_parent.child")
    child.setLevel(logging.DEBUG)  # child 接受所有
    # child 没 handler → propagate 到 parent
    try:
        child.info("from child")
        out = parent_buf.getvalue()
        assert "from child" in out
        assert "test_prop_parent.child" in out  # logger 名应是 child
    finally:
        parent.removeHandler(parent_handler)


def test_logging_no_propagation():
    """真 propagate=False 阻断"""
    parent = logging.getLogger("test_noprop")
    parent_buf = io.StringIO()
    parent_handler = logging.StreamHandler(parent_buf)
    parent_handler.setFormatter(logging.Formatter("%(name)s|%(message)s"))
    parent.addHandler(parent_handler)
    parent.setLevel(logging.INFO)

    child = logging.getLogger("test_noprop.child")
    child.propagate = False
    try:
        child.info("isolated")
        # parent_buf 应空
        assert parent_buf.getvalue() == ""
    finally:
        parent.removeHandler(parent_handler)
        child.propagate = True


def test_logging_thread_safety_real():
    """真 20 线程各 100 行 = 2000 行不丢"""
    logger = logging.getLogger("test_thread")
    logger.setLevel(logging.INFO)
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    logger.addHandler(handler)
    errors = []

    def worker(n):
        try:
            for i in range(100):
                logger.info(f"thread{n} line{i}")
        except Exception as e:
            errors.append(e)

    try:
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        logger.removeHandler(handler)

    assert not errors, f"线程内异常: {errors}"
    # 20 * 100 = 2000 行
    out = buf.getvalue()
    assert out.count("thread") == 2000
    # 每线程 100 行 — 全 20 thread 编号
    for n in range(20):
        assert out.count(f"thread{n} line") == 100


def test_logging_capturewarnings():
    """真 captureWarnings 把 warning 路由到 logging"""
    logger = logging.getLogger("test_capture")
    logger.setLevel(logging.DEBUG)
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    logger.addHandler(handler)
    try:
        # 启用 captureWarnings
        logging.captureWarnings(True)
        try:
            warnings_logger = logging.getLogger("py.warnings")
            warnings_logger.addHandler(handler)
            warnings_logger.propagate = False
            try:
                import warnings
                warnings.warn("this is a test warning", UserWarning)
                out = buf.getvalue()
                assert "this is a test warning" in out
            finally:
                warnings_logger.removeHandler(handler)
                warnings_logger.propagate = True
        finally:
            logging.captureWarnings(False)
    finally:
        logger.removeHandler(handler)


def test_logging_different_levels():
    """真 5 个 level 真按 severity 排序"""
    logger = logging.getLogger("test_levels")
    logger.setLevel(logging.DEBUG)
    assert logging.DEBUG < logging.INFO < logging.WARNING < logging.ERROR < logging.CRITICAL
    assert logging.DEBUG == 10
    assert logging.INFO == 20
    assert logging.WARNING == 30
    assert logging.ERROR == 40
    assert logging.CRITICAL == 50


def test_logging_exception_info():
    """真 exc_info=True 真记 traceback"""
    logger = logging.getLogger("test_exc")
    logger.setLevel(logging.ERROR)
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    logger.addHandler(handler)
    try:
        try:
            raise ValueError("test error")
        except ValueError:
            logger.error("caught error", exc_info=True)
        out = buf.getvalue()
        assert "caught error" in out
        assert "ValueError" in out
        assert "test error" in out
        assert "Traceback" in out
    finally:
        logger.removeHandler(handler)


def test_logging_rotating_real():
    """真 RotatingFileHandler 真轮转 + 真 backup"""
    import logging.handlers
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "rotate.log")
        logger = logging.getLogger("test_rotate")
        logger.setLevel(logging.INFO)
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=100, backupCount=3
        )
        logger.addHandler(handler)
        try:
            # 写 ~50 行 (每行 5 字节 + \n = 6)
            for i in range(50):
                logger.info(f"line{i:04d}")
        finally:
            logger.removeHandler(handler)
            handler.close()

        # 真有 rotate.log
        assert os.path.exists(path)
        # 至少有 1 个 backup
        files = sorted(os.listdir(tmp))
        # rotate.log.1, rotate.log.2, rotate.log.3 也许存在
        log_files = [f for f in files if f.startswith("rotate.log")]
        assert len(log_files) >= 2  # 至少 rotate.log + rotate.log.1


def test_logging_getlogger_same_instance():
    """真 getLogger 同名返同 instance"""
    l1 = logging.getLogger("test_same")
    l2 = logging.getLogger("test_same")
    assert l1 is l2
    # 不同名不同 instance
    l3 = logging.getLogger("test_other")
    assert l1 is not l3
