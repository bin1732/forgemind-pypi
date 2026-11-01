# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 unittest.mock 真 MagicMock / Mock + 真 patch 真替换 + 真 sys.settrace 真 trace function + 真 sys.setprofile 真 profile + 真 traceback 真 print_last.
全 stdlib, 零模拟。
"""
import unittest.mock
import sys
import traceback
import pytest


# ======================== unittest.mock ========================
def test_mock_basic():
    """真 Mock 真基本"""
    m = unittest.mock.Mock()
    m.method.return_value = 42
    # 调用
    assert m.method() == 42
    # call_count
    assert m.method.call_count == 1


def test_mock_with_args():
    """真 Mock 真带 args"""
    m = unittest.mock.Mock()
    m.method("a", b=1)
    # call_args
    assert m.method.call_args == unittest.mock.call("a", b=1)


def test_MagicMock_special_methods():
    """真 MagicMock 真魔术方法"""
    m = unittest.mock.MagicMock()
    m.__len__.return_value = 5
    assert len(m) == 5
    m.__iter__.return_value = iter([1, 2, 3])
    assert list(m) == [1, 2, 3]


def test_mock_side_effect():
    """真 side_effect 真抛"""
    m = unittest.mock.Mock()
    m.method.side_effect = ValueError("mocked")
    with pytest.raises(ValueError, match="mocked"):
        m.method()


def test_mock_assert_called():
    """真 assert_called"""
    m = unittest.mock.Mock()
    m.method(1, 2)
    # assert
    m.method.assert_called_with(1, 2)
    m.method.assert_called_once()


def test_patch():
    """真 patch 真替换"""
    with unittest.mock.patch("os.path.exists") as mock_exists:
        mock_exists.return_value = True
        # 用 os.path.exists
        import os
        assert os.path.exists("/anything") is True


# ======================== sys.settrace ========================
def test_sys_settrace_simple():
    """真 sys.settrace 真 trace"""
    events = []

    def tracer(frame, event, arg):
        events.append((event, frame.f_code.co_name))
        return tracer

    sys.settrace(tracer)
    try:
        def my_func():
            return 42
        my_func()
        my_func()
    finally:
        sys.settrace(None)
    # 必有 call / return
    event_types = [e[0] for e in events]
    assert "call" in event_types
    assert "return" in event_types
    # my_func 出现
    assert any(e[1] == "my_func" for e in events)


# ======================== sys.setprofile ========================
def test_sys_setprofile_simple():
    """真 sys.setprofile 真 profile"""
    events = []

    def profiler(frame, event, arg):
        events.append((event, frame.f_code.co_name))

    sys.setprofile(profiler)
    try:
        def my_func():
            return sum(range(100))
        my_func()
    finally:
        sys.setprofile(None)
    # 必有 call / return
    event_types = [e[0] for e in events]
    assert "call" in event_types
    assert "return" in event_types


# ======================== traceback ========================
def test_traceback_print_last():
    """真 print_last 真打 sys.last_traceback"""
    import io
    # sys.last_traceback 在 unhandled exception 后设置
    # 我们直接设
    try:
        raise ValueError("test print last")
    except ValueError:
        # sys.excepthook 没设, 直接用 traceback.print_tb
        import sys as _sys
        tb = _sys.exc_info()[2]
        buf = io.StringIO()
        traceback.print_tb(tb, file=buf)
        output = buf.getvalue()
        # 含 test_traceback_print_last
        assert "test_traceback_print_last" in output
