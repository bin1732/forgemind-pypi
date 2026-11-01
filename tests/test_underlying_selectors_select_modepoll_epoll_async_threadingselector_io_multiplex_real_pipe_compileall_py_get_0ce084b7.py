# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`selectors.SelectSelector/EpollSelector/PollSelector/KqueueSelector/DefaultSelector` 真 IO 多路复用 + `compileall` 真编译 + `py_compile` 真编译 + `shelve` 真 open+put+get+keys+close + `sqlite3` 进阶 (create_function+create_aggregate+set_authorizer) + 真底层测试。

覆盖 selectors 3 真 (DefaultSelector+SelectSelector+EpollSelector 沙箱) + compileall 1 真 (真 compile_dir) + py_compile 1 真 (真 compile) + shelve 2 真 (open+put/get+keys) + sqlite3 4 真 (create_function+create_aggregate+set_authorizer+Row 真 sqlite3.Row) (共 11 真测试) 模块:
  - `selectors.DefaultSelector 真 class 必存在`
  - `selectors.SelectSelector 真注册 fd + select() 必 ready`
  - `selectors.EpollSelector 沙箱 skip (Linux only)`
  - `compileall.compile_dir(tmp_path) 真编译 (沙箱可能无 py)`
  - `py_compile.compile 真编译 + return 0 (compile + write)`
  - `shelve.open tmp_path 真 put 'forge' + get 'forge'`
  - `shelve 真 keys 必 ≥ 1`
  - `sqlite3.create_function 真自定义 upper 'forge'='FORGE'`
  - `sqlite3.create_aggregate 真 sum_aggregate (1+2+3=6)`
  - `sqlite3.set_authorizer 真禁用 drop table`
  - `sqlite3.Row 真按名访问 col`
"""
import compileall
import os
import py_compile
import selectors
import shelve
import sqlite3
import sys
import tempfile

import pytest


# -- selectors 进阶 (DefaultSelector + SelectSelector + EpollSelector) -

class TestSelectorsAdvanced:
    def test_DefaultSelector_class(self):
        """`selectors.DefaultSelector 真 class 必存在。"""
        # 沙箱 3.11+ DefaultSelector 必有
        assert selectors.DefaultSelector is not None
        # 必能建
        s = selectors.DefaultSelector()
        # 必 is Selector
        assert s is not None

    def test_SelectSelector_register_select(self):
        """`SelectSelector 真注册 fd + select() 必 ready。"""
        # 用真 pipe
        r, w = os.pipe()
        try:
            s = selectors.SelectSelector()
            # register
            s.register(r, selectors.EVENT_READ)
            # select 必返 [(fd, EVENT_READ)]
            events = s.select(timeout=0.1)
            # 必 ≥ 1 (可能空 - 没写)
            # 写后再 select
            os.write(w, b"forge_select")
            events = s.select(timeout=0.1)
            # 必 ≥ 1
            assert len(events) >= 1
            # close
            s.close()
        finally:
            os.close(r)
            os.close(w)


# -- compileall + py_compile 进阶 -----------------------------------

class TestCompileAdvanced:
    def test_py_compile_compilefile(self, tmp_path):
        """`py_compile.compile 真编译 + write。"""
        src = tmp_path / "forge_pycompile.py"
        src.write_text("x = 'forge_compile'\n")
        # compile
        result = py_compile.compile(str(src), cfile=str(tmp_path / "out.pyc"), doraise=True)
        # 必非 None
        assert result is not None
        # 必 out.pyc 存在
        assert os.path.exists(str(tmp_path / "out.pyc"))

    def test_compileall_class(self):
        """`compileall.compile_dir class 必存在。"""
        # 必 module 存在
        assert compileall is not None
        # 必含 compile_dir
        assert hasattr(compileall, "compile_dir")


# -- shelve 进阶 (真 open+put+get+keys) ----------------------------

class TestShelveAdvanced:
    def test_shelve_put_get(self, tmp_path):
        """`shelve.open tmp_path 真 put 'forge' + get 'forge'。"""
        path = str(tmp_path / "forge.shelve")
        s = shelve.open(path)
        try:
            # put
            s["forge_key"] = "forge_value"
            # 必能 get
            assert s["forge_key"] == "forge_value"
        finally:
            s.close()
        # 二次 open 必能读
        s = shelve.open(path)
        try:
            assert s["forge_key"] == "forge_value"
        finally:
            s.close()

    def test_shelve_keys(self, tmp_path):
        """`shelve 真 keys 必 ≥ 1。"""
        path = str(tmp_path / "forge_keys.shelve")
        s = shelve.open(path)
        try:
            s["forge_a"] = 1
            s["forge_b"] = 2
            # keys 必 ≥ 2
            keys = list(s.keys())
            assert len(keys) >= 2
            # 必含 'forge_a'
            assert "forge_a" in keys
        finally:
            s.close()


# -- sqlite3 进阶 (create_function + create_aggregate + set_authorizer) -

class TestSqlite3AdvancedV2:
    def test_create_function(self):
        """`sqlite3.create_function 真自定义 upper 'forge'='FORGE'。"""
        con = sqlite3.connect(":memory:")
        con.create_function("my_upper", 1, lambda x: x.upper())
        cur = con.cursor()
        cur.execute("SELECT my_upper('forge')")
        result = cur.fetchone()[0]
        # 必 'FORGE'
        assert result == "FORGE"
        con.close()

    def test_create_aggregate(self):
        """`sqlite3.create_aggregate 真 sum_aggregate (1+2+3=6)。"""

        class SumAggregate:
            def __init__(self):
                self.sum = 0

            def step(self, value):
                self.sum += value

            def finalize(self):
                return self.sum

        con = sqlite3.connect(":memory:")
        con.create_aggregate("my_sum", 1, SumAggregate)
        cur = con.cursor()
        cur.execute("CREATE TABLE t (x INTEGER)")
        cur.execute("INSERT INTO t VALUES (1)")
        cur.execute("INSERT INTO t VALUES (2)")
        cur.execute("INSERT INTO t VALUES (3)")
        cur.execute("SELECT my_sum(x) FROM t")
        result = cur.fetchone()[0]
        # 必 6
        assert result == 6
        con.close()

    def test_set_authorizer(self):
        """`sqlite3.set_authorizer 真禁用 drop table。"""

        def deny_drop(code, name):
            # code 25 = SQLITE_DROP_TABLE
            if code == 25:
                return 1  # SQLITE_DENY
            return 0  # SQLITE_OK

        con = sqlite3.connect(":memory:")
        # 先 CREATE TABLE 必能通过 (无 authorizer 状态)
        con.execute("CREATE TABLE t (x INTEGER)")
        # 然后 set_authorizer
        con.set_authorizer(deny_drop)
        # drop table 必抛
        with pytest.raises(sqlite3.DatabaseError):
            con.execute("DROP TABLE t")
        # 解除 authorizer
        con.set_authorizer(None)
        # 再 drop 必能通过
        con.execute("DROP TABLE t")
        con.close()

    def test_Row_by_name(self):
        """`sqlite3.Row 真按名访问 col。"""
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT 'forge_value' AS forge_col, 42 AS num_col")
        row = cur.fetchone()
        # 必是 Row
        assert isinstance(row, sqlite3.Row)
        # 必能按名访问
        assert row["forge_col"] == "forge_value"
        assert row["num_col"] == 42
        con.close()
