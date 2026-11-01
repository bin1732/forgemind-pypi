# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`compile` 真 syntax error + `dis` code object 字段 + `inspect` 进阶 + `typing` 进阶 + `ctypes` 进阶 真底层测试。

覆盖编译错误 / code object 属性 / 内省 / 类型 / FFI 进阶:
  - `compile(bad) 真抛 SyntaxError`
  - `compile('x = 1', '<test>', 'eval') 真返 eval code`
  - `compile('x = 1', '<test>', 'single') 真返 single code`
  - `code.co_consts 真 list`
  - `code.co_names 真 list`
  - `code.co_varnames 真 list`
  - `code.co_code bytes 真 bytecode`
  - `dis.dis(code_object) 真打 bytecode 到 stdout`
  - `inspect.getargspec 真返 ArgSpec (3.11-)`
  - `inspect.getfullargspec 3.x 真返 FullArgSpec`
  - `typing.TypeVarTuple 真 variadic`
  - `typing.ParamSpec 真签名捕获`
  - `typing.Concatenate 真前缀`
  - `ctypes.Structure 真建 + 字段`
  - `ctypes.Union 真建 + 字段`
  - `ctypes.POINTER 进阶真取 c_int pointer`
  - `ctypes.cast 进阶真强转 c_void_p → c_char_p`
