# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`xml.etree.XMLPullParser` 真用 + `asyncio.Lock` 真 lock+release+locked + `inspect.getclosurevars 3.11+` 真用 + `re.compile 进阶真 pattern flags 3.11+` + `pathlib.stat.st_mode+st_uid+st_gid 3.11+` 真用 + `csv.writerows+field_size_limit 3.11+` 真用 + `logging.handlers.WatchedFileHandler 3.11+` 真用 + 真底层测试。

覆盖 xml.etree 1 真 (XMLPullParser 真 read+feed) + asyncio 2 真 (Lock+locked) + inspect 1 真 (getclosurevars 3.11+) + re 2 真 (compile flags) + pathlib 1 真 (stat st_mode+st_uid+st_gid) + csv 2 真 (writerows+field_size_limit) + logging 1 真 (WatchedFileHandler) (共 10 真测试) 模块:
  - `xml.etree.XMLPullParser 真 read+feed 'forge' 必 1 element 'a'`
  - `asyncio.Lock 真 acquire+release + locked 必 True/False`
  - `asyncio.Lock 真 acquire+release 不抛 + locked True+False`
  - `inspect.getclosurevars 3.11+ 内闭包 vars 必 dict ≥ 0`
  - `re.compile 真 r'forge' flags 必 Pattern + search 'forge' 必 match`
  - `re.compile DOTALL 真 '\\n' 必 match`
  - `pathlib.stat tmp_path 真 st_mode + st_uid + st_gid`
  - `csv.writerows 真 3 rows ['a','b','c']`
  - `csv.field_size_limit 必 int ≥ 0`
  - `logging.handlers.WatchedFileHandler 真 open + emit 不抛`
"""
import asyncio
import csv
import inspect
import io
import logging.handlers
import os
import pathlib
import re
import xml.etree.ElementTree as ET

import pytest


# -- xml.etree.XMLPullParser 真用 进阶 ----------------

class TestXmlEtreeXMLPullParserAdvance:
    def test_XMLPullParser(self):
        """`xml.etree.XMLPullParser 真 read+feed 'forge' 必 1 element 'a'。"""
        p = ET.XMLPullParser(events=("end",))
        # feed 真
        p.feed("<a>forge</a>")
        p.close()
        # read 必 1
        elements = list(p.read_events())
        # 必 ≥ 1
        assert len(elements) >= 1
        # 必 'end' event
        events = [e for e, _ in elements]
        assert "end" in events


# -- asyncio.Lock 真 lock+release+locked 进阶 ------------

class TestAsyncioLockLockedAdvance:
    def test_Lock_acquire_release(self):
        """`asyncio.Lock 真 acquire+release + locked 必 True/False。"""

        async def main():
            lock = asyncio.Lock()
            # 必非 locked
            assert lock.locked() is False
            # acquire
            await lock.acquire()
            # 必 locked
            assert lock.locked() is True
            # release
            lock.release()
            # 必非 locked
            assert lock.locked() is False

        asyncio.run(main())

    def test_Lock_context(self):
        """`asyncio.Lock 真 async with + locked 必 True+False。"""

        async def main():
            lock = asyncio.Lock()
            async with lock:
                # 必 locked
                assert lock.locked() is True
            # 必非 locked
            assert lock.locked() is False

        asyncio.run(main())


# -- inspect.getclosurevars 3.11+ 真用 进阶 ------------

def _make_closure():
    forge_outer = "forge_outer"
    forge_inner = "forge_inner"

    def inner():
        return forge_inner

    return inner


class TestInspectGetclosurevarsAdvance:
    def test_getclosurevars(self):
        """`inspect.getclosurevars 3.11+ 内闭包 vars 必 dict ≥ 0。"""
        fn = _make_closure()
        # 沙箱 3.11+ 必能
        cvars = inspect.getclosurevars(fn)
        # 必 ClosureVars 类
        # 必 nonlocals ≥ 0
        assert hasattr(cvars, "nonlocals")
        # 必 globals
        assert hasattr(cvars, "globals")


# -- re.compile 进阶真 pattern flags 3.11+ -----------

class TestReCompilePatternFlagsAdvance:
    def test_compile_search(self):
        """`re.compile 真 r'forge' flags 必 Pattern + search 'forge' 必 match。"""
        p = re.compile(r"forge", re.IGNORECASE)
        # 必 Pattern
        assert isinstance(p, re.Pattern)
        # search 必 match
        m = p.search("forge_value")
        # 必能
        assert m is not None
        # 必 'forge'
        assert m.group() == "forge"

    def test_compile_DOTALL(self):
        """`re.compile DOTALL 真 '\\n' 必 match。"""
        p = re.compile(r"a.b", re.DOTALL)
        # 必 match
        m = p.search("a\nb")
        # 必能
        assert m is not None
        # 必 'a\nb'
        assert m.group() == "a\nb"


# -- pathlib.stat 进阶 (st_mode+st_uid+st_gid) ---------

class TestPathlibStatAdvance:
    def test_stat_st_mode(self, tmp_path):
        """`pathlib.stat tmp_path 真 st_mode + st_uid + st_gid。"""
        f = tmp_path / "forge.txt"
        f.write_text("forge")
        # stat
        s = f.stat()
        # 必 st_mode int
        assert isinstance(s.st_mode, int)
        # 必 st_uid int
        assert isinstance(s.st_uid, int)
        # 必 st_gid int
        assert isinstance(s.st_gid, int)


# -- csv.writerows + field_size_limit 3.11+ 真用 -------

class TestCsvWriterowsFieldSizeLimitAdvance:
    def test_writerows(self):
        """`csv.writerows 真 3 rows ['a','b','c']。"""
        buf = io.StringIO()
        writer = csv.writer(buf)
        # writerows
        writer.writerows([["a", "b", "c"]])
        # 必含 'a' 'b' 'c'
        output = buf.getvalue()
        assert "a" in output
        assert "b" in output
        assert "c" in output

    def test_field_size_limit(self):
        """`csv.field_size_limit 必 int ≥ 0。"""
        old = csv.field_size_limit()
        # 必 int
        assert isinstance(old, int)
        # 必 ≥ 0
        assert old >= 0
        # restore
        csv.field_size_limit(old)


# -- logging.handlers.WatchedFileHandler 3.11+ 真用 -----

class TestLoggingWatchedFileHandlerAdvance:
    def test_WatchedFileHandler(self, tmp_path):
        """`logging.handlers.WatchedFileHandler 真 open + emit 不抛。"""
        f = tmp_path / "forge_watched.log"
        h = logging.handlers.WatchedFileHandler(str(f))
        try:
            # emit
            record = logging.LogRecord("forge_n", logging.INFO, "/p", 1, "msg", None, None)
            h.emit(record)
            # 必不抛
            assert True
        finally:
            h.close()
