# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`compile` 方向的底层真实行为测试:真实编译、真实执行与 code object 属性核对。

覆盖模块:compile(内置编译函数)、code 对象属性、exec/eval 真实执行。

真实测试项:
  - `compile(src, "<mod>", "exec")` 真产出 code 对象,co_name 与 co_filename 正确
  - `compile(src, "<ev>", "eval")` 真求值出结果
  - `compile(src, "<one>", "single")` 真只执行一条语句,多条语句真抛 SyntaxError
  - 非法 mode 真抛 ValueError 并说明只支持 exec/eval/single
  - code 对象 co_consts / co_names 真反映源码里的常量与名字
  - 函数 code 对象 co_argcount / co_kwonlyargcount / co_varnames 真对齐函数签名
  - code 对象 co_flags 真标记 VARARGS 与 VARKEYWORDS
  - `exec(code, ns)` 真在给定命名空间里执行并写入变量
  - `exec` 真把运行时异常原样抛出
  - 语法错误真带出 filename 与 lineno
  - `optimize` 等级真剥掉 assert 与 docstring
  - `dont_inherit` 真切断 future 标志的继承
  - `ast.PyCF_ONLY_AST` 真只产出语法树
  - 嵌套函数的 code 对象真出现在 co_consts 里且可被调用
  - `co_lines()` / `co_positions()` 真给出字节码到行列的映射
  - `code.co_code_adaptive`(3.12+)真给出带内联 CACHE 的字节码,首指令仍是 RESUME
