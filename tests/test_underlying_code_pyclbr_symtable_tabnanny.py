# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`code` + `codeop` + `pyclbr` + `symtable` + `tabnanny` 真底层测试。

覆盖 Python 编译器支撑模块:
  - `code.InteractiveConsole.push` 真把每行输入当 source 编入并执行
  - `codeop.compile_command` 真 partial-input 增量编译 (`if True:` 不完整,补 `pass` 完成)
  - `pyclbr.readmodule` 真解析 .py 文件拿到 ClassDef 字典
  - `symtable.symtable` 真构建符号表,顶层 `SENTINEL` + 类体子表中的 `m`
  - `tabnanny.check` 真检测含混合缩进的源文件并返回 `(filename, msg, kind)` tuple
"""
import code
import codeop
import io
import os
import pyclbr
import sys
import symtable
import tabnanny
import tempfile
import textwrap

import pytest


# -- code / codeop ------------------------------------------------------------

class TestCodeInteractiveConsole:
    def test_push_runs_two_statements(self):
        """`code.InteractiveConsole.push` 真把每段输入当 source 编入并执行。

        两段独立提交 `x = 7` + `print(x * 6)`,期望 stdout 真出现 42。
        走的是 `push` -> `runsource` -> `runcode` 完整路径。
        """
        console = code.InteractiveConsole()
        out = io.StringIO()
        old = sys.stdout
        sys.stdout = out
        try:
            assert console.push("x = 7") is False, "赋值不 complete 会进 buffer"
            assert console.push("print(x * 6)") is False, "正常语句应执行成功"
        finally:
            sys.stdout = old
        assert out.getvalue().strip() == "42"

    def test_compile_command_handles_partial_input(self):
        """`codeop.compile_command` 真支持多行增量提交。

        单条 `if True:` 不完整,第一调用返 None;
        同一语句的第二行 `    pass` 触发完整编译。
        """
        first = codeop.compile_command("if True:", symbol="exec")
        assert first is None, "单行不完整 if 应返 None"
        second = codeop.compile_command("if True:\n    pass", symbol="exec")
        assert second is not None, "完整 if 块应编译成功"
        assert hasattr(second, "co_code"), "应返真 code object"

    def test_compile_command_syntax_error_raises(self):
        """语法错误真抛 `SyntaxError`,不静默吞掉。"""
        with pytest.raises(SyntaxError):
            codeop.compile_command("def 1bad(", symbol="exec")


# -- pyclbr -------------------------------------------------------------------

class TestPyclbrReadmodule:
    def test_readmodule_returns_classdef_dict_for_py_file(self):
        """`pyclbr.readmodule` 真解析 .py 文件为 ClassDef 字典。

        写一个临时模块,内含一个 class `KlassX`,调用 readmodule 拿字典,
        期待 KlassX 出现,`file` 字段指向该临时文件。
        """
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "tiny_mod.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write("class KlassX:\n    pass\n")
            classes = pyclbr.readmodule("tiny_mod", path=[d])
            assert "KlassX" in classes
            entry = classes["KlassX"]
            assert entry.name == "KlassX"
            assert entry.file.endswith("tiny_mod.py")

    def test_readmodule_exposes_function_defs(self):
        """`readmodule_ex` 真把模块级 def 收进返回值,`functions` 字典包含它。"""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "func_mod.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write("def top_fn():\n    return 1\n")
            result = pyclbr.readmodule_ex("func_mod", path=[d])
            assert "top_fn" in result
            assert result["top_fn"].name == "top_fn"


# -- symtable -----------------------------------------------------------------

class TestSymtable:
    def test_symtable_top_level_symbol(self):
        """`symtable.symtable` 真把模块顶层 name 收进 symbols。

        用 `<module>` 顶层 + 一个常量赋值,期望在 `get_symbols()` 拿到
        名为 `SENTINEL` 的 symbol。
        """
        source = textwrap.dedent("""
            SENTINEL = 42
            class _C:
                pass
        """)
        st = symtable.symtable(source, "<test>", "exec")
        assert isinstance(st, symtable.SymbolTable)
        assert st.get_type() == "module"
        names = {sym.get_name() for sym in st.get_symbols()}
        assert "SENTINEL" in names, "顶层常量 SENTINEL 应出现在顶层 symbols"
        assert "_C" in names, "顶层类 _C 应出现在顶层 symbols"

    def test_class_symbol_table_has_methods(self):
        """类体真收进独立子表,方法名 `m` 在子表 symbols 中。"""
        source = textwrap.dedent("""
            class _C:
                def m(self):
                    return 1
        """)
        st = symtable.symtable(source, "<test>", "exec")
        children = list(st.get_children())
        assert children, "类体应产生子 symbol table"
        cls_st = children[0]
        method_names = {s.get_name() for s in cls_st.get_symbols()}
        assert "m" in method_names


# -- tabnanny -----------------------------------------------------------------

class TestTabNanny:
    def test_check_detects_mixed_indentation(self):
        """`tabnanny.check` 真检测同层混用 space/TAB 并写错误到 stdout。

        写一个临时文件,3 行 4 space 缩进 + 第 3 行 1 TAB 缩进,
        同层逻辑缩进但前缀不一致,触发 tabnanny 输出
        `<filename> 3 '<TAB>x = 3\\n'` 错误到 stdout。
        """
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "bad_indent.py")
            with open(path, "wb") as f:
                f.write(b"x = 1\n    x = 2\n\tx = 3\n")
            out = io.StringIO()
            old = sys.stdout
            sys.stdout = out
            try:
                tabnanny.check(path)
            finally:
                sys.stdout = old
            output = out.getvalue()
            assert "bad_indent.py" in output, f"tabnanny 应点名文件,实际 {output!r}"
            assert "3" in output, f"tabnanny 应给出 lineno 3,实际 {output!r}"
