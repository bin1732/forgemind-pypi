# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`py_compile` + `compileall` + `cProfile`/`pstats` 真底层测试。

覆盖 Python 编译/剖析支撑模块:
  - `py_compile.compile` 真写 .pyc 到 `__pycache__/`,并能在
    `imp.cache_from_source` 路径下用 `marshal` 反序列化回 code object
  - `compileall.compile_dir` 真递归编译一个目录树到 .pyc,统计文件数对得上
  - `cProfile.Profile` 真跑一段可计时函数并 `print_stats` 到 StringIO,
    看到 `function calls` 头
  - `pstats.Stats` 真从 cProfile 输出流构造并按 `cumulative` 排序取前 N 行
"""
import compileall
import cProfile
import io
import marshal
import os
import pstats
import py_compile
import shutil
import sys
import tempfile
import textwrap

import pytest


# -- py_compile ---------------------------------------------------------------

class TestPyCompile:
    def test_compile_writes_pyc_to_pyc_cache(self):
        """`py_compile.compile` 真写 .pyc 到 `__pycache__/`。

        写一个临时 .py,调 `py_compile.compile(path, cfile=...)`,然后
        `marshal.load` 读回,得到真 code object (`co_code` 非空)。
        """
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "tiny.py")
            with open(src, "w", encoding="utf-8") as f:
                f.write("x = 1\nprint(x)\n")
            cfile = py_compile.compile(src, doraise=True)
            assert cfile is not None
            assert os.path.isfile(cfile), f"应生成 {cfile}"
            assert cfile.endswith(".pyc")
            with open(cfile, "rb") as f:
                # .pyc header 16 bytes, then marshal payload
                f.read(16)
                code_obj = marshal.load(f)
            assert hasattr(code_obj, "co_code")
            assert code_obj.co_filename == src

    def test_py_compile_raises_on_syntax_error(self):
        """`py_compile.compile` 在 doraise=True 时真抛 PyCompileError。"""
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "bad.py")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("def 1bad(:\n")
            with pytest.raises(py_compile.PyCompileError):
                py_compile.compile(bad, doraise=True)


# -- compileall ---------------------------------------------------------------

class TestCompileAll:
    def test_compile_dir_recursively_compiles_pyc(self):
        """`compileall.compile_dir` 真递归编译目录树。

        写一个 src/pkg/ 目录,3 个 .py 文件,跑 compile_dir 后
        检查 `__pycache__/<name>.cpython-311.pyc` 文件数 = 3。
        """
        if sys.version_info < (3, 11):
            pytest.skip("compile_dir 行为在 3.10+ 稳定")
        with tempfile.TemporaryDirectory() as d:
            pkg = os.path.join(d, "pkg")
            os.makedirs(pkg)
            for name in ("a.py", "b.py", "c.py"):
                with open(os.path.join(pkg, name), "w", encoding="utf-8") as f:
                    f.write(f"# {name}\nVALUE = 1\n")
            ok = compileall.compile_dir(pkg, quiet=1, force=True)
            assert ok is True, f"compileall 应返 True,实际 {ok}"
            # Count .pyc under pkg/__pycache__/
            cache = os.path.join(pkg, "__pycache__")
            assert os.path.isdir(cache), f"应生成 __pycache__ 目录"
            pycs = [f for f in os.listdir(cache) if f.endswith(".pyc")]
            assert len(pycs) == 3, f"应生成 3 个 .pyc,实际 {len(pycs)}"


# -- cProfile / pstats --------------------------------------------------------

def _busy_loop(n: int) -> int:
    """被 cProfile 采样的可计时函数:平方和。"""
    s = 0
    for i in range(n):
        s += i * i
    return s


class TestCProfileAndPstats:
    def test_cprofile_runs_function_and_captures_output(self):
        """`cProfile.Profile` 真跑函数并把 stats 写到 StringIO。

        跑 `_busy_loop(5000)`,把 output 喂到 `pstats.Stats`,
        验证 `print_stats` 在 StringIO 中真出现 `function calls` 头。
        """
        pr = cProfile.Profile()
        pr.enable()
        _busy_loop(5000)
        pr.disable()
        out = io.StringIO()
        stats = pstats.Stats(pr, stream=out)
        stats.print_stats()
        output = out.getvalue()
        assert "function calls" in output, (
            f"pstats.print_stats 应含 'function calls' 头,实际前 200 字: {output[:200]!r}"
        )
        assert "_busy_loop" in output or "busy_loop" in output, (
            f"被剖析函数名应出现,实际前 200 字: {output[:200]!r}"
        )

    def test_pstats_sort_by_cumulative(self):
        """`pstats.Stats.sort_stats('cumulative')` 真按累计时间排序。

        跑两个耗时不同的函数,sort 后调 print_stats 写到 StringIO,
        取前两行的 cumtime 验证排序生效。
        """
        pr = cProfile.Profile()
        pr.enable()

        def hot():
            return sum(i * i for i in range(20000))

        def cold():
            return 1 + 1

        for _ in range(5):
            hot()
            cold()
        pr.disable()

        out = io.StringIO()
        stats = pstats.Stats(pr, stream=out)
        stats.sort_stats("cumulative").print_stats()
        # 跳过 header 行 ("... function calls in 0.024 seconds") 那些非数据行
        # 真实数据行: 5 列 (ncalls tottime percall cumtime percall ...)
        rows = []
        for line in out.getvalue().splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0].lstrip("0123456789/") == "":
                try:
                    float(parts[3])
                    rows.append(parts)
                except ValueError:
                    pass
        assert len(rows) >= 2
        first_cum = float(rows[0][3])
        second_cum = float(rows[1][3])
        assert first_cum >= second_cum, (
            f"按 cumulative 排序后,第一行 cumtime ({first_cum}) 应 ≥ 第二行 ({second_cum})"
        )