"""

import __future__

import ast
import dis
import inspect
import types

import pytest


def _signature(a, b=1, *args, c=2, **kw):
    return a


class TestCompileModes:
    def test_compile_exec_mode_returns_module_code_object(self):
        """`compile("x = 1", "<mod>", "exec")` 真产出 code 对象,co_name='<module>'、co_consts=(1, None)。"""
        code_obj = compile("x = 1", "<mod>", "exec")
        assert isinstance(code_obj, types.CodeType)
        assert code_obj.co_name == "<module>"
        assert code_obj.co_filename == "<mod>"
        assert code_obj.co_consts == (1, None)
        assert code_obj.co_names == ("x",)

    def test_compile_eval_mode_evaluates_expression_to_value(self):
        """`compile("2 ** 10", "<ev>", "eval")` 真求值出 1024,常量折叠后 co_consts 只剩 1024。"""
        code_obj = compile("2 ** 10", "<ev>", "eval")
        assert code_obj.co_name == "<module>"
        assert code_obj.co_filename == "<ev>"
        assert eval(code_obj) == 1024
        assert code_obj.co_consts == (1024,)

    def test_compile_single_mode_runs_one_statement(self):
        """`compile(..., "single")` 真执行一条语句并写入变量;多条语句真抛 SyntaxError。"""
        namespace = {}
        exec(compile("x = 5", "<one>", "single"), namespace)
        assert namespace["x"] == 5
        with pytest.raises(SyntaxError, match="multiple statements found"):
            compile("x = 1\ny = 2\n", "<one>", "single")

    def test_compile_rejects_unknown_mode_with_value_error(self):
        """mode 传 'function' 或 'bogus' 时真抛 ValueError,提示只支持 exec/eval/single。"""
        with pytest.raises(ValueError, match=r"compile\(\) mode must be"):
            compile("pass", "<bad>", "function")
        with pytest.raises(ValueError, match=r"compile\(\) mode must be"):
            compile("pass", "<bad>", "bogus")


class TestCodeObjectAttributes:
    def test_compile_code_object_consts_names_and_filename(self):
        """模块级 code 对象的 co_names 真是 ('os','len','sep','result'),co_consts 是 (0, None)。"""
        code_obj = compile("import os\nresult = len(os.sep)\n", "<ns>", "exec")
        assert code_obj.co_filename == "<ns>"
        assert code_obj.co_names == ("os", "len", "sep", "result")
        assert code_obj.co_consts == (0, None)
        assert code_obj.co_nlocals == 0

    def test_compile_function_code_argcount_and_varnames(self):
        """函数 code 对象真对齐签名:argcount=2、kwonlyargcount=1、varnames 含 args 与 kw。"""
        code_obj = _signature.__code__
        assert code_obj.co_name == "_signature"
        assert code_obj.co_argcount == 2
        assert code_obj.co_posonlyargcount == 0
        assert code_obj.co_kwonlyargcount == 1
        assert code_obj.co_varnames == ("a", "b", "c", "args", "kw")
        assert code_obj.co_nlocals == 5

    def test_compile_code_object_flags_mark_varargs_and_kwargs(self):
        """code 对象 co_flags 真标记 VARARGS/VARKEYWORDS/OPTIMIZED,非生成器则无 GENERATOR 位。"""
        flags = _signature.__code__.co_flags
        assert flags & inspect.CO_VARARGS == inspect.CO_VARARGS
        assert flags & inspect.CO_VARKEYWORDS == inspect.CO_VARKEYWORDS
        assert flags & inspect.CO_OPTIMIZED == inspect.CO_OPTIMIZED
        assert flags & inspect.CO_GENERATOR == 0
        assert dis.COMPILER_FLAG_NAMES[inspect.CO_VARARGS] == "VARARGS"

    def test_compile_code_object_lines_and_positions_mapping(self):
        """`co_lines()` 真给出 (起止 offset, 行号),`co_positions()` 真给出 (行, 列) 映射。"""
        code_obj = compile("x = 1\ny = 2\n", "<map>", "exec")
        lines = list(code_obj.co_lines())
        assert lines[0] == (0, 2, 0)
        assert (2, 4, 1) in lines
        assert (4, 6, 1) in lines
        assert (6, 8, 2) in lines
        positions = list(code_obj.co_positions())
        assert positions[0] == (0, 1, 0, 0)
        assert positions[1] == (1, 1, 4, 5)
        assert (2, 2, 4, 5) in positions

    def test_compile_nested_function_code_appears_in_consts(self):
        """嵌套函数的 code 对象真出现在外层 co_consts 里,co_name='inner',调用返回 7。"""
        code_obj = compile("def inner():\n    return 7\n", "<nest>", "exec")
        nested = [item for item in code_obj.co_consts if isinstance(item, types.CodeType)]
        assert len(nested) == 1
        assert nested[0].co_name == "inner"
        namespace = {}
        exec(code_obj, namespace)
        assert namespace["inner"]() == 7

    @pytest.mark.skipif(
        not hasattr(types.CodeType, "co_code_adaptive"),
        reason="code.co_code_adaptive 需要 Python 3.12+",
    )
    def test_compile_code_object_adaptive_bytes_expose_inline_caches(self):
        """3.12+ 的 `code.co_code_adaptive` 真带内联缓存:首指令是 RESUME,指令流里含 CACHE 且不短于 co_code。"""
        code_obj = compile("x = 1", "<adapt>", "exec")
        adaptive = code_obj.co_code_adaptive
        base = code_obj.co_code
        adaptive_opcodes = {adaptive[index] for index in range(0, len(adaptive), 2)}
        assert adaptive[0] == dis.opmap["RESUME"]
        assert base[0] == dis.opmap["RESUME"]
        assert len(adaptive) >= len(base)
        assert dis.opmap["CACHE"] in adaptive_opcodes


class TestRealExecution:
    def test_exec_runs_compiled_code_in_supplied_namespace(self):
        """`exec(code, ns)` 真在给定命名空间执行,out=20 且内置命名空间被自动注入。"""
        namespace = {"seed": 10}
        exec(compile("out = seed * 2", "<ns>", "exec"), namespace)
        assert namespace["out"] == 20
        assert namespace["seed"] == 10
        assert "__builtins__" in namespace

    def test_exec_propagates_runtime_error_from_compiled_code(self):
        """`exec` 真把编译代码里的运行时异常原样抛出,异常消息为 'boom'。"""
        with pytest.raises(ValueError, match="boom"):
            exec(compile("raise ValueError('boom')", "<err>", "exec"), {})

    def test_compile_syntax_error_reports_filename_and_lineno(self):
        """语法错误真带出 filename='<bad.py>'、lineno=1 与 'invalid syntax' 消息。"""
        with pytest.raises(SyntaxError) as excinfo:
            compile("def (", "<bad.py>", "exec")
        assert excinfo.value.filename == "<bad.py>"
        assert excinfo.value.lineno == 1
        assert excinfo.value.msg == "invalid syntax"


class TestCompileFlags:
    def test_compile_optimize_level_strips_asserts_and_docstrings(self):
        """optimize=0 保留 assert 与 docstring,optimize=1 剥掉 assert,optimize=2 再剥掉 docstring。"""
        source = "def g():\n    '''doc'''\n    assert 1 == 2, 'boom'\n    return 1\n"
        level_zero = {}
        exec(compile(source, "<opt>", "exec", optimize=0), level_zero)
        assert level_zero["g"].__doc__ == "doc"
        with pytest.raises(AssertionError, match="boom"):
            level_zero["g"]()
        level_one = {}
        exec(compile(source, "<opt>", "exec", optimize=1), level_one)
        assert level_one["g"].__doc__ == "doc"
        assert level_one["g"]() == 1
        level_two = {}
        exec(compile(source, "<opt>", "exec", optimize=2), level_two)
        assert level_two["g"].__doc__ is None
        assert level_two["g"]() == 1

    def test_compile_dont_inherit_controls_future_flag_inheritance(self):
        """`dont_inherit=True` 真切断 future 标志继承:继承时带 annotations 标志,切断后为 0。"""
        flag = __future__.annotations.compiler_flag
        future_source = (
            "from __future__ import annotations\n"
            f"inherited = compile('x = 1', '<inner>', 'exec').co_flags & {flag}\n"
            f"isolated = compile('x = 1', '<inner>', 'exec', dont_inherit=True)"
            f".co_flags & {flag}\n"
        )
        namespace = {}
        exec(compile(future_source, "<outer>", "exec"), namespace)
        assert namespace["inherited"] == flag
        assert namespace["isolated"] == 0

    def test_compile_only_ast_flag_returns_syntax_tree(self):
        """`ast.PyCF_ONLY_AST` 真只产出语法树,源码有语法错误时真抛 SyntaxError。"""
        tree = compile("x = 1", "<ast>", "exec", flags=ast.PyCF_ONLY_AST)
        assert isinstance(tree, ast.Module)
        assert isinstance(tree.body[0], ast.Assign)
        assert tree.body[0].targets[0].id == "x"
        with pytest.raises(SyntaxError, match="invalid syntax"):
            compile("x =", "<ast>", "exec", flags=ast.PyCF_ONLY_AST)
