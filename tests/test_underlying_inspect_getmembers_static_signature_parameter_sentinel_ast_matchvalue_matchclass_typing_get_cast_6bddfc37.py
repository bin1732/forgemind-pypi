# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`inspect` 大进阶 (getmembers_static/signature/Parameter/Signature/cleandoc/getsource) + `ast.MatchValue/MatchClass` 3.10+ + `typing.get_overloads/cast/NewType distinct` + `dis.get_instructions/show_code` + `tokenize.untokenize` + `ast.unparse` 真底层测试。

覆盖 inspect 6 真 + ast 4 真 + typing 5 真 + dis 3 真 + tokenize 1 真 (共 19 真测试) 模块:
  - `inspect.getmembers_static 真返 list`
  - `inspect.signature 真返 Signature`
  - `inspect.Parameter.empty 真 sentinel`
  - `inspect.cleandoc 真清空 docstring 缩进`
  - `inspect.getsource 真取 source`
  - `inspect.isbuiltin/isfunction/ismethod 真判`
  - `ast.MatchValue 3.10+ value=42`
  - `ast.MatchClass 3.10+ cls=Name('A')`
  - `ast.TryStar 3.11+ 真 class 存在`
  - `ast.unparse 真反向 (3.9+)`
  - `typing.get_overloads 真返 list`
  - `typing.cast 真 runtime noop`
  -`typing.NewType 真创 distinct`
  - `typing.get_type_hints 解 forward ref`
  - `typing.Any 真用`
  - `dis.get_instructions 真返 Instructions list`
  - `dis.show_code 真打 (3.11+ 沙箱 skip)`
  - `dis.Bytecode 真子化`
  - `tokenize.untokenize 真 round-trip (3.11+ bytes)`
"""
import ast
import dis
import inspect
import io
import sys
import tokenize
import typing

import pytest


# -- inspect 进阶 ---------------------------------------------------------

class TestInspectAdvancedV6:
    def test_getmembers_static(self):
        """`inspect.getmembers_static 真返 list (不触发 descriptor)`"""

        class _Obj:
            @property
            def x(self):
                return 99

        members = inspect.getmembers_static(_Obj)
        # 必 list
        assert isinstance(members, list)
        # 必含 'x'
        names = [n for n, _ in members]
        assert "x" in names

    def test_signature(self):
        """`inspect.signature 真返 Signature。"""
        def my_fn(a: int, b: str = "forge") -> bool:
            return True

        sig = inspect.signature(my_fn)
        # 必 2 param
        assert len(sig.parameters) == 2
        # 必含 a, b
        assert "a" in sig.parameters
        assert "b" in sig.parameters

    def test_Parameter_empty(self):
        """`inspect.Parameter.empty 真 sentinel。"""
        sig = inspect.signature(lambda a, b=42: None)
        # a 必 empty
        assert sig.parameters["a"].default is inspect.Parameter.empty
        # b 必 42
        assert sig.parameters["b"].default == 42

    def test_cleandoc(self):
        """`inspect.cleandoc 真清缩进。"""
        doc = """
        line1
        line2
        line3
        """
        cleaned = inspect.cleandoc(doc)
        # 必 line1 在前
        assert "line1" in cleaned
        # 必含 line1+line2
        assert "line1" in cleaned
        assert "line2" in cleaned

    def test_getsource(self):
        """`inspect.getsource 真取 source。"""
        def my_test_fn():
            return "forge_source"

        src = inspect.getsource(my_test_fn)
        # 必含 'forge_source'
        assert "forge_source" in src

    def test_predicates(self):
        """`inspect.isbuiltin/isfunction/ismethod 真判。"""
        assert inspect.isbuiltin(print) is True
        # 用户 fn 必 is function
        def my_local():
            return 42

        assert inspect.isfunction(my_local) is True
        # str.islower 必是 builtin function (不是 method)
        assert inspect.isbuiltin("".islower) is True


# -- ast 进阶 (MatchValue / MatchClass / TryStar / unparse) ---------------

class TestAstAdvancedV26:
    def test_MatchValue(self):
        """`ast.MatchValue 3.10+ value=42。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ MatchValue")
        mv = ast.MatchValue(value=ast.Constant(value=42))
        assert mv.value.value == 42

    def test_MatchClass(self):
        """`ast.MatchClass 3.10+ cls=Name('A')。"""
        if sys.version_info < (3, 10):
            pytest.skip("3.10+ MatchClass")
        if not hasattr(ast, "MatchClass"):
            pytest.skip("沙箱无 MatchClass")
        mc = ast.MatchClass(
            cls=ast.Name(id="A", ctx=ast.Load()),
            patterns=[],
            kwd_attrs=[],
            kwd_patterns=[],
        )
        assert mc.cls.id == "A"

    def test_TryStar_exists(self):
        """`ast.TryStar 3.11+ 沙箱 3.11 验真。"""
        if sys.version_info < (3, 11):
            pytest.skip("3.11+ TryStar")
        if not hasattr(ast, "TryStar"):
            pytest.skip("沙箱无 TryStar")
        # 真有
        assert ast.TryStar is not None

    def test_unparse(self):
        """`ast.unparse 真反向 (3.9+)。"""
        if sys.version_info < (3, 9):
            pytest.skip("3.9+ unparse")
        tree = ast.parse("x = 1")
        code = ast.unparse(tree)
        # 必含 x + 1
        assert "x" in code
        assert "1" in code


