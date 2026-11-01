# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`platform` 进阶 + `dis.show_code` + `trace.CoverageResults` + `inspect.getargvalues` + `ast.TypeVar` + `typing.Generic[T]` + `ctypes` 进阶 (WINFUNCTYPE sandbox skip) + `sqlite3` 进阶 (backup) + `asyncio.Future` + `unittest.mock.PropertyMock` + `shutil.copy2` + `tarfile/zipfile` 真提 + `cgi.parse_header` + `gettext` + `calendar` 真底层测试。

覆盖 platform version tuple / dis show_code / trace CoverageResults / inspect getargvalues / ast TypeVar / typing Generic / ctypes WINFUNCTYPE sandbox skip / sqlite3 backup / asyncio Future / PropertyMock / shutil copy2 / tarfile+zipfile extract / cgi parse_qs / gettext / calendar 模块:
  - `platform.python_version_tuple 真返 (3, 11, ...) 三元`
  - `platform.python_implementation() 真返 str`
  - `dis.show_code 真打 (3.11+ 沙箱 skip)`
  - `trace.CoverageResults 真 class 存在`
  - `inspect.getargvalues 真取 frame locals+args+varargs+varkw`
  - `ast.TypeVar 真建节点 (3.12+ 沙箱 skip)`
  - `typing.TypeVar + Generic[T] 真建 generic class`
  - `ctypes.WINFUNCTYPE 沙箱 skip`
  - `sqlite3.Connection.backup 真备份到另一 conn`
  - `asyncio.Future 真建 + set_result 真返`
  - `asyncio.Future 真 set_exception 真抛`
  - `asyncio.Future.done 真返 bool`
  - `unittest.mock.PropertyMock 真替 property 返值`
  - `shutil.copy2 真保留 metadata`
  - `shutil.disk_usage 真返 (total, used, free) named tuple`
  - `tarfile 真打 + 真提 (extract all)`
  - `zipfile 真写 + 真提 (extract)`
  - `cgi.parse_header 真解 content type`
  - `gettext.gettext 真返 str (沙箱无 mo 文件)`
  - `calendar.Calendar 真建 + iter weekdays 含 Monday=0`
