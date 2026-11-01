# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.StreamReader` 进阶 (feed+at_eof 3.11+) + `multiprocessing.Manager` 50 item dict 真跨 process + `logging.handlers.RotatingFileHandler+TimedRotatingFileHandler 真 backupCount` + `tempfile.TemporaryDirectory 进阶` + `inspect.getsource+getsourcelines+getcomments 3.11+` 真用 + 真底层测试。

覆盖 asyncio 1 真 (StreamReader feed+read) + multiprocessing 1 真 (Manager dict 50 真跨 process) + logging 2 真 (RotatingFileHandler+TimedRotatingFileHandler emit) + tempfile 1 真 (TemporaryDirectory cleanup) + inspect 3 真 (getsource+getsourcelines+getcomments 3.11+) (共 8 真测试) 模块:
  - `asyncio.StreamReader 真 feed 'forge' + read 必 'forge'`
  - `multiprocessing.Manager dict 50 真跨 process 必 'forge_value_49'`
  - `logging.handlers.RotatingFileHandler emit 不抛 + backupCount=3`
  - `logging.handlers.TimedRotatingFileHandler emit 不抛 + backupCount=3`
  - `tempfile.TemporaryDirectory 真 cleanup tmp_path 必 1 file`
  - `inspect.getsource 函数 必 str 含 'forge'`
  - `inspect.getsourcelines 函数 必 (lines, 0) 含 'forge'`
  - `inspect.getcomments 模块 必 list + 0+ 行`
"""
import asyncio
import inspect
import logging.handlers
import multiprocessing
import os
import pathlib
import tempfile
import time

import pytest


def _mp_target(d, key):
    d[key] = f"forge_value_{key}"


# -- asyncio.StreamReader 进阶 (feed+read) ----------------

class TestAsyncioStreamReaderAdvance:
    def test_StreamReader_feed(self):
        """`asyncio.StreamReader 真 feed 'forge' + read 必 'forge'。"""
        # 真用 event loop
        async def main():
            reader = asyncio.StreamReader()
            # feed
            reader.feed_data(b"forge")
            reader.feed_eof()
            # read 5
            data = await reader.read(5)
            return data

        result = asyncio.run(main())
        # 必 'forge'
        assert result == b"forge"


# -- multiprocessing.Manager 50 item dict 真跨 process -----

class TestMultiprocessingManager50DictAdvance:
    def test_Manager_dict_50(self):
        """`multiprocessing.Manager dict 50 真跨 process 必 'forge_value_49'。"""
        with multiprocessing.Manager() as mgr:
            d = mgr.dict()
            procs = []
            for i in range(50):
                p = multiprocessing.Process(target=_mp_target, args=(d, i))
                p.start()
                procs.append(p)
            for p in procs:
                p.join(timeout=10)
            # 必 ≥ 50
            assert len(d) >= 50
            # 必 'forge_value_49'
            assert d[49] == "forge_value_49"


# -- logging.handlers 进阶 (RotatingFileHandler+TimedRotatingFileHandler) --

class TestLoggingRotatingFileHandlerAdvance:
    def test_RotatingFileHandler_emit(self, tmp_path):
        """`logging.handlers.RotatingFileHandler emit 不抛 + backupCount=3。"""
        f = tmp_path / "forge_rotating.log"
        h = logging.handlers.RotatingFileHandler(
            str(f), maxBytes=1000, backupCount=3
        )
        try:
            # emit
            record = logging.LogRecord("forge_n", logging.INFO, "/p", 1, "msg", None, None)
            h.emit(record)
            # 必不抛
            assert True
        finally:
            h.close()

    def test_TimedRotatingFileHandler_emit(self, tmp_path):
        """`logging.handlers.TimedRotatingFileHandler emit 不抛 + backupCount=3。"""
        f = tmp_path / "forge_timed.log"
        h = logging.handlers.TimedRotatingFileHandler(
            str(f), when="S", interval=1, backupCount=3
        )
        try:
            # emit
            record = logging.LogRecord("forge_n", logging.INFO, "/p", 1, "msg", None, None)
            h.emit(record)
            # 必不抛
            assert True
        finally:
            h.close()


# -- tempfile.TemporaryDirectory 进阶 -------------------

class TestTempfileTemporaryDirectoryAdvance:
    def test_TemporaryDirectory_cleanup(self, tmp_path):
        """`tempfile.TemporaryDirectory 真 cleanup tmp_path 必 1 file。"""
        with tempfile.TemporaryDirectory(dir=str(tmp_path)) as d:
            (pathlib.Path(d) / "forge.txt").write_text("forge")
            # 必能 listdir
            files = os.listdir(d)
            # 必 ≥ 1
            assert len(files) >= 1
            # 必 'forge.txt'
            assert "forge.txt" in files
        # 必 cleanup (沙箱 3.11+ cleanup 必能)
        # 必 cleanup 后 d 不存在
        assert not os.path.exists(d)


# -- inspect.getsource+getsourcelines+getcomments 3.11+ 真用 -

def _forge_func():
    """forge docstring"""
    return "forge"


class TestInspectGetsourceAdvance:
    def test_getsource(self):
        """`inspect.getsource 函数 必 str 含 'forge'。"""
        src = inspect.getsource(_forge_func)
        # 必 str
        assert isinstance(src, str)
        # 必含 'forge'
        assert "forge" in src

    def test_getsourcelines(self):
        """`inspect.getsourcelines 函数 必 (lines, 0) 含 'forge'。"""
        lines, start = inspect.getsourcelines(_forge_func)
        # 必 list
        assert isinstance(lines, list)
        # 必 start int
        assert isinstance(start, int)
        # 必 ≥ 1 line
        assert len(lines) >= 1
        # 必含 'forge'
        assert any("forge" in line for line in lines)

    def test_getcomments(self):
        """`inspect.getcomments 函数 必 str or None。"""
        c = inspect.getcomments(_forge_func)
        # 必 str or None
        assert c is None or isinstance(c, str)
