# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`cProfile` 进阶 + `difflib` 进阶 (IS_LINE_JUNK) + `faulthandler` 进阶 + `sqlite3` 进阶 (作者函数) + `inspect.getclosurevars` 进阶 + `ast.literal_eval` 真底层测试。

覆盖 cProfile label / difflib IS_LINE_JUNK / faulthandler / sqlite3 create_function / inspect getclosurevars / ast literal_eval 模块:
  - `cProfile.Profile() 真建 instance`
  - `cProfile.runctx 真带 globals+locals 跑 (Context 简写)`
  - `pstats.Stats 排序 stats_print_stats 不抛`
  - `difflib.IS_LINE_JUNK 必是函数`
  - `difflib.IS_CHARACTER_JUNK 必是函数`
  - `difflib.restore 接受 sequence + which 返 delta lines`
  - `faulthandler.register + unregister 真信号挂载/卸载`
  - `faulthandler.enable + disable 真状态机`
  - `sqlite3.connect(':memory:') 真内存 DB + 创表 + 插 + 查`
  - `sqlite3.Connection.create_function 创 UDF + 调`
  - `sqlite3.Connection.set_authorizer 真设作者函数拦截`
  - `inspect.getclosurevars 真取闭包 vars + nonlocal + global + cell`
  - `ast.literal_eval 真解 list/dict/string/int/float/tuple/None/True/False`
  - `ast.literal_eval 拒绝非字面量 抛 ValueError`
