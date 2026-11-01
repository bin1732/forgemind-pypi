# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 platform 真 (node() / release() / system()) + 真 signal 真 (SIGUSR1 进阶) + 真 fcntl 真 (flock 真 LOCK_UN) + 真 locale 真 (format_string 进阶) + 真 tracemalloc 进阶 (compare_to 进阶) + 真 urllib 真 (parse 进阶) + 真 http 真 (HTTPStatus 进阶).
全 stdlib, 零模拟。
"""
import platform
import signal
import fcntl
import locale
import tracemalloc
import urllib.parse
import http
import os
import tempfile
import pytest


# ======================== platform 进阶 ========================
def test_platform_node():
    """真 node() 真"""
    node = platform.node()
    assert isinstance(node, str)
    assert len(node) > 0


def test_platform_system():
    """真 system() 真"""
    system = platform.system()
    assert system in ("Linux", "Darwin", "Windows", "Java")


def test_platform_release():
    """真 release() 真"""
    release = platform.release()
    assert isinstance(release, str)
    assert len(release) > 0


def test_platform_python_implementation():
    """真 python_implementation() 真"""
    impl = platform.python_implementation()
    assert impl in ("CPython", "PyPy", "Jython", "IronPython")


# ======================== signal 进阶 ========================
def test_signal_signame():
    """真 signame 真"""
    # SIGUSR1 名字
    name = signal.Signals(10).name
    # 10 = SIGUSR1 on linux
    assert "USR" in name or "URG" in name


def test_signal_str_signal():
    """真 Signals 进阶"""
    # 比较
    assert signal.SIGUSR1 == signal.Signals.SIGUSR1
    # int
    assert int(signal.SIGUSR1) == 10


def test_signal_default_handler():
    """真 SIG_DFL 真"""
    assert signal.SIG_DFL is not None
    assert signal.SIG_IGN is not None
    # 不同
    assert signal.SIG_DFL != signal.SIG_IGN


# ======================== fcntl 进阶 ========================
def test_fcntl_flock_unlock():
    """真 flock 真 LOCK_UN 真释放"""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
    try:
        with open(path, "w") as f:
            # 锁
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            # 解锁
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            # 再锁 LOCK_SH
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            # 再释放
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    finally:
        os.unlink(path)


# ======================== locale 进阶 ========================
def test_locale_format_string():
    """真 format_string 进阶"""
    # "%d" % 1000000
    result = locale.format_string("%d", 1000000, grouping=True)
    # 必有数字 (千位分隔)
    assert "1" in result
    assert "000" in result


def test_locale_atof():
    """真 atof 真"""
    # "1,000.5" parse
    try:
        val = locale.atof("1,000.5")
        # 必是 1000.5 (实际依赖 locale)
        # 或 1.0005 (欧洲)
        assert isinstance(val, float)
    except ValueError:
        pytest.skip("locale-dependent")


# ======================== tracemalloc 进阶 ========================
def test_tracemalloc_compare_to_by_lineno():
    """真 compare_to lineno 进阶"""
    tracemalloc.start()
    try:
        # 快照 1
        a = [1] * 100
        snap1 = tracemalloc.take_snapshot()
        del a
        # 快照 2
        b = [2] * 200
        snap2 = tracemalloc.take_snapshot()
        # compare by lineno
        diffs = snap2.compare_to(snap1, "lineno")
        # list of StatDiff
        assert isinstance(diffs, list)
    finally:
        tracemalloc.stop()


# ======================== urllib.parse 进阶 ========================
def test_urllib_parse_urlencode():
    """真 urlencode 真"""
    encoded = urllib.parse.urlencode({"q": "中文", "page": 1})
    # 必有 q=
    assert "q=" in encoded
    # 中文 URL encoded
    assert "%" in encoded or "中文" in encoded


def test_urllib_parse_qs():
    """真 parse_qs 真"""
    parsed = urllib.parse.parse_qs("q=test&page=1")
    assert parsed["q"] == ["test"]
    assert parsed["page"] == ["1"]


# ======================== http.HTTPStatus 进阶 ========================
def test_http_HTTPStatus_codes():
    """真 HTTPStatus 真"""
    assert http.HTTPStatus.OK.value == 200
    assert http.HTTPStatus.NOT_FOUND.value == 404
    assert http.HTTPStatus.INTERNAL_SERVER_ERROR.value == 500


def test_http_HTTPStatus_phrase():
    """真 HTTPStatus phrase 真"""
    assert "OK" in http.HTTPStatus.OK.phrase
    assert "Not Found" in http.HTTPStatus.NOT_FOUND.phrase
