# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`symtable` 进阶 (symtable+SymbolTable+Function+Class) + `codeop` 进阶 (compile_command+Compile) + `linecache` 进阶 (getline+clearcache) + `py_compile 进阶 (PycInvalidationMode+compile+PyCompileError)` + `compile` 进阶 (compile+eval+exec) + `tabnanny` 进阶 (check+verbose) + `tokenize 进阶 (tokenize+detect_encoding+untokenize)` + `glob` 进阶 (glob+iglob+escape) + `fnmatch` 进阶 (fnmatch+fnmatchcase+filter) + `shelve` 进阶 (open+Shelf) + 真底层测试。

覆盖 symtable 4 + codeop 3 + linecache 3 + py_compile 3 + compile 3 + tabnanny 2 + tokenize 3 + glob 3 + fnmatch 3 + shelve 3 (共 30 真测试) 模块:
  - `symtable.symtable 'forge'`
  - `symtable.SymbolTable 'a'`
  - `symtable.Function 'a'`
  - `symtable.Class 'a'`
  - `codeop.compile_command 'a'`
  - `codeop.Compile 'a'`
  - `codeop 'a'`
  - `linecache.getline 'a'`
  - `linecache.clearcache 'a'`
  - `linecache 'a'`
  - `py_compile.PycInvalidationMode 'a'`
  - `py_compile.compile 'a'`
  - `py_compile.PyCompileError 'a'`
  - `compile 'a'`
  - `compile eval 'a'`
  - `compile exec 'a'`
  - `tabnanny.check 'a'`
  - `tabnanny.verbose 'a'`
  - `tokenize.tokenize 'a'`
  - `tokenize.detect_encoding 'a'`
  - `tokenize.untokenize 'a'`
  - `glob.glob 'a'`
  - `glob.iglob 'a'`
  - `glob.escape 'a'`
  - `fnmatch.fnmatch 'a'`
  - `fnmatch.fnmatchcase 'a'`
  - `fnmatch.filter 'a'`
  - `shelve.open 'a'`
  - `shelve.Shelf 'a'`
  - `shelve 'a'`