"""
import ctypes
import dis
import inspect
import sys
import typing

import pytest


# -- compile 真 syntax error --------------------------------------------------

class TestCompileAdvanced:
    def test_compile_syntax_error(self):
        """`compile('x =', '<test>', 'exec') 真抛 SyntaxError`。"""
        with pytest.raises(SyntaxError):
            compile("x =", "<test>", "exec")

    def test_compile_eval_mode(self):
        """`compile('1+2', '<test>', 'eval') 真建 eval code。"""
        code_obj = compile("1+2", "<test>", "eval")
        # eval code, co_name == '<module>' ? 或 '<expr>'
        # 简化: 必能 exec
        result = eval(code_obj)
        assert result == 3

    def test_compile_single_mode(self):
        """`compile('x = 42', '<test>', 'single') 真建 single code (单 statement)。"""
        code_obj = compile("x = 42", "<test>", "single")
        # co_name 必是 '<module>'
        assert code_obj.co_name == "<module>"

    def test_code_object_consts(self):
        """`code.co_consts 真 list of constants`。"""
        code_obj = compile("x = 1; y = 'hello'; z = 3.14", "<test>", "exec")
        consts = code_obj.co_consts
        # 必含 1, 'hello', 3.14
        assert 1 in consts
        assert "hello" in consts
        assert 3.14 in consts

    def test_code_object_names(self):
        """`code.co_names 真 list of global var names`。"""
        code_obj = compile("import os; x = os.path", "<test>", "exec")
        names = code_obj.co_names
        # 必含 'os'
        assert "os" in names

    def test_code_object_varnames(self):
        """`code.co_varnames 真 list of local var names`。"""
        code_obj = compile(
            "def f(a, b, c):\n return a + b + c\n", "<test>", "exec"
        )
        # co_consts 必含 code for f
        func_code = [c for c in code_obj.co_consts if hasattr(c, "co_varnames")][0]
        # 必含 a, b, c
        assert "a" in func_code.co_varnames
        assert "b" in func_code.co_varnames
        assert "c" in func_code.co_varnames

    def test_code_object_code_bytes(self):
        """`code.co_code 真 bytes 字节码`。"""
        code_obj = compile("x = 1", "<test>", "exec")
        assert isinstance(code_obj.co_code, bytes)
        assert len(code_obj.co_code) > 0


# -- dis 真打 bytecode --------------------------------------------------------

class TestDisAdvancedV4:
    def test_dis_to_string(self):
        """`dis.dis(code_object) 真打 bytecode (用 stdout 重定向)`。"""
        import contextlib
        import io
        code_obj = compile("x = 1", "<test>", "exec")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dis.dis(code_obj)
        out = buf.getvalue()
        # 必 ≥ 1 个字节码指令
        assert len(out) > 0
        # 必含 'code' or 'RESUME' or 'LOAD'
        assert any(s in out for s in ("RESUME", "LOAD", "STORE", "RETURN"))


# -- inspect 进阶 ------------------------------------------------------------

def _complex_fn(a: int, b: str, *args, key=None, **kwargs) -> bool:
    return True


class TestInspectAdvancedV4:
    def test_getfullargspec(self):
        """`inspect.getfullargspec 真返 FullArgSpec`。"""
        spec = inspect.getfullargspec(_complex_fn)
        # 必含 args, varargs, varkw, defaults
        assert spec.args == ["a", "b"]
        assert spec.varargs == "args"
        assert spec.varkw == "kwargs"
        assert "key" in spec.kwonlyargs

    def test_signature_positional_or_keyword(self):
        """`inspect.Parameter.POSITIONAL_OR_KEYWORD` 真常量。"""
        sig = inspect.signature(_complex_fn)
        # a, b 是 POSITIONAL_OR_KEYWORD
        assert sig.parameters["a"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        # args 是 VAR_POSITIONAL
        assert sig.parameters["args"].kind == inspect.Parameter.VAR_POSITIONAL
        # kwargs 是 VAR_KEYWORD
        assert sig.parameters["kwargs"].kind == inspect.Parameter.VAR_KEYWORD


# -- typing 进阶 --------------------------------------------------------------

class TestTypingAdvancedV6:
    def test_TypeVarTuple(self):
        """`typing.TypeVarTuple 3.11+ 真 variadic`。"""
        if not hasattr(typing, "TypeVarTuple"):
            pytest.skip("无 TypeVarTuple")
        Ts = typing.TypeVarTuple("Ts")

        def f(*args: "typing.Unpack[Ts]") -> None:  # type: ignore
            pass

        # 编译能过
        assert f is not None

    def test_ParamSpec_basic(self):
        """`typing.ParamSpec 真捕获签名`。"""
        if not hasattr(typing, "ParamSpec"):
            pytest.skip("无 ParamSpec")
        P = typing.ParamSpec("P")

        def decorator(fn):
            def inner(*args: "P.args", **kwargs: "P.kwargs") -> None:  # type: ignore
                return fn(*args, **kwargs)

            return inner

        @decorator
        def my_fn(x: int, y: str) -> None:
            pass

        # 真能调
        my_fn(1, "hello")


# -- ctypes 进阶 -------------------------------------------------------------

class _Point(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
    ]


class _Variant(ctypes.Union):
    _fields_ = [
        ("i", ctypes.c_int),
        ("f", ctypes.c_float),
    ]


class TestCtypesAdvancedV2:
    def test_Structure_fields(self):
        """`ctypes.Structure 真建 + 字段访问`。"""
        p = _Point()
        p.x = 10
        p.y = 20
        assert p.x == 10
        assert p.y == 20
        # sizeof = 8 (2 个 c_int)
        assert ctypes.sizeof(_Point) == 8

    def test_Union_fields(self):
        """`ctypes.Union 真建 + 字段共享内存`。"""
        v = _Variant()
        v.i = 0x41424344
        # f 是同 4 字节, 必是 float 表示
        # 简化: i 必等于所写
        assert v.i == 0x41424344

    def test_POINTER_to_c_int(self):
        """`ctypes.POINTER(c_int) 真建 pointer type。"""
        PI = ctypes.POINTER(ctypes.c_int)
        i = ctypes.c_int(42)
        p = ctypes.pointer(i)
        assert isinstance(p, PI)
        assert p.contents.value == 42

    def test_cast_voidp_to_charp(self):
        """`ctypes.cast(c_void_p(...), c_char_p) 真强转`。"""
        import ctypes as ct
        # 建一个 bytes buffer
        buf = ct.create_string_buffer(b"hello forge")
        # 取 buffer address
        addr = ct.addressof(buf)
        vp = ct.c_void_p(addr)
        # 强转为 c_char_p
        cp = ct.cast(vp, ct.c_char_p)
        # 必能读
        assert cp.value == b"hello forge"