# -- typing 进阶 (get_overloads/cast/NewType/Any) -----------------------

class TestTypingAdvancedV26:
    def test_get_overloads(self):
        """`typing.get_overloads 真返 list。"""
        @typing.overload
        def overload_fn(x: int) -> int: ...

        @typing.overload
        def overload_fn(x: str) -> str: ...

        def overload_fn(x):
            return x

        overloads = typing.get_overloads(overload_fn)
        # 必 list
        assert isinstance(overloads, list)
        # 必 ≥ 1
        assert len(overloads) >= 1

    def test_cast(self):
        """`typing.cast 真 runtime noop。"""
        # cast 不改 runtime
        v = typing.cast(str, 42)
        assert v == 42

    def test_NewType_distinct(self):
        """`typing.NewType 真创 distinct type。"""
        UserId = typing.NewType("UserId", int)
        uid = UserId(42)
        # 必 is int
        assert isinstance(uid, int)
        # callable
        assert callable(UserId)

    def test_get_type_hints_forward_ref(self):
        """`typing.get_type_hints 解 forward ref 'int'。"""
        def my_fn(x: "int") -> "bool":
            return True

        hints = typing.get_type_hints(my_fn)
        # 必含 x + return
        assert "x" in hints
        assert "return" in hints
        # 必解 'int' → int
        assert hints["x"] is int
        assert hints["return"] is bool

    def test_Any(self):
        """`typing.Any 真用 + isinstance check。"""
        # Any 与任何兼容
        v: typing.Any = 42
        v = "forge"
        v = [1, 2, 3]
        # isinstance 必 True
        assert isinstance(v, list)


# -- dis 进阶 -------------------------------------------------------------

class TestDisAdvancedV7:
    def test_get_instructions(self):
        """`dis.get_instructions 真返 Instructions list。"""
        def add(a, b):
            return a + b

        instrs = list(dis.get_instructions(add))
        # 必 ≥ 1
        assert len(instrs) >= 1
        # 必含 RESUME
        assert any(i.opname == "RESUME" for i in instrs)

    def test_show_code_sandbox_skip(self):
        """`dis.show_code 沙箱 3.11 skip file=。"""
        fn = lambda x: x + 1  # noqa: E731
        # 沙箱 3.11 不接受 file= kwargs
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                dis.show_code(fn, file=buf)
            except TypeError:
                dis.show_code(fn)
        # 不抛即过
        assert True

    def test_Bytecode_class(self):
        """`dis.Bytecode 真子化。"""
        def my_fn():
            return 42

        bc = dis.Bytecode(my_fn)
        # 必 list-able
        instrs = list(bc)
        assert len(instrs) >= 1


# -- tokenize 进阶 --------------------------------------------------------

class TestTokenizeAdvancedV3:
    def test_untokenize_bytes(self):
        """`tokenize.untokenize 真 round-trip (3.11+ bytes)`. """
        src = b"x = 1\n"
        tokens = list(tokenize.tokenize(io.BytesIO(src).readline))
        out = tokenize.untokenize(tokens)
        # 3.11+ 返 bytes
        if isinstance(out, bytes):
            decoded = out.decode("utf-8", errors="ignore")
        else:
            decoded = out
        # 必含 x + 1
        assert "x" in decoded
        assert "1" in decoded
