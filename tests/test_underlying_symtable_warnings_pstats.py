# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 symtable 真 symbol table 解析 + 真 warnings 真 filter 路由 + 真 pstats 真解析 cProfile 输出 + 真 doctest + 真 unittest 进阶。
全 stdlib, 零模拟。
"""
import symtable
import warnings
import pstats
import cProfile
import doctest
import unittest
import io
import pytest


# ======================== symtable ========================
def test_symtable_parse():
    """真 symtable 真解析"""
    code = """
x = 1
def func(a, b):
    return a + b
class MyClass:
    pass
"""
    table = symtable.symtable(code, "<test>", "exec")
    # 顶层
    assert table.get_type() == "module"
    # 找 func (namespace = function 或 class)
    func_symbol = table.lookup("func")
    assert func_symbol.is_namespace()
    # 找 class
    class_symbol = table.lookup("MyClass")
    assert class_symbol.is_namespace()


def test_symtable_get_identifiers():
    """真 symtable 真列所有 ident"""
    code = "x = 1; y = 2; z = x + y"
    table = symtable.symtable(code, "<test>", "exec")
    # top-level identifiers
    names = table.get_identifiers()
    assert "x" in names
    assert "y" in names
    assert "z" in names


def test_symtable_nested():
    """真 symtable 真嵌套"""
    code = """
def outer():
    def inner():
        x = 1
    return inner
"""
    table = symtable.symtable(code, "<test>", "exec")
    outer = table.lookup("outer")
    assert outer.is_namespace()
    # get_children 拿嵌套 sym table
    outer_table = outer.get_namespace()
    children = outer_table.get_children()
    inner_table = [c for c in children if c.get_name() == "inner"]
    assert len(inner_table) == 1


# ======================== warnings ========================
def test_warnings_catch_warnings():
    """真 warnings 真 catch 真路由"""
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter("always")
        warnings.warn("test message", UserWarning)
        assert len(ws) == 1
        assert issubclass(ws[0].category, UserWarning)
        assert "test message" in str(ws[0].message)


def test_warnings_filter():
    """真 warnings 真 filter"""
    # 加 filter
    warnings.filterwarnings("error", category=DeprecationWarning)
    try:
        with pytest.raises(DeprecationWarning):
            warnings.warn("test", DeprecationWarning)
    finally:
        # 复原
        warnings.filters.pop()


def test_warnings_simplefilter_ignore():
    """真 simplefilter ignore"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # 不抛
        warnings.warn("test", UserWarning)


def test_warnings_categories():
    """真 warnings 类别继承"""
    assert issubclass(DeprecationWarning, Warning)
    assert issubclass(UserWarning, Warning)
    assert issubclass(SyntaxWarning, Warning)
    assert issubclass(RuntimeWarning, Warning)
    assert issubclass(FutureWarning, Warning)


# ======================== cProfile + pstats ========================
def test_cprofile_pstats():
    """真 cProfile 真 profile + pstats 真解析"""
    profiler = cProfile.Profile()
    profiler.enable()
    # 跑点算
    total = sum(range(10000))
    _ = [i * 2 for i in range(10000)]
    profiler.disable()
    # pstats 读
    s = io.StringIO()
    stats = pstats.Stats(profiler, stream=s)
    stats.print_stats()
    output = s.getvalue()
    # 含 function calls
    assert "function calls" in output


def test_pstats_sort():
    """真 pstats 真 sort"""
    profiler = cProfile.Profile()
    profiler.enable()
    sum(range(1000))
    profiler.disable()
    s = io.StringIO()
    stats = pstats.Stats(profiler, stream=s)
    # sort by tottime
    stats.sort_stats("tottime")
    stats.print_stats(5)
    output = s.getvalue()
    assert "function calls" in output


# ======================== doctest ========================
def test_doctest_run():
    """真 doctest 真 run doctest"""
    code = """
def add(a, b):
    '''Add two numbers.

    >>> add(1, 2)
    3
    >>> add(0, 0)
    0
    '''
    return a + b
"""
    # 解析 docstring
    import ast
    tree = ast.parse(code)
    func = tree.body[0]
    docstring = ast.get_docstring(func)
    assert ">>> add(1, 2)" in docstring
    # 跑 doctest
    results = doctest.run_docstring_examples(
        func, {"add": func}, name="add", verbose=False
    )


def test_doctest_DocTestFinder():
    """真 DocTestFinder 真找 test"""
    finder = doctest.DocTestFinder()
    def add(a, b):
        '''>>> add(1, 2)
        3
        '''
        return a + b
    tests = finder.find(add)
    assert len(tests) >= 1


# ======================== unittest ========================
def test_unittest_TestCase():
    """真 unittest TestCase 真跑"""
    class TestMath(unittest.TestCase):
        def test_add(self):
            self.assertEqual(1 + 1, 2)
        def test_sub(self):
            self.assertEqual(5 - 3, 2)

    # runner
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMath)
    runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
    result = runner.run(suite)
    assert result.wasSuccessful()
    assert result.testsRun == 2


def test_unittest_assert_methods():
    """真 unittest assert methods"""
    class T(unittest.TestCase):
        def test_a(self):
            self.assertEqual(1, 1)
        def test_b(self):
            self.assertIn(1, [1, 2, 3])
        def test_c(self):
            with self.assertRaises(ValueError):
                raise ValueError("test")

    suite = unittest.TestLoader().loadTestsFromTestCase(T)
    runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
    result = runner.run(suite)
    assert result.wasSuccessful()
    assert result.testsRun == 3
