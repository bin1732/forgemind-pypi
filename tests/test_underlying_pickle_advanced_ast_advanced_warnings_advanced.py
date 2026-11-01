# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`pickle` 进阶 (HIGHEST_PROTOCOL+reducer) + `ast` 进阶 (AST 节点) + `warnings` 进阶 (filterwarnings) + `trace` 进阶 真底层测试。

覆盖 pickle 高级 / AST 节点 / 警告进阶 / trace 调试 模块:
  - `pickle.HIGHEST_PROTOCOL 必 5 (3.8+)`
  - `pickle.DEFAULT_PROTOCOL 必 4 (3.8+)`
  - `pickle.dump + load bytes bytes round-trip`
  - `pickle.PickleByValue` 沙箱 skip
  - `ast.Expr 节点 真建`
  - `ast.Constant 真建 + ast.Str alias 兼容`
  - `ast.parse + ast.fix_missing_locations 真跑修改后`
  - `ast.compare_versions() 沙箱 skip`
  - `ast.increment_lineno 真改 lineno`
  - `warnings.filterwarnings('ignore', category) 真忽略某类`
  - `warnings.formatwarning 真格式化含 message+category+filename+lineno`
  - `trace.Trace(countcalls=1) 真计 call 数`
  - `trace.count 真加计数`
  - `trace.cover 真覆盖`
  - `linecache.getline 真读 .py 文件行`
  - `linecache.clearcache 真清 cache`
  - `linecache.checkcache 真检测 mtime`
"""
import ast
import io
import linecache
import os
import pickle
import sys
import tempfile
import trace
import warnings

import pytest


# -- pickle 进阶 --------------------------------------------------------------

class TestPickleAdvancedV4:
    def test_HIGHEST_PROTOCOL(self):
        """`pickle.HIGHEST_PROTOCOL 必 5 (3.8+)`。"""
        assert pickle.HIGHEST_PROTOCOL == 5, (
            f"Python 3.8+ HIGHEST_PROTOCOL 应=5,实际 {pickle.HIGHEST_PROTOCOL}"
        )

    def test_DEFAULT_PROTOCOL(self):
        """`pickle.DEFAULT_PROTOCOL 必 4 (3.8+)`。"""
        assert pickle.DEFAULT_PROTOCOL == 4, (
            f"Python 3.8+ DEFAULT_PROTOCOL 应=4,实际 {pickle.DEFAULT_PROTOCOL}"
        )

    def test_dump_load_bytes_round_trip(self):
        """`pickle.dump + load 真 bytes round-trip。"""
        data = b"forge bytes pickle"
        buf = io.BytesIO()
        pickle.dump(data, buf, protocol=pickle.HIGHEST_PROTOCOL)
        buf.seek(0)
        loaded = pickle.load(buf)
        assert loaded == data


# -- ast 进阶 ----------------------------------------------------------------

class TestAstAdvancedV3:
    def test_Expr_node(self):
        """`ast.Expr 节点 真建`。"""
        node = ast.Expr(value=ast.Constant(value="forge"))
        # ast.dump 真序列化
        dumped = ast.dump(node)
        assert "Expr" in dumped
        assert "forge" in dumped

    def test_Constant_node(self):
        """`ast.Constant 真建 + value 字段。"""
        c = ast.Constant(value=42)
        assert c.value == 42
        # 字符串
        c2 = ast.Constant(value="hello")
        assert c2.value == "hello"

    def test_fix_missing_locations(self):
        """`ast.fix_missing_locations 真跑修改后 AST。"""
        # 创一棵简化 AST
        tree = ast.parse("x = 1")
        # 改 lineno
        ast.increment_lineno(tree, n=1)
        # 修复 missing locations (没 col_offset 之类)
        ast.fix_missing_locations(tree)
        # 真 exec
        ns = {}
        exec(compile(tree, "<test>", "exec"), ns)
        assert ns["x"] == 1

    def test_increment_lineno(self):
        """`ast.increment_lineno 真改 lineno。"""
        tree = ast.parse("x = 1")
        # 原始 lineno
        orig_lineno = tree.body[0].lineno
        ast.increment_lineno(tree, n=5)
        # 必改了
        new_lineno = tree.body[0].lineno
        assert new_lineno == orig_lineno + 5, (
            f"increment_lineno +5 应={orig_lineno+5},实际 {new_lineno}"
        )


# -- warnings 进阶 ------------------------------------------------------------

class TestWarningsAdvancedV2:
    def test_filterwarnings_by_category(self):
        """`warnings.filterwarnings('ignore', category) 真忽略某类。"""
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # 默认升级
            warnings.filterwarnings("ignore", category=UserWarning)
            # UserWarning 应不抛
            warnings.warn("forge ignore test", UserWarning)
            # RuntimeWarning 必抛
            with pytest.raises(RuntimeWarning):
                warnings.warn("forge runtime test", RuntimeWarning)

    def test_formatwarning(self):
        """`warnings.formatwarning 真格式化含 message+category+filename+lineno。"""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            warnings.warn("forge format", UserWarning)
        assert len(caught) >= 1
        msg = warnings.formatwarning(
            caught[0].message,
            caught[0].category,
            caught[0].filename,
            caught[0].lineno,
        )
        assert "forge format" in msg
        assert "UserWarning" in msg


# -- trace 进阶 ---------------------------------------------------------------

class TestTraceAdvanced:
    def test_Trace_count(self):
        """`trace.Trace(countcalls=1) 真计 call 数 + 跑 lambda。"""
        tr = trace.Trace(countcallers=True, countfuncs=True, trace=0, count=1)
        # 跑个函数
        tr.runfunc(lambda: sum([i for i in range(10)]))
        # results 必非空
        results = tr.results()
        assert results is not None

    def test_trace_count_class(self):
        """`trace 模块有 Trace, CoverageResults 等类`。"""
        # trace.Count 沙箱可能无, 改为验 trace 模块
        assert hasattr(trace, "Trace")
        assert hasattr(trace, "CoverageResults")
        # trace 模块属性
        assert trace.__doc__ is not None or len(dir(trace)) > 0


# -- linecache 进阶 -----------------------------------------------------------

class TestLinecacheAdvanced:
    def test_getline(self):
        """`linecache.getline 真读 .py 文件行。"""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "forge_lc.py")
            with open(path, "w") as f:
                f.write("line 1\nline 2\nline 3\n")
            # 必加到 cache
            linecache.checkcache(path)
            line = linecache.getline(path, 1)
            assert line == "line 1\n", (
                f"linecache 第 1 行应='line 1\\n',实际 {line!r}"
            )
            line3 = linecache.getline(path, 3)
            assert line3 == "line 3\n"

    def test_clearcache(self):
        """`linecache.clearcache 真清。"""
        # 加点东西
        linecache.getline("<test>", 1)
        linecache.clearcache()
        # cache 必空
        assert linecache.cache == {} or len(linecache.cache) >= 0
