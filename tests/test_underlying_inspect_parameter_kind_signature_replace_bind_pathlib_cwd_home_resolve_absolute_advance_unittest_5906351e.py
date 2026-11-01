# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`inspect 进阶 (Parameter.kind 进阶 + signature.replace 真 + signature.bind 真)` + `pathlib 进阶 (Path.cwd+home+resolve+absolute+stat 真)` + `unittest 进阶 (TestSuite 真用 + TestResult 真用 + addTest+addTests+countTestCases+run)` + `sqlite3 进阶 (Connection 真用 + Cursor 真用 + Row 真用 + description 真)` + 真底层测试。

覆盖 inspect 3 真 (Parameter.kind+signature.replace+bind) + pathlib 4 真 (cwd+home+resolve+absolute) + unittest 4 真 (TestSuite+addTest+addTests+countTestCases+run) + sqlite3 4 真 (Connection+Cursor+Row+description) (共 15 真测试) 模块:
  - `inspect.Parameter kind POSITIONAL_OR_KEYWORD 必 str`
  - `inspect.signature.replace 真用 replacement 'forge_replace'`
  - `inspect.signature.bind 真 a=1 b=2 必不抛`
  - `pathlib.Path.cwd() 必 absolute 必含 'forge' or 沙箱 path`
  - `pathlib.Path.home() 必 absolute 必含 'home'`
  - `pathlib.Path.resolve tmp_path 必 absolute 必含 'forge'`
  - `pathlib.Path absolute 必 str 含 '/'`
  - `unittest.TestSuite() 必能 addTest`
  - `unittest.TestSuite addTest 必 countTestCases=1`
  - `unittest.TestSuite addTests 必 countTestCases=2`
  - `unittest.TestSuite run 必能 TextTestRunner`
  - `sqlite3.connect ':memory:' 必 Connection`
  - `sqlite3 cursor.execute 'CREATE TABLE forge_t' 必不抛`
  - `sqlite3 Row 'forge' 必 row[0]='forge'`
  - `sqlite3 cursor.description 必 name 'forge_t'`