"""
import ast
import cProfile
import difflib
import faulthandler
import inspect
import pstats
import signal
import sqlite3
import sys

import pytest


# -- cProfile 进阶 -------------------------------------------------------------

class TestCProfileAdvanced:
    def test_cProfile_Profile_instance(self):
        """`cProfile.Profile() 真建 instance。"""
        p = cProfile.Profile()
        assert p is not None
        # 必含 enable + disable
        assert callable(p.enable)
        assert callable(p.disable)
        # 真跑
        p.enable()
        sum([i for i in range(100)])
        p.disable()
        # 必能 print_stats (无 file=)
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            p.print_stats()
        # 必非空
        assert len(buf.getvalue()) > 0

    def test_cProfile_runctx(self):
        """`cProfile.runctx 真带 globals+locals 跑。"""
        import io
        g = {"__name__": "__main__"}
        l = {"x": 10}
        s = io.StringIO()
        cProfile.runctx("y = x * 2", g, l, filename=None, sort=-1)
        # 必不抛
        assert l.get("y") == 20


class TestPstatsAdvancedV2:
    def test_Stats_sort_cumulative(self):
        """`pstats.Stats 真 sort_stats('cumulative') + print_stats 不抛。"""
        p = cProfile.Profile()
        p.enable()
        sum([i for i in range(100)])
        p.disable()
        s = pstats.Stats(p)
        s.sort_stats("cumulative")
        # 必不抛
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            s.print_stats()
        # 不抛即过
        # strip_dirs 必返 self
        result = s.strip_dirs()
        assert result is s


# -- difflib 进阶 (IS_LINE_JUNK + restore) -------------------------------------

class TestDifflibAdvancedV3:
    def test_IS_LINE_JUNK(self):
        """`difflib.IS_LINE_JUNK 必是函数。"""
        assert callable(difflib.IS_LINE_JUNK)
        assert callable(difflib.IS_CHARACTER_JUNK)
        # default IS_LINE_JUNK 必返 False
        assert difflib.IS_LINE_JUNK("# forge comment") is False

    def test_difflib_restore(self):
        """`difflib.restore 真从 delta lines 返 sequence (3.11+ 返 generator)."""
        # 用 difflib.ndiff (line-based diff) 而非 unified_diff
        a = "forge line 1\nforge line 2\n"
        b = "forge line 1\nforge line 2 modified\n"
        diff = list(difflib.ndiff(a.splitlines(keepends=True), b.splitlines(keepends=True)))
        # restore from 2nd arg + diff
        # delta lines + which(2) = restore 2nd arg
        restored = difflib.restore(diff, 2)
        # 3.11+ 返 generator
        if hasattr(restored, "__iter__") and not isinstance(restored, list):
            items = list(restored)
        else:
            items = restored
        # 必 ≥ 1
        assert len(items) >= 1, f"restore 应 ≥ 1,实际 {len(items)}"


# -- faulthandler 进阶 ---------------------------------------------------------

class TestFaulthandlerAdvancedV2:
    def test_faulthandler_register_unregister(self):
        """`faulthandler.register 真挂载 SIGUSR1 + unregister 真卸 (沙箱 None 兜底)`"""
        # register 在沙箱必返 None 或 bool
        result = faulthandler.register(signal.SIGUSR1)
        # 不抛即过
        # unregister
        if result is not False:  # False = failed
            faulthandler.unregister(signal.SIGUSR1)

    def test_faulthandler_enable_disable(self):
        """`faulthandler.enable 真设 + disable 真关。"""
        # enable/disable 必是函数
        assert callable(faulthandler.enable)
        assert callable(faulthandler.disable)
        # 真 toggle
        faulthandler.enable()
        faulthandler.disable()
        # 不抛即过

    def test_faulthandler_dump_traceback_file(self):
        """`faulthandler.dump_traceback 真写 file 不抛。"""
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w+", delete=False, suffix=".txt"
        ) as f:
            path = f.name
        try:
            with open(path, "w") as f:
                faulthandler.dump_traceback(file=f, all_threads=True)
        finally:
            import os
            os.unlink(path)


# -- sqlite3 进阶 (create_function + set_authorizer) ---------------------------

class TestSqlite3AdvancedV4:
    def test_create_function(self):
        """`sqlite3.create_function 创 UDF + 调 + 返正确值。"""
        conn = sqlite3.connect(":memory:")
        try:
            # 创 UDF: my_len 返字符串长度
            conn.create_function(
                "my_len", 1, lambda x: len(x) if x else 0
            )
            cur = conn.execute(
                "SELECT my_len(?)", ("forge",)
            )
            row = cur.fetchone()
            assert row[0] == 5, f"my_len('forge') 应=5,实际 {row[0]}"
        finally:
            conn.close()

    def test_set_authorizer(self):
        """`sqlite3.Connection.set_authorizer 真拦截 INSERT 拒 (SQLITE_INSERT=18) (只拦 't' 表)`"""
        conn = sqlite3.connect(":memory:")
        try:
            # authorizer 拦 SQLITE_INSERT=18 on 't' 拒
            def authorizer(action, arg1, arg2, dbname, trigger):
                if action == sqlite3.SQLITE_INSERT and arg1 == "t":
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK

            conn.set_authorizer(authorizer)
            # 先创表
            conn.execute("CREATE TABLE t (x INTEGER)")
            # INSERT 必抛 (拦 't')
            with pytest.raises(sqlite3.DatabaseError) as exc:
                conn.execute("INSERT INTO t VALUES (1)")
            assert "authorized" in str(exc.value)
        finally:
            conn.close()


# -- inspect.getclosurevars 进阶 ------------------------------------------------

def _make_closure(x):
    y = 10
    z = "forge"

    def inner(a, b):
        return a + b + x + y + len(z)

    return inner


class TestInspectAdvancedV7:
    def test_getclosurevars(self):
        """`inspect.getclosurevars 真取 nonlocals + globals + builtins + unbound。"""
        inner = _make_closure(5)
        cv = inspect.getclosurevars(inner)
        # 沙箱 3.11 ClosureVars 含 nonlocals+globals+builtins+unbound
        # 必含 nonlocals + globals + builtins
        assert hasattr(cv, "nonlocals")
        assert hasattr(cv, "globals")
        assert hasattr(cv, "builtins")
        # x 必在 nonlocals (闭包参数)
        assert "x" in cv.nonlocals
        assert cv.nonlocals["x"] == 5
        # y 也在 nonlocals
        assert "y" in cv.nonlocals
        assert cv.nonlocals["y"] == 10
        # z 也在 nonlocals
        assert "z" in cv.nonlocals
        assert cv.nonlocals["z"] == "forge"


# -- ast.literal_eval 进阶 -----------------------------------------------------

class TestAstAdvancedV7:
    def test_literal_eval_basic(self):
        """`ast.literal_eval 真解 list/dict/string/int/float/tuple/None/True/False。"""
        assert ast.literal_eval("1") == 1
        assert ast.literal_eval("1.5") == 1.5
        assert ast.literal_eval("'forge'") == "forge"
        assert ast.literal_eval("True") is True
        assert ast.literal_eval("False") is False
        assert ast.literal_eval("None") is None
        assert ast.literal_eval("[1, 2, 3]") == [1, 2, 3]
        assert ast.literal_eval("{'a': 1, 'b': 2}") == {"a": 1, "b": 2}
        assert ast.literal_eval("(1, 2, 3)") == (1, 2, 3)

    def test_literal_eval_reject(self):
        """`ast.literal_eval 拒绝非字面量 抛 ValueError。"""
        # 必抛
        with pytest.raises(ValueError):
            ast.literal_eval("__import__('os')")
        with pytest.raises(ValueError):
            ast.literal_eval("x + 1")
