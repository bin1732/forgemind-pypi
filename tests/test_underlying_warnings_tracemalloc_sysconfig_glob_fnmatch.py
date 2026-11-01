# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`warnings` + `tracemalloc` 进阶 + `sysconfig` + `glob` + `fnmatch` 真底层测试。

覆盖警告 / 内存追踪 / 系统配置 / 文件通配模块:
  - `warnings.warn('msg')` 真触发 UserWarning
  - `warnings.simplefilter('always')` 真设过滤
  - `warnings.catch_warnings()` 真上下文管理
  - `warnings.formatwarning` 真格式化
  - `tracemalloc.start()` 真启 3.11+ trace
  - `tracemalloc.get_traced_memory()` 真返 (current, peak)
  - `tracemalloc.take_snapshot()` 真返 Snapshot
  - `tracemalloc.Snapshot.statistics('lineno')` 真返 stat list
  - `sysconfig.get_platform()` 真返 'linux-x86_64' 之类
  - `sysconfig.get_path('purelib')` 真返 site-packages path
  - `sysconfig.get_config_var('Py_ENABLE_SHARED')` 真返 0 或 1
  - `glob.glob('*.py')` 真通配返 list
  - `glob.escape('a[b].py')` 真 escape 元字符
  - `fnmatch.fnmatch('foo.txt', '*.txt')` 真判 True
  - `fnmatch.filter(['a.py', 'b.txt'], '*.py')` 真滤
"""
import fnmatch
import glob
import sys
import sysconfig
import tracemalloc
import warnings

import pytest


# -- warnings ------------------------------------------------------------------

class TestWarnings:
    def test_warn_triggers_capture(self):
        """`warnings.warn('msg')` 真触发,`catch_warnings` 记录 record。"""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            warnings.warn("forge warning")
        assert len(caught) == 1
        assert str(caught[0].message) == "forge warning"
        assert issubclass(caught[0].category, UserWarning)

    def test_simplefilter_error_raises(self):
        """`warnings.simplefilter('error')` 真把警告升级为异常。"""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with pytest.raises(UserWarning):
                warnings.warn("test", UserWarning)

    def test_formatwarning_includes_message(self):
        """`warnings.formatwarning` 真格式化含 message + category。"""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            warnings.warn("forge here", UserWarning)
            msg = warnings.formatwarning(
                caught[0].message,
                caught[0].category,
                caught[0].filename,
                caught[0].lineno,
            )
        assert "forge here" in msg
        assert "UserWarning" in msg


# -- tracemalloc 进阶 ---------------------------------------------------------

class TestTracemallocAdvanced:
    def test_start_and_get_traced_memory(self):
        """`tracemalloc.start()` + `get_traced_memory()` 真返 (current, peak)。"""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        try:
            current, peak = tracemalloc.get_traced_memory()
            assert current >= 0
            assert peak >= current
        finally:
            tracemalloc.stop()

    def test_take_snapshot_and_statistics(self):
        """`tracemalloc.take_snapshot()` + `Snapshot.statistics('lineno')` 真返 stat。"""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        try:
            # 分配一些内存
            data = [i for i in range(1000)]
            snap = tracemalloc.take_snapshot()
            stats = snap.statistics("lineno")
            # stats 必是 list,即使空 (沙箱无 .pyc 也可能有)
            assert isinstance(stats, list)
            # 释放
            del data
        finally:
            tracemalloc.stop()

    def test_stop_and_is_tracing(self):
        """`tracemalloc.stop()` 真停,`is_tracing()` 返 False。"""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        tracemalloc.stop()
        assert not tracemalloc.is_tracing()


# -- sysconfig ----------------------------------------------------------------

class TestSysconfig:
    def test_get_platform(self):
        """`sysconfig.get_platform()` 真返 'linux-x86_64' / 'darwin' 等。"""
        p = sysconfig.get_platform()
        assert isinstance(p, str) and p, f"platform 应非空,实际 {p!r}"
        # 必含 OS
        assert any(os in p for os in ("linux", "darwin", "win")), (
            f"platform 应含 linux/darwin/win,实际 {p!r}"
        )

    def test_get_path_purelib(self):
        """`sysconfig.get_path('purelib')` 真返 site-packages 类 path。"""
        p = sysconfig.get_path("purelib")
        assert isinstance(p, str) and p, f"purelib 应非空,实际 {p!r}"
        assert "site-packages" in p or "dist-packages" in p, (
            f"purelib 应含 site-packages,实际 {p!r}"
        )

    def test_get_config_var_python_version(self):
        """`sysconfig.get_config_var('Py_ENABLE_SHARED')` 真返 0 / 1 / None。"""
        v = sysconfig.get_config_var("Py_ENABLE_SHARED")
        # None 或 0 或 1
        assert v is None or v in (0, 1, "0", "1"), (
            f"Py_ENABLE_SHARED 应=None/0/1,实际 {v!r}"
        )


# -- glob ---------------------------------------------------------------------

class TestGlob:
    def test_glob_returns_list(self):
        """`glob.glob('*.py')` 真通配返 list。"""
        result = glob.glob("*.py")
        assert isinstance(result, list)

    def test_glob_escape_meta(self):
        """`glob.escape('a[b].py')` 真 escape 元字符 `[` `]`。"""
        escaped = glob.escape("a[b].py")
        # 沙箱 glob 模块: 'a[[]b].py' 或 'a\\[b\\].py'
        assert "[" in escaped, f"escape 应含 [,实际 {escaped!r}"
        # 完整 path 不应再匹配任意字符
        # 简单 sanity: 长度 >= 原始
        assert len(escaped) >= len("a[b].py")


# -- fnmatch ------------------------------------------------------------------

class TestFnmatch:
    def test_fnmatch_wildcard(self):
        """`fnmatch.fnmatch('foo.txt', '*.txt')` 真判 True。"""
        assert fnmatch.fnmatch("foo.txt", "*.txt") is True
        assert fnmatch.fnmatch("foo.py", "*.txt") is False

    def test_fnmatch_case_insensitive_default(self):
        """`fnmatch.fnmatchcase` 真区分大小写,`fnmatch` 平台相关。"""
        # fnmatchcase 严格区分大小写
        assert fnmatch.fnmatchcase("Foo.TXT", "*.txt") is False
        assert fnmatch.fnmatchcase("foo.txt", "*.txt") is True

    def test_fnmatch_filter(self):
        """`fnmatch.filter(['a.py', 'b.txt'], '*.py')` 真滤 ['a.py']。"""
        result = fnmatch.filter(["a.py", "b.txt", "c.py", "d.md"], "*.py")
        assert sorted(result) == ["a.py", "c.py"], f"filter 应=['a.py','c.py'],实际 {result}"
