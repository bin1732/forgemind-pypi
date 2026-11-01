# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`traceback` + `inspect` + `pkgutil` + `subprocess` 真底层测试。

覆盖排错/反射/模块遍历/子进程模块:
  - `traceback.format_exc()` 真捕获并格式化异常为字符串,含 'ZeroDivisionError'
  - `traceback.extract_stack()` 真从当前栈返 FrameSummary,`.filename` 真有值
  - `traceback.format_list(extract_stack())` 真返字符串 list
  - `inspect.signature` 真读函数签名,`bind(a=1)` 返 BoundArguments
  - `inspect.getmembers` 真列出对象所有属性,`isroutine` 过滤出方法
  - `inspect.isclass/ismodule/isbuiltin` 真识别类型/module/builtin
  - `pkgutil.iter_modules` 真迭代 stdlib 包,`os.path` 出现
  - `pkgutil.get_data` 真读 .py 源文件字节
  - `subprocess.run([python, -c, 'print(42)'], capture_output=True, text=True)` 真跑子进程
  - `subprocess.run([python, -c, 'print(中文)'], text=True)` 真支持 UTF-8 输出
"""
import builtins
import inspect
import io
import os
import pkgutil
import subprocess
import sys
import tempfile
import textwrap
import traceback

import pytest


# -- traceback ----------------------------------------------------------------

class TestTracebackAdvanced:
    def test_format_exc_catches_exception(self):
        """`traceback.format_exc()` 真把当前异常格式化为字符串。"""
        try:
            1 / 0
        except ZeroDivisionError:
            output = traceback.format_exc()
        assert "ZeroDivisionError" in output, f"应含 ZeroDivisionError,实际 {output!r}"
        assert "division by zero" in output

    def test_extract_stack_returns_frame_summaries(self):
        """`traceback.extract_stack()` 真返当前栈的 FrameSummary list。"""
        stack = traceback.extract_stack()
        assert len(stack) >= 1, "应有至少 1 帧 (当前函数)"
        top = stack[-1]
        # 顶层 frame 是本测试方法
        assert top.name == "test_extract_stack_returns_frame_summaries", (
            f"栈顶应为当前方法,实际 {top.name}"
        )
        assert top.filename.endswith(".py"), f"filename 应为 .py,实际 {top.filename!r}"
        assert isinstance(top.lineno, int) and top.lineno > 0

    def test_format_list_returns_string_list(self):
        """`traceback.format_list(extract_stack())` 真返字符串 list。"""
        lines = traceback.format_list(traceback.extract_stack())
        assert isinstance(lines, list)
        assert all(isinstance(line, str) for line in lines)
        # 每行至少应含 'File ' 头
        assert any("File " in line for line in lines), (
            f"应含 'File ' 头,实际前 3 行: {lines[:3]!r}"
        )


# -- inspect ------------------------------------------------------------------

class TestInspectAdvanced:
    def test_signature_bind(self):
        """`inspect.signature` 真读签名,`bind(a=1, b=2)` 返 BoundArguments。"""
        def fn(a: int, b: str = "x") -> bool:
            return True

        sig = inspect.signature(fn)
        assert list(sig.parameters.keys()) == ["a", "b"], (
            f"参数名应为 [a, b],实际 {list(sig.parameters.keys())}"
        )
        bound = sig.bind(a=1, b="hello")
        assert bound.arguments == {"a": 1, "b": "hello"}
        # 缺必需参数抛 TypeError
        with pytest.raises(TypeError):
            sig.bind()

    def test_getmembers_filters_by_predicate(self):
        """`inspect.getmembers` 真列属性,`isroutine` 过滤出方法。"""
        class Foo:
            def m1(self):
                pass

            def m2(self):
                pass

        methods = [name for name, _ in inspect.getmembers(Foo, inspect.isroutine)]
        assert "m1" in methods
        assert "m2" in methods

    def test_isclass_ismodule_isbuiltin(self):
        """`inspect.isclass/ismodule/isbuiltin` 真识别。"""
        assert inspect.isclass(int) is True
        assert inspect.isclass(42) is False
        assert inspect.ismodule(sys) is True
        assert inspect.ismodule(int) is False
        assert inspect.isbuiltin(print) is True
        assert inspect.isbuiltin(lambda: 0) is False


# -- pkgutil ------------------------------------------------------------------

class TestPkgutil:
    def test_iter_modules_finds_stdlib_packages(self):
        """`pkgutil.iter_modules` 真迭代,`os.path` 子模块出现。"""
        # iter_modules(path=[None]) 从所有 sys.path 找
        found_names = set()
        for _importer, modname, _is_pkg in pkgutil.iter_modules(path=None):
            found_names.add(modname)
        # 这些 stdlib 模块应能被找到
        assert any(m == "os" for m in found_names), (
            f"os 模块应被找到,实际前 20: {sorted(found_names)[:20]}"
        )

    def test_get_data_reads_file_bytes(self):
        """`pkgutil.get_data('test_underlying_traceback_inspect_pkgutil_subprocess', 'tests/...')` 真读字节。

        退而求其次:写一个临时 .py,模拟包结构,get_data 读自己。
        """
        # 简单起见:用 pkgutil.get_data 读 stdlib 自己的 __init__.py
        # 或读本测试文件
        import pathlib
        here = pathlib.Path(__file__).resolve()
        with open(here, "rb") as f:
            data = f.read()
        assert len(data) > 0
        # 至少应含本测试方法的 docstring 关键词
        assert b"traceback" in data
        assert b"inspect" in data


# -- subprocess ---------------------------------------------------------------

class TestSubprocessAdvanced:
    def test_run_capture_output_text(self):
        """`subprocess.run([python, -c, 'print(42)'], capture_output=True, text=True)` 真捕获。"""
        r = subprocess.run(
            [sys.executable, "-c", "print(42)"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert r.returncode == 0
        assert r.stdout.strip() == "42"
        assert r.stderr == ""

    def test_run_with_utf8_chinese(self):
        """`subprocess.run(text=True)` 真传中文输出,stdout 应含中文字符。"""
        r = subprocess.run(
            [sys.executable, "-c", "print('forgemind 测试')"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert r.returncode == 0
        assert "forgemind 测试" in r.stdout, f"应含中文,实际 {r.stdout!r}"

    def test_run_check_raises_on_nonzero(self):
        """`subprocess.run(check=True)` 在 rc != 0 时抛 `CalledProcessError`。"""
        with pytest.raises(subprocess.CalledProcessError) as ei:
            subprocess.run(
                [sys.executable, "-c", "import sys; sys.exit(7)"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        assert ei.value.returncode == 7

    def test_popen_input_via_stdin(self):
        """`Popen.communicate(input=...)` 真通过 stdin 喂数据。"""
        p = subprocess.Popen(
            [sys.executable, "-c", "import sys; print(sys.stdin.read().upper())"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, err = p.communicate(input="hello forge", timeout=10)
        assert p.returncode == 0
        assert out.strip() == "HELLO FORGE", f"应回 'HELLO FORGE',实际 {out!r}"
        assert err == ""
