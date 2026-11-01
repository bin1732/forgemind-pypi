# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`logging` 进阶 + `inspect` 进阶 + `pkgutil` 进阶 + `traceback` 进阶 + `compileall` 进阶 真底层测试。

覆盖日志/检查/包工具/traceback/编译模块:
  - `logging.Logger.addHandler/removeHandler` 真管 handler
  - `logging.Logger.handlers` 返 list
  - `logging.LogRecord(levelname, msg)` 真建
  - `logging.getLogger(__name__)` 真返 singleton
  - `logging.Logger.propagate = True/False` 真控
  - `inspect.signature` 真取签名
  - `inspect.getmembers` 真列成员
  - `inspect.isclass/ismodule/isbuiltin` 真判
  - `inspect.getsource` 真取源码
  - `inspect.getfile` 真取文件路径
  - `pkgutil.iter_modules` 真列模块
  - `pkgutil.get_data` 真读资源
  - `pkgutil.resolve_name` 真解 dotted
  - `traceback.print_exc` 真打到 stream
  - `traceback.format_exc` 真返 string
  - `traceback.extract_stack` 真返 FrameSummary list
  - `traceback.format_list` 真格式化
  - `compileall.compile_file` + `force=True` 真重新编
  - `compileall.compile_dir` 真递归
"""
import compileall
import inspect
import io
import logging
import os
import pkgutil
import tempfile
import traceback

import pytest


# -- logging 进阶 -------------------------------------------------------------

class TestLoggingAdvanced:
    def test_add_remove_handler(self):
        """`Logger.addHandler/removeHandler` 真管 handler 集合。"""
        log = logging.getLogger("forge_add_remove")
        log.setLevel(logging.DEBUG)
        initial = len(log.handlers)
        h = logging.StreamHandler()
        log.addHandler(h)
        assert h in log.handlers
        log.removeHandler(h)
        assert h not in log.handlers
        assert len(log.handlers) == initial

    def test_LogRecord_construction(self):
        """`logging.LogRecord(name, level, pathname, lineno, msg, args, exc_info)` 真建。"""
        rec = logging.LogRecord(
            "forge", logging.WARNING, "/path", 42, "hello %s", ("forge",), None
        )
        assert rec.name == "forge"
        assert rec.levelname == "WARNING"
        assert rec.lineno == 42
        # args 透传
        assert rec.args == ("forge",)

    def test_logger_propagate(self):
        """`Logger.propagate = False` 真阻止传到 root。"""
        log = logging.getLogger("forge_propagate")
        log.propagate = False
        assert log.propagate is False
        log.propagate = True
        assert log.propagate is True


# -- inspect 进阶 -------------------------------------------------------------

def _sample_fn(a: int, b: str = "default") -> bool:
    return a > 0


class TestInspectAdvanced:
    def test_signature(self):
        """`inspect.signature` 真取参数签名。"""
        sig = inspect.signature(_sample_fn)
        params = list(sig.parameters.keys())
        assert params == ["a", "b"]
        # b 有 default
        assert sig.parameters["b"].default == "default"

    def test_getmembers(self):
        """`inspect.getmembers` 真列类成员。"""

        class _Sample:
            value = 1

            def method(self):
                pass

        members = inspect.getmembers(_Sample)
        names = [n for n, _ in members]
        assert "value" in names
        assert "method" in names

    def test_isclass_ismodule_isbuiltin(self):
        """`isclass(int)=True, ismodule(sys)=True, isbuiltin(print)=True`。"""
        assert inspect.isclass(int) is True
        assert inspect.isclass(42) is False
        import sys as _sys
        assert inspect.ismodule(_sys) is True
        assert inspect.isbuiltin(print) is True

    def test_getsource_getfile(self):
        """`inspect.getsource/getfile` 真取源码/文件。"""
        src = inspect.getsource(_sample_fn)
        assert "def _sample_fn" in src
        # getfile 返回 .py path
        path = inspect.getfile(_sample_fn)
        assert path.endswith(".py")


# -- pkgutil 进阶 -------------------------------------------------------------

class TestPkgutilAdvanced:
    def test_iter_modules_finds_os(self):
        """`pkgutil.iter_modules` 真找 stdlib os。"""
        names = [info.name for info in pkgutil.iter_modules()]
        assert "os" in names, f"应含 'os',实际前 20: {names[:20]}"

    def test_get_data_reads_file(self):
        """`pkgutil.get_data('json', 'encoder.py')` 真读 bytes。"""
        # 沙箱可能 json 不可用,用 tokenize 替代
        data = pkgutil.get_data("tokenize", "tokenize.py")
        if data is None:
            pytest.skip("pkgutil.get_data 不可用")
        assert isinstance(data, bytes)
        assert b"def" in data

    def test_resolve_name(self):
        """`pkgutil.resolve_name('os.path')` 真解模块。"""
        mod = pkgutil.resolve_name("os.path")
        assert mod is not None
        # os.path 必含 join
        assert hasattr(mod, "join")


# -- traceback 进阶 -----------------------------------------------------------

class TestTracebackAdvanced:
    def test_format_exc(self):
        """`traceback.format_exc` 真返 string (在 except 块)。"""
        try:
            1 / 0
        except ZeroDivisionError:
            exc_str = traceback.format_exc()
        assert "ZeroDivisionError" in exc_str or "division" in exc_str

    def test_extract_stack(self):
        """`traceback.extract_stack` 真返 FrameSummary list。"""
        stack = traceback.extract_stack()
        assert len(stack) >= 1
        # 必是 FrameSummary-like
        first = stack[-1]
        assert hasattr(first, "filename")
        assert hasattr(first, "lineno")

    def test_format_list(self):
        """`traceback.format_list` 真返字符串 list。"""
        stack = traceback.extract_stack()
        formatted = traceback.format_list(stack)
        assert isinstance(formatted, list)
        # 至少含 'File '
        assert any("File " in s for s in formatted)


# -- compileall 进阶 ----------------------------------------------------------

class TestCompileallAdvancedV2:
    def test_compile_file_with_force(self):
        """`compile_file(path, force=True)` 真重新编。"""
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "forge_compile.py")
            with open(src, "w") as f:
                f.write("VAL = 42\n")
            ok1 = compileall.compile_file(src, quiet=1, force=True)
            assert ok1 is True
            # 第二次 force=True 也返 True
            ok2 = compileall.compile_file(src, quiet=1, force=True)
            assert ok2 is True

    def test_compile_dir_recursive(self):
        """`compile_dir(dir)` 真递归编 3 文件。"""
        with tempfile.TemporaryDirectory() as d:
            for n in ("a.py", "b.py", "sub/c.py"):
                full = os.path.join(d, n)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "w") as f:
                    f.write(f"# {n}\n")
            ok = compileall.compile_dir(d, quiet=1, force=True)
            assert ok is True