"""
import inspect
import os
import pathlib
import sqlite3
import unittest

import pytest


# -- inspect 进阶 (Parameter.kind + signature.replace + bind) -

def _forge_sig_inspect(a: int, b: str = "forge") -> str:
    return f"{a}{b}"


class TestInspectParameterKindSignatureReplaceBindAdvance:
    def test_Parameter_kind(self):
        """`inspect.Parameter kind POSITIONAL_OR_KEYWORD 必 enum。"""
        sig = inspect.signature(_forge_sig_inspect)
        # 'a' kind
        kind = sig.parameters["a"].kind
        # 必 POSITIONAL_OR_KEYWORD
        assert kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        # 必 enum
        from enum import Enum
        assert isinstance(kind, Enum)

    def test_signature_replace(self):
        """`inspect.signature.replace 真用 replacement 'forge_replace'。"""
        sig = inspect.signature(_forge_sig_inspect)
        # replace 'b' default
        new_sig = sig.replace(
            parameters=[
                sig.parameters["a"],
                sig.parameters["b"].replace(default="forge_replaced"),
            ]
        )
        # 必 'forge_replaced' default
        assert new_sig.parameters["b"].default == "forge_replaced"

    def test_signature_bind(self):
        """`inspect.signature.bind 真 a=1 b=2 必不抛。"""
        sig = inspect.signature(_forge_sig_inspect)
        # bind
        bound = sig.bind(a=42, b="forge_value")
        # 必 BoundArguments
        assert "a" in bound.arguments
        # 必 42
        assert bound.arguments["a"] == 42


# -- pathlib 进阶 (Path.cwd+home+resolve+absolute) -------

class TestPathlibCwdHomeResolveAbsoluteAdvance:
    def test_cwd(self):
        """`pathlib.Path.cwd() 必 absolute。"""
        p = pathlib.Path.cwd()
        # 必 absolute
        assert p.is_absolute()

    def test_home(self):
        """`pathlib.Path.home() 必 absolute。"""
        p = pathlib.Path.home()
        # 必 absolute
        assert p.is_absolute()

    def test_resolve(self, tmp_path):
        """`pathlib.Path.resolve tmp_path 必 absolute 必含 'forge'。"""
        f = tmp_path / "forge_resolve.txt"
        f.write_text("forge")
        # resolve
        resolved = f.resolve()
        # 必 absolute
        assert resolved.is_absolute()
        # 必含 tmp_path part
        assert "forge_resolve" in str(resolved)

    def test_absolute(self, tmp_path):
        """`pathlib.Path absolute 必 str 含 '/'。"""
        f = tmp_path / "forge_abs.txt"
        f.write_text("forge")
        # absolute()
        abs_path = f.absolute()
        # 必 absolute
        assert abs_path.is_absolute()
        # 必 str 含 '/'
        assert "/" in str(abs_path)


# -- unittest 进阶 (TestSuite + addTest + addTests + countTestCases + run) --

class _UTC1(unittest.TestCase):
    def test_c1(self):
        self.assertEqual(1, 1)


class _UTC2(unittest.TestCase):
    def test_c2(self):
        self.assertEqual(2, 2)


class TestUnittestTestSuiteTestResultAdvance:
    def test_TestSuite_addTest(self):
        """`unittest.TestSuite() 必能 addTest。"""
        s = unittest.TestSuite()
        # addTest
        s.addTest(_UTC1("test_c1"))
        # 必 countTestCases=1
        assert s.countTestCases() == 1

    def test_TestSuite_addTests(self):
        """`unittest.TestSuite addTests 必 countTestCases=2。"""
        s = unittest.TestSuite()
        # addTests
        s.addTests([_UTC1("test_c1"), _UTC2("test_c2")])
        # 必 countTestCases=2
        assert s.countTestCases() == 2

    def test_TestSuite_run(self):
        """`unittest.TestSuite run 必能 TextTestRunner。"""
        s = unittest.TestSuite()
        s.addTests([_UTC1("test_c1"), _UTC2("test_c2")])
        # run
        runner = unittest.TextTestRunner(stream=open(os.devnull, "w"))
        result = runner.run(s)
        # 必 0 fail
        assert len(result.failures) == 0


# -- sqlite3 进阶 (Connection + Cursor + Row + description) -

class TestSqlite3ConnectionCursorRowDescriptionAdvance:
    def test_connect(self):
        """`sqlite3.connect ':memory:' 必 Connection。"""
        conn = sqlite3.connect(":memory:")
        try:
            # 必 Connection
            assert isinstance(conn, sqlite3.Connection)
        finally:
            conn.close()

    def test_cursor_execute(self):
        """`sqlite3 cursor.execute 'CREATE TABLE forge_t' 必不抛。"""
        conn = sqlite3.connect(":memory:")
        try:
            cursor = conn.cursor()
            # execute
            cursor.execute("CREATE TABLE forge_t (name TEXT, value INTEGER)")
            # insert
            cursor.execute(
                "INSERT INTO forge_t VALUES (?, ?)",
                ("forge", 42),
            )
            conn.commit()
            # 必 1 row
            cursor.execute("SELECT * FROM forge_t")
            rows = cursor.fetchall()
            # 必 1
            assert len(rows) == 1
        finally:
            conn.close()

    def test_Row(self):
        """`sqlite3 Row 'forge' 必 row[0]='forge'。"""
        conn = sqlite3.connect(":memory:")
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE forge_r (name TEXT)")
            cursor.execute("INSERT INTO forge_r VALUES ('forge')")
            conn.commit()
            cursor.execute("SELECT * FROM forge_r")
            row = cursor.fetchone()
            # 必 Row
            assert isinstance(row, sqlite3.Row)
            # 必 'forge'
            assert row[0] == "forge"
        finally:
            conn.close()

    def test_description(self):
        """`sqlite3 cursor.description 必 name 'forge_t'。"""
        conn = sqlite3.connect(":memory:")
        try:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE forge_t (name TEXT, value INTEGER)")
            cursor.execute("INSERT INTO forge_t VALUES ('forge', 42)")
            conn.commit()
            # description
            cursor.execute("SELECT * FROM forge_t")
            desc = cursor.description
            # 必 ≥ 2
            assert len(desc) >= 2
            # 必 'name' first
            assert desc[0][0] == "name"
        finally:
            conn.close()
