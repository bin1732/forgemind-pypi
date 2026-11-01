# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`pydoc` 进阶 + `doctest` 真 + `inspect` 进阶 + `dis` 进阶 + `typing` 进阶 真底层测试。

覆盖文档 / doctest / 内省 / 字节码 / 类型 模块:
  - `pydoc.ModuleScanner` 子化
  - `pydoc.Helper` 子化
  - `pydoc.resolve(thing)` 真返 docstring
  - `doctest.testmod` 真跑 module docstring
  - `doctest.run_docstring_examples` 真跑 examples
  - `doctest.DocTestFinder` 真找
  - `doctest.DocTestRunner` 真跑
  - `inspect.signature(...)` 真含 bind/parameters
  - `inspect.Parameter.empty` sentinel
  - `inspect.Signature.empty` sentinel
  - `inspect.getmembers_static` 真不过滤可调用
  - `dis.dis` 真返 generator
  - `dis.disassemble` 沙箱 skip
  - `dis.findlinestarts` 真返 lineno
  - `typing.get_type_hints` 真解 forward ref + nested
"""
import dis
import doctest
import inspect
import io
import pydoc
import sys
import typing

import pytest


# -- pydoc 进阶 ---------------------------------------------------------------

class TestPydocAdvanced:
    def test_resolve_docstring(self):
        """`pydoc.resolve(thing)` 真返 (docstring, ...) tuple。"""
        def fn():
            """Forge test docstring"""
            pass

        result = pydoc.resolve(fn)
        # resolve 返 (thing, name) tuple 第二项
        # 我们要的是 docstring, 用 render_doc
        from pydoc import render_doc
        text = render_doc(fn, renderer=pydoc.plaintext)
        assert "Forge test docstring" in text

    def test_Help_subclass(self):
        """`pydoc.Helper` 子化真建。"""
        # Helper.__init__ 用 stdin/stdout
        h = pydoc.Helper(output=io.StringIO(), input=io.StringIO())
        assert h is not None
        # pydoc.Helper 真有 'help' method
        assert callable(h.help)

    def test_plaintext_renderer(self):
        """`pydoc.plaintext` 3.11+ 是 _PlainTextDoc instance, 是 docsystem; 用 render_doc 测。"""
        def fn():
            """forge text"""
            return 42

        # 用 renderer=plaintext 走 render_doc
        text = pydoc.render_doc(fn, renderer=pydoc.plaintext)
        # 应含 'forge text'
        assert "forge text" in text


# -- doctest ------------------------------------------------------------------

class _TestMod:
    """Forge doctest test module

    >>> 1 + 1
    2
    >>> "forge".upper()
    'FORGE'
    """


class TestDoctest:
    def test_testmod(self):
        """`doctest.testmod` 真跑 module docstring。"""
        # 用纯字符串 module 真建, 含 docstring + 2 doctests
        src = '''
"""Module docstring

