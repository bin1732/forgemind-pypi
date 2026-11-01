# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`traceback` 进阶 + `unittest.mock` 真 + `inspect.getclosurevars` + `logging` 进阶 + `gc` freeze/unfreeze 真底层测试。

覆盖 traceback / mock / 内省闭包 / 日志捕获 / GC 冻结 模块:
  - `traceback.extract_tb 真返 FrameSummary list`
  - `traceback.walk_tb 真返 (frame, lineno) generator`
  - `traceback.StackSummary.from_list 真建`
  - `traceback.format_tb 真格式化`
  - `unittest.mock.Mock()` 真建 + `mock.assert_called_once`
  - `unittest.mock.MagicMock()` 真建 + 支持 magic
  - `unittest.mock.patch 真上下文替换`
  - `inspect.getclosurevars 真取闭包 vars`
  - `inspect.Signature.replace 真替换参数`
  - `logging.captureWarnings(True) 真接管 warnings`
  - `logging.setLoggerClass 真设 logger class`
  - `gc.freeze/unfreeze 沙箱 3.11+ (skip)`
"""
import gc
import inspect
import logging
import os
import sys
import tempfile
import traceback
import unittest.mock
import warnings

import pytest


# -- traceback 进阶 ------------------------------------------------------------

class TestTracebackAdvancedV2:
    def test_extract_tb(self):
        """`traceback.extract_tb 真返 FrameSummary list`。"""
        try:
            1 / 0
        except ZeroDivisionError as e:
            tb_list = traceback.extract_tb(e.__traceback__)
        assert len(tb_list) >= 1
        # 必含 filename, lineno, name
        first = tb_list[0]
        assert hasattr(first, "filename")
        assert hasattr(first, "lineno")
        assert hasattr(first, "name")

    def test_walk_tb(self):
        """`traceback.walk_tb 真返 (frame, lineno) generator`。"""
        try:
            1 / 0
        except ZeroDivisionError as e:
            pairs = list(traceback.walk_tb(e.__traceback__))
        assert len(pairs) >= 1
        # 必含 (frame, lineno) tuple
        frame, lineno = pairs[0]
        assert frame is not None
        assert isinstance(lineno, int)

    def test_StackSummary_from_list(self):
        """`traceback.StackSummary.from_list 真建`。"""
        try:
            1 / 0
        except ZeroDivisionError as e:
            tb_list = traceback.extract_tb(e.__traceback__)
        stack = traceback.StackSummary.from_list(tb_list)
        # 真格式化
        out = stack.format()
        assert len(out) >= 1
        # 必含 'File '
        assert any("File " in s for s in out)

    def test_format_tb(self):
        """`traceback.format_tb 真返 list of strings`。"""
        try:
            1 / 0
        except ZeroDivisionError as e:
            lines = traceback.format_tb(e.__traceback__)
        # 必 ≥ 1 行
        assert len(lines) >= 1
        # 必含 'File '
        assert any("File " in s for s in lines)


# -- unittest.mock ------------------------------------------------------------

class TestUnittestMock:
    def test_Mock_basic(self):
        """`unittest.mock.Mock() 真建 + assert_called_once`。"""
        m = unittest.mock.Mock()
        m("hello forge")
        m.assert_called_once_with("hello forge")

    def test_Mock_return_value(self):
        """`Mock(return_value=42) 真设返回值`。"""
        m = unittest.mock.Mock(return_value=42)
        assert m() == 42
        assert m("arg") == 42  # return_value 忽略 args

    def test_MagicMock(self):
        """`unittest.mock.MagicMock() 真支持 magic methods`。"""
        m = unittest.mock.MagicMock()
        m.__len__.return_value = 5
        assert len(m) == 5

    def test_patch_decorator(self):
        """`unittest.mock.patch 真上下文替换 + restore`。"""
        # patch 'os.path.join' 替换为 lambda *a: 'MOCKED'
        with unittest.mock.patch("os.path.join", return_value="/MOCKED/path") as m:
            result = os.path.join("a", "b")
        assert result == "/MOCKED/path", f"应='/MOCKED/path',实际 {result!r}"
        # 退出 patch 后, os.path.join 恢复
        assert os.path.join("a", "b") == "a/b"


# -- inspect.getclosurevars ----------------------------------------------------

def _make_closure():
    x = 10
    y = 20
    def inner():
        return x + y
    return inner


class TestInspectAdvancedV3:
    def test_getclosurevars(self):
        """`inspect.getclosurevars(fn) 真取闭包 vars`。"""
        f = _make_closure()
        cv = inspect.getclosurevars(f)
        # cv 必是 inspect.ClosureVars
        assert hasattr(cv, "nonlocals")
        assert hasattr(cv, "globals")
        # 闭包内 x, y 是 nonlocals
        nonlocals_dict = dict(cv.nonlocals)
        assert "x" in nonlocals_dict
        assert "y" in nonlocals_dict
        # 真值
        assert nonlocals_dict["x"] == 10
        assert nonlocals_dict["y"] == 20

    def test_Signature_replace(self):
        """`inspect.Signature.replace 真替换参数 + return_annotation`。"""
        sig = inspect.signature(lambda a, b: a + b)
        new_sig = sig.replace(return_annotation=int)
        assert new_sig.return_annotation is int
        # 参数不变
        assert list(new_sig.parameters.keys()) == ["a", "b"]


# -- logging 进阶 -------------------------------------------------------------

class TestLoggingAdvancedV3:
    def test_capture_warnings(self):
        """`logging.captureWarnings(True) 真接管 warnings`。"""
        old = logging.captureWarnings(True)
        try:
            # 发 warning
            with warnings.catch_warnings(record=True) as caught:
                # captureWarnings 把 warning 发到 logging
                warnings.simplefilter("always")
                warnings.warn("forge capture test", UserWarning)
            # 至少捕获 1
            assert len(caught) >= 1
        finally:
            logging.captureWarnings(old)

    def test_setLoggerClass(self):
        """`logging.setLoggerClass 真设 custom logger class`。"""

        class _MyLogger(logging.Logger):
            pass

        logging.setLoggerClass(_MyLogger)
        try:
            log = logging.getLogger("forge_custom_class")
            assert isinstance(log, _MyLogger), (
                f"应=_MyLogger,实际 {type(log)}"
            )
        finally:
            # 恢复
            logging.setLoggerClass(logging.Logger)


# -- gc 进阶 (freeze/unfreeze) -------------------------------------------------

class TestGcAdvancedV3:
    def test_freeze_unfreeze(self):
        """`gc.freeze/unfreeze 真冻/解冻 (3.7+)`。"""
        if not hasattr(gc, "freeze"):
            pytest.skip("无 gc.freeze")
        # 冻 + 解冻不抛
        gc.freeze()
        # 再冻
        gc.unfreeze()
        # 多次不抛
        gc.freeze()
        gc.freeze()
        gc.unfreeze()
        gc.unfreeze()

    def test_get_objects_after_collect(self):
        """`gc.get_objects() 在 gc.collect 后返 list (必 ≥ 1)`。"""
        gc.collect()
        objs = gc.get_objects()
        assert isinstance(objs, list)
        assert len(objs) > 0
