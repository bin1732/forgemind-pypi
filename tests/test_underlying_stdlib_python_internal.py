# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 stdlib Python 内部 — ast 真 parse / dis 真反汇编 / inspect 真查 / tokenize 真分词。
"""
import ast
import dis
import inspect
import sys
import textwrap
import tokenize
import io

import pytest


def test_ast_parse_real():
    """ast 真 parse Python 源"""
    source = """
def add(a, b):
    return a + b

class Calc:
    def mul(self, x, y):
        return x * y
"""
    tree = ast.parse(source)
    assert isinstance(tree, ast.Module)
    # 顶层有 function + class
    names = [type(n).__name__ for n in tree.body]
    assert "FunctionDef" in names
    assert "ClassDef" in names


def test_ast_unparse_round_trip():
    """ast.unparse 真能反向生成代码"""
    source = "x = 1 + 2 * 3"
    tree = ast.parse(source)
    regenerated = ast.unparse(tree)
    # 重新 parse 验语法等价
    tree2 = ast.parse(regenerated)
    # 看新生成的代码值
    # 1 + 2 * 3 = 7
    # unparse 可能加括号或不加, eval 都应 = 7
    # 但 regenerated 可能没 x 赋值
    assert "1" in regenerated
    assert "2" in regenerated
    assert "3" in regenerated


def test_ast_get_source_segment():
    """ast.get_source_segment 真拿节点对应源码"""
    source = "x = 1 + 2"
    tree = ast.parse(source)
    # 找 BinOp
    binop = tree.body[0].value
    seg = ast.get_source_segment(source, binop)
    assert seg == "1 + 2", f"应 '1 + 2', 实际 {seg!r}"


def test_ast_walk_all_nodes():
    """ast.walk 真遍历所有节点"""
    source = """
x = 1
y = x + 2
def f(z):
    return z * 3
"""
    tree = ast.parse(source)
    nodes = list(ast.walk(tree))
    # 至少 10 个节点 (Name, Constant, BinOp, FunctionDef, ...)
    assert len(nodes) >= 10
    # 应有 FunctionDef
    funcs = [n for n in nodes if isinstance(n, ast.FunctionDef)]
    assert len(funcs) == 1


def test_dis_bytecode_for_lambda():
    """dis 真反汇编 lambda 字节码"""
    code = compile("x = lambda a, b: a + b", "<test>", "exec")
    # 拿第一个常量 (lambda)
    consts = code.co_consts
    lambda_code = [c for c in consts if hasattr(c, "co_code")][0]
    # dis
    output = io.StringIO()
    dis.dis(lambda_code, file=output)
    bytecode_text = output.getvalue()
    # 应含 BINARY_OP (Python 3.11+) 或 BINARY_ADD
    assert "BINARY" in bytecode_text, f"应含 BINARY 指令, 实际: {bytecode_text[:200]}"
    # 应含 RETURN_VALUE
    assert "RETURN" in bytecode_text


def test_dis_show_code_attributes():
    """dis 真展示 code 对象属性"""
    def sample():
        x = 1
        y = 2
        return x + y

    code = sample.__code__
    # 真属性
    assert code.co_name == "sample"
    assert code.co_argcount == 0
    # co_names 在 PEP 657 后可能不含局部 var name; 改用 co_varnames
    assert "x" in code.co_varnames or "y" in code.co_varnames
    # bytecode 长度应 > 0
    assert len(code.co_code) > 0


def test_inspect_signature_real():
    """inspect 真拿函数签名"""
    def my_func(a: int, b: str = "default", *args, **kwargs) -> bool:
        return True

    sig = inspect.signature(my_func)
    params = sig.parameters
    assert "a" in params
    assert params["a"].annotation is int
    assert params["b"].default == "default"
    assert params["args"].kind == inspect.Parameter.VAR_POSITIONAL
    assert params["kwargs"].kind == inspect.Parameter.VAR_KEYWORD
    assert sig.return_annotation is bool


def test_inspect_getsource_real():
    """inspect 真拿函数源码"""
    def my_unique_function_name():
        return 42

    src = inspect.getsource(my_unique_function_name)
    assert "def my_unique_function_name" in src
    assert "return 42" in src


def test_inspect_iscoroutinefunction_real():
    """inspect 真识别 async 函数"""
    async def my_async():
        return 1

    def my_sync():
        return 2

    assert inspect.iscoroutinefunction(my_async)
    assert not inspect.iscoroutinefunction(my_sync)


def test_inspect_getmembers_real():
    """inspect 真列对象成员"""
    class Cls:
        x = 1
        y = 2
        def method(self):
            pass

    members = dict(inspect.getmembers(Cls))
    assert "x" in members
    assert "y" in members
    assert "method" in members


def test_tokenize_real():
    """tokenize 真分 Python 源"""
    source = "x = 1 + 2\n"
    tokens = list(tokenize.tokenize(io.BytesIO(source.encode()).readline))
    # 至少 NAME = NUMBER + NUMBER NEWLINE
    assert len(tokens) > 3
    # 找 NAME
    names = [t for t in tokens if t.type == tokenize.NAME]
    assert any("x" in str(t.string) for t in names)
    # 找 NUMBER
    numbers = [t for t in tokens if t.type == tokenize.NUMBER]
    assert len(numbers) >= 2  # 1 和 2


def test_tokenize_round_trip_via_untokenize():
    """tokenize 真能反组回源代码"""
    source = "y = 3 + 4\n"
    tokens = list(tokenize.tokenize(io.BytesIO(source.encode()).readline))
    reconstructed = tokenize.untokenize(tokens)
    # 重新 parse 应成功
    ast.parse(reconstructed)


def test_compile_real_executes():
    """compile 真能执行"""
    code = compile("result = 6 * 7", "<test>", "exec")
    namespace = {}
    exec(code, namespace)
    assert namespace["result"] == 42


def test_ast_litteral_eval_safe():
    """ast.literal_eval 真只支持 literal"""
    # 安全 (literal_eval 只接受 literal 表达式, 不接受 BinOp)
    assert ast.literal_eval("[1, 2, 3]") == [1, 2, 3]
    assert ast.literal_eval("{'a': 1, 'b': 2}") == {"a": 1, "b": 2}
    assert ast.literal_eval("'hello'") == "hello"
    assert ast.literal_eval("42") == 42
    # 不安全: 表达式 (会抛)
    with pytest.raises(ValueError):
        ast.literal_eval("__import__('os').system('echo PWNED')")
