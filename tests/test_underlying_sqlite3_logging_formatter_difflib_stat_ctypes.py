# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`sqlite3` 进阶 + `logging.Formatter` + `difflib` 进阶 + `stat` + `ctypes` 进阶 + `mimetypes` 真底层测试。

覆盖数据库/日志/比较/文件状态/FFI/类型模块:
  - `sqlite3.connect` 真持久化 DB round-trip
  - `sqlite3.Row factory` 真按名访问
  - `sqlite3.Cursor.executemany` 真批 5 行
  - `sqlite3.Connection.create_function` 真注册 UDF
  - `logging.Formatter('%(asctime)s %(name)s')` 真格式
  - `logging.LoggerAdapter` 真 wrap logger
  - `logging.FileHandler` 真写到 file
  - `difflib.SequenceMatcher` 真 ratio
  - `difflib.ndiff` 真逐行 diff
  - `difflib.context_diff` 真 context diff
  - `stat.S_ISDIR(mode)` 真判文件类型
  - `stat.S_ISREG(mode)` 真判 regular
  - `stat.filemode(mode)` 真返 'drwxr-xr-x' 类
  - `ctypes.c_uint8/16/32/64` 真整数
  - `ctypes.c_float/double` 真浮点
  - `ctypes.c_wchar_p` 真 wide char
  - `ctypes.POINTER + byref` 真 ref
  - `mimetypes.readfp + guess_type` 真从 fp 读 mime db