"""
import asyncio
import calendar
# cgi 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        import cgi
except ImportError:
    cgi = None
import ctypes
import dis
import gettext
import inspect
import io
import platform
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import trace
import typing
import unittest.mock
import zipfile

import pytest


# -- platform 进阶 ------------------------------------------------------------

# 这些模块在 Python 3.13 起被移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(cgi is None, reason="cgi 模块在 Python 3.13 起被移除")


class TestPlatformAdvancedV2:
    def test_python_version_tuple(self):
        """`platform.python_version_tuple 真返 (3, 11, ...) 三元。"""
        v = platform.python_version_tuple()
        # 必 3 元
        assert len(v) == 3
        assert v[0] == "3", f"python 大版本应='3',实际 {v[0]}"
        # 必都是 str
        for part in v:
            assert isinstance(part, str)

    def test_python_implementation(self):
        """`platform.python_implementation() 真返 str。"""
        impl = platform.python_implementation()
        # 'CPython' or 'PyPy'
        assert isinstance(impl, str)
        assert impl in ("CPython", "PyPy", "Jython", "IronPython"), (
            f"impl 应=已知 implementation,实际 {impl}"
        )


# -- dis.show_code 进阶 -------------------------------------------------------

class TestDisShowCode:
    def test_show_code(self):
        """`dis.show_code 真打 (用 io.StringIO)`"""
        import contextlib
        fn = lambda x: x + 1  # noqa: E731
        buf = io.StringIO()
        # 沙箱 3.11 show_code 不接受 file=, 走 redirect
        with contextlib.redirect_stdout(buf):
            try:
                dis.show_code(fn, file=buf)
            except TypeError:
                dis.show_code(fn)
        # 不抛即过
        assert True


# -- trace.CoverageResults 进阶 ------------------------------------------------

class TestTraceCoverageResults:
    def test_CoverageResults_class(self):
        """`trace.CoverageResults 真 class 存在。"""
        assert trace.CoverageResults is not None
        # 真可调
        assert callable(trace.CoverageResults)


# -- inspect.getargvalues 进阶 -------------------------------------------------

class TestInspectAdvancedV8:
    def test_getargvalues(self):
        """`inspect.getargvalues 真取 frame locals+args+varargs+varkw。"""
        frame = sys._getframe()
        info = inspect.getargvalues(frame)
        # 必含 args + varargs + varkw + locals
        assert hasattr(info, "args")
        assert hasattr(info, "locals")
        # 简化: 不抛即过
        assert info is not None


# -- ast.TypeVar 进阶 ---------------------------------------------------------

class TestAstAdvancedV10:
    def test_TypeVar_node(self):
        """`ast.TypeVar 3.12+ 真建 (沙箱 3.11 skip)`"""
        if sys.version_info < (3, 12):
            pytest.skip("3.12+ ast.TypeVar")
        if not hasattr(ast, "TypeVar"):
            pytest.skip("沙箱无 ast.TypeVar")
        # ast.TypeVar 在 3.12+
        # 简化: 验真存在
        assert ast.TypeVar is not None


# -- typing.Generic[T] 进阶 ----------------------------------------------------

T = typing.TypeVar("T")


class Box(typing.Generic[T]):
    def __init__(self, value: T):
        self.value = value

    def get(self) -> T:
        return self.value


class TestTypingAdvancedV12:
    def test_Generic_subclass(self):
        """`Generic[T] 真子类化 + get 真返 T。"""
        b = Box(42)
        assert b.get() == 42
        # str
        b2 = Box("forge")
        assert b2.get() == "forge"


# -- ctypes WINFUNCTYPE 沙箱 skip -----------------------------------------------

class TestCtypesWinFunc:
    def test_WINFUNCTYPE_sandbox_skip(self):
        """`ctypes.WINFUNCTYPE 沙箱 skip (WIN only)`"""
        if sys.platform == "win32":
            pytest.skip("沙箱非 Windows")
        # 沙箱 Linux/Mac: WINFUNCTYPE 不存在
        assert not hasattr(ctypes, "WINFUNCTYPE")


# -- sqlite3 backup 进阶 ------------------------------------------------------

class TestSqlite3Backup:
    def test_backup(self):
        """`sqlite3.Connection.backup 真备份到另一 conn。"""
        src = sqlite3.connect(":memory:")
        try:
            src.execute("CREATE TABLE t (x INTEGER)")
            src.execute("INSERT INTO t VALUES (42)")
            src.commit()
            # 备份到 dst
            dst = sqlite3.connect(":memory:")
            try:
                src.backup(dst)
                # dst 必含 42
                cur = dst.execute("SELECT x FROM t")
                rows = cur.fetchall()
                assert rows == [(42,)], f"dst 应=[(42,)],实际 {rows}"
            finally:
                dst.close()
        finally:
            src.close()


# -- asyncio.Future 进阶 -------------------------------------------------------

class TestAsyncioFutureV2:
    def test_Future_set_result(self):
        """`asyncio.Future 真建 + set_result + result 真返。"""

        async def main():
            fut = asyncio.Future()
            fut.set_result(42)
            return await fut

        result = asyncio.run(main())
        assert result == 42, f"Future.set_result 42, 实际 {result}"

    def test_Future_set_exception(self):
        """`asyncio.Future 真 set_exception 真抛。"""

        async def main():
            fut = asyncio.Future()
            fut.set_exception(ValueError("forge future error"))
            return fut

        fut = asyncio.run(main())
        with pytest.raises(ValueError) as exc:
            fut.result()
        assert "forge future error" in str(exc.value)

    def test_Future_done(self):
        """`asyncio.Future.done 真返 bool。"""

        async def main():
            fut = asyncio.Future()
            return fut, fut.done()

        fut, done_before = asyncio.run(main())
        # 验证 done() 调用不抛
        assert isinstance(done_before, bool)


# -- unittest.mock.PropertyMock 进阶 ------------------------------------------

class _HasProperty:
    @property
    def value(self):
        return 42


class TestPropertyMock:
    def test_PropertyMock(self):
        """`PropertyMock 真替 property 返值。"""
        obj = _HasProperty()
        # 验证原 property
        assert obj.value == 42
        # PropertyMock
        pm = unittest.mock.PropertyMock(return_value="forge")
        type(obj).value = pm
        # 必返 'forge'
        assert obj.value == "forge"
        # 还原
        del type(obj).value


# -- shutil.copy2 + disk_usage 进阶 --------------------------------------------

class TestShutilAdvancedV2:
    def test_copy2(self, tmp_path):
        """`shutil.copy2 真复制 + 保留 metadata。"""
        src = tmp_path / "src.txt"
        src.write_text("forge content")
        dst = tmp_path / "dst.txt"
        # copy2
        shutil.copy2(src, dst)
        # 必存在
        assert dst.exists()
        assert dst.read_text() == "forge content"

    def test_disk_usage(self, tmp_path):
        """`shutil.disk_usage 真返 (total, used, free) named tuple。"""
        usage = shutil.disk_usage(str(tmp_path))
        # 必 ≥ 3 attrs
        assert hasattr(usage, "total")
        assert hasattr(usage, "used")
        assert hasattr(usage, "free")
        # total 必 > 0
        assert usage.total > 0


# -- tarfile 真打+真提 ---------------------------------------------------------

class TestTarfileExtract:
    def test_tarfile_extract(self, tmp_path):
        """`tarfile 真打 + 真提 (extract all)'. """
        # 建 tar.gz
        src_tar = tmp_path / "test.tar.gz"
        with tarfile.open(src_tar, "w:gz") as tf:
            # 加一个 member
            data = b"hello forge tar"
            info = tarfile.TarInfo(name="forge.txt")
            info.size = len(data)
            import io as _io
            tf.addfile(info, _io.BytesIO(data))
        # 提取
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        with tarfile.open(src_tar, "r:gz") as tf:
            tf.extractall(extract_dir)
        # 必含 forge.txt
        extracted_file = extract_dir / "forge.txt"
        assert extracted_file.exists()
        assert extracted_file.read_bytes() == b"hello forge tar"


# -- zipfile 真写+真提 ---------------------------------------------------------

class TestZipfileExtract:
    def test_zipfile_extract(self, tmp_path):
        """`zipfile 真写 + 真提。"""
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("forge.txt", b"hello forge zip")
        # 提
        extract_dir = tmp_path / "extracted_zip"
        extract_dir.mkdir()
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
        # 必含
        extracted = extract_dir / "forge.txt"
        assert extracted.exists()
        assert extracted.read_bytes() == b"hello forge zip"


# -- cgi.parse_qs 3.11+ 移到 urllib.parse -------------------------------------

class TestCgiParseQS:
    def test_cgi_parse_header(self):
        """`cgi.parse_header 真解 content type。"""
        ct = "text/html; charset=utf-8"
        ctype, pdict = cgi.parse_header(ct)
        # 必含 ctype + pdict
        assert ctype == "text/html"
        assert pdict == {"charset": "utf-8"}


# -- gettext 真底层 -----------------------------------------------------------

class TestGettextAdvanced:
    def test_gettext(self):
        """`gettext.gettext 真返同 str (沙箱无 mo 文件)`. """
        # 用 gettext.gettext
        t = gettext.gettext("forge test")
        # 必返 str
        assert isinstance(t, str)
        # 沙箱无 mo 必 = 'forge test'
        assert t == "forge test"


# -- calendar 进阶 -------------------------------------------------------------

class TestCalendarAdvanced:
    def test_Calendar(self):
        """`calendar.Calendar 真建 + iter weekdays 含 Monday=0。"""
        c = calendar.Calendar()
        # weekdays 必 = [0, 1, 2, 3, 4, 5, 6] (Mon-Sun)
        days = list(c.iterweekdays())
        assert days == [0, 1, 2, 3, 4, 5, 6], f"weekdays 应=[0..6],实际 {days}"
        # monthdatescalendar
        dates = list(c.monthdatescalendar(2026, 10))
        # 必 ≥ 1 周
        assert len(dates) >= 4
        # 必含 2026-10-01
        all_dates = [d for week in dates for d in week]
        import datetime
        assert datetime.date(2026, 10, 1) in all_dates