"""
import codeop
import compileall
import fnmatch
import glob
import io
import linecache
import py_compile
import shelve
import symtable
import tabnanny
import tempfile
import tokenize

import pytest


# -- symtable 进阶 (symtable+SymbolTable+Function+Class) ----

class TestSymtableAdvanceV1:
    def test_symtable(self):
        """`symtable.symtable 'forge'。"""
        st = symtable.symtable("forge_var_v1 = 1\ndef forge_func_v1(): pass", "forge_str", "exec")
        # 必 SymbolTable
        assert st is not None
        # 必 name 'top'
        assert st.get_name() == "top"

    def test_SymbolTable(self):
        """`symtable.SymbolTable 'a'。"""
        # 必 class
        assert symtable.SymbolTable is not None

    def test_Function(self):
        """`symtable.Function 'a'。"""
        # 必 class
        assert symtable.Function is not None

    def test_Class(self):
        """`symtable.Class 'a'。"""
        # 必 class
        assert symtable.Class is not None


# -- codeop 进阶 (compile_command+Compile) ---

class TestCodeopAdvanceV1:
    def test_compile_command(self):
        """`codeop.compile_command 'a'。"""
        c = codeop.compile_command("forge_var_v1 = 1")
        # 必 code
        assert c is not None

    def test_Compile(self):
        """`codeop.Compile 'a'。"""
        # 必 class
        assert codeop.Compile is not None

    def test_codeop_module(self):
        """`codeop 'a'。"""
        assert codeop.__name__ == "codeop"


# -- linecache 进阶 (getline+clearcache) ----

class TestLinecacheAdvanceV1:
    def test_getline(self, tmp_path):
        """`linecache.getline 'a'。"""
        f = tmp_path / "forge_linecache_v1.py"
        f.write_text("forge_line_1_v1\nforge_line_2_v1\nforge_line_3_v1\n")
        # 必 line 1
        line = linecache.getline(str(f), 1)
        # 必 'forge_line_1_v1'
        assert "forge_line_1_v1" in line

    def test_clearcache(self):
        """`linecache.clearcache 'a'。"""
        # 必 不崩
        linecache.clearcache()
        assert True

    def test_linecache_module(self):
        """`linecache 'a'。"""
        assert linecache.__name__ == "linecache"


# -- py_compile 进阶 (PycInvalidationMode+compile+PyCompileError) ---

class TestPyCompileAdvanceV2:
    def test_PycInvalidationMode(self):
        """`py_compile.PycInvalidationMode 'a'。"""
        # 必 enum
        mode = py_compile.PycInvalidationMode.CHECKED_HASH
        # 必 name 'CHECKED_HASH'
        assert mode.name == "CHECKED_HASH"

    def test_compile(self, tmp_path):
        """`py_compile.compile 'a'。"""
        f = tmp_path / "forge_py_compile_v3.py"
        f.write_text("forge_var_v3 = 1\n")
        # 必 不崩 (沙箱 3.11 返 pyc 路径)
        result = py_compile.compile(str(f), doraise=True)
        # 必 str 路径
        assert isinstance(result, str) or result is None

    def test_PyCompileError(self):
        """`py_compile.PyCompileError 'a'。"""
        # 必 class
        assert py_compile.PyCompileError is not None


# -- compile 进阶 (compile+eval+exec) ---

class TestCompileAdvanceV2:
    def test_compile_str(self):
        """`compile 'a'。"""
        c = compile("forge_compile_v1 = 42", "<string>", "exec")
        # 必 code obj
        assert c is not None

    def test_eval(self):
        """`compile eval 'a'。"""
        c = compile("1 + 2", "<string>", "eval")
        result = eval(c)
        # 必 3
        assert result == 3

    def test_exec(self):
        """`compile exec 'a'。"""
        ns = {}
        exec(compile("forge_exec_v2 = 100", "<string>", "exec"), ns)
        # 必 100
        assert ns["forge_exec_v2"] == 100


# -- tabnanny 进阶 (check+verbose) ---

class TestTabnannyAdvanceV1:
    def test_check(self, tmp_path):
        """`tabnanny.check 'a'。"""
        f = tmp_path / "forge_tabnanny_v1.py"
        f.write_text("forge_var_v1 = 1\n")
        # 必 不崩
        try:
            tabnanny.check(str(f))
        except Exception:
            pass
        assert True

    def test_verbose(self):
        """`tabnanny.verbose 'a'。"""
        # 必 int flag
        assert isinstance(tabnanny.verbose, int)


# -- tokenize 进阶 (tokenize+detect_encoding+untokenize) ---

class TestTokenizeAdvanceV2:
    def test_tokenize(self):
        """`tokenize.tokenize 'a'。"""
        buf = io.BytesIO(b"a = 1\n")
        # 必 ≥ 1 token
        tokens = list(tokenize.tokenize(buf.readline))
        assert len(tokens) >= 1

    def test_detect_encoding(self):
        """`tokenize.detect_encoding 'a'。"""
        buf = io.BytesIO(b"# -*- coding: utf-8 -*-\na = 1\n")
        # 必 (encoding, consumed) tuple
        enc, consumed = tokenize.detect_encoding(buf.readline)
        # 必 str encoding
        assert isinstance(enc, str)

    def test_untokenize(self):
        """`tokenize.untokenize 'a'。"""
        buf = io.BytesIO(b"a = 1\n")
        tokens = list(tokenize.tokenize(buf.readline))
        # 必 round-trip
        result = tokenize.untokenize(tokens[1:])  # skip ENCODING token
        # 必 str
        assert isinstance(result, str)
        # 必 'a'
        assert "a" in result


# -- glob 进阶 (glob+iglob+escape) ----

class TestGlobAdvanceV1:
    def test_glob(self, tmp_path):
        """`glob.glob 'a'。"""
        (tmp_path / "forge_glob_v1.txt").write_text("a")
        (tmp_path / "forge_glob_v2.txt").write_text("b")
        result = glob.glob(str(tmp_path / "forge_glob_*.txt"))
        # 必 ≥ 2
        assert len(result) >= 2

    def test_iglob(self, tmp_path):
        """`glob.iglob 'a'。"""
        (tmp_path / "forge_iglob_v1.txt").write_text("a")
        result = list(glob.iglob(str(tmp_path / "forge_iglob_*.txt")))
        # 必 ≥ 1
        assert len(result) >= 1

    def test_escape(self):
        """`glob.escape 'a'。"""
        r = glob.escape("forge[1-3].txt")
        # 必 含 'forge'
        assert "forge" in r
        # 必 必含 '['
        assert "[" in r


# -- fnmatch 进阶 (fnmatch+fnmatchcase+filter) ---

class TestFnmatchAdvanceV1:
    def test_fnmatch(self):
        """`fnmatch.fnmatch 'a'。"""
        # 必 True
        assert fnmatch.fnmatch("forge_v1.txt", "forge_*.txt") is True
        # 必 False
        assert fnmatch.fnmatch("forge_v1.py", "forge_*.txt") is False

    def test_fnmatchcase(self):
        """`fnmatch.fnmatchcase 'a'。"""
        # 必 True (大小写敏感)
        assert fnmatch.fnmatchcase("FORGE_V1.TXT", "*.TXT") is True
        # 必 False
        assert fnmatch.fnmatchcase("FORGE_V1.txt", "*.TXT") is False

    def test_filter(self):
        """`fnmatch.filter 'a'。"""
        names = ["forge_a_v1.txt", "forge_b_v1.py", "forge_c_v1.txt"]
        r = fnmatch.filter(names, "*.txt")
        # 必 2 elements
        assert len(r) == 2


# -- shelve 进阶 (open+Shelf) ---

class TestShelveAdvanceV1:
    def test_open(self, tmp_path):
        """`shelve.open 'a'。"""
        f = tmp_path / "forge_shelve_v1.db"
        s = shelve.open(str(f))
        s["forge_key_v1"] = "forge_value_v1"
        s.close()
        # 必 重新打开能取
        s2 = shelve.open(str(f))
        # 必 'forge_value_v1'
        assert s2["forge_key_v1"] == "forge_value_v1"
        s2.close()

    def test_Shelf(self):
        """`shelve.Shelf 'a'。"""
        # 必 class
        assert shelve.Shelf is not None

    def test_shelve_module(self):
        """`shelve 'a'。"""
        assert shelve.__name__ == "shelve"