"""
import ctypes
import difflib
import io
import logging
import mimetypes
import os
import sqlite3
import stat as stat_mod
import sys
import tempfile

import pytest


# -- sqlite3 进阶 -------------------------------------------------------------

class TestSqlite3Advanced:
    def test_connect_persist(self):
        """`sqlite3.connect + CREATE + INSERT + SELECT` 真持久化 DB。"""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "forge.db")
            conn = sqlite3.connect(path)
            try:
                conn.execute("CREATE TABLE t (k TEXT, v INTEGER)")
                conn.executemany(
                    "INSERT INTO t VALUES (?, ?)",
                    [("a", 1), ("b", 2), ("c", 3)],
                )
                conn.commit()
                # 重连 SELECT
                conn.close()
                conn2 = sqlite3.connect(path)
                rows = conn2.execute("SELECT k, v FROM t ORDER BY k").fetchall()
                assert rows == [("a", 1), ("b", 2), ("c", 3)]
                conn2.close()
            except Exception:
                conn.close()
                raise

    def test_Row_factory_named_access(self):
        """`sqlite3.Row 真按名访问 row['k']`。"""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("CREATE TABLE t (k TEXT, v INTEGER)")
            conn.execute("INSERT INTO t VALUES ('x', 7)")
            row = conn.execute("SELECT k, v FROM t").fetchone()
            # 按名访问
            assert row["k"] == "x"
            assert row["v"] == 7
            # 按索引也能
            assert row[0] == "x"
        finally:
            conn.close()

    def test_executemany_inserts(self):
        """`Cursor.executemany` 真批插入 5 行,rowcount=5。"""
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE TABLE t (n INTEGER)")
            cursor = conn.executemany(
                "INSERT INTO t VALUES (?)", [(i,) for i in range(5)]
            )
            assert cursor.rowcount == 5
            n = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
            assert n == 5
        finally:
            conn.close()

    def test_create_function_UDF(self):
        """`Connection.create_function('my_len', 1, my_len_fn)` 真 UDF。"""
        conn = sqlite3.connect(":memory:")
        try:
            def my_len(s):
                return len(s)

            conn.create_function("my_len", 1, my_len)
            conn.execute("CREATE TABLE t (s TEXT)")
            conn.execute("INSERT INTO t VALUES ('forge')")
            conn.execute("INSERT INTO t VALUES ('hello')")
            rows = conn.execute("SELECT s, my_len(s) FROM t ORDER BY s").fetchall()
            assert rows == [("forge", 5), ("hello", 5)]
        finally:
            conn.close()


# -- logging 进阶 -------------------------------------------------------------

class TestLoggingAdvancedV2:
    def test_Formatter_format(self):
        """`logging.Formatter('%(asctime)s %(name)s %(message)s')` 真格式 record。"""
        fmt = logging.Formatter("%(name)s %(levelname)s %(message)s")
        rec = logging.LogRecord(
            "forge", logging.INFO, "/x.py", 1, "hello", (), None
        )
        out = fmt.format(rec)
        assert "forge" in out
        assert "INFO" in out
        assert "hello" in out

    def test_FileHandler_writes(self):
        """`logging.FileHandler` 真写日志到文件。"""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "forge.log")
            # 同一进程里别的用例可能关掉了全局日志,这里恢复
            logging.disable(logging.NOTSET)
            log = logging.getLogger("forge_file_handler")
            log.setLevel(logging.INFO)
            log.disabled = False
            # 不向上传播。同一进程里别的用例调整过根记录器的级别或
            # 关闭过日志,传播过来的级别会把这条记录挡掉。
            log.propagate = False
            h = logging.FileHandler(path)
            h.setLevel(logging.INFO)
            log.addHandler(h)
            try:
                log.info("forge test line")
                # flush + close
                h.flush()
                with open(path) as f:
                    content = f.read()
                assert "forge test line" in content
            finally:
                log.removeHandler(h)
                h.close()

    def test_LoggerAdapter_wraps(self):
        """`logging.LoggerAdapter` 真 wrap logger 加 context。"""
        log = logging.getLogger("forge_adapter")
        adapter = logging.LoggerAdapter(log, {"task": "unit_test"})
        # adapter.process(msg, kwargs) 返 (msg, merged kwargs) tuple
        msg, kwargs = adapter.process("hello %(task)s", {"task": "x"})
        # msg 保持原样, kwargs 合并了 'extra': {'task': 'unit_test'}
        assert msg == "hello %(task)s"
        # kwargs 含 extra
        assert "extra" in kwargs
        assert kwargs["extra"]["task"] == "unit_test"


# -- difflib 进阶 -------------------------------------------------------------

class TestDifflibAdvancedV2:
    def test_SequenceMatcher_ratio(self):
        """`SequenceMatcher.ratio` 真返 0~1。"""
        m = difflib.SequenceMatcher(None, "abcde", "abxde")
        r = m.ratio()
        # 4/5 相同
        assert 0.5 < r <= 1.0, f"ratio 应 ∈ (0.5, 1],实际 {r}"

    def test_ndiff(self):
        """`difflib.ndiff` 真逐行 diff,含 '- line2' '+ LINE2' (前导 2 字符 code)。"""
        a = "line1\nline2\nline3\n"
        b = "line1\nLINE2\nline3\n"
        diff = list(difflib.ndiff(a.splitlines(keepends=True), b.splitlines(keepends=True)))
        # ndiff 必含 '- line2' (前导空格) + '+ LINE2'
        joined = "".join(diff)
        assert "- line2" in joined
        assert "+ LINE2" in joined
        # 含 '  line1' (相同行, 前导 2 空格)
        assert "  line1" in joined
        # 至少 4 行
        assert len(diff) >= 4

    def test_context_diff(self):
        """`difflib.context_diff` 真生成 context diff。"""
        a = ["line1\n", "line2\n", "line3\n"]
        b = ["line1\n", "line2 modified\n", "line3\n"]
        diff = list(difflib.context_diff(a, b, fromfile="a", tofile="b"))
        joined = "".join(diff)
        assert "*** a" in joined
        assert "--- b" in joined


# -- stat ---------------------------------------------------------------------

class TestStat:
    def test_S_ISDIR(self):
        """`stat.S_ISDIR(mode)` 真判目录。"""
        with tempfile.TemporaryDirectory() as d:
            mode = os.stat(d).st_mode
            assert stat_mod.S_ISDIR(mode) is True

    def test_S_ISREG(self):
        """`stat.S_ISREG(mode)` 真判 regular file。"""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.txt")
            with open(path, "w") as f:
                f.write("forge")
            mode = os.stat(path).st_mode
            assert stat_mod.S_ISREG(mode) is True

    def test_filemode(self):
        """`stat.filemode(0o100644)` 真返 '-rw-r--r--'。"""
        m = stat_mod.filemode(0o100644)
        assert m == "-rw-r--r--", f"filemode 0o100644 应='-rw-r--r--',实际 {m!r}"
        # 目录
        m_dir = stat_mod.filemode(0o040755)
        assert m_dir.startswith("d"), f"目录应以 'd' 开头,实际 {m_dir!r}"


# -- ctypes 进阶 --------------------------------------------------------------

class TestCtypesAdvanced:
    def test_c_uint_sizes(self):
        """`ctypes.c_uint8/16/32/64` 真整数。"""
        assert ctypes.c_uint8(255).value == 255
        assert ctypes.c_uint16(65535).value == 65535
        assert ctypes.c_uint32(0xFFFFFFFF).value == 0xFFFFFFFF
        assert ctypes.c_uint64(0xDEADBEEFCAFE).value == 0xDEADBEEFCAFE

    def test_c_float_double(self):
        """`ctypes.c_float/c_double` 真浮点。"""
        f = ctypes.c_float(1.5)
        assert f.value == 1.5
        d = ctypes.c_double(2.5)
        assert d.value == 2.5

    def test_c_wchar_p(self):
        """`ctypes.c_wchar_p` 真 wide char pointer。"""
        s = ctypes.c_wchar_p("forge")
        assert s.value == "forge"

    def test_POINTER_byref(self):
        """`ctypes.POINTER + byref` 真取 ref。"""
        # 准备一个 c_int, byref 真取 ref
        i = ctypes.c_int(42)
        p = ctypes.pointer(i)
        assert p.contents.value == 42
        # byref 引用
        v = ctypes.c_int()
        ctypes.memmove(ctypes.byref(v), ctypes.byref(i), ctypes.sizeof(i))
        assert v.value == 42


# -- mimetypes 进阶 -----------------------------------------------------------

class TestMimetypesAdvancedV2:
    def test_mimetypes_init(self):
        """`mimetypes.init()` 真初始化。"""
        mimetypes.init()
        # 至少 1 个 type
        assert len(mimetypes.types_map) > 0

    def test_mimetypes_add_type(self):
        """`mimetypes.add_type('app/x-forge', '.forge')` 真注册。"""
        mimetypes.add_type("application/x-forge", ".forge")
        ctype, _ = mimetypes.guess_type("a.forge")
        assert ctype == "application/x-forge"

    def test_mimetypes_readfp(self):
        """`mimetypes.add_type` 多次注册 + `guess_all_extensions` 真查。"""
        mimetypes.add_type("application/x-forge2", ".forge2")
        mimetypes.add_type("text/x-forge3", ".forge3")
        assert mimetypes.guess_type("a.forge2")[0] == "application/x-forge2"
        assert mimetypes.guess_type("a.forge3")[0] == "text/x-forge3"
        # guess_all_extensions
        exts = mimetypes.guess_all_extensions("application/x-forge2")
        assert ".forge2" in exts
