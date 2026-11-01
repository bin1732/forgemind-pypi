# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 inspect 真 (Parameter 真 name + annotation + default) + 真 tokenize 真 (f-string 真 / raw string) + 真 ast 真 (Compare 进阶) + 真 compile 真 (mode 多种 exec/eval/single) + 真 code 真 (co_lnotab) 进阶.
全 stdlib, 零模拟。
"""
import inspect
import tokenize
import ast
import io
import pytest


# ======================== inspect 进阶 ========================
def test_inspect_Parameter_full():
    """真 Parameter 真 full 属性"""
    def f(a: int = 10, *args: str, kw: float = 1.0, **kwargs: int) -> bool:
        return True

    sig = inspect.signature(f)
    p_a = sig.parameters["a"]
    # name
    assert p_a.name == "a"
    # annotation
    assert p_a.annotation is int
    # default
    assert p_a.default == 10
    # empty
    assert p_a.empty is inspect.Parameter.empty
    # kind
    assert p_a.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    # return
    assert sig.return_annotation is bool


def test_inspect_signature_replace():
    """真 signature 真 replace"""
    def f(a, b=10, *, c=20):
        pass

    sig = inspect.signature(f)
    # 改 b default
    new_sig = sig.replace(parameters=[
        sig.parameters["a"].replace(),
        sig.parameters["b"].replace(default=99),
        sig.parameters["c"].replace(),
    ])
    # 新 sig
    new_b = new_sig.parameters["b"]
    assert new_b.default == 99


# ======================== tokenize 真 f-string ========================
def test_tokenize_fstring():
    """真 f-string 真 tokenize"""
    code = 'f"hello {name} world {age}"'
    tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    # fstring
    fstring = [t for t in tokens if t.type == tokenize.STRING]
    assert len(fstring) >= 1
    # f-prefix
    assert any('f"' in t.string for t in fstring)


def test_tokenize_raw_string():
    """真 raw string 真"""
    code = r'r"C:\path\to\file"'
    tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    raw = [t for t in tokens if t.type == tokenize.STRING]
    assert len(raw) >= 1
    # r prefix
    assert any('r"' in t.string for t in raw)


# ======================== ast 进阶 ========================
def test_ast_Compare_operators():
    """真 ast 真 Compare 节点"""
    code = "x == 1"
    tree = ast.parse(code, mode="eval")
    # 是 Compare
    assert isinstance(tree.body, ast.Compare)
    # ops = [Eq()]
    assert len(tree.body.ops) == 1
    # Eq
    assert isinstance(tree.body.ops[0], ast.Eq)
    # left x
    assert isinstance(tree.body.left, ast.Name)
    assert tree.body.left.id == "x"
    # right 1
    assert tree.body.comparators[0].value == 1


def test_ast_IfExp_ternary():
    """真 ast 真 IfExp 三元"""
    code = "a if x > 0 else b"
    tree = ast.parse(code, mode="eval")
    assert isinstance(tree.body, ast.IfExp)
    # test
    assert isinstance(tree.body.test, ast.Compare)


def test_ast_function_def_attrs():
    """真 ast 真 FunctionDef attributes"""
    code = """
@decorator
def f(x, y=10):
    '''docstring'''
    return x + y
"""
    tree = ast.parse(code)
    func = tree.body[0]
    # name
    assert func.name == "f"
    # decorator_list
    assert len(func.decorator_list) == 1
    # args
    assert func.args.args[0].arg == "x"
    assert func.args.args[1].arg == "y"
    assert func.args.args[1].annotation is None  # 没 type
    # docstring
    docstring = ast.get_docstring(func)
    assert docstring == "docstring"


# ======================== compile 真 ========================
def test_compile_exec():
    """真 compile exec 真"""
    code = compile("x = 1; y = 2", "<test>", "exec")
    ns = {}
    exec(code, ns)
    assert ns["x"] == 1
    assert ns["y"] == 2


def test_compile_eval():
    """真 compile eval 真"""
    expr = compile("1 + 2 * 3", "<test>", "eval")
    result = eval(expr)
    assert result == 7


def test_compile_single():
    """真 compile single 真 (3.11+)"""
    if hasattr(compile, "__call__"):
        # Python 3.11+ new single
        code = "x = 1; y = 2"  # 但 single 模式只第一行
        # single 模式: 1 个 expression
        single = compile("x = 1", "<test>", "single")
        ns = {}
        exec(single, ns)
        assert ns["x"] == 1


# ======================== code 真 ========================
def test_code_firstlineno():
    """真 co_firstlineno"""
    def f():
        return 42

    assert f.__code__.co_firstlineno > 0


def test_code_filename():
    """真 co_filename"""
    def f():
        return 42

    # 必是 .py
    assert f.__code__.co_filename.endswith(".py")
    assert "test_underlying" in f.__code__.co_filename