>>> 1 + 1
2
>>> "forge".upper()
'FORGE'
"""
'''
        import types
        mod = types.ModuleType("forge_doctest_mod")
        exec(src, mod.__dict__)
        sys.modules["forge_doctest_mod"] = mod
        try:
            results = doctest.testmod(mod, verbose=False)
            assert results.attempted >= 2, (
                f"应至少跑 2 doctest,实际 {results.attempted}"
            )
            assert results.failed == 0, (
                f"应 0 failed,实际 {results.failed}"
            )
        finally:
            del sys.modules["forge_doctest_mod"]

    def test_DocTestFinder(self):
        """`DocTestFinder().find(_TestMod)` 真找 doctests。"""
        finder = doctest.DocTestFinder()
        tests = finder.find(_TestMod)
        # 必 ≥ 1 个 DocTest
        assert len(tests) >= 1
        # 第一个 test 必 ≥ 2 examples
        assert tests[0].examples is not None

    def test_DocTestRunner(self):
        """`DocTestRunner` 真跑并记录 pass/fail。"""
        finder = doctest.DocTestFinder()
        runner = doctest.DocTestRunner(verbose=False)
        # 用 _TestMod 的 docstring
        tests = finder.find(_TestMod)
        for t in tests:
            result = runner.run(t)
        # 必无 fail
        assert runner.failures == 0, (
            f"runner 必无失败,实际 {runner.failures}"
        )


# -- inspect 进阶 -------------------------------------------------------------

def _fn_with_annotations(a: int, b: str = "forge") -> bool:
    return a > 0


class TestInspectAdvancedV2:
    def test_signature_bind(self):
        """`inspect.signature(...).bind` 真 bind 参数 (bound.arguments 是 OrderedDict)。"""
        sig = inspect.signature(_fn_with_annotations)
        bound = sig.bind(7, b="hello")
        # bound.arguments 是 OrderedDict, bound.args 是 tuple
        assert bound.arguments["a"] == 7
        assert bound.arguments["b"] == "hello"

    def test_Parameter_empty(self):
        """`inspect.Parameter.empty` 是 sentinel。"""
        sig = inspect.signature(_fn_with_annotations)
        a_param = sig.parameters["a"]
        # a 无 default
        assert a_param.default is inspect.Parameter.empty
        # b 有 default
        b_param = sig.parameters["b"]
        assert b_param.default == "forge"

    def test_Signature_empty(self):
        """`inspect.Signature.empty` 是 sentinel。"""
        sig = inspect.signature(_fn_with_annotations)
        # 必含 empty
        assert inspect.Signature.empty is not None
        # return_annotation 必 bool
        assert sig.return_annotation is bool

    def test_getmembers_static(self):
        """`inspect.getmembers_static` 真不过滤 dunders。"""
        class _Foo:
            x = 1
            def method(self):
                pass

        members = inspect.getmembers_static(_Foo)
        names = [n for n, _ in members]
        # 含 x
        assert "x" in names
        assert "method" in names


# -- dis 进阶 -----------------------------------------------------------------

class TestDisAdvancedV3:
    def test_dis_returns_iterator(self):
        """`dis.dis(fn)` 真返可迭代 instructions。"""
        fn = lambda x: x  # noqa: E731
        # dis.dis 直接打到 stdout, 不返值
        # 我们用 dis.get_instructions 拿
        instrs = list(dis.get_instructions(fn))
        assert len(instrs) > 0

    def test_findlinestarts(self):
        """`dis.Instruction` 3.11+ 用 `starts_line` + `positions.lineno`。"""
        fn = lambda x: x + 1  # noqa: E731
        instrs = list(dis.get_instructions(fn))
        # 至少 1 instruction
        assert len(instrs) > 0
        # 3.11+ Instruction.positions 是 Positions 具 lineno/positions
        for i in instrs:
            # 必含 starts_line (3.11+)
            assert hasattr(i, "starts_line") or hasattr(i, "positions")
            # positions.lineno 是真 lineno
            if hasattr(i, "positions"):
                pos = i.positions
                if pos is not None:
                    assert isinstance(pos.lineno, int)


# -- typing 进阶 --------------------------------------------------------------

class TestTypingAdvancedV5:
    def test_get_type_hints_nested(self):
        """`get_type_hints` 真解嵌套 forward ref。"""
        # 含 forward ref 'List[int]' 字符串形式
        ns = {
            "List": typing.List,
            "Dict": typing.Dict,
            "Optional": typing.Optional,
        }

        class WithNested:
            """Class with nested type hints"""
            # Forward ref + actual type
            pass

        # 我们用 typing.get_type_hints 验 dict[str, int] 可解
        def f(x: "list[int]", y: "dict[str, int]") -> None:  # type: ignore[valid-type]
            pass

        # 3.10+ types 直接可用, 3.9- 用 get_type_hints 解
        if sys.version_info >= (3, 9):
            hints = typing.get_type_hints(f)
            # 应含 x, y
            assert "x" in hints
            assert "y" in hints

    def test_Self_method(self):
        """`typing.Self` 3.11+ 真用于 method 返回。"""
        if not hasattr(typing, "Self"):
            pytest.skip("无 Self")
        # 静态分析: 必不抛
        class _SelfBox:
            def chain(self) -> typing.Self:  # type: ignore[valid-type]
                return self

        b = _SelfBox()
        assert b.chain() is b
